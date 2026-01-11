# PDF Demo Indexer

A FastAPI-based PDF indexing and semantic search system with hybrid search (BM25 + vector embeddings), reranking, conversation history, and optional LLM-powered question answering.

## Overview

This application provides a complete solution for ingesting PDF documents, creating a searchable index, and retrieving relevant information through full-text search. It supports optional integration with Ollama for LLM-based question answering using retrieved context.

### Key Features

- **🎨 Chat-Like Web Interface**: Beautiful, modern UI for conversational interaction with your PDFs
- **🔍 Hybrid Search**: Combines BM25 keyword matching with vector embeddings for semantic understanding
- **⚡ Intelligent Reranking**: Cross-encoder model reranks results for maximum relevance
- **💬 Conversation History**: Multi-turn conversations with context awareness
- **PDF Ingestion**: Automatically extracts and indexes text from PDF documents with parallel processing
- **Vector Embeddings**: Semantic search using sentence-transformers (all-MiniLM-L6-v2)
- **Smart Chunking**: Overlapping text chunks (1500 chars, 250 overlap) for better context preservation
- **Incremental Updates**: Only processes changed files (SHA256 + timestamp tracking)
- **LLM Integration**: Optional Ollama integration for question answering with citations
- **REST API**: Simple FastAPI endpoints for all operations
- **Error Handling**: Comprehensive error handling with helpful error messages
- **Database Management**: Efficient connection pooling with context managers

## Architecture

### Components

1. **main.py** - FastAPI application and API endpoints
2. **db.py** - SQLite database connection and schema management
3. **ingest.py** - PDF processing, text extraction, and embedding generation
4. **search.py** - Hybrid search (BM25 + vector similarity) with reranking
5. **embeddings.py** - Vector embeddings and cross-encoder reranking
6. **model.py** - Ollama LLM client for question answering with conversation history
7. **config.py** - Configuration (currently empty, placeholder)

### Data Flow

```
PDF Files (data/pdfs/)
    ↓
Ingest (PyMuPDF extraction + Parallel Processing)
    ↓
Chunking (1500 chars, 250 overlap)
    ↓
Vector Embeddings (all-MiniLM-L6-v2, 384 dim)
    ↓
SQLite Database (storage/index.db)
    ├── FTS5 Index (BM25 ranking)
    └── Vector Embeddings (BLOB storage)
    ↓
User Query
    ↓
Hybrid Search (BM25 + Vector Similarity)
    ↓
Reranking (Cross-Encoder)
    ↓
Top Results (context-aware with conversation history)
    ↓
[Optional] LLM Answer Generation (top 5 results)
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
- `sentence-transformers` - Vector embeddings and reranking models
- `numpy` - Vector operations
- `torch` - PyTorch backend for transformer models

**Note:** First run will download models:
- `all-MiniLM-L6-v2` (~90MB) - Embedding model
- `cross-encoder/ms-marco-MiniLM-L-6-v2` (~90MB) - Reranking model

### Optional: Ollama Setup

For LLM-powered answers, install [Ollama](https://ollama.ai/) and pull a model:

```bash
ollama pull qwen2.5:0.5b-instruct
```

## Usage

### Quick Start (Recommended)

1. **Install dependencies:**
   ```bash
   pip install -r req.txt
   ```

2. **Start the server:**
   ```bash
   uvicorn app.main:app --reload
   ```

3. **Open the Chat UI:**

   Navigate to `http://localhost:8000` in your browser

4. **Index your PDFs:**
   - Place PDF files in the `data/pdfs/` folder
   - Click the "📥 Index PDFs" button in the UI

5. **Start asking questions:**
   - Type your question in the chat interface
   - Get instant answers with citations from your documents!

### Chat UI Features

The web interface at `http://localhost:8000` provides:

- **💬 Conversational Interface**: Chat naturally with your documents
- **🤖 AI-Powered Answers**: Automatic question answering with source citations
- **📝 Quote Highlighting**: See exact quotes from your PDFs
- **⚡ Real-Time Feedback**: Loading indicators and status updates
- **🎨 Beautiful Design**: Modern, responsive gradient UI
- **📥 One-Click Indexing**: Index PDFs directly from the browser

### Alternative: Using the API Directly

The REST API is also available at `http://localhost:8000`

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

## Recent Improvements

This version includes several major enhancements for production readiness:

### 🚀 Advanced Search & AI Features (Latest)

