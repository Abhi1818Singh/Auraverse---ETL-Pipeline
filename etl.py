import json
from typing import Dict, Any, List, Set, TYPE_CHECKING

if TYPE_CHECKING:
    from sqlalchemy.orm import Session
else:
    Session = Any  # runtime fallback when SQLAlchemy isn't available for import-time checks

from sqlalchemy import select

from models import Record, SchemaVersion


# --------- Transform helper: flatten nested JSON ----------

def flatten_dict(
    data: Dict[str, Any],
    parent_key: str = "",
    sep: str = "."
) -> Dict[str, Any]:
    """
    Recursively flattens a nested dictionary.

    Example:
    {"user": {"name": "A", "age": 12}, "city": "Delhi"}
    --> {"user.name": "A", "user.age": 12, "city": "Delhi"}
    """
    items = []
    for key, value in data.items():
        new_key = f"{parent_key}{sep}{key}" if parent_key else key
        if isinstance(value, dict):
            items.extend(flatten_dict(value, new_key, sep=sep).items())
        else:
            items.append((new_key, value))
    return dict(items)


# --------- Core ETL: Transform + Load ----------

def get_latest_schema(db: Session) -> SchemaVersion | None:
    stmt = select(SchemaVersion).order_by(SchemaVersion.version.desc())
    return db.execute(stmt).scalars().first()


def process_and_store(record_dict: Dict[str, Any], db: Session) -> Record:
    """
    Takes a raw JSON dict:
    - Flattens it
    - Compares its fields with the latest schema
    - If new fields appear, creates a new schema version
    - Stores the record with its schema_version
    """
    # Transform step: flatten
    flat = flatten_dict(record_dict)
    new_fields: Set[str] = set(flat.keys())

    # Load step: schema handling
    latest_schema = get_latest_schema(db)

    if latest_schema is None:
        # First ever schema
        version = 1
        schema = SchemaVersion(
            version=version,
            fields=json.dumps(sorted(list(new_fields)))
        )
        db.add(schema)
    else:
        existing_fields: Set[str] = set(json.loads(latest_schema.fields))
        if new_fields.issubset(existing_fields):
            # No new fields → keep same version
            version = latest_schema.version
        else:
            # New fields found → create new version with merged fields
            version = latest_schema.version + 1
            merged_fields: List[str] = sorted(list(existing_fields.union(new_fields)))
            schema = SchemaVersion(
                version=version,
                fields=json.dumps(merged_fields)
            )
            db.add(schema)

    # Store record
    rec = Record(
        original_json=json.dumps(record_dict),
        flattened_json=json.dumps(flat),
        schema_version=version
    )
    db.add(rec)
    db.commit()
    db.refresh(rec)
    return rec

