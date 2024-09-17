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
    """Retrieve a change record by its ID.

    This function queries the database for a change record with the specified
    ID and returns the corresponding record if found.

    Args:
        record_id (int): The ID of the change record to retrieve.

    Returns:
        Changes or None: The change record if found, otherwise None.
    """
    change_record = db.session.query(Changes).filter(Changes.id == record_id).first()
    return change_record


def rfc_3339_date(date):
    """Convert a datetime object to an RFC 3339 formatted string.

    This function takes a datetime object and returns a string representation
    in RFC 3339 format, which is a subset of ISO 8601. The resulting string
    includes a 'Z' suffix to indicate that the time is in UTC.

    Args:
        date (datetime): The datetime object to convert.

    Returns:
        str: The RFC 3339 formatted date string.
    """
    return date.isoformat(sep='T') + 'Z'


def get_entries_by_tag_or_not(tag_name=None, limit=None):
    """Retrieve feed entries filtered by tag name or return all entries.

    This function fetches feed entries from the database. If a tag name is
    provided, it retrieves entries associated with that tag. If no tag name
    is specified, it returns all feed entries. The results can be limited
    by the specified limit.

    Args:
        tag_name (str, optional): The name of the tag to filter entries.
        limit (int, optional): The maximum number of entries to return.

    Returns:
        list: A list of FeedEntry objects matching the criteria. If the
        tag is not found, an empty list is returned.
    """
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