**Hybrid Search with Vector Embeddings** (app/search.py:44-164, app/embeddings.py)
- Combines traditional BM25 keyword search with semantic vector similarity
- Uses `all-MiniLM-L6-v2` model (384-dimensional embeddings) for semantic understanding
- Finds conceptually related content even without exact keyword matches
- Weighted combination: 50% BM25 + 50% vector similarity for balanced results
- Example: "airplane safety" now matches "aircraft operational procedures"

**Intelligent Reranking** (app/embeddings.py:49-73, app/search.py:157-160)
- Cross-encoder model (`ms-marco-MiniLM-L-6-v2`) reranks candidates
- Computes query-document relevance scores for final ranking
- Processes top candidates (k×3) for comprehensive reranking
- Significantly improves answer quality by surfacing most relevant chunks first

**Conversation History & Context Awareness** (app/main.py:25-33, app/model.py:12-40, static/index.html:379-465)
- Maintains last 10 messages for multi-turn conversations
- LLM uses conversation history to resolve references ("it", "they", "that")
- Frontend tracks conversation state and sends with each query
- Backend includes last 6 messages in LLM prompt for context
- Enables follow-up questions: "What is X?" → "Tell me more about it"

**Impact:**
- **Semantic understanding**: Find results by meaning, not just keywords
- **Higher precision**: Reranking ensures most relevant results appear first
- **Natural conversations**: Ask follow-up questions without repeating context
- **Better UX**: Chat feels more like talking to an expert, not a search engine

### 🎯 Enhanced Retrieval Quality

**Optimized Chunk Sizes** (app/ingest.py:21)
- Increased chunk size from 900 to 1500 characters for richer context
- Increased overlap from 150 to 250 characters for better boundary preservation
- Reduces fragmentation of important information across chunks
- Improves LLM's ability to understand complete context

**More Context to LLM** (app/main.py:67)
- Increased from top 3 to top 5 search results sent to LLM
- Provides more comprehensive information for answer generation
- Better coverage of relevant content across multiple sources

**Better Search Defaults** (static/index.html:484)
- Increased default search results from k=5 to k=10
- More candidate results for ranking and selection
- Improved recall while maintaining precision

**Impact:**
- 67% larger chunks (900→1500) provide more complete paragraphs and ideas
- 67% more overlap (150→250) ensures no information lost at boundaries
- 67% more context to LLM (3→5 results) for better answer quality
- 100% more search results (5→10) for improved candidate selection

### ✨ New Features

**Chat-Like Web Interface** (`static/index.html`)
- Modern, responsive chat UI with gradient design
- Real-time PDF indexing from the browser
- AI-powered answers with citations and quotes
- Smooth animations and loading states
- Mobile-friendly responsive design

### 🛡️ Error Handling & Reliability

**API Error Handling** (app/main.py:46-79)
- Comprehensive try/catch blocks on all endpoints
- Input validation (empty queries, k limits 1-100)
- Proper HTTP status codes (400 for bad requests, 500 for errors)
- Detailed error logging for debugging

**Model Error Handling** (app/model.py:29-67)
- Network failure recovery with helpful error messages
- JSON parsing with fallback to raw response
- Connection timeout handling
- Graceful degradation when LLM is unavailable

**Ingestion Error Logging** (app/ingest.py:99-101)
- Detailed error messages showing which file failed
- Continues processing despite individual file errors
- Error statistics in response

### 🔧 Technical Improvements

**Multiprocessing for PDF Ingestion** (app/ingest.py:54-141)
- Parallel processing of multiple PDFs using Python multiprocessing
- Automatically utilizes all CPU cores for faster indexing
- 2-4x performance improvement on multi-core systems
- Each worker process has its own database connection

**Database Connection Management** (app/db.py:42-50)
- Context manager for automatic connection cleanup
- Prevents connection leaks
- More efficient resource usage
- Used in search.py:43 with `with get_db()`

**Bug Fixes**
- Fixed FTS virtual table deletion order bug (ingest.py:39-43)
  - Now deletes from FTS before chunks (previously would fail)
- Proper cleanup of old chunks when re-indexing files

### 📊 Enhanced User Experience

- Status indicators showing system health
- Progress feedback during operations
- Welcome screen with quick tips
- Clear error messages for common issues
- Source citations in answers

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
- `get_db()`: Context manager for automatic connection cleanup (app/db.py:42-50)

**Location:** `app/db.py`

### ingest.py - PDF Processing

