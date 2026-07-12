# Integration Roadmap - Hans V2 → Production API

## Current Status: What's Done ✅

### Backend (Complete)
- ✅ Schema v2 created (`hans_v2.documents`, `hans_v2.chunks`)
- ✅ 170 documents migrated with full metadata
- ✅ 930 chunks with BGE embeddings (768-dim)
- ✅ Retrieval code updated to query hans_v2 tables
- ✅ BGE embeddings (no E5 prefixes)
- ✅ Reranking with cross-encoder working
- ✅ End-to-end tests passing

### What Works Now
```python
from hansdb.conn import get_db_connection, load_config
from hansdb.retrieval import retrieve_top_k

conn = get_db_connection(load_config())
results = retrieve_top_k(conn, "semester fee", top_k=10)
# Returns: List of dicts with title, url, content, object_id, object_type, score
```

---

## What's Left: API Integration

### Step 1: Check Your Current API

Let me look for your API file:
```bash
# Find the API file
find . -name "*api*.py" -o -name "*server*.py" | grep -v __pycache__
```

Typical locations:
- `htw_assistant_api.py`
- `api/main.py`
- `server.py`
- `app.py`

### Step 2: Update API Endpoint

Your API probably has an endpoint like:
```python
@app.post("/ask")
def ask_question(query: str, max_sources: int = 10):
    # OLD CODE (using old schema)
    conn = get_db_connection()
    results = retrieve_top_k(conn, query, top_k=max_sources)
    # Generate answer with LLM
    # Return response
```

**What needs to change:**
1. **Nothing!** If your API already uses `retrieve_top_k()`, it now automatically uses hans_v2
2. The function signature is the same
3. Results include new fields (`object_id`, `object_type`) but are backwards compatible

### Step 3: Optional Improvements

You can now enhance your API responses:

```python
@app.post("/ask")
def ask_question(query: str, max_sources: int = 10):
    conn = get_db_connection()

    # Retrieve with reranking (recommended)
    results = retrieve_top_k(
        conn,
        query,
        top_k=max_sources,
        model_name="BAAI/bge-base-en-v1.5",  # BGE model
        reranker_config={
            'enabled': True,
            'model_name': 'cross-encoder/ms-marco-MiniLM-L-6-v2',
            'max_rerank': 30
        },
        top_k_db=30  # Fetch 30, rerank to top 10
    )

    # Build context for LLM
    context = "\n\n".join([
        f"Source: {r['title']} ({r['object_type']})\n"
        f"URL: {r['url']}\n"
        f"Content: {r['content']}"
        for r in results
    ])

    # Generate answer with LLM
    answer = generate_answer(query, context)

    # Return enhanced response
    return {
        "answer": answer,
        "sources": [
            {
                "title": r["title"],
                "url": r["url"],
                "object_type": r["object_type"],  # NEW
                "object_id": r["object_id"],      # NEW
                "score": r["score"],
                "rerank_score": r.get("rerank_score")  # NEW
            }
            for r in results
        ]
    }
```

---

## Integration Steps (Detailed)

### Option A: Zero-Change Integration (Easiest)

If your API already uses `hansdb.retrieval.retrieve_top_k()`:

1. **No code changes needed!**
2. Just restart your API server
3. It will automatically use hans_v2 schema

```bash
# Restart API
cd /path/to/your/api
python3 htw_assistant_api.py
```

**Test:**
```bash
curl -X POST http://localhost:8000/ask \
  -H "Content-Type: application/json" \
  -d '{"q": "What is the semester fee?", "max_sources": 10}'
```

### Option B: Enhanced Integration (Recommended)

Add new features to leverage hans_v2 improvements:

1. **Enable reranking** for better precision
2. **Use object_type** for filtering or grouping
3. **Show metadata** in API response

**Example API updates:**

