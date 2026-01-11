import re
import unicodedata
from .db import get_db

STOPWORDS = {
    "a","an","and","are","as","at","be","but","by","can","could","did","do","does",
    "for","from","had","has","have","how","i","if","in","into","is","it","its",
    "me","my","of","on","or","our","s","so","that","the","their","then","there",
    "these","this","those","to","was","were","what","when","where","which","who",
    "why","will","with","you","your"
}

def _tokens(q: str):
    q = unicodedata.normalize("NFKC", q)
    return [t.lower() for t in re.findall(r"\w+", q)]

def _fts_query(q: str, mode: str):
    toks = [t for t in _tokens(q) if t not in STOPWORDS]
    if not toks:
        toks = _tokens(q)  # fallback: even stopwords if that's all we have
    if not toks:
        return ""
    joiner = " AND " if mode == "AND" else " OR "
    return joiner.join(toks)

def _run(con, fts_query: str, k: int):
    return con.execute("""
        SELECT
          chunks.id as chunk_id,
          chunks.text as text,
          chunks.page_num as page_num,
          files.path as path,
          bm25(chunks_fts) as score
        FROM chunks_fts
        JOIN chunks ON chunks_fts.rowid = chunks.id
        JOIN files ON chunks.file_id = files.id
        WHERE chunks_fts MATCH ?
        ORDER BY score
        LIMIT ?;
    """, (fts_query, k)).fetchall()

def search(query: str, k: int = 5):
    with get_db() as con:
        # Try strict AND first (more precise)
        q_and = _fts_query(query, "AND")
        rows = _run(con, q_and, k) if q_and else []

        # If nothing, fallback to OR (broader)
        if not rows:
            q_or = _fts_query(query, "OR")
            rows = _run(con, q_or, k) if q_or else []

        return [
            {
                "path": r["path"],
                "page_num": r["page_num"],
                "chunk_id": r["chunk_id"],
                "score": float(r["score"]),
                "text": r["text"],
            }
            for r in rows
        ]
