from fastapi import FastAPI, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session
from sqlalchemy import select

from database import Base, engine, get_db
from models import Record, SchemaVersion
from etl import process_and_store
from parsers import parse_any, UnsupportedContentType
import json

# import requests
from fastapi import UploadFile, File

from schema_inspector import (
    analyze_file_schema,
    list_nosql_docs,
    get_nosql_doc,
    search_nosql_docs,
)



# ---------- FastAPI app ----------

app = FastAPI(title="Dynamic ETL Pipeline (Multi-format)")

# CORS (so frontend JS can call API even if opened from browser)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------- DB setup on startup ----------

@app.on_event("startup")
def on_startup():
    Base.metadata.create_all(bind=engine)


# ---------- Request / Response Models ----------

class IngestPayload(BaseModel):
    content_type: str = Field(
        ...,
        description=(
            'Type of content: "json", "html", "xml", "text", '
            '"image_meta", "video_meta", "audio_meta"'
        )
    )
    content: str = Field(
        ...,
        description="Raw content (JSON string, HTML, XML, plain text, captions, subtitles, etc.)"
    )
    metadata: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Optional extra metadata (EXIF fields, language, source URL, etc.)"
    )

class UrlIngestPayload(BaseModel):
    content_type: str = Field(
        ...,
        description='Same as before: "html", "xml", "json", "text", "image_meta", "video_meta", etc.'
    )
    url: str = Field(
        ...,
        description="The URL to fetch content from (webpage, XML feed, JSON API, etc.)"
    )
    metadata: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Optional metadata to attach (same as earlier)."
    )



class RecordResponse(BaseModel):
    id: int
    original: Dict[str, Any]
    flattened: Dict[str, Any]
    schema_version: int


class SchemaResponse(BaseModel):
    version: int
    fields: List[str]


# ---------- API Routes ----------

# @app.post("/api/ingest", response_model=RecordResponse)
# def ingest_data(payload: IngestPayload, db: Session = Depends(get_db)):
#     """
#     Universal ingestion endpoint.

#     1. Parse raw content (JSON / HTML / XML / text / multimedia metadata)
#        -> to a Python dict using parsers.py
#     2. Use ETL (flatten + dynamic schema) to store.
#     """
#     try:
#         # 1) Extract / normalize
#         record_dict = parse_any(
#             content_type=payload.content_type,
#             content=payload.content,
#             metadata=payload.metadata,
#         )

#         # 2) ETL transform + load
#         record = process_and_store(record_dict, db)

#         return RecordResponse(
#             id=record.id,
#             original=json.loads(record.original_json),
#             flattened=json.loads(record.flattened_json),
#             schema_version=record.schema_version,
#         )
#     except UnsupportedContentType as e:
#         raise HTTPException(status_code=400, detail=str(e))
#     except json.JSONDecodeError as e:
#         raise HTTPException(status_code=400, detail=f"JSON parse error: {e}")
#     except Exception as e:
#         raise HTTPException(status_code=400, detail=str(e))
    


# ===== 

# @app.post("/api/ingest_url", response_model=RecordResponse)
# def ingest_from_url(payload: UrlIngestPayload, db: Session = Depends(get_db)):
#     """
#     Fetches content from a URL, then runs it through the same ETL pipeline
#     using parse_any + process_and_store.
#     """
#     # 1) Fetch the URL
#     try:
#         resp = requests.get(payload.url, timeout=10)
#         resp.raise_for_status()
#     except Exception as e:
#         raise HTTPException(status_code=400, detail=f"Error fetching URL: {e}")

#     raw_content = resp.text  # HTML, XML, JSON, text, etc.

#     # 2) Parse and store
#     try:
#         record_dict = parse_any(
#             content_type=payload.content_type,
#             content=raw_content,
#             metadata=payload.metadata,
#         )
#         record = process_and_store(record_dict, db)

#         return RecordResponse(
#             id=record.id,
#             original=json.loads(record.original_json),
#             flattened=json.loads(record.flattened_json),
#             schema_version=record.schema_version,
#             # if you don't have lineage yet, just return {}
#             lineage={} if not getattr(record, "lineage_json", None) else json.loads(record.lineage_json),
#         )
#     except UnsupportedContentType as e:
#         raise HTTPException(status_code=400, detail=str(e))
#     except json.JSONDecodeError as e:
#         raise HTTPException(status_code=400, detail=f"JSON parse error during parsing: {e}")
#     except Exception as e:
#         raise HTTPException(status_code=400, detail=str(e))



