# PDF Demo Indexer

A FastAPI-based PDF indexing and semantic search system with optional LLM-powered question answering.

## Overview

This application provides a complete solution for ingesting PDF documents, creating a searchable index, and retrieving relevant information through full-text search. It supports optional integration with Ollama for LLM-based question answering using retrieved context.

### Key Features

- **PDF Ingestion**: Automatically extracts and indexes text from PDF documents
- **Full-Text Search**: SQLite FTS5 with BM25 ranking for efficient search
- **Smart Chunking**: Overlapping text chunks for better context preservation
- **Incremental Updates**: Only processes changed files (SHA256 + timestamp tracking)
- **LLM Integration**: Optional Ollama integration for question answering
- **REST API**: Simple FastAPI endpoints for all operations

## Architecture

### Components

1. **main.py** - FastAPI application and API endpoints
2. **db.py** - SQLite database connection and schema management
3. **ingest.py** - PDF processing and text extraction
4. **search.py** - Full-text search with BM25 ranking
5. **model.py** - Ollama LLM client for question answering
6. **config.py** - Configuration (currently empty, placeholder)

### Data Flow

```
PDF Files (data/pdfs/)
    ↓
Ingest (PyMuPDF extraction)
    ↓
Chunking (900 chars, 150 overlap)
    ↓
SQLite Database (storage/index.db)
    ↓
FTS5 Search (BM25 ranking)
    ↓
[Optional] LLM Answer Generation
    ↓
JSON Response
```

## Installation

### Requirements

```bash
pip install -r req.txt
```

Dependencies:
- `fastapi` - Web framework
- `uvicorn` - ASGI server
- `pydantic` - Data validation
- `python-multipart` - File upload support
- `pymupdf` - PDF text extraction

### Optional: Ollama Setup

