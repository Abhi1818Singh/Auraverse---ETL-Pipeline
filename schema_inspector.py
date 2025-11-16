# from __future__ import annotations

# import json
# import re
# from io import BytesIO
# from typing import Any, Dict, List

# from PyPDF2 import PdfReader

# from parsers import parse_any
# from etl import flatten_dict


# # ---------- small helpers ----------

# def infer_value_type(v: Any) -> str:
#     if v is None:
#         return "null"
#     if isinstance(v, bool):
#         return "bool"
#     if isinstance(v, int):
#         return "int"
#     if isinstance(v, float):
#         return "float"
#     if isinstance(v, str):
#         return "string"
#     if isinstance(v, list):
#         return "array"
#     if isinstance(v, dict):
#         return "object"
#     return type(v).__name__


# def build_schema_for_obj(obj: Dict[str, Any]) -> Dict[str, str]:
#     """
#     Flatten an object and return { field: type_string }
#     """
#     flat = flatten_dict(obj)
#     return {k: infer_value_type(v) for k, v in flat.items()}


# def detect_content_type_from_filename_and_text(filename: str, text: str) -> str:
#     """
#     Best-effort guess: json / xml / html / text
#     based on file extension + a snippet of content.
#     """
#     name_lower = filename.lower()
#     sniff = text.lstrip()[:500]

#     if name_lower.endswith(".json"):
#         return "json"
#     if name_lower.endswith(".xml"):
#         return "xml"
#     if name_lower.endswith(".html") or name_lower.endswith(".htm"):
#         return "html"

#     # Guess from content if extension not clear
#     if sniff.startswith("{") or sniff.startswith("["):
#         return "json"
#     if sniff.startswith("<?xml") or (sniff.startswith("<") and ("</" in sniff or "/>" in sniff)):
#         return "xml"
#     if "<html" in sniff.lower():
#         return "html"

#     return "text"


# # ---------- find JSON blocks embedded inside text ----------

# def _find_json_blocks(text: str, max_blocks: int = 5) -> List[Dict[str, Any]]:
#     """
#     Scan the text and try to extract a few well-formed JSON objects.
#     This will pick up product JSON, JSON-LD, etc.
#     """
#     blocks: List[Dict[str, Any]] = []
#     n = len(text)
#     i = 0

#     while i < n and len(blocks) < max_blocks:
#         if text[i] == "{":
#             depth = 0
#             for j in range(i, n):
#                 ch = text[j]
#                 if ch == "{":
#                     depth += 1
#                 elif ch == "}":
#                     depth -= 1
#                     if depth == 0:
#                         candidate = text[i: j + 1]
#                         try:
#                             obj = json.loads(candidate)
#                         except Exception:
#                             pass
#                         else:
#                             blocks.append(obj)
#                             i = j + 1
#                             break
#             else:
#                 i += 1
#         else:
#             i += 1

#     return blocks


# # ---------- important points (entities, numbers, CSV-like) ----------

# STOP_WORDS = {
#     "the", "this", "that", "a", "an", "and", "or", "of", "for", "with",
#     "in", "on", "at", "to", "is", "are", "was", "were", "it", "he",
#     "she", "they", "we", "you", "i"
# }


# def extract_entities_and_numbers(text: str, max_points: int = 20) -> List[str]:
#     """
#     Simple heuristics:
#     - capitalised words → possible entities (names, nouns)
#     - numbers + the next 1–2 words → quantities ("5 sweets")
#     """
#     insights: List[str] = []
#     seen = set()

#     sentences = re.split(r'(?<=[.!?])\s+', text.strip())
#     for sent in sentences:
#         if not sent:
#             continue

#         # Capitalised words
#         words = re.findall(r"\b[A-Z][a-zA-Z]+\b", sent)
#         for w in words:
#             lw = w.lower()
#             if lw not in STOP_WORDS and w not in seen:
#                 insights.append(f"Possible entity: {w}")
#                 seen.add(w)
#                 if len(insights) >= max_points:
#                     return insights

#         # Numbers + following words
#         for match in re.finditer(r"\b(\d+(?:\.\d+)?)\b", sent):
#             num = match.group(1)
#             rest = sent[match.end():].strip()
#             if not rest:
#                 continue
#             unit_words = rest.split()
#             unit = " ".join(unit_words[:2])  # up to 2 words after number
#             fact = f"{num} {unit}".strip()
#             if fact and fact not in seen:
#                 insights.append(f"Quantity mentioned: {fact}")
#                 seen.add(fact)
#                 if len(insights) >= max_points:
#                     return insights

#     return insights


# def detect_csv_like_sections(text: str, max_tables: int = 2) -> List[str]:
#     """
#     Detect simple CSV-like blocks:
#     - consecutive lines containing commas
#     - infer basic column names and types
#     """
#     lines = [l for l in text.splitlines() if l.strip()]
#     results: List[str] = []
#     i = 0
#     n = len(lines)

#     while i < n and len(results) < max_tables:
#         if "," in lines[i]:
#             block = [lines[i]]
#             j = i + 1
#             while j < n and "," in lines[j]:
#                 block.append(lines[j])
#                 j += 1

#             if len(block) >= 3:  # header + at least 2 rows
#                 header = [h.strip() for h in block[0].split(",")]
#                 cols = len(header)

#                 col_values: List[List[str]] = [[] for _ in range(cols)]
#                 for row_line in block[1:]:
#                     cells = [c.strip() for c in row_line.split(",")]
#                     for c_idx in range(min(cols, len(cells))):
#                         if cells[c_idx]:
#                             col_values[c_idx].append(cells[c_idx])

#                 def infer_col_type(values: List[str]) -> str:
#                     num_int = num_float = 0
#                     for v in values:
#                         try:
#                             int(v)
#                             num_int += 1
#                             continue
#                         except Exception:
#                             pass
#                         try:
#                             float(v)
#                             num_float += 1
#                             continue
#                         except Exception:
#                             pass
#                     if num_int == len(values) and len(values) > 0:
#                         return "int"
#                     if (num_int + num_float) == len(values) and len(values) > 0:
#                         return "float"
#                     return "string"

#                 col_summaries = []
#                 for idx, col_name in enumerate(header):
#                     ctype = infer_col_type(col_values[idx])
#                     col_summaries.append(f"{col_name or f'col{idx}'} ({ctype})")

#                 summary = "Detected CSV-like table with columns: " + ", ".join(col_summaries)
#                 results.append(summary)

#             i = j
#         else:
#             i += 1

#     return results


# # ---------- main text analysis helper ----------

# def analyze_text_block(text: str, include_json_blocks: bool = True) -> List[Dict[str, Any]]:
#     """
#     From a plain text block, produce:
#     - one 'text' entry with insights
#     - zero or more 'json' entries for embedded JSON blocks
#     """
#     detected: List[Dict[str, Any]] = []

