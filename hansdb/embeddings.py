"""
Embedding model management for HANS
"""

import numpy as np
import logging
from sentence_transformers import SentenceTransformer
from typing import List, Optional
import os

logger = logging.getLogger(__name__)

# Global embedding model instance
_embedding_model: Optional[SentenceTransformer] = None

def get_embedding_model(model_name: str = "BAAI/bge-base-en-v1.5") -> SentenceTransformer:
    """
    Get or initialize the embedding model (singleton pattern) with proxy support
    
    Args:
        model_name: Name of the sentence-transformer model
    
    Returns:
        Initialized SentenceTransformer model
    """
    global _embedding_model
    
    if _embedding_model is None:
        logger.info(f"Loading embedding model: {model_name}")
        
        # Configure proxy environment for model downloads
        # sentence-transformers uses requests/urllib internally which respects these env vars
        original_proxies = {}
        if os.getenv('HTTP_PROXY'):
            original_proxies['http_proxy'] = os.environ.get('http_proxy')
            os.environ['http_proxy'] = os.getenv('HTTP_PROXY')
        if os.getenv('HTTPS_PROXY'):
            original_proxies['https_proxy'] = os.environ.get('https_proxy')
            os.environ['https_proxy'] = os.getenv('HTTPS_PROXY')
        
        try:
            _embedding_model = SentenceTransformer(model_name)
            logger.info(f"Embedding model loaded. Dimension: {_embedding_model.get_sentence_embedding_dimension()}")
        finally:
            # Restore original proxy settings
            for key, value in original_proxies.items():
                if value is None:
                    os.environ.pop(key, None)
                else:
                    os.environ[key] = value
    
    return _embedding_model

def embed_and_normalize(texts: List[str], model_name: str = "BAAI/bge-base-en-v1.5") -> List[np.ndarray]:
    """
    Generate L2-normalized embeddings for a list of texts
    
    Args:
        texts: List of text strings to embed
        model_name: Name of the embedding model to use
    
    Returns:
        List of L2-normalized embedding vectors
    """
    if not texts:
        return []
    
    model = get_embedding_model(model_name)
    
    # Generate embeddings with normalization
    embeddings = model.encode(texts, normalize_embeddings=True, show_progress_bar=False)
    
    # Ensure embeddings are numpy arrays
    if isinstance(embeddings, np.ndarray):
        if embeddings.ndim == 1:
            # Single embedding
            return [embeddings]
        else:
            # Multiple embeddings
            return [emb for emb in embeddings]
    
    return embeddings

def embed_single_text(text: str, model_name: str = "BAAI/bge-base-en-v1.5", is_query: bool = True) -> np.ndarray:
    """
    Generate L2-normalized embedding for a single text

    For E5 models (intfloat/multilingual-e5-*), automatically adds appropriate prefix:
    - Queries: "query: " prefix
    - Documents/passages: "passage: " prefix

    Args:
        text: Text string to embed
        model_name: Name of the embedding model to use
        is_query: True if this is a query, False if it's a document/passage

    Returns:
        L2-normalized embedding vector
    """
    # Add E5-specific prefix if using an E5 model
    if "e5" in model_name.lower():
        prefix = "query: " if is_query else "passage: "
        text = prefix + text

    embeddings = embed_and_normalize([text], model_name)
    return embeddings[0]

def embed_query(query_text: str, model_name: str = "BAAI/bge-base-en-v1.5") -> np.ndarray:
    """
    Generate embedding for a query text (with appropriate prefix for E5 models)

    Args:
        query_text: Query string to embed
        model_name: Name of the embedding model to use

    Returns:
        L2-normalized embedding vector
    """
    return embed_single_text(query_text, model_name, is_query=True)

def embed_passages(passage_texts: List[str], model_name: str = "BAAI/bge-base-en-v1.5") -> List[np.ndarray]:
    """
    Generate embeddings for document passages (with appropriate prefix for E5 models)

    Args:
        passage_texts: List of passage strings to embed
        model_name: Name of the embedding model to use

    Returns:
        List of L2-normalized embedding vectors
    """
    # Add E5-specific prefix if using an E5 model
    if "e5" in model_name.lower():
        passage_texts = ["passage: " + text for text in passage_texts]

    return embed_and_normalize(passage_texts, model_name)

def validate_embedding_dimension(embedding: np.ndarray, expected_dim: int = 768) -> bool:
    """
    Validate that embedding has the expected dimension
    
    Args:
        embedding: Embedding vector to validate
        expected_dim: Expected embedding dimension
    
    Returns:
        True if dimension matches, False otherwise
    """
    return len(embedding) == expected_dim

def normalize_embedding(embedding: np.ndarray) -> np.ndarray:
    """
    L2-normalize an embedding vector
    
    Args:
        embedding: Raw embedding vector
    
    Returns:
        L2-normalized embedding vector
    """
    norm = np.linalg.norm(embedding)
    if norm == 0:
        return embedding
    return embedding / norm