```python
# api/main.py or htw_assistant_api.py

from fastapi import FastAPI
from pydantic import BaseModel
from hansdb.conn import get_db_connection, load_config
from hansdb.retrieval import retrieve_top_k

app = FastAPI()
config = load_config()

class Question(BaseModel):
    q: str
    max_sources: int = 10
    use_reranking: bool = True
    filter_object_type: str = None  # NEW: optional filter

@app.post("/ask")
def ask_question(question: Question):
    conn = get_db_connection(config)

    # Retrieve with optional reranking
    reranker_config = None
    if question.use_reranking:
        reranker_config = {
            'enabled': True,
            'model_name': 'cross-encoder/ms-marco-MiniLM-L-6-v2',
            'max_rerank': 30
        }

    results = retrieve_top_k(
        conn,
        question.q,
        top_k=question.max_sources,
        model_name="BAAI/bge-base-en-v1.5",
        reranker_config=reranker_config,
        top_k_db=30
    )

    # Optional: Filter by object_type
    if question.filter_object_type:
        results = [r for r in results if r['object_type'] == question.filter_object_type]

    # Build context
    context = build_context_from_results(results)

    # Generate answer with LLM
    answer = generate_llm_answer(question.q, context)

    conn.close()

    return {
        "answer": answer,
        "sources": [
            {
                "title": r["title"],
                "url": r["url"],
                "object_type": r["object_type"],
                "object_id": r["object_id"],
                "relevance_score": r.get("rerank_score", r["score"])
            }
            for r in results
        ],
        "metadata": {
            "model": "BAAI/bge-base-en-v1.5",
            "reranking_enabled": question.use_reranking,
            "num_sources": len(results)
        }
    }

def build_context_from_results(results):
    """Build LLM context from retrieval results"""
    context_parts = []
    for i, r in enumerate(results, 1):
        context_parts.append(
            f"[Source {i}] {r['title']} ({r['object_type']})\n"
            f"URL: {r['url']}\n"
            f"{r['content']}\n"
        )
    return "\n\n".join(context_parts)

def generate_llm_answer(query, context):
    """Generate answer using LLM (Ollama/OpenAI/etc)"""
    # Your existing LLM code here
    # Should already exist in your API
    pass
```

---

## Configuration Updates

### Update config.yaml (if needed)

Your config should already point to the right model:

```yaml
# config.yaml
model:
  embedding_model: BAAI/bge-base-en-v1.5  # Already using BGE
  embedding_dim: 768

retrieval:
  top_k_db: 30          # Fetch 30 candidates
  top_k: 10             # Return top 10 after reranking
  distance: cosine
  reranker:
    enabled: true
    model_name: cross-encoder/ms-marco-MiniLM-L-6-v2
    max_rerank: 30
```

---

## Testing the API Integration

### 1. Start API
```bash
cd /path/to/api
python3 htw_assistant_api.py
```

### 2. Test Basic Query
```bash
curl -X POST http://localhost:8000/ask \
  -H "Content-Type: application/json" \
  -d '{
    "q": "What is the semester fee?",
    "max_sources": 5
  }' | jq
```

**Expected response:**
```json
{
  "answer": "The semester fee at HTW Berlin is 357.30 EUR...",
  "sources": [
    {
      "title": "Semester fee",
      "url": "https://www.htw-berlin.de/en/studies/study-organisation/semester-fee/",
      "object_type": "fees_funding_rule",
      "object_id": "fees_funding_rule-semester-fee",
      "relevance_score": 4.44
    }
  ]
}
```

### 3. Test Multiple Queries
```bash
# Test various query types
for query in "semester fee" "application process" "language requirements"; do
  echo "Testing: $query"
  curl -s -X POST http://localhost:8000/ask \
    -H "Content-Type: application/json" \
    -d "{\"q\": \"$query\", \"max_sources\": 3}" | jq '.sources[0].title'
done
```

### 4. Test with Object Type Filter
```bash
curl -X POST http://localhost:8000/ask \
  -H "Content-Type: application/json" \
  -d '{
    "q": "How do I apply?",
    "max_sources": 5,
    "filter_object_type": "application_process"
  }' | jq
```

---

## Migration Checklist for API

### Pre-Deployment
- [ ] Backup current API code
- [ ] Test retrieval functions work (`test_retrieval_v2.py`)
- [ ] Verify database has 170 docs, 930 chunks
- [ ] Check API dependencies installed (FastAPI, etc.)

### Deployment Steps
1. [ ] Update API code (if making enhancements)
2. [ ] Update config.yaml (if needed)
3. [ ] Restart API server
4. [ ] Test basic queries
5. [ ] Test reranking (if enabled)
6. [ ] Monitor logs for errors
7. [ ] Check response quality

### Post-Deployment
- [ ] Monitor API response times
- [ ] Check result relevance
- [ ] Collect user feedback
- [ ] Adjust reranking threshold if needed

---

## Expected Improvements