#     # TEXT entry
#     text_parsed = {
#         "text": text,
#     }
#     text_schema = build_schema_for_obj(text_parsed)
#     insights = extract_entities_and_numbers(text)
#     insights += detect_csv_like_sections(text)

#     detected.append(
#         {
#             "type": "text",
#             "parsed": text_parsed,
#             "schema": text_schema,
#             "insights": insights,
#         }
#     )

#     # Embedded JSONs
#     if include_json_blocks:
#         blocks = _find_json_blocks(text)
#         for block in blocks:
#             if isinstance(block, dict):
#                 detected.append(
#                     {
#                         "type": "json",
#                         "parsed": block,
#                         "schema": build_schema_for_obj(block),
#                         "insights": [],
#                     }
#                 )

#     return detected


# # ---------- main entry used by the API ----------

# def analyze_file_schema(filename: str, file_bytes: bytes) -> Dict[str, Any]:
#     """
#     Returns:
#     {
#       "detected": [
#         { "type": "json", "parsed": {...}, "schema": {...}, "insights": [...] },
#         { "type": "xml",  "parsed": {...}, "schema": {...}, "insights": [...] },
#         { "type": "html", "parsed": {...}, "schema": {...}, "insights": [...] },
#         { "type": "text", "parsed": {...}, "schema": {...}, "insights": [...] }
#       ]
#     }
#     """
#     detected: List[Dict[str, Any]] = []

#     name_lower = filename.lower()

#     # -------- 1) PDF: extract full text, then treat as text --------
#     if name_lower.endswith(".pdf"):
#         reader = PdfReader(BytesIO(file_bytes))
#         pages_text: List[str] = []
#         for page in reader.pages:
#             page_text = page.extract_text() or ""
#             pages_text.append(page_text)
#         text_content = "\n".join(pages_text)

#         detected.extend(analyze_text_block(text_content, include_json_blocks=True))
#         return {"detected": detected}

#     # -------- 2) Non-PDF: decode as text and inspect --------
#     text_content = file_bytes.decode("utf-8", errors="ignore")
#     guess_type = detect_content_type_from_filename_and_text(filename, text_content)

#     # Try whole-document structured parsing first
#     parsed_structured = None
#     if guess_type in ("json", "xml", "html"):
#         try:
#             if guess_type == "json":
#                 parsed_structured = json.loads(text_content)
#             else:
#                 parsed_structured = parse_any(
#                     content_type=guess_type,
#                     content=text_content,
#                     metadata={"filename": filename, "source": "upload"},
#                 )
#         except Exception:
#             parsed_structured = None

#     if parsed_structured is not None:
#         detected.append(
#             {
#                 "type": guess_type,
#                 "parsed": parsed_structured,
#                 "schema": build_schema_for_obj(
#                     parsed_structured if isinstance(parsed_structured, dict) else {"root": parsed_structured}
#                 ),
#                 "insights": [],
#             }
#         )
#         # For a pure JSON/XML/HTML document we can still also look at it as text
#         # to extract entities / numbers etc. but skip embedded-JSON to avoid duplication
#         detected.extend(analyze_text_block(text_content, include_json_blocks=(guess_type != "json")))
#     else:
#         # Treat as plain / mixed text only
#         detected.extend(analyze_text_block(text_content, include_json_blocks=True))

#     return {"detected": detected}








# from __future__ import annotations

# import json
# import re
# from io import BytesIO
# from typing import Any, Dict, List

# from PyPDF2 import PdfReader

# from parsers import parse_any
# from etl import flatten_dict


# # ---------- small helpers ----------

# def infer_value_type(v: Any) -> str:
#     if v is None:
#         return "null"
#     if isinstance(v, bool):
#         return "bool"
#     if isinstance(v, int):
#         return "int"
#     if isinstance(v, float):
#         return "float"
#     if isinstance(v, str):
#         return "string"
#     if isinstance(v, list):
#         return "array"
#     if isinstance(v, dict):
#         return "object"
#     return type(v).__name__


# def build_schema_for_obj(obj: Dict[str, Any]) -> Dict[str, str]:
#     """
#     Flatten an object and return { field: type_string }
#     """
#     flat = flatten_dict(obj)
#     return {k: infer_value_type(v) for k, v in flat.items()}


# def detect_content_type_from_filename_and_text(filename: str, text: str) -> str:
#     """
#     Best-effort guess: json / xml / html / text
#     based on file extension + a snippet of content.
#     """
#     name_lower = filename.lower()
#     sniff = text.lstrip()[:500]

#     if name_lower.endswith(".json"):
#         return "json"
#     if name_lower.endswith(".xml"):
#         return "xml"
#     if name_lower.endswith(".html") or name_lower.endswith(".htm"):
#         return "html"

#     # Guess from content if extension not clear
#     if sniff.startswith("{") or sniff.startswith("["):
#         return "json"
#     if sniff.startswith("<?xml") or (sniff.startswith("<") and ("</" in sniff or "/>" in sniff)):
#         return "xml"
#     if "<html" in sniff.lower():
#         return "html"

#     return "text"


# # ---------- find JSON blocks embedded inside text ----------

# def _find_json_blocks(text: str, max_blocks: int = 5) -> List[Dict[str, Any]]:
#     """
#     Scan the text and try to extract a few well-formed JSON objects.
#     This will pick up product JSON, JSON-LD, etc.
#     """
#     blocks: List[Dict[str, Any]] = []
#     n = len(text)
#     i = 0

#     while i < n and len(blocks) < max_blocks:
#         if text[i] == "{":
#             depth = 0
#             for j in range(i, n):
#                 ch = text[j]
#                 if ch == "{":
#                     depth += 1
#                 elif ch == "}":
#                     depth -= 1
#                     if depth == 0:
#                         candidate = text[i: j + 1]
#                         try:
#                             obj = json.loads(candidate)
#                         except Exception:
#                             pass
#                         else:
#                             blocks.append(obj)
#                             i = j + 1
#                             break
#             else:
#                 i += 1
#         else:
#             i += 1

#     return blocks


# # ---------- important points (entities, numbers) ----------

# STOP_WORDS = {
#     "the", "this", "that", "a", "an", "and", "or", "of", "for", "with",
#     "in", "on", "at", "to", "is", "are", "was", "were", "it", "he",
#     "she", "they", "we", "you", "i"
# }


# def extract_entities_and_numbers(text: str, max_points: int = 20) -> List[str]:
#     """
#     Simple heuristics:
#     - capitalised words → possible entities (names, nouns)
#     - numbers + the next 1–2 words → quantities ("5 sweets")
#     """
#     insights: List[str] = []
#     seen = set()

