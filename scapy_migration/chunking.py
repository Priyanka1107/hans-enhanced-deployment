"""
Chunking utilities for embedding text.
"""

from typing import List, Dict
import re


def chunk_embedding_text(
    embedding_text: str,
    obj: dict,
    chunk_chars: int = 1000,
    chunk_overlap: int = 200,
    min_chars: int = 250
) -> List[Dict]:
    """
    Chunk embedding text with improved boundary handling and guaranteed minimum chunks.

    CHUNKING GUARANTEE: Ensures objects with substantial content get sufficient chunks:
    - len >= 1800 chars → minimum 4 chunks
    - len >= 3500 chars → minimum 6 chunks
    - len >= 7000 chars → minimum 10 chunks

    Args:
        embedding_text: The full embedding text to chunk
        obj: The source object (for metadata)
        chunk_chars: Target chunk size
        chunk_overlap: Overlap between chunks
        min_chars: Minimum chunk size to keep

    Returns:
        List of chunk dicts with text and metadata
    """
    text_len = len(embedding_text)

    # Determine required minimum chunks based on text length
    required_min_chunks = _get_required_min_chunks(text_len)

    # First attempt with default chunk_chars
    chunks = _do_chunking(embedding_text, obj, chunk_chars, chunk_overlap, min_chars)

    # If we don't meet the minimum, rechunk with adjusted size
    if len(chunks) < required_min_chunks and text_len > min_chars:
        # Calculate new chunk size to achieve required minimum
        # Add 10% buffer to ensure we get enough chunks after validation
        target_chunks = int(required_min_chunks * 1.1)
        adjusted_chunk_chars = max(min_chars + 50, text_len // target_chunks)

        # Keep overlap proportional but within bounds
        adjusted_overlap = min(220, max(150, adjusted_chunk_chars // 5))

        # Rechunk with adjusted parameters
        chunks = _do_chunking(embedding_text, obj, adjusted_chunk_chars, adjusted_overlap, min_chars)

    return chunks


def _get_required_min_chunks(text_len: int) -> int:
    """
    Determine required minimum chunks based on text length.

    Args:
        text_len: Length of embedding text

    Returns:
        Required minimum number of chunks
    """
    if text_len >= 7000:
        return 10
    elif text_len >= 3500:
        return 6
    elif text_len >= 1800:
        return 4
    elif text_len >= 1000:
        return 3  # Force objects with 1000-1799 chars to have at least 3 chunks
    else:
        return 1  # No minimum for short texts


def _do_chunking(
    embedding_text: str,
    obj: dict,
    chunk_chars: int,
    chunk_overlap: int,
    min_chars: int
) -> List[Dict]:
    """
    Perform the actual chunking with given parameters.

    Args:
        embedding_text: Text to chunk
        obj: Object metadata
        chunk_chars: Chunk size
        chunk_overlap: Overlap size
        min_chars: Minimum chunk size

    Returns:
        List of chunk dicts
    """
    if len(embedding_text) <= chunk_chars:
        # Single chunk
        if len(embedding_text) >= min_chars and is_chunk_valid(embedding_text):
            return [create_chunk_dict(embedding_text, obj, 0, 0, len(embedding_text))]
        return []

    chunks = []
    start = 0
    chunk_index = 0

    while start < len(embedding_text):
        end = start + chunk_chars

        if end >= len(embedding_text):
            end = len(embedding_text)
        else:
            # Try to break at sentence or paragraph boundary
            end = _find_best_boundary(embedding_text, end, start + chunk_chars // 2)

        chunk_text = embedding_text[start:end].strip()

        # Validate chunk
        if len(chunk_text) >= min_chars and is_chunk_valid(chunk_text):
            chunk_dict = create_chunk_dict(
                chunk_text, obj, chunk_index, start, end
            )
            chunks.append(chunk_dict)
            chunk_index += 1

        # Move to next chunk with overlap
        if end >= len(embedding_text):
            break

        start = end - chunk_overlap

        # Ensure we make progress
        if start <= chunks[-1]['start_char'] if chunks else False:
            start = end

    return chunks


def _find_best_boundary(text: str, target_pos: int, min_pos: int) -> int:
    """
    Find best boundary for chunking, preferring paragraph then sentence breaks.

    Args:
        text: Full text
        target_pos: Target position for split
        min_pos: Minimum acceptable position

    Returns:
        Best boundary position
    """
    search_start = max(min_pos, target_pos - 250)
    search_text = text[search_start:target_pos + 100]

    # Priority 1: Paragraph breaks (double newline or single newline with indent)
    para_boundaries = []
    for match in re.finditer(r'\n\n+', search_text):
        para_boundaries.append(search_start + match.end())
    for match in re.finditer(r'\n\s+', search_text):
        # Newline followed by spaces (likely new paragraph)
        para_boundaries.append(search_start + match.end())

    if para_boundaries:
        closest_para = min(para_boundaries, key=lambda x: abs(x - target_pos))
        if abs(closest_para - target_pos) < 200:
            return closest_para

    # Priority 2: Sentence boundaries
    sent_boundaries = []
    for match in re.finditer(r'[.!?]\s+', search_text):
        sent_boundaries.append(search_start + match.end())

    if sent_boundaries:
        closest_sent = min(sent_boundaries, key=lambda x: abs(x - target_pos))
        if abs(closest_sent - target_pos) < 200:
            return closest_sent

    # Fallback: use target position
    return target_pos




def is_chunk_valid(chunk_text: str) -> bool:
    """
    Check if chunk has sufficient content quality.

    Drops chunks that are mostly boilerplate.
    """
    if not chunk_text:
        return False

    # Calculate alphanumeric ratio
    alphanumeric = sum(c.isalnum() for c in chunk_text)
    if alphanumeric < len(chunk_text) * 0.4:
        # Less than 40% alphanumeric = likely boilerplate
        return False

    # Check for actual words
    words = chunk_text.split()
    if len(words) < 15:
        # Too few words
        return False

    return True


def create_chunk_dict(
    chunk_text: str,
    obj: dict,
    chunk_index: int,
    start_char: int,
    end_char: int
) -> Dict:
    """
    Create chunk dictionary with metadata.

    Returns:
        Dict with text, object_id, object_type, url, title, chunk_index, offsets
    """
    metadata = obj.get('metadata', {})

    return {
        'text': chunk_text,
        'object_id': metadata.get('object_id', 'unknown'),
        'object_type': metadata.get('object_type', 'unknown'),
        'url': metadata.get('url', ''),
        'title': metadata.get('title', ''),
        'chunk_index': chunk_index,
        'start_char': start_char,
        'end_char': end_char
    }


def merge_adjacent_chunks(chunks: List[Dict]) -> List[Dict]:
    """
    Optional: Merge adjacent chunks from same object_id with contiguous indices.

    Args:
        chunks: List of retrieved chunks (already scored/ranked)

    Returns:
        List of potentially merged chunks
    """
    if not chunks:
        return chunks

    merged = []
    i = 0

    while i < len(chunks):
        current = chunks[i]

        # Look ahead for adjacent chunks
        adjacent = [current]
        j = i + 1

        while j < len(chunks):
            next_chunk = chunks[j]

            # Check if adjacent (same object, next index)
            if (next_chunk['object_id'] == current['object_id'] and
                next_chunk['chunk_index'] == adjacent[-1]['chunk_index'] + 1):
                adjacent.append(next_chunk)
                j += 1
            else:
                break

        # Merge if we found adjacent chunks
        if len(adjacent) > 1:
            merged_text = ' '.join(c['text'] for c in adjacent)
            merged_chunk = adjacent[0].copy()
            merged_chunk['text'] = merged_text
            merged_chunk['end_char'] = adjacent[-1]['end_char']
            merged_chunk['merged_from'] = len(adjacent)
            merged.append(merged_chunk)
        else:
            merged.append(current)

        i = j if len(adjacent) > 1 else i + 1

    return merged
