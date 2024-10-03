import html

import feedparser
from ftfy import fix_text

from _config import app, db
from models import FeedEntry


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
        for entry in feed.entries:
            existing_entry = FeedEntry.query.filter_by(feed_id=entry.id).first()

            if not existing_entry:
                title = html.escape(fix_text(entry.title, unescape_html=False))
                rss_entry = FeedEntry(
                    title=title,
                    feed_id=entry.id,
                    link=entry.link,
                    description=entry.get('description', ''),
                )
                db.session.add(rss_entry)

        db.session.commit()