#     sentences = re.split(r'(?<=[.!?])\s+', text.strip())
#     for sent in sentences:
#         if not sent:
#             continue

#         # Capitalised words
#         words = re.findall(r"\b[A-Z][a-zA-Z]+\b", sent)
#         for w in words:
#             lw = w.lower()
#             if lw not in STOP_WORDS and w not in seen:
#                 insights.append(f"Possible entity: {w}")
#                 seen.add(w)
#                 if len(insights) >= max_points:
#                     return insights

#         # Numbers + following words
#         for match in re.finditer(r"\b(\d+(?:\.\d+)?)\b", sent):
#             num = match.group(1)
#             rest = sent[match.end():].strip()
#             if not rest:
#                 continue
#             unit_words = rest.split()
#             unit = " ".join(unit_words[:2])  # up to 2 words after number
#             fact = f"{num} {unit}".strip()
#             if fact and fact not in seen:
#                 insights.append(f"Quantity mentioned: {fact}")
#                 seen.add(fact)
#                 if len(insights) >= max_points:
#                     return insights

#     return insights


# # ---------- DB classification + schema in respective format ----------

# def build_db_mapping(parsed: Any, name_hint: str = "entity") -> Dict[str, Any]:
#     """
#     Decide SQL / NoSQL / Object-based and build schema in that format.
#     - SQL: return a CREATE TABLE statement (Oracle-ish generic SQL)
#     - NoSQL: return a MongoDB-like JSON schema
#     - Object-based: return a class-like definition
#     """
#     # Normalise: we want a dict
#     if isinstance(parsed, dict):
#         obj = parsed
#     else:
#         obj = {"value": parsed}

#     flat = build_schema_for_obj(obj)  # field -> type string
#     field_types = flat

#     has_nested = any("." in key for key in field_types.keys())
#     has_complex = any(t in ("array", "object") for t in field_types.values())

#     # ---------- SQL case (flat, scalars) ----------
#     if not has_nested and not has_complex:
#         # map to Oracle-like types
#         def sql_type(t: str) -> str:
#             if t == "int":
#                 return "NUMBER"
#             if t == "float":
#                 return "NUMBER"
#             if t == "bool":
#                 return "NUMBER(1)"
#             if t == "string":
#                 return "VARCHAR2(4000)"
#             return "CLOB"

#         cols = []
#         for field, t in field_types.items():
#             cols.append(f"    {field} {sql_type(t)}")

#         ddl = "CREATE TABLE " + name_hint + " (\n" + ",\n".join(cols) + "\n);"

#         return {
#             "category": "SQL",
#             "dialect": "Oracle/Generic SQL",
#             "schema": ddl,
#         }

#     # ---------- NoSQL case (nested / arrays) ----------
#     if has_nested or has_complex:
#         # Build a Mongo-style jsonSchema string
#         def mongo_type(t: str) -> str:
#             if t == "int":
#                 return "int"
#             if t == "float":
#                 return "double"
#             if t == "bool":
#                 return "bool"
#             if t == "string":
#                 return "string"
#             if t == "array":
#                 return "array"
#             if t == "object":
#                 return "object"
#             return "any"

#         props = {
#             field: {"bsonType": mongo_type(t)}
#             for field, t in field_types.items()
#         }

#         mongo_schema = {
#             "collName": name_hint,
#             "validator": {
#                 "$jsonSchema": {
#                     "bsonType": "object",
#                     "properties": props,
#                 }
#             }
#         }

#         return {
#             "category": "NoSQL",
#             "dialect": "MongoDB-style",
#             "schema": mongo_schema,
#         }

#     # ---------- fallback: Object-based ----------
#     # Build a simple class-like definition
#     lines = [f"class {name_hint[0].upper() + name_hint[1:]}:"]
#     if not field_types:
#         lines.append("    pass")
#     else:
#         for field, t in field_types.items():
#             # map to generic language types
#             if t == "int":
#                 py_t = "int"
#             elif t == "float":
#                 py_t = "float"
#             elif t == "bool":
#                 py_t = "bool"
#             elif t == "string":
#                 py_t = "str"
#             elif t == "array":
#                 py_t = "list"
#             elif t == "object":
#                 py_t = "dict"
#             else:
#                 py_t = "Any"
#             lines.append(f"    {field}: {py_t}")

#     class_def = "\n".join(lines)

#     return {
#         "category": "Object-based",
#         "dialect": "Generic class model",
#         "schema": class_def,
#     }


# # ---------- main text analysis helper ----------

# def analyze_text_block(text: str, include_json_blocks: bool = True, name_prefix: str = "text_block") -> List[Dict[str, Any]]:
#     """
#     From a plain text block, produce:
#     - one 'text' entry with insights
#     - zero or more 'json' entries for embedded JSON blocks
#     """
#     detected: List[Dict[str, Any]] = []

#     # TEXT entry
#     text_parsed = {
#         "text": text,
#     }
#     text_schema = build_schema_for_obj(text_parsed)
#     insights = extract_entities_and_numbers(text)

#     text_entry: Dict[str, Any] = {
#         "type": "text",
#         "parsed": text_parsed,
#         "schema": text_schema,
#         "insights": insights,
#     }
#     # For plain text, db mapping is usually not very meaningful, so we skip it here.
#     detected.append(text_entry)

#     # Embedded JSONs
#     if include_json_blocks:
#         blocks = _find_json_blocks(text)
#         for idx, block in enumerate(blocks):
#             if isinstance(block, dict):
#                 name_hint = f"{name_prefix}_json_{idx+1}"
#                 db_map = build_db_mapping(block, name_hint=name_hint)
#                 detected.append(
#                     {
#                         "type": "json",
#                         "parsed": block,
#                         "schema": build_schema_for_obj(block),
#                         "insights": [],
#                         "db_mapping": db_map,
#                     }
#                 )

#     return detected


# # ---------- main entry used by the API ----------

# def analyze_file_schema(filename: str, file_bytes: bytes) -> Dict[str, Any]:
#     """
#     Returns:
#     {
#       "detected": [
#         {
#           "type": "...",
#           "parsed": {...},
#           "schema": {...},
#           "insights": [...],
#           "db_mapping": { "category": "...", "dialect": "...", "schema": ... }
#         },
#         ...
#       ]
#     }
#     """
#     detected: List[Dict[str, Any]] = []

#     name_lower = filename.lower()

#     # -------- 1) PDF: extract full text, then treat as text --------
#     if name_lower.endswith(".pdf"):
#         reader = PdfReader(BytesIO(file_bytes))
#         pages_text: List[str] = []
#         for page in reader.pages:
#             page_text = page.extract_text() or ""
#             pages_text.append(page_text)
#         text_content = "\n".join(pages_text)

