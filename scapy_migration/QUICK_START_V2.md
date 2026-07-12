# Quick Start - Hans V2 with API

**TL;DR:** Your backend is ready. Just start the API and test!

---

## Start API Server

```bash
cd /Users/koware/Desktop/HANS/Hans_DB/hans_experiments/baseline_copy

python3 api_server.py
```

Expected output:
```
INFO: Starting HANS API server...
INFO: Database initialized: 170 docs, 930 chunks, 0 Q&A pairs
INFO: HANS agent initialized successfully
INFO: Uvicorn running on http://127.0.0.1:8080 (Press CTRL+C to quit)
```

---

## Test API

### 1. Health Check

```bash
curl http://127.0.0.1:8080/health
```

### 2. Ask a Question

```bash
curl -X POST http://127.0.0.1:8080/ask \
  -H "Content-Type: application/json" \
  -d '{"q": "What is the semester fee?"}' | jq
```

### 3. Web Interface

Open in browser: http://127.0.0.1:8080/

---

## What Changed?

### Backend ✅ DONE
- New schema `hans_v2` with 170 documents, 930 chunks
- BGE embeddings (768-dim, no prefixes)
- Reranking with cross-encoder
- Better chunking with enrichment

### API ✅ AUTOMATIC
- Already queries hans_v2 tables
- Reranking already enabled
- Response format unchanged

### You Need To Do
1. Restart API server (above)
2. Test a few queries
3. That's it!

---

## Files to Know

- **API Server:** [api_server.py](../api_server.py)
- **Agent Logic:** [hans_db_agents.py](../hans_db_agents.py)
- **Retrieval:** [hansdb/retrieval.py](../hansdb/retrieval.py)
- **Config:** [config.yaml](../../config.yaml)

---

## Documentation

- **Integration Status:** [API_INTEGRATION_STATUS.md](API_INTEGRATION_STATUS.md) ← **READ THIS FIRST**
- **Testing Guide:** [TESTING_GUIDE.md](TESTING_GUIDE.md)
- **Schema Details:** [SCHEMA_V2_MIGRATION_COMPLETE.md](SCHEMA_V2_MIGRATION_COMPLETE.md)
- **Retrieval Updates:** [RETRIEVAL_UPDATE_COMPLETE.md](RETRIEVAL_UPDATE_COMPLETE.md)

---

## Troubleshooting

**API won't start?**
```bash
# Check database is running
psql -h 127.0.0.1 -p 5433 -U postgres -d hans -c "SELECT COUNT(*) FROM hans_v2.documents"
# Should return: 170
```

**No results?**
```bash
# Test retrieval directly
python3 test_retrieval_v2.py
```

**Need detailed logs?**
```bash
export LOG_LEVEL=DEBUG
python3 api_server.py
```

---

## Next Steps (Optional)

1. **Add object metadata to API response** - See [API_INTEGRATION_STATUS.md](API_INTEGRATION_STATUS.md#enhancement-1-expose-object-metadata)
2. **Add object type filtering** - See [API_INTEGRATION_STATUS.md](API_INTEGRATION_STATUS.md#enhancement-2-add-object-type-filtering)
3. **Monitor performance** - See [API_INTEGRATION_STATUS.md](API_INTEGRATION_STATUS.md#enhancement-3-performance-monitoring)

---

**Everything is ready to go!** 🚀