For LLM-powered answers, install [Ollama](https://ollama.ai/) and pull a model:

```bash
ollama pull qwen2.5:0.5b-instruct
```

## Usage

### Starting the Server

```bash
uvicorn app.main:app --reload
```

The API will be available at `http://localhost:8000`

### API Endpoints

#### 1. Health Check
```bash
GET /health
```

Returns: `{"ok": true}`

#### 2. Ingest PDFs
```bash
POST /ingest
```

Processes all PDF files in `data/pdfs/` directory.

**Response:**
```json
{
  "folder": "/path/to/data/pdfs",
  "stats": {
    "ingested": 5,
    "skipped": 2,
    "errors": 0
  }
}
```

#### 3. Search
```bash
POST /search
Content-Type: application/json

{
  "query": "your search query",
  "k": 5,
  "use_model": false
}
```

**Parameters:**
- `query` (string, required): Search query
- `k` (int, default: 5): Number of results to return
- `use_model` (bool, default: false): Use LLM for answer generation

**Response:**
```json
{
  "query": "your search query",
  "answer": null,
  "context": "Source: file.pdf (p.1)\nRelevant text...",
  "results": [
    {
      "path": "data/pdfs/file.pdf",
      "page_num": 1,
      "chunk_id": 42,
      "score": -2.5,
      "text": "chunk text..."
    }
  ]
}
```

## Code Documentation

### db.py - Database Layer

**Purpose:** Manages SQLite database connection and schema.

**Schema:**
- `files` table: Tracks PDF files with SHA256 hash and metadata
- `chunks` table: Stores text chunks with page numbers
- `chunks_fts` virtual table: FTS5 full-text search index

**Key Functions:**
- `connect()`: Creates database connection with row factory
- `init_db()`: Initializes schema with WAL mode for better concurrency

**Location:** `app/db.py:4-40`

### ingest.py - PDF Processing

**Purpose:** Extracts text from PDFs and stores chunks in database.

**Key Functions:**

**`sha256_file(path)`** (app/ingest.py:10-15)
- Computes SHA256 hash for file change detection
- Reads file in 1MB chunks for memory efficiency

**`chunk_text(text, chunk_size=900, overlap=150)`** (app/ingest.py:17-27)
- Normalizes Unicode (fixes ligatures like ﬁ → fi)
- Creates overlapping chunks for better context preservation
- Default: 900 characters per chunk with 150 character overlap

**`upsert_file(con, path, sha, modified_ns, size_bytes)`** (app/ingest.py:30-45)
- Smart file update: only re-processes if SHA256 or metadata changed
- Deletes old chunks before re-indexing
- Returns file ID for chunk insertion

**`ingest_pdf_folder(folder)`** (app/ingest.py:47-97)
- Recursively scans folder for PDFs
- Extracts text page-by-page using PyMuPDF (fitz)
- Inserts chunks into both `chunks` and `chunks_fts` tables
- Returns statistics: ingested, skipped, errors

### search.py - Search Engine

**Purpose:** Full-text search with BM25 ranking and query optimization.

**Strategy:**
1. First attempts strict AND search (all terms must match)
2. Falls back to OR search if no results (any term matches)
3. Filters out common stopwords for better relevance

**Key Functions:**

**`_tokens(q)`** (app/search.py:13-15)
- Normalizes query and extracts word tokens
- Case-insensitive tokenization

**`_fts_query(q, mode)`** (app/search.py:17-24)
- Removes stopwords from query
- Constructs FTS5 query with AND/OR logic

**`search(query, k=5)`** (app/search.py:42-65)
- Executes two-tier search (AND then OR fallback)
- Uses BM25 scoring for relevance ranking
- Joins chunks with file metadata
- Returns top-k results

### model.py - LLM Integration

**Purpose:** Ollama client for question answering with strict JSON responses.

**Configuration:**
- Default endpoint: `http://127.0.0.1:11434`
- Default model: `qwen2.5:0.5b-instruct`

**`answer(question, context)`** (app/model.py:8-37)
- Constructs strict prompt requiring JSON output
- Enforces exact quote extraction from context
- Returns structured answer with quote, answer text, and citation
- 120-second timeout for generation
- Temperature: 0.0 (deterministic)

**Response Format:**
```json
{
  "quote": "exact text from context",
  "answer": "short answer based on quote",
  "citation": "sample.pdf p.1"
}
```

### main.py - API Application

**Purpose:** FastAPI application exposing REST endpoints.

**Startup:**
- Initializes database schema on application startup
- Creates `ModelClient` instance for LLM calls
- Expects PDFs in `data/pdfs/` directory

**Endpoints:**
- `/health`: Simple health check
- `/ingest`: Triggers PDF ingestion process
- `/search`: Executes search with optional LLM answer

**SearchRequest Model:**
- `query` (str): Search terms
- `k` (int, default=5): Result count
- `use_model` (bool, default=false): Enable LLM answers

The search endpoint constructs context from top 3 results and optionally sends to LLM for answer generation.

## Database Schema

### files
| Column | Type | Description |
|--------|------|-------------|
| id | INTEGER PRIMARY KEY | Auto-increment ID |
| path | TEXT UNIQUE | File path |
| sha256 | TEXT | File hash for change detection |
| modified_ns | INTEGER | Modification timestamp (nanoseconds) |
| size_bytes | INTEGER | File size |

### chunks
| Column | Type | Description |
|--------|------|-------------|
| id | INTEGER PRIMARY KEY | Auto-increment ID |
| file_id | INTEGER | Foreign key to files |
| page_num | INTEGER | Page number (1-indexed) |
| chunk_index | INTEGER | Chunk number within page |
| text | TEXT | Chunk content |

### chunks_fts (FTS5 Virtual Table)
- Full-text search index on `text` column
- BM25 ranking algorithm
- Content linked to `chunks.id`

## Performance Considerations

### Incremental Updates
The system tracks file hashes and metadata to avoid reprocessing unchanged files. Only modified PDFs are re-indexed.

### Chunking Strategy
- **Chunk size**: 900 characters (optimal for context windows)
- **Overlap**: 150 characters (preserves context across boundaries)
- **Normalization**: Unicode NFKC fixes ligatures and special characters

### Search Optimization
- Two-tier search (AND/OR) balances precision and recall
- Stopword filtering improves relevance
- BM25 ranking weights term frequency and document length
- Index on `file_id` for efficient joins

### Database
- WAL mode enables concurrent reads during writes
- FTS5 provides fast full-text search with minimal overhead
- Content table separation reduces index size

## Directory Structure

```
pdf_demo/
├── app/
│   ├── main.py       # FastAPI application
│   ├── db.py         # Database layer
│   ├── ingest.py     # PDF processing
│   ├── search.py     # Search engine
│   ├── model.py      # LLM client
│   └── config.py     # Configuration
├── data/
│   └── pdfs/         # PDF files to ingest
├── storage/
│   └── index.db      # SQLite database (created on first run)
├── req.txt           # Python dependencies
└── README.md         # This file
```

## Customization

### Changing Chunk Size
Edit `app/ingest.py:17` to adjust `chunk_size` and `overlap` parameters.

### Using Different LLM
Modify `app/model.py:4` to change the Ollama endpoint or model name.

### PDF Directory
Change `PDF_FOLDER` in `app/main.py:11` to point to different directory.

## Troubleshooting

### No results from search
- Ensure PDFs have been ingested: `POST /ingest`
- Check database exists: `storage/index.db`
- Verify PDFs contain extractable text (not scanned images)

### LLM timeout
- Increase timeout in `app/model.py:33`
- Use faster model (e.g., qwen2.5:0.5b-instruct)
- Check Ollama is running: `ollama list`

### Memory issues
- Process PDFs in smaller batches
- Reduce chunk size to decrease database size
- Consider implementing pagination for large result sets

## Future Enhancements

Potential improvements:
- Vector embeddings for semantic search
- Multi-modal support (images, tables)
- Batch API for multiple queries
- User authentication and multi-tenancy
- Real-time ingestion via file watchers
- Query highlighting in results
- PDF preview with highlighted matches