#         detected.extend(analyze_text_block(text_content, include_json_blocks=True, name_prefix="pdf"))
#         return {"detected": detected}

#     # -------- 2) Non-PDF: decode as text and inspect --------
#     text_content = file_bytes.decode("utf-8", errors="ignore")
#     guess_type = detect_content_type_from_filename_and_text(filename, text_content)

#     # Try whole-document structured parsing first for json/xml/html
#     parsed_structured = None
#     if guess_type in ("json", "xml", "html"):
#         try:
#             if guess_type == "json":
#                 parsed_structured = json.loads(text_content)
#             else:
#                 parsed_structured = parse_any(
#                     content_type=guess_type,
#                     content=text_content,
#                     metadata={"filename": filename, "source": "upload"},
#                 )
#         except Exception:
#             parsed_structured = None

#     if parsed_structured is not None:
#         # main structured entry (json/xml/html)
#         if isinstance(parsed_structured, dict):
#             name_hint = f"{guess_type}_root"
#         else:
#             name_hint = f"{guess_type}_value"

#         db_map = build_db_mapping(parsed_structured, name_hint=name_hint)

#         main_entry: Dict[str, Any] = {
#             "type": guess_type,
#             "parsed": parsed_structured,
#             "schema": build_schema_for_obj(
#                 parsed_structured if isinstance(parsed_structured, dict) else {"root": parsed_structured}
#             ),
#             "insights": [],
#             "db_mapping": db_map,
#         }
#         detected.append(main_entry)

#         # Also analyse as plain text for entities / numbers, but skip extra JSON-block detection
#         detected.extend(analyze_text_block(text_content, include_json_blocks=(guess_type != "json"),
#                                            name_prefix="text"))
#     else:
#         # Treat as plain / mixed text only
#         detected.extend(analyze_text_block(text_content, include_json_blocks=True, name_prefix="text"))

#     return {"detected": detected}

# =========== proper up /////// 


# from __future__ import annotations

# import json
# import re
# from datetime import datetime
# from typing import Any, Dict, List

# from pymongo import MongoClient
# from bson import ObjectId


# from etl import flatten_dict


# # ---------- MongoDB Client ----------
# MONGO_URI = "mongodb://localhost:27017"
# client = MongoClient(MONGO_URI)
# db = client["file_schema_db"]
# collection = db["nosql_documents"]


# # ---------- Type helpers ----------
# def infer_value_type(v: Any) -> str:
#     """Return MongoDB-style field type."""
#     if v is None: return "Null"
#     if isinstance(v, bool): return "Boolean"
#     if isinstance(v, int): return "NumberInt"
#     if isinstance(v, float): return "NumberDouble"
#     if isinstance(v, str): return "String"
#     if isinstance(v, list): return "Array"
#     if isinstance(v, dict): return "Object"
#     return "Unknown"


# def build_mongo_schema(obj: Dict[str, Any]) -> Dict[str, str]:
#     flat = flatten_dict(obj)
#     return {k: infer_value_type(v) for k, v in flat.items()}


# # ---------- Important points ----------
# STOP_WORDS = {"the", "this", "that", "a", "an", "and", "or", "of", "for", "with", "in", "on", "at", "to", "is", "are"}

# def extract_insights(text: str) -> List[str]:
#     insights = []
#     seen = set()

#     sentences = re.split(r'(?<=[.!?])\s+', text.strip())
#     for sent in sentences:
#         # Entities
#         for w in re.findall(r"\b[A-Z][a-zA-Z]+\b", sent):
#             if w.lower() not in STOP_WORDS and w not in seen:
#                 insights.append(f"Entity: {w}")
#                 seen.add(w)

#         # Numbers + next 2 words
#         for match in re.finditer(r"\b(\d+(?:\.\d+)?)\b", sent):
#             num = match.group(1)
#             rest = sent[match.end():].strip().split()
#             fact = f"{num} {' '.join(rest[:2])}".strip()
#             if fact and fact not in seen:
#                 insights.append(f"Quantity: {fact}")
#                 seen.add(fact)
#     return insights[:20]


# # ---------- SQL Parsing ----------
# def parse_sql(text: str) -> List[Dict[str, Any]]:
#     tables = []
#     pattern = re.compile(r"CREATE\s+TABLE\s+([`\"\w]+)\s*\((.*?)\)\s*;?", re.IGNORECASE | re.DOTALL)

#     for match in pattern.finditer(text):
#         table_name = match.group(1).strip("`\"")
#         cols_block = match.group(2)

#         cols = []
#         for line in cols_block.splitlines():
#             line = line.strip().rstrip(",")
#             if not line or line.upper().startswith(("PRIMARY","FOREIGN","UNIQUE","KEY","CONSTRAINT")):
#                 continue
#             parts = line.split()
#             cols.append({"name": parts[0], "type": parts[1]})

#         tables.append({"name": table_name, "columns": cols})
#     return tables


# def format_sql_output(filename: str, tables: List[Dict[str, Any]], insights: List[str]) -> str:
#     lines = [
#         f"File: {filename}",
#         "Detected Type: SQL Schema",
#         "",
#     ]
#     for t in tables:
#         lines.append(f"Table: {t['name']}")
#         for col in t["columns"]:
#             lines.append(f"  - {col['name']} : {col['type']}")
#         lines.append("")

#     if insights:
#         lines.append("Important Points:")
#         for i in insights:
#             lines.append(f"  - {i}")

#     return "\n".join(lines)


# # ---------- Mongo NoSQL (JSON) ----------
# def store_in_mongo(filename: str, structured: Any, schema: Dict[str, str]):
#     try:
#         doc = {
#             "filename": filename,
#             "stored_at": datetime.utcnow(),
#             "schema": schema,
#             "document": structured
#         }
#         collection.insert_one(doc)
#     except Exception as e:
#         print(f"Mongo Insert Error: {e}")


# def format_mongo_output(filename: str, struct: Any, insights: List[str]) -> str:
#     schema = build_mongo_schema(struct)
#     store_in_mongo(filename, struct, schema)

#     lines = [
#         f"File: {filename}",
#         "Detected Type: MongoDB / NoSQL",
#         "Collection: nosql_documents",
#         "",
#         "MongoDB Schema:",
#     ]

#     maxlen = max(len(k) for k in schema.keys())
#     for field, typ in sorted(schema.items()):
#         lines.append(f"  {field.ljust(maxlen)} : {typ}")

#     if insights:
#         lines.append("")
#         lines.append("Important Points:")
#         for i in insights:
#             lines.append(f"  - {i}")

#     return "\n".join(lines)


