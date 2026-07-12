# Testing Guide - Hans V2 RAG System

Complete guide for testing the new hans_v2 schema with BGE embeddings.

---

## Quick Test (2 minutes)

Run the comprehensive test script:

```bash
cd /Users/koware/Desktop/HANS/Hans_DB/hans_experiments/baseline_copy
python3 scapy_migration/test_retrieval_v2.py
```

**Expected Output:**
```
✓ All tests passed!
SUCCESS: All retrieval tests passed!
The hans_v2 schema is working correctly with BGE embeddings.
No E5 prefixes are being used.
```

---

## Test 1: Database Verification

### Check Data Counts
```bash
PGPASSWORD=postgres psql -h 127.0.0.1 -p 5433 -U postgres -d hans << 'EOF'
SELECT
    (SELECT COUNT(*) FROM hans_v2.documents) as docs,
    (SELECT COUNT(*) FROM hans_v2.chunks) as chunks,
    (SELECT AVG(chunk_count)::numeric(10,2) FROM (
        SELECT COUNT(*) as chunk_count
        FROM hans_v2.chunks
        GROUP BY document_id
    ) x) as avg_chunks;
EOF
```

**Expected:**
```
 docs | chunks | avg_chunks
------+--------+------------
  170 |    930 |       5.47
```

### Check Sample Data
```bash
PGPASSWORD=postgres psql -h 127.0.0.1 -p 5433 -U postgres -d hans << 'EOF'
SELECT object_id, object_type, title
FROM hans_v2.documents
LIMIT 5;
EOF
```

### Verify Embeddings
```bash
PGPASSWORD=postgres psql -h 127.0.0.1 -p 5433 -U postgres -d hans << 'EOF'
SELECT
    d.object_id,
    c.chunk_index,
    vector_dims(c.embedding) as embedding_dims,
    length(c.chunk_text) as text_length
FROM hans_v2.chunks c
JOIN hans_v2.documents d ON c.document_id = d.id
LIMIT 5;
EOF
```

**Expected:** All embedding_dims should be 768

---

## Test 2: Python API Test

### Basic Retrieval Test
```python
# test_basic.py
from hansdb.conn import get_db_connection, load_config
from hansdb.retrieval import retrieve_top_k

config = load_config()
conn = get_db_connection(config)

# Test query
results = retrieve_top_k(
    conn,
    query_text="What is the semester fee?",
    top_k=5,
    model_name="BAAI/bge-base-en-v1.5"
)

print(f"Retrieved {len(results)} results:")
for i, result in enumerate(results, 1):
    print(f"\n{i}. {result['title']}")
    print(f"   Score: {result['score']:.4f}")
    print(f"   Object Type: {result['object_type']}")
    print(f"   URL: {result['url']}")

conn.close()
```

**Run:**
```bash
python3 test_basic.py
```

---

## Test 3: Reranking Test

### With vs Without Reranking
```python
# test_reranking.py
from hansdb.conn import get_db_connection, load_config
from hansdb.retrieval import retrieve_top_k

config = load_config()
conn = get_db_connection(config)

query = "Barrier-free access for disabled students"

# Without reranking
print("WITHOUT RERANKING:")
results_no_rerank = retrieve_top_k(conn, query, top_k=5, top_k_db=30)
for i, r in enumerate(results_no_rerank, 1):
    print(f"{i}. {r['title']} (score: {r['score']:.4f})")

print("\n" + "="*60 + "\n")

# With reranking
print("WITH RERANKING:")
results_with_rerank = retrieve_top_k(
    conn,
    query,
    top_k=5,
    top_k_db=30,
    reranker_config={
        'enabled': True,
        'model_name': 'cross-encoder/ms-marco-MiniLM-L-6-v2',
        'max_rerank': 30
    }
)
for i, r in enumerate(results_with_rerank, 1):
    print(f"{i}. {r['title']} (vector: {r['score']:.4f}, rerank: {r.get('rerank_score', 0):.4f})")

conn.close()
```

**Run:**
```bash
python3 test_reranking.py
```

---

## Test 4: Query Coverage Test

Test various query types:

