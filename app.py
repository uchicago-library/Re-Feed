import html
from datetime import datetime

import click
import feedparser
import requests
from flask import (
    jsonify,
    redirect,
    render_template,
    request,
    send_from_directory,
    url_for,
)
from ftfy import fix_text

from _config import app, db
from functions import (
    get_change_by_id,
    get_entries_by_tag_or_not,
    rfc_3339_date,
    update_or_create_change,
)
from models import FeedEntry, Tag


def fetch_rss_feed():
    """Fetch and store RSS feed entries in the database.

    This function retrieves the RSS feed from the URL specified in the
    application configuration. It parses the feed, reverses the order of
    the entries, and adds any new entries to the database if they do not
    already exist. Each entry is stored with its title, feed ID, link,
    publication date, and description.

    If the RSS_FEED_URL is not configured, a message is printed to the
    console indicating the missing configuration.

    Returns:
        None
    """
    with app.app_context():
        if not app.config['RSS_FEED_URL']:
            print('Missing RSS_FEED_URL in config.')
        feed = feedparser.parse(app.config['RSS_FEED_URL'])
        feed.entries.reverse()
        for entry in feed.entries:
            existing_entry = FeedEntry.query.filter_by(feed_id=entry.id).first()

            if not existing_entry:  # Only add if it doesn't exist
                title = html.escape(fix_text(entry.title, unescape_html=False))
                rss_entry = FeedEntry(
                    title=title,
                    feed_id=entry.id,
                    link=entry.link,
                    published_at=datetime.strptime(
                        entry.published, app.config['RSS_PUBLISHED_AT_FORMAT']
                    ),
                    description=entry.get('description', ''),
                )
                db.session.add(rss_entry)

        db.session.commit()


def fetch_json_feed():
    """Fetch and store JSON feed entries in the database.

    This function retrieves the JSON feed from the URL specified in the
    application configuration. It sends a GET request to the JSON_FEED_URL
    and, if the response is successful (HTTP status code 200), it parses
    the JSON data. The function reverses the order of the entries and
    adds any new entries to the database if they do not already exist.
    Each entry is stored with its title, feed ID, link, publication date,
    and description.

    If the response status code is not 200, an error message is printed
    indicating the failure to fetch the JSON feed. If there is a problem
    with the URL (e.g., missing schema), a message is printed to the
    console.

    Returns:
        None
    """
    with app.app_context():
        try:
            response = requests.get(app.config['JSON_FEED_URL'])
            if response.status_code == 200:
                json_data = response.json()
                json_data['data'].reverse()
                for item in json_data['data']:
                    existing_entry = FeedEntry.query.filter_by(
                        feed_id=item['id']
                    ).first()

                    if not existing_entry:  # Only add if it doesn't exist
                        feed_entry = FeedEntry(
                            title=fix_text(item['title']),
                            feed_id=item['id'],
                            link=item['url'],
                            published_at=datetime.strptime(
                                item['date_utc'], app.config['JSON_PUBLISHED_AT_FORMAT']
                            ),
                            description=item.get('description', ''),
                        )
                        db.session.add(feed_entry)

                db.session.commit()
            else:
                print(f"Failed to fetch JSON feed: {response.status_code}")
        except requests.exceptions.MissingSchema:
            print('Missing or bad URL in config.')


@app.route('/')
def index():
    """Render the index page with a list of feed entries.

    This function retrieves all feed entries from the database, reverses
    their order, and renders the 'index.html' template. The template is
    populated with the list of entries and an optional logo specified in
    the application configuration.

    Returns:
        str: The rendered HTML template for the index page.
    """
    entries = FeedEntry.query.all()
    entries.reverse()
    return render_template('index.html', entries=entries, logo=app.config['LOGO'])


@app.route('/static/<path:path>')
def send_static(path):
    """Serve static files from the 'static' directory.

    Args:
        path (str): The relative path to the static file.

    Returns:
        Response: The requested static file.
    """
    return send_from_directory('static', path)