# # ---------- MAIN ANALYZER ----------
# def analyze_file_schema(filename: str, file_bytes: bytes) -> Dict[str, Any]:
#     text = file_bytes.decode("utf-8", errors="ignore")
#     insights = extract_insights(text)

#     if "CREATE TABLE" in text.upper():
#         return {"summary": format_sql_output(filename, parse_sql(text), insights)}

#     if text.strip().startswith("{") or text.strip().startswith("["):
#         try:
#             struct = json.loads(text)
#             return {"summary": format_mongo_output(filename, struct, insights)}
#         except:
#             pass

#     # fallback
#     return {"summary": f"File: {filename}\nDetected: Plain Text\n\nImportant Points:\n" + "\n".join(f"- {i}" for i in insights)}




# # ---------- Mongo listing / search helpers ----------

# def list_nosql_docs(limit: int = 20) -> List[Dict[str, Any]]:
#     """
#     Return a lightweight list of recently stored NoSQL documents.
#     Does NOT return the full document body (only metadata + schema size).
#     """
#     docs = (
#         collection
#         .find({}, {"document": 0})  # exclude the big document field
#         .sort("stored_at", -1)
#         .limit(limit)
#     )

#     result: List[Dict[str, Any]] = []
#     for d in docs:
#         result.append(
#             {
#                 "id": str(d.get("_id")),
#                 "filename": d.get("filename"),
#                 "stored_at": d.get("stored_at").isoformat() if d.get("stored_at") else None,
#                 "schema_field_count": len(d.get("schema") or {}),
#             }
#         )
#     return result


# def get_nosql_doc(doc_id: str) -> Dict[str, Any]:
#     """
#     Return a single stored NoSQL document (including full JSON).
#     """
#     try:
#         _id = ObjectId(doc_id)
#     except Exception:
#         raise ValueError("Invalid document id")

#     d = collection.find_one({"_id": _id})
#     if not d:
#         raise ValueError("Document not found")

#     # Convert _id and datetime for JSON
#     d["id"] = str(d.pop("_id"))
#     if d.get("stored_at"):
#         d["stored_at"] = d["stored_at"].isoformat()
#     return d


# def search_nosql_docs(query: str, limit: int = 20) -> List[Dict[str, Any]]:
#     """
#     Simple search by filename substring (case-insensitive).
#     """
#     regex = {"$regex": query, "$options": "i"}
#     docs = (
#         collection
#         .find({"filename": regex}, {"document": 0})
#         .sort("stored_at", -1)
#         .limit(limit)
#     )

#     result: List[Dict[str, Any]] = []
#     for d in docs:
#         result.append(
#             {
#                 "id": str(d.get("_id")),
#                 "filename": d.get("filename"),
#                 "stored_at": d.get("stored_at").isoformat() if d.get("stored_at") else None,
#                 "schema_field_count": len(d.get("schema") or {}),
#             }
#         )
#     return result







# ================== 


# from __future__ import annotations

# import json
# import re
# from datetime import datetime
# from io import BytesIO
# from typing import Any, Dict, List

# from bson import ObjectId
# from pymongo import MongoClient
# from PyPDF2 import PdfReader

# from etl import flatten_dict


# # ---------- MongoDB client ----------

# MONGO_URI = "mongodb://localhost:27017"
# MONGO_DB_NAME = "file_schema_db"
# MONGO_COLLECTION = "nosql_documents"

# mongo_client = MongoClient(MONGO_URI)
# mongo_db = mongo_client[MONGO_DB_NAME]
# collection = mongo_db[MONGO_COLLECTION]


# # ---------- Type helpers (Mongo-style) ----------

# def infer_value_type(v: Any) -> str:
#     """Return MongoDB-style type names."""
#     if v is None:
#         return "Null"
#     if isinstance(v, bool):
#         return "Boolean"
#     if isinstance(v, int):
#         return "NumberInt"
#     if isinstance(v, float):
#         return "NumberDouble"
#     if isinstance(v, str):
#         return "String"
#     if isinstance(v, list):
#         return "Array"
#     if isinstance(v, dict):
#         return "Object"
#     return type(v).__name__


# def build_mongo_schema(obj: Dict[str, Any]) -> Dict[str, str]:
#     flat = flatten_dict(obj)
#     return {k: infer_value_type(v) for k, v in flat.items()}


# # ---------- Important points (entities + numbers + CSV) ----------

# STOP_WORDS = {
#     "the", "this", "that", "a", "an", "and", "or", "of", "for", "with",
#     "in", "on", "at", "to", "is", "are", "was", "were", "it", "he",
#     "she", "they", "we", "you", "i"
# }


# def extract_entities_and_numbers(text: str, max_points: int = 30) -> List[str]:
#     insights: List[str] = []
#     seen = set()

#     sentences = re.split(r'(?<=[.!?])\s+', text.strip())
#     for sent in sentences:
#         if not sent:
#             continue

#         # Entities
#         for w in re.findall(r"\b[A-Z][a-zA-Z]+\b", sent):
#             lw = w.lower()
#             if lw not in STOP_WORDS and w not in seen:
#                 insights.append(f"Entity: {w}")
#                 seen.add(w)
#                 if len(insights) >= max_points:
#                     return insights

#         # Quantities: number + next 1–2 words
#         for m in re.finditer(r"\b(\d+(?:\.\d+)?)\b", sent):
#             num = m.group(1)
#             rest = sent[m.end():].strip().split()
#             unit = " ".join(rest[:2])
#             fact = f"{num} {unit}".strip()
#             if fact and fact not in seen:
#                 insights.append(f"Quantity: {fact}")
#                 seen.add(fact)
#                 if len(insights) >= max_points:
#                     return insights

#     return insights


# def detect_csv_like_sections(text: str, max_tables: int = 3) -> List[str]:
#     """
#     Detect simple CSV-like sections and summarise columns + types.
#     """
#     lines = [l for l in text.splitlines() if l.strip()]
#     results: List[str] = []
#     i = 0
#     n = len(lines)

#     while i < n and len(results) < max_tables:
#         if "," in lines[i]:
#             block = [lines[i]]
#             j = i + 1
#             while j < n and "," in lines[j]:
#                 block.append(lines[j])
#                 j += 1

#             if len(block) >= 3:  # header + 2 rows
#                 header = [h.strip() for h in block[0].split(",")]
#                 cols = len(header)
#                 col_values: List[List[str]] = [[] for _ in range(cols)]

#                 for row in block[1:]:
#                     cells = [c.strip() for c in row.split(",")]
#                     for idx in range(min(cols, len(cells))):
#                         if cells[idx]:
#                             col_values[idx].append(cells[idx])