```python
# test_queries.py
from hansdb.conn import get_db_connection, load_config
from hansdb.retrieval import retrieve_top_k

config = load_config()
conn = get_db_connection(config)

test_queries = [
    # Financial
    "What is the semester fee?",
    "How much does studying cost?",
    "Financial aid for students",

    # Application
    "How do I apply for a study program?",
    "Application deadlines",
    "Required documents for application",

    # International Students
    "Language requirements for international students",
    "English language proof",
    "German language courses",

    # Accessibility
    "Barrier-free access",
    "Support for disabled students",
    "Disability representation",

    # Academic
    "How to change study program?",
    "Leave of absence",
    "Re-registration process",
]

print("QUERY COVERAGE TEST")
print("="*60)

for query in test_queries:
    print(f"\nQuery: {query}")
    results = retrieve_top_k(
        conn,
        query,
        top_k=3,
        reranker_config={
            'enabled': True,
            'model_name': 'cross-encoder/ms-marco-MiniLM-L-6-v2',
            'max_rerank': 30
        },
        top_k_db=30
    )

    if results:
        print(f"  ✓ Found: {results[0]['title']} ({results[0]['object_type']})")
    else:
        print(f"  ✗ No results found")

conn.close()
```

**Run:**
```bash
python3 test_queries.py
```

---

## Test 5: Performance Test

### Measure Query Speed
```python
# test_performance.py
import time
from hansdb.conn import get_db_connection, load_config
from hansdb.retrieval import retrieve_top_k

config = load_config()
conn = get_db_connection(config)

test_queries = [
    "semester fee",
    "application process",
    "language requirements",
    "barrier-free access",
    "study program change"
]

print("PERFORMANCE TEST")
print("="*60)

total_time = 0
for query in test_queries:
    start = time.time()

    results = retrieve_top_k(
        conn,
        query,
        top_k=10,
        top_k_db=30,
        reranker_config={
            'enabled': True,
            'model_name': 'cross-encoder/ms-marco-MiniLM-L-6-v2',
            'max_rerank': 30
        }
    )

    elapsed = time.time() - start
    total_time += elapsed

    print(f"Query: '{query}'")
    print(f"  Time: {elapsed*1000:.0f}ms")
    print(f"  Results: {len(results)}")

print(f"\nAverage: {(total_time/len(test_queries))*1000:.0f}ms per query")

conn.close()
```

**Run:**
```bash
python3 test_performance.py
```

**Expected:** ~150-350ms per query with reranking

---

## Test 6: Object Type Distribution

### Check What Types Are Found
```python
# test_object_types.py
from hansdb.conn import get_db_connection, load_config
from hansdb.retrieval import retrieve_top_k
from collections import Counter

config = load_config()
conn = get_db_connection(config)

queries = [
    "semester fee",
    "application process",
    "language requirements",
    "accessibility support",
    "study program",
]

all_types = []

for query in queries:
    results = retrieve_top_k(conn, query, top_k=10, top_k_db=30)
    for r in results:
        if r['object_type']:
            all_types.append(r['object_type'])

type_counts = Counter(all_types)

print("OBJECT TYPE DISTRIBUTION IN RESULTS")
print("="*60)
for obj_type, count in type_counts.most_common():
    print(f"{obj_type:30} {count:3} results")

conn.close()
```

**Run:**
```bash
python3 test_object_types.py
```

---

## Test 7: No E5 Prefix Verification

### Verify BGE Doesn't Use Prefixes
```python
# test_no_prefixes.py
from hansdb.embeddings import embed_query, embed_single_text
import numpy as np

# Test BGE (should NOT add prefix)
text = "What is the semester fee?"

emb1 = embed_query(text, "BAAI/bge-base-en-v1.5")
emb2 = embed_single_text(text, "BAAI/bge-base-en-v1.5", is_query=True)

print("BGE Embedding Test")
print("="*60)
print(f"Text: '{text}'")
print(f"Embedding shape: {emb1.shape}")
print(f"Embeddings identical: {np.allclose(emb1, emb2)}")
print("✓ No prefix added (BGE doesn't use prefixes)")

# Show what E5 would do (for comparison)
print("\nE5 Comparison (hypothetical):")
print("  E5 would add: 'query: What is the semester fee?'")
print("  BGE uses plain: 'What is the semester fee?'")
```

**Run:**
```bash
python3 test_no_prefixes.py
```

---

## Test 8: Database Stats

