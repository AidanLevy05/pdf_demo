import re
import unicodedata
import numpy as np
from .db import get_db
from .embeddings import create_embedding, deserialize_embedding, cosine_similarity, rerank_results

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

def _vector_search(con, query_embedding: np.ndarray, k: int = 20):
    """
    Perform vector similarity search.
    Returns top k chunks based on cosine similarity.
    """
    # Get all chunks with embeddings
    rows = con.execute("""
        SELECT
          chunks.id as chunk_id,
          chunks.text as text,
          chunks.page_num as page_num,
          chunks.embedding as embedding,
          files.path as path
        FROM chunks
        JOIN files ON chunks.file_id = files.id
        WHERE chunks.embedding IS NOT NULL
    """).fetchall()

    # Compute similarities
    results = []
    for r in rows:
        chunk_embedding = deserialize_embedding(r["embedding"])
        similarity = cosine_similarity(query_embedding, chunk_embedding)
        results.append({
            "chunk_id": r["chunk_id"],
            "text": r["text"],
            "page_num": r["page_num"],
            "path": r["path"],
            "vector_score": similarity,
        })

    # Sort by similarity (highest first) and return top k
    results.sort(key=lambda x: x["vector_score"], reverse=True)
    return results[:k]

def search(query: str, k: int = 5, use_hybrid: bool = True, use_reranking: bool = True):
    """
    Hybrid search combining BM25 and vector similarity with reranking.

    Args:
        query: Search query
        k: Number of final results to return
        use_hybrid: If True, combine BM25 and vector search
        use_reranking: If True, rerank results with cross-encoder

    Returns:
        List of search results with scores
    """
    with get_db() as con:
        results_map = {}  # chunk_id -> result dict

        # 1. BM25 Search (existing FTS)
        q_and = _fts_query(query, "AND")
        bm25_rows = _run(con, q_and, k * 2) if q_and else []

        # Fallback to OR if AND returns nothing
        if not bm25_rows:
            q_or = _fts_query(query, "OR")
            bm25_rows = _run(con, q_or, k * 2) if q_or else []

        for r in bm25_rows:
            results_map[r["chunk_id"]] = {
                "path": r["path"],
                "page_num": r["page_num"],
                "chunk_id": r["chunk_id"],
                "bm25_score": float(r["score"]),
                "vector_score": 0.0,
                "text": r["text"],
            }

        # 2. Vector Search (if hybrid mode enabled)
        if use_hybrid:
            query_embedding = create_embedding(query)
            vector_results = _vector_search(con, query_embedding, k * 2)

            for vr in vector_results:
                chunk_id = vr["chunk_id"]
                if chunk_id in results_map:
                    # Already found by BM25, add vector score
                    results_map[chunk_id]["vector_score"] = vr["vector_score"]
                else:
                    # New result from vector search
                    results_map[chunk_id] = {
                        "path": vr["path"],
                        "page_num": vr["page_num"],
                        "chunk_id": chunk_id,
                        "bm25_score": 0.0,
                        "vector_score": vr["vector_score"],
                        "text": vr["text"],
                    }

        # Convert to list
        results = list(results_map.values())

        # 3. Compute combined score (hybrid score)
        # Normalize scores to 0-1 range for fair combination
        if results:
            max_bm25 = max((r["bm25_score"] for r in results), default=1.0)
            max_vector = max((r["vector_score"] for r in results), default=1.0)

            for r in results:
                norm_bm25 = r["bm25_score"] / max_bm25 if max_bm25 > 0 else 0
                norm_vector = r["vector_score"] / max_vector if max_vector > 0 else 0
                # Weighted combination: 50% BM25, 50% vector
                r["hybrid_score"] = 0.5 * norm_bm25 + 0.5 * norm_vector

            # Sort by hybrid score
            results.sort(key=lambda x: x["hybrid_score"], reverse=True)

            # Take top candidates for reranking
            candidates = results[:k * 3]  # Get more candidates for reranking

            # 4. Rerank with cross-encoder (if enabled)
            if use_reranking and candidates:
                candidates = rerank_results(query, candidates)
                # Return top k after reranking
                return candidates[:k]
            else:
                return candidates[:k]

        return results[:k]
