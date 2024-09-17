from datetime import datetime

from sqlalchemy.ext.declarative import declared_attr

from _config import db


class FeedEntryTag(db.Model):
    """Association model for linking feed entries and tags.

    This model represents the many-to-many relationship between
    FeedEntry and Tag, allowing a feed entry to have multiple tags
    and a tag to be associated with multiple feed entries.
    """

    id = db.Column(db.Integer, primary_key=True)
    feed_entry_id = db.Column(
        db.Integer, db.ForeignKey('feed_entry.id'), nullable=False
    )
    tag_id = db.Column(db.Integer, db.ForeignKey('tag.id'), nullable=False)


class Tag(db.Model):
    """Represents a tag in the system.

    This model corresponds to the 'tag' table in the database and
    contains information about tags that can be associated with
    feed entries.
    """

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), unique=True, nullable=False)


class AbstractFeedEntry(db.Model):
    """Abstract base class for feed entries.

    This abstract model defines common attributes and relationships
    for feed entry models. It includes fields for ID, feed ID, title,
    link, publication date, description, and associated tags.

    Attributes:
        id (int): The unique identifier for the feed entry.
        feed_id (str): The unique identifier for the feed.
        title (str): The title of the feed entry.
        link (str): The URL link to the feed entry.
        published_at (datetime): The publication date of the feed entry.
        description (str): A description of the feed entry.
        tags (list): A list of tags associated with the feed entry.
    """

    __abstract__ = True

    @declared_attr
    def id(cls):
        return db.Column(db.Integer, primary_key=True)

    @declared_attr
    def feed_id(cls):
        return db.Column(db.String(200), unique=True, nullable=False)

    @declared_attr
    def title(cls):
        return db.Column(db.String(200), nullable=False)

    @declared_attr
    def link(cls):
        return db.Column(db.String(200), nullable=False)

    @declared_attr
    def published_at(cls):
        return db.Column(db.DateTime, default=datetime.utcnow)

    @declared_attr
    def description(cls):
        return db.Column(db.Text, nullable=True)

    @declared_attr
    def tags(cls):
        return db.relationship(
            'Tag', secondary='feed_entry_tag', backref='feed_entries'
        )


try:
    from custom_models import AbstractFeedEntry  # noqa
except ImportError:
    pass


class FeedEntry(AbstractFeedEntry):
    """Represents a feed entry in the system.

    This class inherits from AbstractFeedEntry and represents a specific
    feed entry with all the attributes defined in the abstract base class.
    """

    pass


class Changes(db.Model):
    """Represents a record of changes in the system.

    This model tracks updates with a unique identifier and a timestamp
    indicating when the change was made.

    Attributes:
        id (int): The unique identifier for the change record.
        updated (datetime): The timestamp of when the change was last updated.
    """

    id = db.Column(db.Integer, primary_key=True)
    updated = db.Column(db.DateTime, default=datetime.utcnow)