# @app.post("/api/ingest_file", response_model=RecordResponse)
# async def ingest_from_file(
#     content_type: str = Form(...),
#     metadata_json: Optional[str] = Form(None),
#     file: UploadFile = File(...),
#     db: Session = Depends(get_db),
# ):
#     """
#     Ingest from an uploaded file.
#     For now we treat it as TEXT content:
#     - .txt, .html, .xml, .json, .srt, .vtt, etc.
#     """
#     # 1) Read file
#     raw_bytes = await file.read()

#     try:
#         text_content = raw_bytes.decode("utf-8", errors="ignore")
#     except Exception as e:
#         raise HTTPException(status_code=400, detail=f"Could not decode file as text: {e}")

#     # 2) Parse metadata JSON (optional)
#     metadata = None
#     if metadata_json:
#         try:
#             metadata = json.loads(metadata_json)
#         except json.JSONDecodeError as e:
#             raise HTTPException(status_code=400, detail=f"Metadata JSON error: {e}")

#     # 3) Convert to structured dict using your existing parser
#     try:
#         record_dict = parse_any(
#             content_type=content_type,
#             content=text_content,
#             metadata=metadata,
#         )
#         record = process_and_store(record_dict, db)

#         return RecordResponse(
#             id=record.id,
#             original=json.loads(record.original_json),
#             flattened=json.loads(record.flattened_json),
#             schema_version=record.schema_version,
#             lineage={} if not getattr(record, "lineage_json", None) else json.loads(record.lineage_json),
#         )
#     except UnsupportedContentType as e:
#         raise HTTPException(status_code=400, detail=str(e))
#     except Exception as e:
#         raise HTTPException(status_code=400, detail=str(e))



# @app.get("/api/records", response_model=List[RecordResponse])
# def list_records(limit: int = 20, db: Session = Depends(get_db)):
#     stmt = select(Record).order_by(Record.id.desc()).limit(limit)
#     records = db.execute(stmt).scalars().all()
#     resp: List[RecordResponse] = []
#     for r in records:
#         resp.append(
#             RecordResponse(
#                 id=r.id,
#                 original=json.loads(r.original_json),
#                 flattened=json.loads(r.flattened_json),
#                 schema_version=r.schema_version,
#             )
#         )
#     return resp


@app.get("/api/schemas", response_model=List[SchemaResponse])
def list_schemas(db: Session = Depends(get_db)):
    stmt = select(SchemaVersion).order_by(SchemaVersion.version.asc())
    schemas = db.execute(stmt).scalars().all()
    return [
        SchemaResponse(
            version=s.version,
            fields=json.loads(s.fields),
        )
        for s in schemas
    ]

from fastapi import status
from sqlalchemy import delete


@app.delete("/api/clear")
def clear_all_data(db: Session = Depends(get_db)):
    """
    Deletes all records and all schema versions.
    Use carefully!
    """
    # Delete from child table first (Record), then SchemaVersion
    db.query(Record).delete()
    db.query(SchemaVersion).delete()
    db.commit()
    return {"status": "ok", "message": "All data cleared"}





@app.post("/api/file_schema")
async def file_schema(file: UploadFile = File(...)):
    """
    Upload any txt/pdf/html/xml/json file → return a schema summary.
    Does NOT store in DB, just analyzes.
    """
    file_bytes = await file.read()
    try:
        summary = analyze_file_schema(file.filename, file_bytes)
        return summary
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/api/nosql_docs")
def api_list_nosql_docs(limit: int = 20):
    """
    List recent NoSQL documents stored in Mongo.
    """
    return {"items": list_nosql_docs(limit=limit)}


@app.get("/api/nosql_docs/{doc_id}")
def api_get_nosql_doc(doc_id: str):
    """
    Get a single stored document (full JSON + schema).
    """
    try:
        doc = get_nosql_doc(doc_id)
        return doc
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@app.get("/api/nosql_search")
def api_search_nosql_docs(q: str, limit: int = 20):
    """
    Search NoSQL docs by filename substring.
    """
    return {"items": search_nosql_docs(query=q, limit=limit)}


@app.post("/api/file_schema")
async def file_schema(file: UploadFile = File(...)):
    file_bytes = await file.read()
    result = analyze_file_schema(file.filename, file_bytes)
    return result   # now { "detected": [...] }


# ---------- Serve Frontend ----------

app.mount(
    "/",
    StaticFiles(directory="frontend", html=True),
    name="frontend",
)
