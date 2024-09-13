from datetime import datetime

from sqlalchemy.ext.declarative import declared_attr

from _config import db


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


class AbstractFeedEntry(db.Model):
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
    pass


class Changes(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    updated = db.Column(db.DateTime, default=datetime.utcnow)
