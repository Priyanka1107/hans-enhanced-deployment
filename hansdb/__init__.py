"""
HANS Database Package

Database-backed RAG system for HTW Berlin Student Services Assistant.
Replaces FAISS/pickle/Excel file storage with PostgreSQL + pgvector.
"""

__version__ = "1.0.0"

from .conn import get_db_connection, ensure_schema
from .embeddings import embed_and_normalize, get_embedding_model
from .retrieval import retrieve_top_k, retrieve_multi_query

__all__ = [
    "get_db_connection",
    "ensure_schema",
    "embed_and_normalize",
    "get_embedding_model",
    "retrieve_top_k",
    "retrieve_multi_query"
]