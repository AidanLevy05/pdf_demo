import numpy as np
from sentence_transformers import SentenceTransformer, CrossEncoder
import logging

logging.basicConfig(level=logging.INFO)

# Global model instances (lazy loaded)
_embedding_model = None
_reranker_model = None

def get_embedding_model():
    """Get or initialize the embedding model (lazy loading)"""
    global _embedding_model
    if _embedding_model is None:
        logging.info("Loading embedding model: all-MiniLM-L6-v2")
        _embedding_model = SentenceTransformer('all-MiniLM-L6-v2')
    return _embedding_model

def get_reranker_model():
    """Get or initialize the reranker model (lazy loading)"""
    global _reranker_model
    if _reranker_model is None:
        logging.info("Loading reranker model: cross-encoder/ms-marco-MiniLM-L-6-v2")
        _reranker_model = CrossEncoder('cross-encoder/ms-marco-MiniLM-L-6-v2')
    return _reranker_model

def create_embedding(text: str) -> np.ndarray:
    """Create an embedding vector for the given text"""
    model = get_embedding_model()
    embedding = model.encode(text, convert_to_numpy=True)
    return embedding

def serialize_embedding(embedding: np.ndarray) -> bytes:
    """Convert numpy array to bytes for storage in SQLite"""
    return embedding.tobytes()

def deserialize_embedding(blob: bytes, dim: int = 384) -> np.ndarray:
    """Convert bytes back to numpy array (all-MiniLM-L6-v2 has 384 dimensions)"""
    return np.frombuffer(blob, dtype=np.float32).reshape(dim)

def cosine_similarity(a: np.ndarray, b: np.ndarray) -> float:
    """Compute cosine similarity between two vectors"""
    return float(np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b)))

def rerank_results(query: str, results: list[dict]) -> list[dict]:
    """
    Rerank search results using a cross-encoder model.

    Args:
        query: The search query
        results: List of dicts with 'text' field

    Returns:
        Reranked results with added 'rerank_score' field
    """
    if not results:
        return results

    model = get_reranker_model()

    # Create query-document pairs
    pairs = [[query, r['text']] for r in results]

    # Get reranking scores
    scores = model.predict(pairs)

    # Add scores to results and sort
    for i, result in enumerate(results):
        result['rerank_score'] = float(scores[i])

    # Sort by rerank score (highest first)
    results.sort(key=lambda x: x['rerank_score'], reverse=True)

    return results