@app.route('/tag_entry/<int:entry_id>', methods=['POST'])
def tag_entry(entry_id):
    """Add a tag to a feed entry.

    This function retrieves a feed entry by its ID and adds a tag to it.
    If the tag does not exist, it creates a new tag. The tag name is
    taken from the form data, converted to lowercase, and stripped of
    whitespace.

    Args:
        entry_id (int): The ID of the feed entry to tag.

    Returns:
        Response: A redirect to the index page or an error page if the
        entry is not found.
    """
    tag_name = request.form['tags'].strip().lower()
    entry = db.session.get(FeedEntry, entry_id)

    if entry:
        tag = Tag.query.filter(Tag.name.ilike(tag_name)).first()

        if not tag:  # If the tag doesn't exist, create it
            tag = Tag(name=tag_name)
            db.session.add(tag)
            db.session.commit()  # Commit to get the tag ID

        if tag not in entry.tags:
            entry.tags.append(tag)
            db.session.commit()

        update_or_create_change(1)
        return redirect(url_for('index'))

    return render_template('error.html', msg='Entry not found!')


@app.route('/delete_tag/<int:entry_id>/<int:tag_id>', methods=['POST', 'DELETE'])
def delete_tag(entry_id, tag_id):
    """Remove a tag from a feed entry.

    This function retrieves a feed entry and a tag by their IDs. If both
    exist and the tag is associated with the entry, the tag is removed.
    If the tag is not associated with the entry or if either the entry
    or tag is not found, an error message is rendered.

    Args:
        entry_id (int): The ID of the feed entry.
        tag_id (int): The ID of the tag to remove.

    Returns:
        Response: A redirect to the index page or an error page if the
        entry or tag is not found, or if the tag is not associated with
        the entry.
    """
    entry = db.session.get(FeedEntry, entry_id)
    tag = db.session.get(Tag, tag_id)

    if entry and tag:
        # Remove the tag from the entry
        if tag in entry.tags:
            entry.tags.remove(tag)
            db.session.commit()
            update_or_create_change(1)
            return redirect(url_for('index'))
        else:
            return render_template(
                'error.html', msg='Tag not associated with this entry!'
            )
    return render_template('error.html', msg='Entry or tag not found!')


@app.route('/get_feed_rss', methods=['GET'])
@app.route('/get_feed_rss/tag/<string:tag_name>', methods=['GET'])
@app.route('/get_feed_rss/tag/<string:tag_name>/<int:limit>', methods=['GET'])
@app.route('/get_feed_rss/<int:limit>', methods=['GET'])
def get_feed_rss(tag_name=None, limit=None):
    """Generate an RSS feed of feed entries.

    This function retrieves feed entries, optionally filtered by a tag
    name and/or limited to a specified number of entries. It constructs
    and returns an RSS feed in XML format.

    Args:
        tag_name (str, optional): The name of the tag to filter entries.
        limit (int, optional): The maximum number of entries to return.

    Returns:
        tuple: A tuple containing the RSS feed as a string, an HTTP status
        code (200), and a content type of 'application/rss+xml'.
    """
    entries = get_entries_by_tag_or_not(tag_name, limit)
    feed = ''
    feed += '<?xml version="1.0" encoding="utf-8" ?>\n'
    feed += '<rss version="2.0">\n'
    feed += '<channel>\n'

    for entry in entries:
        feed += '<item>\n'
        feed += f'<title>{entry.title}</title>\n'
        feed += f'<link>{entry.link}</link>\n'
        feed += f'<description>{entry.description}</description>\n'
        for tag in entry.tags:
            feed += f'<category term="{tag.name}"/>\n'
        feed += '</item>\n'
    feed += '</channel>\n</rss>'
    return feed, 200, {'Content-Type': 'application/rss+xml'}


