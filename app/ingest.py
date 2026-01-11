import hashlib
import unicodedata
import logging
from pathlib import Path
from multiprocessing import Pool, cpu_count
import fitz  # PyMuPDF

from .db import connect
from .embeddings import create_embedding, serialize_embedding

logging.basicConfig(level=logging.INFO)

ALLOWED_EXT = {".pdf"}

def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()

def chunk_text(text: str, chunk_size=1500, overlap=250):
    text = unicodedata.normalize("NFKC", text)  # fixes ligatures like ﬁ -> fi
    text = " ".join(text.split())
    if not text:
        return []
    chunks = []
    i = 0
    while i < len(text):
        chunks.append(text[i:i+chunk_size])
        i += (chunk_size - overlap)
    return chunks


def upsert_file(con, path: Path, sha: str, modified_ns: int, size_bytes: int) -> int:
    row = con.execute("SELECT id, sha256, modified_ns, size_bytes FROM files WHERE path=?", (str(path),)).fetchone()
    if row and row["sha256"] == sha and row["modified_ns"] == modified_ns and row["size_bytes"] == size_bytes:
        return row["id"]  # unchanged

    if row:
        file_id = row["id"]
        con.execute("UPDATE files SET sha256=?, modified_ns=?, size_bytes=? WHERE id=?",
                    (sha, modified_ns, size_bytes, file_id))
        # Fix: Delete from FTS first, then from chunks
        chunk_ids = [r[0] for r in con.execute("SELECT id FROM chunks WHERE file_id=?", (file_id,)).fetchall()]
        for cid in chunk_ids:
            con.execute("DELETE FROM chunks_fts WHERE rowid=?", (cid,))
        con.execute("DELETE FROM chunks WHERE file_id=?", (file_id,))
        return file_id

    cur = con.execute("INSERT INTO files(path, sha256, modified_ns, size_bytes) VALUES(?,?,?,?)",
                      (str(path), sha, modified_ns, size_bytes))
    return cur.lastrowid

def process_single_pdf(path: Path) -> dict:
    """Process a single PDF file. Returns dict with status."""
    try:
        stat = path.stat()
        sha = sha256_file(path)

        # Each process needs its own database connection
        con = connect()

        try:
            with con:
                file_id = upsert_file(con, path, sha, stat.st_mtime_ns, stat.st_size)

                # Check if chunks already exist (file unchanged)
                existing = con.execute("SELECT 1 FROM chunks WHERE file_id=? LIMIT 1", (file_id,)).fetchone()
                if existing:
                    return {"status": "skipped", "path": str(path)}

                # Extract text from PDF
                doc = fitz.open(path)
                chunk_count = 0
                for page_index in range(len(doc)):
                    page = doc[page_index]
                    text = page.get_text("text")
                    chunks = chunk_text(text)
                    for ci, ch in enumerate(chunks):
                        # Generate embedding for the chunk
                        embedding = create_embedding(ch)
                        embedding_blob = serialize_embedding(embedding)

                        cur = con.execute(
                            "INSERT INTO chunks(file_id, page_num, chunk_index, text, embedding) VALUES(?,?,?,?,?)",
                            (file_id, page_index + 1, ci, ch, embedding_blob),
                        )
                        chunk_id = cur.lastrowid
                        con.execute("INSERT INTO chunks_fts(rowid, text) VALUES(?,?)", (chunk_id, ch))
                        chunk_count += 1
                doc.close()

                return {"status": "ingested", "path": str(path), "chunks": chunk_count}
        finally:
            con.close()

    except Exception as e:
        logging.error(f"Error processing {path}: {e}")
        return {"status": "error", "path": str(path), "error": str(e)}


def ingest_pdf_folder(folder: Path, use_multiprocessing: bool = True) -> dict:
    """
    Ingest all PDFs in a folder using multiprocessing for better performance.

    Args:
        folder: Path to folder containing PDFs
        use_multiprocessing: If True, use multiprocessing to process PDFs in parallel

    Returns:
        Dict with ingested, skipped, and errors counts
    """
    folder = folder.resolve()
    if not folder.exists():
        return {"ingested": 0, "skipped": 0, "errors": 0}

    # Collect all PDF files
    pdf_files = [path for path in folder.rglob("*") if path.suffix.lower() in ALLOWED_EXT]

    if not pdf_files:
        logging.info(f"No PDF files found in {folder}")
        return {"ingested": 0, "skipped": 0, "errors": 0}

    logging.info(f"Found {len(pdf_files)} PDF files to process")

    # Process PDFs
    if use_multiprocessing and len(pdf_files) > 1:
        # Use multiprocessing for parallel processing
        num_workers = min(cpu_count(), len(pdf_files))
        logging.info(f"Using {num_workers} worker processes")

        with Pool(processes=num_workers) as pool:
            results = pool.map(process_single_pdf, pdf_files)
    else:
        # Sequential processing (useful for debugging or single file)
        logging.info("Using sequential processing")
        results = [process_single_pdf(path) for path in pdf_files]

    # Aggregate results
    ingested = sum(1 for r in results if r["status"] == "ingested")
    skipped = sum(1 for r in results if r["status"] == "skipped")
    errors = sum(1 for r in results if r["status"] == "error")

    logging.info(f"Ingestion complete: {ingested} ingested, {skipped} skipped, {errors} errors")
    return {"ingested": ingested, "skipped": skipped, "errors": errors}