#                 def infer_col_type(values: List[str]) -> str:
#                     num_int = num_float = 0
#                     for v in values:
#                         try:
#                             int(v)
#                             num_int += 1
#                             continue
#                         except Exception:
#                             pass
#                         try:
#                             float(v)
#                             num_float += 1
#                             continue
#                         except Exception:
#                             pass
#                     if values and num_int == len(values):
#                         return "NumberInt"
#                     if values and (num_int + num_float) == len(values):
#                         return "NumberDouble"
#                     return "String"

#                 col_desc = []
#                 for idx, name in enumerate(header):
#                     col_desc.append(f"{name or f'col{idx}'} ({infer_col_type(col_values[idx])})")

#                 results.append("CSV-like table columns: " + ", ".join(col_desc))

#             i = j
#         else:
#             i += 1

#     return results


# # ---------- JSON-in-text detection ----------

# def _find_json_blocks(text: str, max_blocks: int = 5) -> List[Dict[str, Any]]:
#     """
#     Find stand-alone JSON objects inside a large text blob.
#     """
#     blocks: List[Dict[str, Any]] = []
#     n = len(text)
#     i = 0

#     while i < n and len(blocks) < max_blocks:
#         if text[i] == "{":
#             depth = 0
#             for j in range(i, n):
#                 ch = text[j]
#                 if ch == "{":
#                     depth += 1
#                 elif ch == "}":
#                     depth -= 1
#                     if depth == 0:
#                         candidate = text[i:j + 1]
#                         try:
#                             obj = json.loads(candidate)
#                         except Exception:
#                             pass
#                         else:
#                             blocks.append(obj)
#                             i = j + 1
#                             break
#             else:
#                 i += 1
#         else:
#             i += 1

#     return blocks


# # ---------- SQL parsing ----------

# def parse_sql_tables(text: str) -> List[Dict[str, Any]]:
#     """
#     Parse CREATE TABLE statements into table + columns.
#     """
#     tables: List[Dict[str, Any]] = []
#     pattern = re.compile(
#         r"CREATE\s+TABLE\s+([`\"\w]+)\s*\((.*?)\)\s*;?",
#         re.IGNORECASE | re.DOTALL,
#     )

#     for match in pattern.finditer(text):
#         table_name = match.group(1).strip("`\"")
#         cols_block = match.group(2)

#         cols: List[Dict[str, str]] = []
#         for line in cols_block.splitlines():
#             line = line.strip().rstrip(",")
#             if not line:
#                 continue
#             upper = line.upper()
#             if upper.startswith(("PRIMARY KEY", "FOREIGN KEY", "UNIQUE", "KEY", "CONSTRAINT", "CHECK")):
#                 continue
#             parts = line.split()
#             if len(parts) < 2:
#                 continue
#             col_name = parts[0].strip("`\"")
#             col_type = parts[1]
#             cols.append({"name": col_name, "type": col_type})

#         if cols:
#             tables.append({"name": table_name, "columns": cols})

#     return tables


# # ---------- Mongo storage ----------

# def store_in_mongo(filename: str, structured: Any, schema: Dict[str, str]) -> None:
#     """
#     Store JSON/NoSQL object(s) into Mongo.
#     """
#     meta = {
#         "filename": filename,
#         "stored_at": datetime.utcnow(),
#         "schema": schema,
#     }
#     try:
#         if isinstance(structured, dict):
#             collection.insert_one({**meta, "document": structured})
#         elif isinstance(structured, list):
#             docs = []
#             for elem in structured:
#                 if isinstance(elem, dict):
#                     docs.append({**meta, "document": elem})
#             if docs:
#                 collection.insert_many(docs)
#         else:
#             collection.insert_one({**meta, "document": {"root": structured}})
#     except Exception as e:
#         print(f"[Mongo] store error: {e}")


# # ---------- Main analyzer ----------

# def analyze_file_schema(filename: str, file_bytes: bytes) -> Dict[str, Any]:
#     """
#     High-level logic:

#     - Extract text (PDF → PyPDF2, others → decode)
#     - Detect SQL tables
#     - Detect JSON blocks (NoSQL)
#     - Extract important points (entities, quantities, CSV)
#     - Build a plain-text summary
#     """
#     name_lower = filename.lower()

#     # 1) Get text
#     if name_lower.endswith(".pdf"):
#         reader = PdfReader(BytesIO(file_bytes))
#         pages = []
#         for page in reader.pages:
#             pages.append(page.extract_text() or "")
#         text = "\n".join(pages)
#     else:
#         text = file_bytes.decode("utf-8", errors="ignore")

#     # 2) Important points
#     insights = extract_entities_and_numbers(text)
#     insights.extend(detect_csv_like_sections(text))

#     lines: List[str] = []
#     lines.append(f"File: {filename}")

#     # 3) SQL schemas
#     tables = parse_sql_tables(text)
#     if tables:
#         lines.append("Detected: SQL schema")
#         lines.append("")
#         for t in tables:
#             lines.append(f"Table: {t['name']}")
#             for col in t["columns"]:
#                 lines.append(f"  - {col['name']} : {col['type']}")
#             lines.append("")

#     # 4) JSON / NoSQL schemas
#     json_structs: List[Dict[str, Any]] = []

#     # try full JSON first
#     try:
#         full_json = json.loads(text)
#         if isinstance(full_json, (dict, list)):
#             json_structs.append(full_json)
#     except Exception:
#         pass

#     # if no full JSON, search embedded blocks
#     if not json_structs:
#         json_structs = _find_json_blocks(text)

#     if json_structs:
#         if tables:
#             lines.append("----")
#         lines.append("Detected: JSON / NoSQL blocks")
#         for idx, obj in enumerate(json_structs):
#             lines.append(f"JSON block #{idx + 1}:")
#             if isinstance(obj, dict):
#                 schema = build_mongo_schema(obj)
#             else:
#                 schema = build_mongo_schema({"root": obj})

#             # store in Mongo
#             store_in_mongo(filename, obj, schema)

#             if schema:
#                 max_field_len = max(len(f) for f in schema.keys())
#             else:
#                 max_field_len = 0

#             for field, typ in sorted(schema.items()):
#                 lines.append(f"  {field.ljust(max_field_len)} : {typ}")
#             lines.append("")

#     if not tables and not json_structs:
#         lines.append("Detected: Plain / mixed text")
#         lines.append("")

#     # 5) Important points
#     if insights:
#         lines.append("Important points:")
#         for p in insights:
#             lines.append(f"  - {p}")

#     summary = "\n".join(lines)
#     return {"summary": summary}


# # ---------- Mongo listing / search helpers (for panel) ----------