### Quality
- ✅ **Better chunking**: Guaranteed minimums ensure better coverage
- ✅ **Enrichment**: Thin objects borrowed content from related pages
- ✅ **Metadata**: object_id and object_type enable filtering
- ✅ **BGE embeddings**: Better semantic understanding

### Performance
- ✅ **Reranking**: Cross-encoder improves top-10 precision
- ✅ **Optimized index**: IVFFlat with cosine distance
- ✅ **Fewer chunks**: 930 vs potential noise from old pipeline

### Metrics to Track
- **Response time**: Should be ~150-350ms with reranking
- **Relevance**: Top result should be more accurate
- **Coverage**: Should find information from all 170 objects
- **User satisfaction**: Monitor feedback/corrections needed

---

## Rollback Plan

If something breaks:

### 1. Quick Rollback (Retrieval Only)
```bash
# Revert retrieval.py changes
cd /path/to/project
git checkout hansdb/retrieval.py

# Restart API
# Old schema (documents, web_chunks) still has data
```

### 2. Full Rollback (Schema + Code)
```bash
# Revert all changes
git checkout hansdb/retrieval.py
git checkout config.yaml

# Update config to use E5
# Edit config.yaml:
#   model:
#     embedding_model: intfloat/multilingual-e5-base

# Restart API
```

Old data is preserved, so rollback is safe!

---

## Advanced Features (Future)

### 1. Object Type Filtering
```python
# Filter by type before retrieval
WHERE d.object_type IN ('application_process', 'fees_funding_rule')
```

### 2. Hybrid Search
```python
# Combine keyword + vector search
WITH keyword_results AS (
    SELECT ... WHERE chunk_text @@ to_tsquery('semester & fee')
),
vector_results AS (
    SELECT ... ORDER BY embedding <=> query_vector
)
SELECT * FROM keyword_results UNION vector_results
```

### 3. Query Expansion
```python
# Expand query with synonyms
expanded_query = expand_with_synonyms(user_query)
results = retrieve_top_k(conn, expanded_query, ...)
```

### 4. Caching
```python
# Cache popular queries
@lru_cache(maxsize=100)
def cached_retrieve(query: str, top_k: int):
    return retrieve_top_k(conn, query, top_k)
```

---

## Monitoring & Debugging

### Log Important Metrics
```python
import logging

logger = logging.getLogger(__name__)

@app.post("/ask")
def ask_question(question: Question):
    start_time = time.time()

    results = retrieve_top_k(...)
    retrieval_time = time.time() - start_time

    logger.info(
        f"Query: {question.q[:50]} | "
        f"Results: {len(results)} | "
        f"Time: {retrieval_time*1000:.0f}ms | "
        f"Top score: {results[0]['score'] if results else 'N/A'}"
    )

    # ... rest of code
```

### Debug Queries
```python
# Add debug endpoint
@app.post("/debug/search")
def debug_search(query: str):
    conn = get_db_connection(config)
    results = retrieve_top_k(conn, query, top_k=10, top_k_db=30)

    return {
        "query": query,
        "num_results": len(results),
        "results": [
            {
                "rank": i,
                "title": r["title"],
                "object_type": r["object_type"],
                "vector_score": r["score"],
                "rerank_score": r.get("rerank_score"),
                "content_preview": r["content"][:200]
            }
            for i, r in enumerate(results, 1)
        ]
    }
```

---

## Summary: What You Need to Do

### Minimal Integration (Zero Changes)
1. Your API already works with hans_v2 (if using `retrieve_top_k()`)
2. Just restart the API server
3. Test with a few queries
4. Done! ✅

### Enhanced Integration (Recommended)
1. Add reranking to API calls
2. Return `object_type` and `object_id` in response
3. Optional: Add filtering by object_type
4. Test thoroughly
5. Deploy with monitoring

### Timeline
- **Minimal**: 5 minutes (restart API)
- **Enhanced**: 1-2 hours (code updates + testing)
- **Full production**: 1 day (monitoring + validation)

---

## Need Help Finding Your API?

Run this to locate your API file:
```bash
find /Users/koware/Desktop/HANS/Hans_DB -name "*.py" | xargs grep -l "def ask\|@app.post\|FastAPI\|flask" | grep -v __pycache__
```

Or tell me where your API is, and I can show you exactly what to change!

---

**Current Status: Backend is READY. API integration is 90% automatic!** ✅