**Purpose:** Extracts text from PDFs and stores chunks in database.

**Key Functions:**

**`sha256_file(path)`** (app/ingest.py:10-15)
- Computes SHA256 hash for file change detection
- Reads file in 1MB chunks for memory efficiency

**`chunk_text(text, chunk_size=1500, overlap=250)`** (app/ingest.py:21-31)
- Normalizes Unicode (fixes ligatures like ﬁ → fi)
- Creates overlapping chunks for better context preservation
- Default: 1500 characters per chunk with 250 character overlap (~17% overlap)
- Larger chunks preserve complete paragraphs and ideas for better LLM comprehension

**`upsert_file(con, path, sha, modified_ns, size_bytes)`** (app/ingest.py:30-45)
- Smart file update: only re-processes if SHA256 or metadata changed
- Deletes old chunks before re-indexing
- Returns file ID for chunk insertion

**`process_single_pdf(path)`** (app/ingest.py:54-95)
- Processes a single PDF file (used by worker processes)
- Each worker creates its own database connection
- Returns status dict with result

**`ingest_pdf_folder(folder, use_multiprocessing=True)`** (app/ingest.py:98-141)
- Recursively scans folder for PDFs
- Uses multiprocessing.Pool to process PDFs in parallel
- Automatically scales to available CPU cores
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
- `/`: Serves the chat UI interface
- `/health`: Simple health check
- `/ingest`: Triggers PDF ingestion process with error handling
- `/search`: Executes search with optional LLM answer and input validation
- `/static/*`: Static files (CSS, JS, images)

**SearchRequest Model:**
- `query` (str): Search terms
- `k` (int, default=5): Result count
- `use_model` (bool, default=false): Enable LLM answers
- `conversation_history` (list, default=[]): Previous messages for context-aware conversations
  - Each message: `{"role": "user"|"assistant", "content": "message text"}`

The search endpoint uses hybrid search (BM25 + vectors) with reranking, constructs context from top 5 results, and optionally sends to LLM with conversation history for context-aware answer generation.

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
| embedding | BLOB | Vector embedding (384-dim, serialized numpy array) |

### chunks_fts (FTS5 Virtual Table)
- Full-text search index on `text` column
- BM25 ranking algorithm
- Content linked to `chunks.id`

## Performance Considerations

### Multiprocessing for Fast Ingestion
PDF ingestion uses multiprocessing to process multiple PDFs in parallel:
- Automatically uses all available CPU cores
- Each PDF is processed independently in its own worker process
- Typical speedup: 2-4x faster on multi-core systems
- Falls back to sequential processing for single files or debugging
- **Note**: Embedding generation happens per-chunk during ingestion (~10-20ms per chunk on CPU)

### Hybrid Search Performance
- **BM25 Search**: Very fast (< 10ms) using SQLite FTS5 index
- **Vector Search**: Computes similarity against all stored embeddings (~50-100ms for 1000 chunks)
- **Reranking**: Cross-encoder processes top candidates (~100-200ms for 30 candidates)
- **Total**: Typically 200-400ms end-to-end for hybrid search with reranking

### Incremental Updates
The system tracks file hashes and metadata to avoid reprocessing unchanged files. Only modified PDFs are re-indexed.

### Chunking Strategy
- **Chunk size**: 1500 characters (optimal for richer context and complete ideas)
- **Overlap**: 250 characters (preserves context across boundaries, ~17% overlap)
- **Normalization**: Unicode NFKC fixes ligatures and special characters
- **Rationale**: Larger chunks reduce fragmentation and improve LLM comprehension

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
│   ├── main.py       # FastAPI application & API endpoints
│   ├── db.py         # Database layer with connection management
│   ├── ingest.py     # PDF processing & text extraction
│   ├── search.py     # Full-text search engine
│   ├── model.py      # LLM client for Q&A
│   └── config.py     # Configuration (placeholder)
├── static/
│   └── index.html    # Chat UI web interface
├── data/
│   └── pdfs/         # PDF files to ingest (place your PDFs here)
├── storage/
│   └── index.db      # SQLite database (auto-created on first run)
├── req.txt           # Python dependencies
└── README.md         # This file
```

## Customization

### Changing Chunk Size
Edit `app/ingest.py:21` to adjust `chunk_size` and `overlap` parameters.
- Current defaults: 1500 characters with 250 character overlap
- Increase for more context per chunk (better for longer documents)
- Decrease for faster search and smaller database (better for fragmented info)

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