# def list_nosql_docs(limit: int = 20) -> List[Dict[str, Any]]:
#     docs = (
#         collection
#         .find({}, {"document": 0})
#         .sort("stored_at", -1)
#         .limit(limit)
#     )
#     result: List[Dict[str, Any]] = []
#     for d in docs:
#         result.append(
#             {
#                 "id": str(d.get("_id")),
#                 "filename": d.get("filename"),
#                 "stored_at": d.get("stored_at").isoformat() if d.get("stored_at") else None,
#                 "schema_field_count": len(d.get("schema") or {}),
#             }
#         )
#     return result


# def get_nosql_doc(doc_id: str) -> Dict[str, Any]:
#     try:
#         _id = ObjectId(doc_id)
#     except Exception:
#         raise ValueError("Invalid document id")

#     d = collection.find_one({"_id": _id})
#     if not d:
#         raise ValueError("Document not found")

#     d["id"] = str(d.pop("_id"))
#     if d.get("stored_at"):
#         d["stored_at"] = d["stored_at"].isoformat()
#     return d


# def search_nosql_docs(query: str, limit: int = 20) -> List[Dict[str, Any]]:
#     regex = {"$regex": query, "$options": "i"}
#     docs = (
#         collection
#         .find({"filename": regex}, {"document": 0})
#         .sort("stored_at", -1)
#         .limit(limit)
#     )

#     result: List[Dict[str, Any]] = []
#     for d in docs:
#         result.append(
#             {
#                 "id": str(d.get("_id")),
#                 "filename": d.get("filename"),
#                 "stored_at": d.get("stored_at").isoformat() if d.get("stored_at") else None,
#                 "schema_field_count": len(d.get("schema") or {}),
#             }
#         )
#     return result









# ======================================= 


from __future__ import annotations

import json
import re
from datetime import datetime
from io import BytesIO
from typing import Any, Dict, List

from bson import ObjectId
from pymongo import MongoClient
from PyPDF2 import PdfReader

from etl import flatten_dict


# ---------- MongoDB client ----------

MONGO_URI = "mongodb://localhost:27017"
MONGO_DB_NAME = "file_schema_db"
MONGO_COLLECTION = "nosql_documents"

mongo_client = MongoClient(MONGO_URI)
mongo_db = mongo_client[MONGO_DB_NAME]
collection = mongo_db[MONGO_COLLECTION]


# ---------- Type helpers (Mongo-style) ----------

def infer_value_type(v: Any) -> str:
    """Return MongoDB-style type names."""
    if v is None:
        return "Null"
    if isinstance(v, bool):
        return "Boolean"
    if isinstance(v, int):
        return "NumberInt"
    if isinstance(v, float):
        return "NumberDouble"
    if isinstance(v, str):
        return "String"
    if isinstance(v, list):
        return "Array"
    if isinstance(v, dict):
        return "Object"
    return type(v).__name__


def build_mongo_schema(obj: Dict[str, Any]) -> Dict[str, str]:
    flat = flatten_dict(obj)
    return {k: infer_value_type(v) for k, v in flat.items()}


# ---------- Important points (entities + numbers + CSV) ----------

STOP_WORDS = {
    "the", "this", "that", "a", "an", "and", "or", "of", "for", "with",
    "in", "on", "at", "to", "is", "are", "was", "were", "it", "he",
    "she", "they", "we", "you", "i"
}


def extract_entities_and_numbers(text: str, max_points: int = 30) -> List[str]:
    """
    Returns a list like:
    - 'Possible entity: Source'
    - 'Quantity: 5 sweets'
    """
    insights: List[str] = []
    seen = set()

    sentences = re.split(r'(?<=[.!?])\s+', text.strip())
    for sent in sentences:
        if not sent:
            continue

        # Entities
        for w in re.findall(r"\b[A-Z][a-zA-Z]+\b", sent):
            lw = w.lower()
            if lw not in STOP_WORDS and w not in seen:
                insights.append(f"Possible entity: {w}")
                seen.add(w)
                if len(insights) >= max_points:
                    return insights

        # Quantities: number + next 1–2 words
        for m in re.finditer(r"\b(\d+(?:\.\d+)?)\b", sent):
            num = m.group(1)
            rest = sent[m.end():].strip().split()
            unit = " ".join(rest[:2])
            fact = f"{num} {unit}".strip()
            if fact and fact not in seen:
                insights.append(f"Quantity: {fact}")
                seen.add(fact)
                if len(insights) >= max_points:
                    return insights

    return insights


def detect_csv_like_sections(text: str, max_tables: int = 3) -> List[str]:
    """
    Detect simple CSV-like sections and summarise columns + types.
    """
    lines = [l for l in text.splitlines() if l.strip()]
    results: List[str] = []
    i = 0
    n = len(lines)

    while i < n and len(results) < max_tables:
        if "," in lines[i]:
            block = [lines[i]]
            j = i + 1
            while j < n and "," in lines[j]:
                block.append(lines[j])
                j += 1

            if len(block) >= 3:  # header + 2 rows
                header = [h.strip() for h in block[0].split(",")]
                cols = len(header)
                col_values: List[List[str]] = [[] for _ in range(cols)]

                for row in block[1:]:
                    cells = [c.strip() for c in row.split(",")]
                    for idx in range(min(cols, len(cells))):
                        if cells[idx]:
                            col_values[idx].append(cells[idx])

                def infer_col_type(values: List[str]) -> str:
                    num_int = num_float = 0
                    for v in values:
                        try:
                            int(v)
                            num_int += 1
                            continue
                        except Exception:
                            pass
                        try:
                            float(v)
                            num_float += 1
                            continue
                        except Exception:
                            pass
                    if values and num_int == len(values):
                        return "NumberInt"
                    if values and (num_int + num_float) == len(values):
                        return "NumberDouble"
                    return "String"

                col_desc = []
                for idx, name in enumerate(header):
                    col_desc.append(f"{name or f'col{idx}'} ({infer_col_type(col_values[idx])})")

                results.append("CSV-like table columns: " + ", ".join(col_desc))

            i = j
        else:
            i += 1

    return results


# ---------- JSON-in-text detection ----------

def _find_json_blocks(text: str, max_blocks: int = 5) -> List[Any]:
    """
    Find stand-alone JSON objects or arrays inside a large text blob.
    """
    blocks: List[Any] = []
    n = len(text)
    i = 0

    while i < n and len(blocks) < max_blocks:
        if text[i] in "{[":
            depth = 0
            start_char = text[i]
            end_char = "}" if start_char == "{" else "]"
            for j in range(i, n):
                ch = text[j]
                if ch == start_char:
                    depth += 1
                elif ch == end_char:
                    depth -= 1
                    if depth == 0:
                        candidate = text[i:j + 1]
                        try:
                            obj = json.loads(candidate)
                        except Exception:
                            pass
                        else:
                            blocks.append(obj)
                            i = j + 1
                            break
            else:
                i += 1
        else:
            i += 1

    return blocks


