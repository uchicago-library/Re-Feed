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

from _config import app, db


# Junction table for many-to-many relationship
class FeedEntryTag(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    feed_entry_id = db.Column(
        db.Integer, db.ForeignKey('feed_entry.id'), nullable=False
    )
    tag_id = db.Column(db.Integer, db.ForeignKey('tag.id'), nullable=False)


class Tag(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), unique=True, nullable=False)


class FeedEntry(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    feed_id = db.Column(db.String(200), unique=True, nullable=False)
    title = db.Column(db.String(200), nullable=False)
    link = db.Column(db.String(200), nullable=False)
    published_at = db.Column(db.DateTime, default=datetime.utcnow)
    description = db.Column(db.Text, nullable=True)
    tags = db.relationship('Tag', secondary='feed_entry_tag', backref='feed_entries')


class Changes(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    updated = db.Column(db.DateTime, default=datetime.utcnow)


def update_or_create_change(record_id):
    """
    Get a Changes record by ID or create a new one if it doesn't exist.

    Args:
        record_id (int): The ID of the Changes record.

    Returns:
        Changes: The retrieved or newly created Changes record.
    """
    record = Changes.query.get(record_id)

    if record:
        record.updated = datetime.utcnow()
    else:
        record = Changes(id=record_id, updated=datetime.utcnow())
        db.session.add(record)

    try:
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        print(f"An error occurred: {e}")

    return record


def get_change_by_id(record_id):
    change_record = db.session.query(Changes).filter(Changes.id == record_id).first()
    return change_record


def rfc_3339_date(date):
    return date.isoformat(sep='T') + 'Z'


def fetch_rss_feed():
    with app.app_context():
        if not app.config['RSS_FEED_URL']:
            print('Missoing RSS_FEED_URL in config.')
        feed = feedparser.parse(app.config['RSS_FEED_URL'])
        feed.entries.reverse()
        for entry in feed.entries:
            existing_entry = FeedEntry.query.filter_by(feed_id=entry.id).first()

            if not existing_entry:  # Only add if it doesn't exist
                rss_entry = FeedEntry(
                    title=entry.title,
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
                            title=item['title'],
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
    entry = FeedEntry.query.get(entry_id)

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
    entry = FeedEntry.query.get(entry_id)
    tag = Tag.query.get(tag_id)

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
def get_feed_rss():
    entries = FeedEntry.query.all()
    entries.reverse()
    feed = ''
    feed += '<?xml version="1.0" encoding="UTF-8" ?>\n'
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
def get_feed_atom():
    try:
        updated = rfc_3339_date(get_change_by_id(1).updated)
    except (AttributeError):
        updated = rfc_3339_date(update_or_create_change(1).updated)

    feed_title = app.config['FEED_TITLE']
    entries = FeedEntry.query.all()
    entries.reverse()
    feed = ''
    feed += '<?xml version="1.0" encoding="UTF-8" ?>\n'
    feed += '<feed xmlns="http://www.w3.org/2005/Atom">\n'
    feed += f'<title>{feed_title}</title>\n'
    feed += f'<id>{request.base_url}</id>\n'
    feed += f'<updated>{updated}</updated>\n'

    for entry in entries:
        feed += '<entry>\n'
        feed += f'<title>{entry.title}</title>\n'
        feed += f'<id>{entry.id}</id>\n'
        feed += f'<link href="{entry.link}" rel="alternate" type="text/html"/>\n'
        feed += f'<description><![CDATA[ {entry.description} ]]></description>\n'
        for tag in entry.tags:
            feed += f'<category term="{tag.name}"/>\n'
        feed += '</entry>\n'
    feed += '</feed>\n'
    return feed, 200, {'Content-Type': 'application/rss+xml'}


@app.route('/get_feed_json', methods=['GET'])
def get_feed_json():
    entries = FeedEntry.query.all()
    entries.reverse()
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
    # from custom import FeedEntry  # noqa
    from custom import *  # noqa
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