### Get Comprehensive Statistics
```bash
PGPASSWORD=postgres psql -h 127.0.0.1 -p 5433 -U postgres -d hans << 'EOF'
-- Document counts by type
SELECT object_type, COUNT(*) as count
FROM hans_v2.documents
GROUP BY object_type
ORDER BY count DESC;

-- Chunk statistics
SELECT
    COUNT(*) as total_chunks,
    MIN(chunk_text_len) as min_length,
    MAX(chunk_text_len) as max_length,
    AVG(chunk_text_len)::int as avg_length,
    SUM(CASE WHEN enriched THEN 1 ELSE 0 END) as enriched_count,
    SUM(CASE WHEN still_thin THEN 1 ELSE 0 END) as thin_count
FROM hans_v2.chunks;

-- Chunks per document distribution
SELECT
    chunk_count,
    COUNT(*) as num_documents
FROM (
    SELECT document_id, COUNT(*) as chunk_count
    FROM hans_v2.chunks
    GROUP BY document_id
) x
GROUP BY chunk_count
ORDER BY chunk_count;
EOF
```

---

## Test 9: Stress Test

### High-Volume Query Test
```python
# test_stress.py
import time
from hansdb.conn import get_db_connection, load_config
from hansdb.retrieval import retrieve_top_k

config = load_config()
conn = get_db_connection(config)

queries = [
    "semester fee", "application", "language", "barrier-free",
    "study program", "registration", "documents", "deadline"
] * 10  # 80 queries

print(f"STRESS TEST: {len(queries)} queries")
print("="*60)

start = time.time()
success_count = 0
error_count = 0

for i, query in enumerate(queries, 1):
    try:
        results = retrieve_top_k(conn, query, top_k=5, top_k_db=30)
        if results:
            success_count += 1

        if i % 10 == 0:
            elapsed = time.time() - start
            qps = i / elapsed
            print(f"  {i}/{len(queries)} queries - {qps:.1f} QPS")

    except Exception as e:
        error_count += 1
        print(f"  Error on query {i}: {e}")

total_time = time.time() - start
avg_qps = len(queries) / total_time

print(f"\nResults:")
print(f"  Total queries: {len(queries)}")
print(f"  Success: {success_count}")
print(f"  Errors: {error_count}")
print(f"  Total time: {total_time:.2f}s")
print(f"  Average QPS: {avg_qps:.2f}")

conn.close()
```

**Run:**
```bash
python3 test_stress.py
```

---

## Test 10: End-to-End Integration Test

### Full Pipeline Test
```python
# test_integration.py
import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent))

from hansdb.conn import get_db_connection, load_config
from hansdb.retrieval import retrieve_top_k, get_retrieval_stats

def test_integration():
    """Complete integration test"""

    print("INTEGRATION TEST")
    print("="*60)

    # 1. Load config
    print("\n1. Loading config...")
    config = load_config()
    print("   ✓ Config loaded")

    # 2. Connect to DB
    print("\n2. Connecting to database...")
    conn = get_db_connection(config)
    print("   ✓ Connected")

    # 3. Check stats
    print("\n3. Checking database stats...")
    stats = get_retrieval_stats(conn)
    print(f"   Documents: {stats['documents']}")
    print(f"   Chunks: {stats['web_chunks']}")
    print(f"   Q&A: {stats['qa_pairs']}")

    assert stats['documents'] == 170, "Expected 170 documents"
    assert stats['web_chunks'] == 930, "Expected 930 chunks"
    print("   ✓ Stats verified")

    # 4. Test vector search
    print("\n4. Testing vector search...")
    results = retrieve_top_k(conn, "semester fee", top_k=5, top_k_db=30)
    assert len(results) > 0, "Expected results from vector search"
    assert 'object_id' in results[0], "Expected object_id in results"
    assert 'object_type' in results[0], "Expected object_type in results"
    print(f"   ✓ Found {len(results)} results")
    print(f"   ✓ Top result: {results[0]['title']}")

    # 5. Test reranking
    print("\n5. Testing reranking...")
    results_rerank = retrieve_top_k(
        conn,
        "barrier-free access",
        top_k=5,
        top_k_db=30,
        reranker_config={
            'enabled': True,
            'model_name': 'cross-encoder/ms-marco-MiniLM-L-6-v2',
            'max_rerank': 30
        }
    )
    assert 'rerank_score' in results_rerank[0], "Expected rerank_score"
    print(f"   ✓ Reranking working")
    print(f"   ✓ Top result: {results_rerank[0]['title']}")
    print(f"      Rerank score: {results_rerank[0]['rerank_score']:.4f}")

    # 6. Test multiple queries
    print("\n6. Testing multiple query types...")
    test_cases = [
        ("semester fee", "fees_funding_rule"),
        ("application process", "application_process"),
        ("barrier-free", "accessibility_support"),
        ("language requirements", "language_proof_rule"),
    ]

    for query, expected_type in test_cases:
        results = retrieve_top_k(conn, query, top_k=3, top_k_db=30)
        found_type = any(r['object_type'] == expected_type for r in results)
        status = "✓" if found_type else "✗"
        print(f"   {status} '{query}' → {expected_type}")

    conn.close()

    print("\n" + "="*60)
    print("✓ ALL INTEGRATION TESTS PASSED")
    print("="*60)
    return True

if __name__ == '__main__':
    try:
        test_integration()
    except AssertionError as e:
        print(f"\n✗ TEST FAILED: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\n✗ ERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
```

