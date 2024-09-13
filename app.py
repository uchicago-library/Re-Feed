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
    entries = FeedEntry.query.all()
    entries.reverse()
    return render_template('index.html', entries=entries, logo=app.config['LOGO'])


@app.route('/static/<path:path>')
def send_static(path):
    return send_from_directory('static', path)


@app.route('/tag_entry/<int:entry_id>', methods=['POST'])
def tag_entry(entry_id):
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
    """Fetches a JSON or RSS feed and imports entries into an SQLite database.

    MODE: The type of feed to fetch. Should be "json" or "rss"."""
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
