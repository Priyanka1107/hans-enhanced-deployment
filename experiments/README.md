# HANS RAG Quality Experiments

This directory contains the experimental harness for systematically testing RAG quality improvements in HANS.

## 🐘 Local Postgres (Docker) Setup

Before running experiments, set up a local PostgreSQL database with pgvector:

### 1. Start the Database

```bash
cd hans_experiments/baseline_copy
bash scripts/start_local_db.sh
```

This creates a Docker container named `hans-pg` with PostgreSQL 16 + pgvector, running on port 5433.

### 2. Initialize Schema and Data

```bash
# Load environment variables
export $(grep -v '^#' .env.local | xargs)

# Initialize database (creates tables, indexes, and ingests content)
bash scripts/init_local_db.sh
```

This will:
- Enable pgvector extension
- Create tables (documents, web_chunks, qa_pairs)
- Create vector indexes (IVFFlat with cosine distance)
- Ingest web JSON data and Excel Q&A pairs
- Generate embeddings for all content

**Note:** Ingestion may take a few minutes depending on content size.

### 3. Run the API Server

```bash
python api_server.py
```

The API will start on `http://localhost:8080` by default.

### 4. Run Experiments

```bash
# In another terminal
python experiments/run_experiments.py

# When prompted, name your experiment (e.g., "baseline_local")
```

### Important Notes

- **This database is separate from HTW's production database** - safe for experimentation
- **Port conflicts:** If port 5433 is already in use, edit `start_local_db.sh` to change `-p 5433:5432` to `-p 5434:5432`, then update `.env.local` to `postgresql://postgres:postgres@localhost:5434/hans`
- **Stop the database:** `docker stop hans-pg`
- **Restart the database:** `bash scripts/start_local_db.sh` (automatically detects existing container)
- **Reset everything:** `docker rm -f hans-pg && docker volume rm hans_pgdata` then re-run setup

## 🎯 Purpose

- Test one change at a time in an isolated environment
- Compare performance against the baseline (original) system
- Document the impact of each modification
- Build evidence for which changes improve answer quality

## 📁 Files

- **`test_queries.json`**: Fixed set of 10 representative English test queries about HTW Berlin Master's programs
- **`run_experiments.py`**: Python script that sends queries to the local API and logs responses
- **`results/`**: Directory where experiment results are saved (auto-created)

## 🔬 Workflow

### 1. Baseline Run (First Time)

```bash
# From the baseline_copy directory
cd hans_experiments/baseline_copy

# Start the API server (Terminal 1)
python api_server.py

# In another terminal, run the experiment (Terminal 2)
python experiments/run_experiments.py
```

Save the results with a descriptive name like `baseline` when prompted.

### 2. Make ONE Change

Examples of changes you might test:
- Change embedding model in `config.yaml` (e.g., `intfloat/multilingual-e5-base`)
- Adjust chunk size: `chunk_chars: 800` instead of `1800`
- Modify top_k retrieval count
- Update system prompt in `hans_db_agents.py`
- Add re-ranking logic in `hansdb/retrieval.py`

### 3. Re-run Experiment

```bash
# Restart API server to pick up config changes (Ctrl+C first)
python api_server.py

# Run experiments again
python experiments/run_experiments.py
```

Save with a name describing the change (e.g., `multilingual_embeddings`, `chunk_800`, etc.)

### 4. Compare Results

Review the JSON files in `experiments/results/` to compare:
- Answer quality (subjective - does it answer the question?)
- Confidence scores
- Source retrieval (are the right documents found?)
- Response consistency

### 5. Document Findings

Keep notes on what worked and what didn't. Consider:
- Which changes improved German query handling?
- Which changes improved confidence accuracy?
- Any unexpected side effects?

## 🧪 Change 1: Chunking-only Experiment

This experiment tests whether smaller, less aggressive chunking improves retrieval precision and answer quality.

### Configuration Changes

In [config.yaml](../config.yaml), the `ingestion:` section has been updated to:

```yaml
ingestion:
  min_chars: 300        # keep slightly more small bits (was: 400)
  chunk_chars: 800      # smaller chunks for more precise retrieval (was: 1800)
  chunk_overlap: 150    # moderate overlap (was: 200)
  skip_short: false     # do NOT drop short chunks (was: true)
```

### Running This Experiment

