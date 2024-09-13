from datetime import datetime

from _config import db
from models import Changes, FeedEntry, FeedEntryTag, Tag


def update_or_create_change(record_id):
    """
    Get a Changes record by ID or create a new one if it doesn't exist.

    Args:
        record_id (int): The ID of the Changes record.

    Returns:
        Changes: The retrieved or newly created Changes record.
    """
    record = db.session.get(Changes, record_id)

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


def get_entries_by_tag_or_not(tag_name=None, limit=None):
    if tag_name:
        tag = Tag.query.filter(Tag.name.ilike(tag_name)).first()
        if tag:
            query = (
                FeedEntry.query.join(FeedEntryTag)
                .filter(FeedEntryTag.tag_id == tag.id)
                .order_by(FeedEntry.id.desc())
            )
            if limit:
                query = query.limit(limit)
            entries = query.all()
        else:
            print('Tag not found!')
            return []
    else:
        query = FeedEntry.query.order_by(FeedEntry.id.desc())
        if limit:
            query = query.limit(limit)
        entries = query.all()
    return entries
