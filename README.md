# Re-Feed
Re-Feed is a simple Flask app that allows you to import `JSON` or `RSS` feeds and tag items in them. It then generates a new `JSON` or `RSS` feed with the tags included. It also allows you to customize and re-map things in the original feeds if you should need to. For example, you could add data to the titles in the feed or pull them from a different element in the original feed.

## Installation
1. Clone the repo.
2. Create a Virtualenv: `python3 -m venv venv`
3. Install the requirements: `pip install -r requirements.txt`

## Setup
1. Create a `config.py` file in the root directory.
2. Add settings to your `config.py`. At a minimum you will need `RSS_FEED_URL` or `JSON_FEED_URL`.
3. Create a `custom_models.py` if you need to customize the data model for a feed or a `custom_functions.py` if you need to customize one of the fetch or get functions.

## Configuration
Example settings:
```
SQLALCHEMY_DATABASE_URI = 'sqlite:///re-feed.db' # Database name
SQLALCHEMY_TRACK_MODIFICATIONS = False
RSS_FEED_URL = 'https://some-rss-feed/'
JSON_FEED_URL = 'https://some-json-feed/'
FETCH_MODE = 'json' # If not JSON, will default to RSS
RSS_PUBLISHED_AT_FORMAT = '%a, %d %b %Y %H:%M:%S %z'
JSON_PUBLISHED_AT_FORMAT = '%Y-%m-%d %H:%M:%S'
FEED_TITLE = 'My Feed' # Used for the Atom feed
LOGO = '<svg width="100" height="100" xmlns="http://www.w3.org/2000/svg">
  <circle cx="50" cy="50" r="40" stroke="black" stroke-width="2" fill="lightblue" />
</svg>'
```
Date formats (`*_FORMAT`) will need need to match the date formats in the feed you're importing. Add any of these that need to be overridden, to your `config.py`.

## API
This app uses `SQLAlchemy` models to create and save to an `SQLite` database, `fetch_` functions to read and import feeds, and `get_` functions to generate new feeds. Any of these can be customized in your `custom_models.py` or `custom_functions.py`. If your feed is different from a simple calendar events feed and/or you need to track more data, you will likely need to customize the `AbstractFeedEntry` model, one `fetch_` function, and one `get_` function.

- `AbstractFeedEntry` - The base data model for feed items. This is the data that's saved to the SQLite database.
- `FeedEntry` - Concrete data model that's generated from the default `AbstractFeedEntry` or the `AbstractFeedEntry` in your `custom_models.py` file.
- `fetch_rss_feed` - Imports an RSS feed.
- `fetch_json_feed` - Imports a JSON feed.
- `get_feed_rss` - Generates an RSS feed.
- `get_feed_atom` - Generates an Atom feed.
- `get_feed_json` - Generates a JSON feed.

## Customization
This app was developed to work with a simple calendar events `RSS` feed and the default data model lends itself to that. It creates a `FeedEntry` database model with the following items:

- `id` - Primary key, created by the app
- `tags` - Tags, created by the app
- `feed_id` - Unique ID from the feed item we fetch
- `title` - Title of the feed item we fetch 
- `link` - Link to the feed item we fetch.
- `published_at` - Date of the feed item we fetch.
- `description` - Description or content of the feed item we fetch.

If you need to customize the `AbstractFeedEntry` model to save more fields to the database and/or map them differently, you will likely need to customize a `fetch_` method and a `get_method`. When you customize a `get_` method, **you will get a new endpoint** for your customized feed. A possible `custom_models.py` might look like this:

```
from sqlalchemy.ext.declarative import declared_attr
from _config import db
from models import AbstractFeedEntry

class AbstractFeedEntry(AbstractFeedEntry):
    __abstract__ = True

    # Override the link field and make it nullable
    @declared_attr
    def link(cls):
        return db.Column(
            db.String(200), nullable=True
        )

    # Add a new foobar field
    @declared_attr
    def foobar(cls):
        return db.Column(
            db.String(200), default='Rise above!', nullable=False
        )
```

A `custom_functions.py` might look like this:

```
from datetime import datetime
import feedparser
from flask import request
from ftfy import fix_text

from _config import app, db
from functions import (
    get_change_by_id,
    get_entries_by_tag_or_not,
    rfc_3339_date,
    update_or_create_change,
)
from models import FeedEntry

def fetch_rss_feed():
    with app.app_context():
        if not app.config['RSS_FEED_URL']:
            print('Missing RSS_FEED_URL in config.')
        feed = feedparser.parse(app.config['RSS_FEED_URL'])
        feed.entries.reverse()
        for entry in feed.entries:
            existing_entry = FeedEntry.query.filter_by(feed_id=entry.id).first()

            if not existing_entry:
                title = fix_text(entry.title, unescape_html=False) # Remove HTML escaping on title
                rss_entry = FeedEntry(
                    title=title,
                    feed_id=entry.id,
                    link=entry.link,
                    published_at=datetime.strptime(
                        entry.published, app.config['RSS_PUBLISHED_AT_FORMAT']
                    ),
                    description=entry.get('description', ''),
                    foobar=title,  # Populate the foobar field with the feed item title.
                )
                db.session.add(rss_entry)

        db.session.commit()


@app.route('/get_custom_feed_atom', methods=['GET'])
@app.route('/get_custom_feed_atom/tag/<string:tag_name>', methods=['GET'])
@app.route('/get_custom_feed_atom/tag/<string:tag_name>/<int:limit>', methods=['GET'])
@app.route('/get_custom_feed_atom/<int:limit>', methods=['GET'])
def get_custom_feed_atom(tag_name=None, limit=None):
    try:
        updated = rfc_3339_date(get_change_by_id(1).updated)
    except (AttributeError):
        updated = rfc_3339_date(update_or_create_change(1).updated)

    feed_title = app.config['FEED_TITLE']
    entries = get_entries_by_tag_or_not(tag_name, limit)
    feed = ''
    feed += '<?xml version="1.0" encoding="utf-8" ?>\n'
    feed += '<feed xmlns="http://www.w3.org/2005/Atom">\n'
    feed += f'<title type="html">{feed_title}</title>\n' # Remove type="html" attribute
    feed += f'<id>{request.base_url}</id>\n'
    feed += f'<updated>{updated}</updated>\n'

    for entry in entries:
        feed += '<entry>\n'
        feed += f'<title>{entry.title}</title>\n' # Remove type="html" attribute
        feed += f'<foobar>{entry.foobar}</foobar>\n' # Add the foobar field to our Atom feed
        feed += f'<id>{entry.id}</id>\n'
        feed += f'<link href="{entry.link}" rel="alternate" type="text/html"/>\n'
        feed += f'<content type="html"><![CDATA[ {entry.description} ]]></content>\n'
        for tag in entry.tags:
            feed += f'<category term="{tag.name}"/>\n'
        feed += '</entry>\n'
    feed += '</feed>\n'
    return feed, 200, {'Content-Type': 'application/rss+xml'}
```

The examples above shows how you could add a `foobar` field to the default `AbstractFeedEntry` model and make the `link` field optional. We could then add a `fetch_rss_feed` function that would populate the `foobar` entry with the title of the feed item we're importing and remove the default html escaping on the title field. Lastly we write a `get_custom_feed_atom` function that adds the `foobar` field to the feed we generate. This feed is available at http://127.0.0.1:5000/get_custom_feed_atom. The new feed will have tags if we add them in the admin interface and it will have a `foobar` field on every item. Link fields will be optional.

## Running in dev mode
```
source venv/bin/activate
python app.p
```
The tagging interface is available at: http://127.0.0.1:5000.

### Endpoints
The admin for tagging and untagging items is found here: http://127.0.0.1:5000. Re-Feed also creates the following enpoints for every feed type offered (JSON, RSS, Atom):

- http://127.0.0.1:5000/get_feed_TYPE
- http://127.0.0.1:5000/get_feed_TYPE/tag/TAG_NAME
- http://127.0.0.1:5000/get_feed_TYPE/tag/TAG_NAME/NUMBER
- http://127.0.0.1:5000/get_feed_TYPE/NUMBER

This allows you to get the whole feed, all items tagged a certain way, or either of those limited by a number. For example, if you wanted to get an Atom feed with the five most recent items tagged with "fun", you would go to: http://127.0.0.1:5000/get_feed_atom/tag/fun/5.
