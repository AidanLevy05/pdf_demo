import hashlib
import unicodedata
import logging
from pathlib import Path
import fitz  # PyMuPDF

from .db import connect

logging.basicConfig(level=logging.INFO)

ALLOWED_EXT = {".pdf"}

def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()

def chunk_text(text: str, chunk_size=900, overlap=150):
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

def ingest_pdf_folder(folder: Path) -> dict:
    folder = folder.resolve()
    if not folder.exists():
        return {"ingested": 0, "skipped": 0, "errors": 0}

    ingested = skipped = errors = 0
    con = connect()

    for path in folder.rglob("*"):
        if path.suffix.lower() not in ALLOWED_EXT:
            continue
        try:
            stat = path.stat()
            sha = sha256_file(path)
            with con:
                file_id = upsert_file(con, path, sha, stat.st_mtime_ns, stat.st_size)

                # if unchanged, upsert_file returned existing id but didn't clear chunks
                # so detect if chunks already exist
                existing = con.execute("SELECT 1 FROM chunks WHERE file_id=? LIMIT 1", (file_id,)).fetchone()
                if existing:
                    skipped += 1
                    continue

                doc = fitz.open(path)
                chunk_count = 0
                for page_index in range(len(doc)):
                    page = doc[page_index]
                    text = page.get_text("text")
                    chunks = chunk_text(text)
                    for ci, ch in enumerate(chunks):
                        cur = con.execute(
                            "INSERT INTO chunks(file_id, page_num, chunk_index, text) VALUES(?,?,?,?)",
                            (file_id, page_index + 1, ci, ch),
                        )
                        chunk_id = cur.lastrowid
                        con.execute("INSERT INTO chunks_fts(rowid, text) VALUES(?,?)", (chunk_id, ch))
                        chunk_count += 1
                doc.close()

                if chunk_count > 0:
                    ingested += 1
                else:
                    # No text extracted, still counts as ingested but it won't be searchable
                    ingested += 1

        except Exception as e:
            logging.error(f"Error processing {path}: {e}")
            errors += 1

    con.close()
    return {"ingested": ingested, "skipped": skipped, "errors": errors}