After making the config changes above, you **must rebuild the database** to apply the new chunking:

1. **Rebuild the local content DB:**
   ```bash
   cd hans_experiments/baseline_copy
   export $(grep -v '^#' .env.local | xargs)
   python scripts/build_content_db.py --force
   ```

2. **Restart the API server:**
   ```bash
   python api_server.py
   ```

3. **Run the experiment suite:**
   ```bash
   # In another terminal
   python experiments/run_experiments.py
   ```

   When prompted for experiment name, use: **`chunking_only`**

### What This Tests

- **Keeps the same embedding model** (BAAI/bge-base-en-v1.5) and LLM (llama3:8b) as baseline
- **Only changes chunking strategy** to create smaller, more focused chunks
- **Goal**: Determine if smaller chunks improve:
  - Retrieval relevance (better matching of specific questions)
  - Answer precision (less noise from large chunks)
  - Source quality (more targeted references)

### Expected Impact

Smaller chunks should theoretically:
- ✅ Reduce irrelevant content in retrieved passages
- ✅ Allow more precise semantic matching
- ⚠️ May lose some contextual information from larger passages
- ⚠️ May retrieve more chunks but each with narrower focus

Compare the `chunking_only` results with your baseline (`3rd test.json`) to evaluate these trade-offs.

## 🎯 Change 2: Retrieval Tuning (More Sources + Optional Min-Score Filter)

This experiment tests whether retrieving more sources improves answer quality and coverage.

### Configuration Changes

**1. Increased retrieval breadth from 6 to 10 sources:**

In [config.yaml](../config.yaml):
```yaml
retrieval:
  top_k: 10  # was: 6
  distance: cosine
  min_score: 0.0  # Optional filter: max distance threshold (0.0 = no filtering)
```

In [api_server.py](../api_server.py):
```python
class QueryRequest(BaseModel):
    q: str
    max_sources: Optional[int] = 10  # was: 6
```

In [experiments/run_experiments.py](run_experiments.py):
```python
json={"q": query, "max_sources": 10}  # was: 6
```

**2. Added configurable min_score filter:**

- New parameter `retrieval.min_score` in config.yaml (default: 0.0)
- When set to 0.0, no filtering is applied (backwards compatible)
- When > 0.0, acts as a max distance threshold to filter out weak matches
- Includes safe fallback: if all results filtered, keeps unfiltered results

### Running This Experiment

**Note:** Since chunking configuration didn't change from Change 1, rebuilding the database is optional. However, for completeness:

1. **Rebuild the local content DB (optional):**
   ```bash
   cd hans_experiments/baseline_copy
   export $(grep -v '^#' .env.local | xargs)
   python scripts/build_content_db.py --force
   ```

2. **Restart the API server:**
   ```bash
   python api_server.py
   ```

3. **Run the experiment suite:**
   ```bash
   # In another terminal
   python experiments/run_experiments.py
   ```

   When prompted for experiment name, use: **`retrieval_tuned`**

### What This Tests

- **Keeps the same embedding model** (BAAI/bge-base-en-v1.5), chunking (800 chars), and LLM (llama3:8b) as Change 1
- **Only changes retrieval behavior** to fetch more sources per query
- **Goal**: Determine if broader retrieval improves:
  - Answer completeness (more context available)
  - Source diversity (different perspectives/documents)
  - Recall (finding relevant info that would be missed with fewer sources)

### Expected Impact

More sources (10 vs 6) should theoretically:
- ✅ Increase recall - less likely to miss relevant information
- ✅ Provide more diverse context to the LLM
- ✅ Better handle queries that span multiple documents
- ⚠️ May introduce more noise (weaker matches included)
- ⚠️ Slightly slower retrieval (minimal impact with indexing)

The `min_score` filter (currently 0.0) provides a mechanism to tune the quality/quantity tradeoff in future experiments.

Compare the `retrieval_tuned` results with `chunking_only` to evaluate the impact of increased retrieval breadth.

## 📝 Change 3: System Prompt Tuning (English-only, Concise, Grounded)

This experiment tests whether a more explicit and structured system prompt improves answer quality, consistency, and usefulness.

### Configuration Changes

The system prompt in [hans_db_agents.py](../hans_db_agents.py) (function `_build_system_prompt()`) has been rewritten to enforce:

**1. Language constraint:**
- ALWAYS answer in English, even if the question is in German or another language
- Use simple, clear language suitable for international students

**2. Conciseness and structure:**
- Maximum 2 short paragraphs + 1 bullet list
- Target length: approximately 150-180 words
- Start with a direct answer (1-3 sentences)
- Add bullet points for key details when helpful

**3. Grounding and honesty:**
- Base answers ONLY on provided context
- Never invent deadlines, fees, ECTS values, test scores, or programme names
- Explicitly state when information is missing or unclear
- Acknowledge when something "depends on the specific programme"
- Never fabricate URLs

**4. Source attribution:**
- Reference sources naturally (e.g., "According to the HTW Berlin application portal...")
- No need to list all URLs, but don't contradict provided documents

**5. Uncertainty handling:**
- If context doesn't contain requested details, say so explicitly
- Recommend where to look next (official website, Student Services contact, etc.)

### Running This Experiment

**Note:** No database rebuild is required since retrieval, chunking, and embeddings remain unchanged from Change 2.

1. **Restart the API server:**
   ```bash
   cd hans_experiments/baseline_copy
   export $(grep -v '^#' .env.local | xargs)
   python api_server.py
   ```

2. **Run the experiment suite:**
   ```bash
   # In another terminal
   cd hans_experiments/baseline_copy
   export $(grep -v '^#' .env.local | xargs)
   python experiments/run_experiments.py
   ```

   When prompted for experiment name, use: **`prompt_tuned`**

### What This Tests

- **Keeps everything else constant:** Same embedding model (BAAI/bge-base-en-v1.5), chunking (800 chars), retrieval (top_k=10), and LLM (llama3:8b)
- **Only changes the system prompt instructions** given to the LLM
- **Goal:** Determine if explicit prompt engineering improves:
  - Response consistency (always English)
  - Answer quality (more focused, less hallucination)
  - Usefulness (clear structure, explicit about missing info)
  - Trust (honest about limitations)

### Expected Impact

A better-engineered prompt should theoretically:
- ✅ Eliminate German responses (enforce English-only)
- ✅ Reduce hallucinations (explicit "don't invent" rules)
- ✅ Improve answer structure (consistent format)
- ✅ Increase trust (clear when info is missing)
- ✅ Better length control (~150-180 words vs potentially longer rambling)
- ⚠️ May produce slightly more cautious/conservative answers
- ⚠️ May explicitly say "I don't know" more often (which is actually good if true)

Compare the `prompt_tuned` results with `retrieval_tuned` to isolate the impact of prompt engineering on answer quality.

## 🌐 Change 4: Embedding Upgrade + Cross-Encoder Reranker

This experiment tests whether upgrading to a multilingual embedding model and adding semantic reranking improves retrieval quality and answer relevance.

### Configuration Changes

**1. Embedding Model Upgrade:**

In [config.yaml](../config.yaml):
```yaml
model:
  embedding_model: intfloat/multilingual-e5-base  # was: BAAI/bge-base-en-v1.5
  embedding_dim: 768  # unchanged - no DB schema changes needed
```

Key improvements:
- **Multilingual support:** Better handling of German queries and mixed-language documents
- **E5 architecture:** Uses query/passage prefixes for optimal performance
  - Queries embedded with `"query: "` prefix
  - Documents embedded with `"passage: "` prefix
- **Same dimensionality (768):** No database schema changes required

**2. Two-Stage Retrieval with Reranking:**

In [config.yaml](../config.yaml):
```yaml
retrieval:
  top_k_db: 30      # Fetch 30 candidates from vector search
  top_k: 10         # Keep best 10 after reranking
  distance: cosine
  min_score: 0.0
  reranker:
    enabled: true
    model_name: cross-encoder/ms-marco-MiniLM-L-6-v2
    max_rerank: 30
```

Retrieval pipeline:
1. **Stage 1 - Vector Search:** Fetch `top_k_db` (30) candidates via cosine similarity
2. **Stage 2 - Semantic Reranking:** Use CrossEncoder to re-score query-passage pairs
3. **Final Selection:** Keep best `top_k` (10) results based on reranker scores

**3. Code Changes:**

