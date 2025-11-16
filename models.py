from sqlalchemy import Column, Integer, Text, DateTime, func
from database import Base


class Record(Base):
    __tablename__ = "records"

    id = Column(Integer, primary_key=True, index=True)
    original_json = Column(Text, nullable=False)   # raw data as JSON string
    flattened_json = Column(Text, nullable=False)  # flattened form as JSON string
    schema_version = Column(Integer, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class SchemaVersion(Base):
    __tablename__ = "schema_versions"

    id = Column(Integer, primary_key=True, index=True)
    version = Column(Integer, unique=True, nullable=False)
    fields = Column(Text, nullable=False)  # JSON list of field names
    created_at = Column(DateTime(timezone=True), server_default=func.now())