@app.route('/get_feed_atom', methods=['GET'])
@app.route('/get_feed_atom/tag/<string:tag_name>', methods=['GET'])
@app.route('/get_feed_atom/tag/<string:tag_name>/<int:limit>', methods=['GET'])
@app.route('/get_feed_atom/<int:limit>', methods=['GET'])
def get_feed_atom(tag_name=None, limit=None):
    """Generate an Atom feed of feed entries.

    This function retrieves feed entries, optionally filtered by a tag
    name and/or limited to a specified number of entries. It constructs
    and returns an Atom feed in XML format, including metadata such as
    the feed title and last updated time.

    Args:
        tag_name (str, optional): The name of the tag to filter entries.
        limit (int, optional): The maximum number of entries to return.

    Returns:
        tuple: A tuple containing the Atom feed as a string, an HTTP status
        code (200), and a content type of 'application/atom+xml'.
    """
    try:
        updated = rfc_3339_date(get_change_by_id(1).updated)
    except (AttributeError):
        updated = rfc_3339_date(update_or_create_change(1).updated)

    feed_title = app.config['FEED_TITLE']
    entries = get_entries_by_tag_or_not(tag_name, limit)
    feed = ''
    feed += '<?xml version="1.0" encoding="utf-8" ?>\n'
    feed += '<feed xmlns="http://www.w3.org/2005/Atom">\n'
    feed += f'<title type="html">{feed_title}</title>\n'
    feed += f'<id>{request.base_url}</id>\n'
    feed += f'<updated>{updated}</updated>\n'

    for entry in entries:
        feed += '<entry>\n'
        feed += f'<title type="html">{entry.title}</title>\n'
        feed += f'<id>{entry.id}</id>\n'
        feed += f'<link href="{entry.link}" rel="alternate" type="text/html"/>\n'
        feed += f'<content type="html"><![CDATA[ {entry.description} ]]></content>\n'
        for tag in entry.tags:
            feed += f'<category term="{tag.name}"/>\n'
        feed += '</entry>\n'
    feed += '</feed>\n'
    return feed, 200, {'Content-Type': 'application/rss+xml'}


@app.route('/get_feed_json', methods=['GET'])
@app.route('/get_feed_json/tag/<string:tag_name>', methods=['GET'])
@app.route('/get_feed_json/tag/<string:tag_name>/<int:limit>', methods=['GET'])
@app.route('/get_feed_json/<int:limit>', methods=['GET'])
def get_feed_json(tag_name=None, limit=None):
    """Generate a JSON feed of feed entries.

    This function retrieves feed entries, optionally filtered by a tag
    name and/or limited to a specified number of entries. It constructs
    and returns a JSON representation of the feed entries.

    Args:
        tag_name (str, optional): The name of the tag to filter entries.
        limit (int, optional): The maximum number of entries to return.

    Returns:
        Response: A JSON response containing a list of feed entries.
    """
    entries = get_entries_by_tag_or_not(tag_name, limit)
    feed_data = []

    for entry in entries:
        entry_data = {
            'title': entry.title,
            'link': entry.link,
            'description': entry.description,
            'tags': [tag.name for tag in entry.tags],
        }
        feed_data.append(entry_data)

    return jsonify(feed_data)


@app.cli.command('fetch_feed')
@click.argument('mode')
def fetch_feed(mode):
    """Fetch and import feed entries into the SQLite database.

    This command fetches entries from a specified feed type (JSON or RSS)
    and imports them into the SQLite database. The mode argument determines
    the type of feed to fetch.

    Args:
        mode (str): The type of feed to fetch. Must be either "json" or "rss".

    Usage:
        To fetch a JSON feed:
            flask fetch_feed json

        To fetch an RSS feed:
            flask fetch_feed rss
    """
    mode = mode.lower()
    if mode == 'json':
        fetch_json_feed()
    elif mode == 'rss':
        fetch_rss_feed()
    else:
        print(
            'You must specify what kind of a feed to fetch. Only "json" and "rss" are recognized.'
        )


# Load optional overrides
try:
    from custom_functions import *  # noqa
except ImportError:
    pass

with app.app_context():
    db.create_all()

if __name__ == '__main__':
    with app.app_context():
        # Fetch feeds when the app starts
        if app.config['FETCH_MODE'].lower() == 'json':
            fetch_json_feed()
        else:
            fetch_rss_feed()
    app.run(debug=True)
