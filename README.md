# Auraverse---ETL-Pipeline


to run this type 
" uvicorn main:app --reload " in your terminal





## 1. Overview

This project is an **ETL (Extract–Transform–Load) pipeline** designed for **unstructured and semi-structured scraped data**.  

Key capabilities:

- Accepts scraped data in **JSON / CSV / raw text** formats.
- **Analyzes and classifies** data according to storage target:
  - Relational **SQL** databases (e.g. PostgreSQL, MySQL)
  - **NoSQL** databases (e.g. MongoDB)
  - **Oracle** databases
- **Infers schemas dynamically** based on the input data:
  - Detects column/field names
  - Infers data types (string, int, float, boolean, date, nested object, list, etc.)
- Generates **DDL / schema definitions** for SQL, NoSQL, and Oracle.
- Provides a **REST API** (and optionally a small frontend) to:
  - Upload sample data
  - Preview inferred schemas
  - Download generated schema definitions
  - Trigger ETL jobs
- Persists logs and metadata about each run for debugging and audit.

---

## 2. Architecture

**High-level flow:**

1. **Extract**
   - Scraped data is sent to the API or read from files.
   - Supported formats: `.json`, `.csv`, `.txt` (with JSON lines, etc.).

2. **Classify**
   - Data is analyzed for:
     - Structure (flat vs nested)
     - Presence of nested documents, arrays
     - Data type distribution
   - Based on rules, data is classified into:
     - `SQL` (flat, table-like)
     - `NoSQL` (nested, flexible, document-like)
     - `ORACLE` (similar to SQL but can produce Oracle-specific DDL)

3. **Schema Inference**
   - For each field:
     - Collects sample values
     - Infers type (string / int / float / bool / date / object / array).
   - For SQL / Oracle:
     - Generates table name
     - Maps to appropriate SQL types
   - For NoSQL:
     - Generates a document schema description (JSON schema-like output).

4. **Transform**
   - Cleans data:
     - Normalizes field names
     - Handles missing values / nulls
     - Converts types where needed
   - Optionally flattens nested structures for SQL.

5. **Load**
   - If configured with DB connections:
     - Creates tables/collections.
     - Inserts transformed data.
   - Otherwise, outputs:
     - `*.sql` files (for SQL/Oracle)
     - `schema.json` (for NoSQL)
     - `transformed_data.json/csv`.

---

## 3. Tech Stack

> Adjust this section to your actual implementation if different.

- **Language:** Python 3.x
- **Backend Framework:** FastAPI / Flask (REST API)
- **DB Libraries:**
  - `SQLAlchemy` for SQL DBs
  - `cx_Oracle` or `oracledb` for Oracle (if used)
  - `pymongo` for MongoDB (if used)
- **Other Libraries:**
  - `pydantic` for data models
  - `pandas` for data wrangling (optional)
  - `python-dotenv` for config
- **Frontend (optional):**
  - Simple HTML/CSS/JS or React to interact with the API.

---

## 4. Folder Structure

Example structure (adapt to your code):

```bash
etl-pipeline/
├─ backend/
│  ├─ app.py                 # Main API entry point
│  ├─ etl/
│  │  ├─ extract.py          # Extraction utilities
│  │  ├─ classify.py         # SQL / NoSQL / Oracle classifier
│  │  ├─ infer_schema.py     # Dynamic schema inference logic
│  │  ├─ transform.py        # Data cleaning & transformation
│  │  ├─ load_sql.py         # SQL loader + DDL generator
│  │  ├─ load_nosql.py       # Mongo/NoSQL loader
│  │  ├─ load_oracle.py      # Oracle-specific DDL + loader
│  │  └─ utils.py            # Common helpers
│  ├─ models/
│  │  └─ dto.py              # Request/response models (Pydantic)
│  ├─ config/
│  │  └─ settings.py         # Configuration handling
│  └─ requirements.txt
├─ frontend/                 # Optional - UI for interacting with API
│  ├─ index.html
│  └─ ...
├─ samples/                  # Example input data files
├─ output/                   # Generated schemas and transformed output
├─ .env                      # Environment variables (DB URLs, etc.)
└─ README.md