# ---------- SQL parsing & dialect detection ----------

def parse_sql_tables(text: str) -> List[Dict[str, Any]]:
    tables: List[Dict[str, Any]] = []
    pattern = re.compile(
        r"CREATE\s+TABLE\s+([`\"\w]+)\s*\((.*?)\)\s*;?",
        re.IGNORECASE | re.DOTALL,
    )

    for match in pattern.finditer(text):
        table_name = match.group(1).strip("`\"")
        cols_block = match.group(2)

        cols: List[Dict[str, str]] = []
        for line in cols_block.splitlines():
            line = line.strip().rstrip(",")
            if not line:
                continue
            upper = line.upper()
            if upper.startswith(("PRIMARY KEY", "FOREIGN KEY", "UNIQUE", "KEY", "CONSTRAINT", "CHECK")):
                continue
            parts = line.split()
            if len(parts) < 2:
                continue
            col_name = parts[0].strip("`\"")
            col_type = parts[1]
            cols.append({"name": col_name, "type": col_type})

        if cols:
            tables.append({"name": table_name, "columns": cols})

    return tables


def detect_sql_dialect(tables: List[Dict[str, Any]]) -> str:
    """
    Very rough heuristic: if we see Oracle-ish types, call it 'oracle_sql',
    otherwise just 'sql'.
    """
    oracle_keywords = ("VARCHAR2", "NVARCHAR2", "NUMBER(", "CLOB", "NCLOB")
    for t in tables:
        for c in t["columns"]:
            ttype = c["type"].upper()
            if any(k in ttype for k in oracle_keywords):
                return "oracle_sql"
    return "sql"


# ---------- Mongo storage ----------

def store_in_mongo(filename: str, structured: Any, schema: Dict[str, str]) -> None:
    meta = {
        "filename": filename,
        "stored_at": datetime.utcnow(),
        "schema": schema,
    }
    try:
        if isinstance(structured, dict):
            collection.insert_one({**meta, "document": structured})
        elif isinstance(structured, list):
            docs = []
            for elem in structured:
                if isinstance(elem, dict):
                    docs.append({**meta, "document": elem})
            if docs:
                collection.insert_many(docs)
        else:
            collection.insert_one({**meta, "document": {"root": structured}})
    except Exception as e:
        print(f"[Mongo] store error: {e}")


# ---------- MAIN: build detected[] list ----------

def analyze_file_schema(filename: str, file_bytes: bytes) -> Dict[str, Any]:
    """
    Return:
    {
      "detected": [
        { "type": "text",        "parsed": {...}, "schema": {...}, "insights": [...] },
        { "type": "sql",         "parsed": {...}, "schema": {...}, "insights": [...] },
        { "type": "oracle_sql",  "parsed": {...}, "schema": {...}, "insights": [...] },
        { "type": "nosql_mongo", "parsed": {...}, "schema": {...}, "insights": [...] }
      ]
    }
    """
    name_lower = filename.lower()

    # ---- 1) Extract text (PDF vs others) ----
    if name_lower.endswith(".pdf"):
        reader = PdfReader(BytesIO(file_bytes))
        pages = []
        for page in reader.pages:
            pages.append(page.extract_text() or "")
        text = "\n".join(pages)
    else:
        text = file_bytes.decode("utf-8", errors="ignore")

    detected: List[Dict[str, Any]] = []

    # ---- 2) TEXT block with insights ----
    text_insights = extract_entities_and_numbers(text)
    text_insights.extend(detect_csv_like_sections(text))

    detected.append(
        {
            "type": "text",
            "parsed": {"text": text},
            "schema": {"text": "string"},
            "insights": text_insights,
        }
    )

    # ---- 3) SQL detection ----
    tables = parse_sql_tables(text)
    if tables:
        dialect = detect_sql_dialect(tables)  # "sql" or "oracle_sql"
        sql_schema: Dict[str, str] = {}
        for t in tables:
            tname = t["name"]
            for c in t["columns"]:
                key = f"{tname}.{c['name']}"
                sql_schema[key] = c["type"]

        detected.append(
            {
                "type": dialect,
                "parsed": {
                    "tables": tables,
                    "dialect": dialect,
                },
                "schema": sql_schema,
                "insights": [],
            }
        )

    # ---- 4) JSON / NoSQL detection ----
    json_structs: List[Any] = []

    # full JSON?
    try:
        full_json = json.loads(text)
        if isinstance(full_json, (dict, list)):
            json_structs.append(full_json)
    except Exception:
        pass

    # embedded JSON blocks?
    if not json_structs:
        json_structs = _find_json_blocks(text)

    for obj in json_structs:
        if isinstance(obj, dict):
            schema = build_mongo_schema(obj)
        else:
            schema = build_mongo_schema({"root": obj})

        store_in_mongo(filename, obj, schema)

        detected.append(
            {
                "type": "nosql_mongo",
                "parsed": obj,
                "schema": schema,
                "insights": [],  # text insights already in the 'text' block
            }
        )

    return {"detected": detected}


# ---------- Mongo listing / search helpers (for NoSQL panel) ----------

def list_nosql_docs(limit: int = 20) -> List[Dict[str, Any]]:
    docs = (
        collection
        .find({}, {"document": 0})
        .sort("stored_at", -1)
        .limit(limit)
    )
    result: List[Dict[str, Any]] = []
    for d in docs:
        result.append(
            {
                "id": str(d.get("_id")),
                "filename": d.get("filename"),
                "stored_at": d.get("stored_at").isoformat() if d.get("stored_at") else None,
                "schema_field_count": len(d.get("schema") or {}),
            }
        )
    return result


def get_nosql_doc(doc_id: str) -> Dict[str, Any]:
    try:
        _id = ObjectId(doc_id)
    except Exception:
        raise ValueError("Invalid document id")

    d = collection.find_one({"_id": _id})
    if not d:
        raise ValueError("Document not found")

    d["id"] = str(d.pop("_id"))
    if d.get("stored_at"):
        d["stored_at"] = d["stored_at"].isoformat()
    return d


def search_nosql_docs(query: str, limit: int = 20) -> List[Dict[str, Any]]:
    regex = {"$regex": query, "$options": "i"}
    docs = (
        collection
        .find({"filename": regex}, {"document": 0})
        .sort("stored_at", -1)
        .limit(limit)
    )

    result: List[Dict[str, Any]] = []
    for d in docs:
        result.append(
            {
                "id": str(d.get("_id")),
                "filename": d.get("filename"),
                "stored_at": d.get("stored_at").isoformat() if d.get("stored_at") else None,
                "schema_field_count": len(d.get("schema") or {}),
            }
        )
    return result