- [hansdb/embeddings.py](../hansdb/embeddings.py): Added `embed_query()` and `embed_passages()` functions with E5 prefix logic
- [hansdb/retrieval.py](../hansdb/retrieval.py): Added `get_reranker_model()` and two-stage retrieval pipeline
- [scripts/build_content_db.py](../scripts/build_content_db.py): Updated to use passage prefixes for document embeddings

### Running This Experiment

**IMPORTANT:** The embedding model has changed, so you **MUST rebuild the database** with new embeddings.

1. **Rebuild the local content DB with new embeddings:**
   ```bash
   cd hans_experiments/baseline_copy
   export $(grep -v '^#' .env.local | xargs)
   python scripts/build_content_db.py --force
   ```

   **Note:** This will re-embed all documents with the multilingual-e5-base model and E5 passage prefixes. This may take several minutes.

2. **Restart the API server:**
   ```bash
   python api_server.py
   ```

3. **Run the experiment suite:**
   ```bash
   # In another terminal
   cd hans_experiments/baseline_copy
   export $(grep -v '^#' .env.local | xargs)
   python experiments/run_experiments.py
   ```

   When prompted for experiment name, use: **`embedding_rerank`**

### What This Tests

- **Keeps everything else constant:** Same chunking (800 chars), system prompt (English-only, concise), and LLM (llama3:8b) as Change 3
- **Changes both embedding and retrieval:**
  - **Better embeddings:** Multilingual-e5-base for improved semantic understanding
  - **Smarter retrieval:** Cross-encoder reranking to filter noise and prioritize relevance
- **Goal:** Determine if better embeddings + reranking improve:
  - Retrieval precision (finding the RIGHT documents, not just similar ones)
  - Answer quality (LLM gets better context)
  - Cross-lingual performance (German queries → English documents or vice versa)
  - Source relevance (fewer off-topic or tangentially related chunks)

### Expected Impact

**From multilingual embeddings:**
- ✅ Better handling of German queries
- ✅ Improved cross-lingual retrieval (German ↔ English)
- ✅ More nuanced semantic understanding

**From cross-encoder reranking:**
- ✅ Significantly improved precision (top results are truly relevant)
- ✅ Reduced noise (filters out weakly-related matches)
- ✅ Better handling of ambiguous queries (semantic re-scoring helps)
- ⚠️ Slightly slower per query (reranking 30 candidates takes ~100-300ms)
- ⚠️ Higher memory usage (two models loaded: embedder + reranker)

**Combined effect:**
- ✅ Best-in-class retrieval quality
- ✅ More focused, accurate answers
- ✅ Fewer hallucinations (better context = less guessing)
- ✅ More consistent source quality across diverse query types

Compare the `embedding_rerank` results with `prompt_tuned` to evaluate the impact of upgraded embeddings and reranking on overall system quality.

## 🔧 Experiment Ideas (from Analysis)

Based on `HANS_DEEP_CODE_ANALYSIS.md`, prioritized changes to test:

### HIGH IMPACT
1. **Multilingual embeddings**: Change `embedding_model` to `intfloat/multilingual-e5-base`
2. **Smaller chunks**: Set `chunk_chars: 800` and `chunk_overlap: 150`
3. **Add re-ranking**: Implement cross-encoder in `retrieval.py`

### MEDIUM IMPACT
4. **Better prompting**: Update system prompt in `hans_db_agents.py` lines 149-168
5. **More retrieval**: Increase `top_k: 12` (then re-rank to top 6)
6. **Query prefix**: Add "query:" prefix for E5 embeddings

### LOW IMPACT
7. **Confidence scoring**: Add semantic similarity check (currently just retrieval-based)
8. **Hybrid search**: Add BM25 sparse retrieval alongside vector search

## 📊 Expected Output

Each run produces:
- Terminal output showing all queries, answers, confidence, and sources
- JSON file in `results/` with full structured data
- Summary stats (successful vs failed queries)

## ⚠️ Important Notes

- Always restart the API server after changing `config.yaml` or code
- The original HANS project (parent directory) is untouched
- Each experiment should test ONE variable at a time for clear comparison
- Save results with descriptive names to track what was changed
- If you break something, just delete `baseline_copy` and re-copy from parent

## 🚀 Next Steps

1. Run baseline experiment
2. Pick ONE change from high-impact list
3. Test and compare
4. If better, keep the change; if worse, revert
5. Document the outcome
6. Repeat with next change