**Run:**
```bash
python3 test_integration.py
```

---

## Expected Test Results

### All Tests Should Show:
- ✅ 170 documents in hans_v2.documents
- ✅ 930 chunks in hans_v2.chunks
- ✅ 768-dimensional embeddings (BGE)
- ✅ No E5 prefixes used
- ✅ Vector search returns relevant results
- ✅ Reranking improves precision
- ✅ object_id and object_type populated
- ✅ Average query time: 150-350ms with reranking
- ✅ All object types retrievable

### Success Criteria:
1. **Database**: All tables exist and populated
2. **Embeddings**: 768 dims, no prefixes
3. **Retrieval**: Relevant results for test queries
4. **Reranking**: Higher quality top results
5. **Performance**: < 500ms per query
6. **Coverage**: All object types findable

---

## Troubleshooting

### Issue: No results returned
```bash
# Check if chunks exist
psql -h 127.0.0.1 -p 5433 -U postgres -d hans -c "SELECT COUNT(*) FROM hans_v2.chunks;"
```

### Issue: Slow queries
```bash
# Check if index exists
psql -h 127.0.0.1 -p 5433 -U postgres -d hans -c "
SELECT indexname FROM pg_indexes WHERE schemaname = 'hans_v2';
"

# Rebuild index if needed
psql -h 127.0.0.1 -p 5433 -U postgres -d hans -c "
DROP INDEX IF EXISTS hans_v2.idx_chunks_embedding_ivfflat;
ANALYZE hans_v2.chunks;
CREATE INDEX idx_chunks_embedding_ivfflat ON hans_v2.chunks
USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100);
"
```

### Issue: Type mismatch errors
```python
# Verify both IDs are cast to text in SQL
# Check hansdb/retrieval.py line 79: c.id::text
# Check hansdb/retrieval.py line 93: qa.id::text
```

---

## Quick Command Reference

```bash
# Run all tests
python3 scapy_migration/test_retrieval_v2.py
python3 test_integration.py
python3 test_performance.py
python3 test_queries.py

# Check database
psql -h 127.0.0.1 -p 5433 -U postgres -d hans

# Verify counts
psql -h 127.0.0.1 -p 5433 -U postgres -d hans -c "
SELECT
    (SELECT COUNT(*) FROM hans_v2.documents) as docs,
    (SELECT COUNT(*) FROM hans_v2.chunks) as chunks;
"

# Test single query
python3 -c "
from hansdb.conn import get_db_connection, load_config
from hansdb.retrieval import retrieve_top_k
conn = get_db_connection(load_config())
results = retrieve_top_k(conn, 'semester fee', top_k=3)
for r in results: print(r['title'])
conn.close()
"
```

---

## Success Checklist

Before declaring the system ready:

- [ ] test_retrieval_v2.py passes
- [ ] test_integration.py passes
- [ ] Database has 170 docs, 930 chunks
- [ ] All queries return relevant results
- [ ] Reranking improves result quality
- [ ] Performance is acceptable (<500ms)
- [ ] No E5 prefixes used
- [ ] object_id and object_type populated
- [ ] All object types are findable
- [ ] No errors in logs

**If all checkboxes pass → System is ready for production! ✅**
