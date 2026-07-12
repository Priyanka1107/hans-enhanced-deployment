# HANS RAG System: Deep Code Analysis & Improvement Plan

---

## [1] CODE-BASED ARCHITECTURE SUMMARY

### 1.1 Repository Structure & Key Files

**Core Application Files:**
- `api_server.py` - FastAPI backend, main HTTP interface
- `htw_assistant_api_gui.py` - Tkinter GUI client (SSH tunnel-enabled)
- `hans_db_agents.py` - **Core RAG orchestration layer**
- `config.yaml` - System configuration (models, retrieval, database)

**Database & Retrieval Module (`hansdb/`):**
- `hansdb/conn.py` - PostgreSQL connection management, schema versioning
- `hansdb/retrieval.py` - Vector similarity search, unified retrieval from web_chunks + qa_pairs
- `hansdb/embeddings.py` - SentenceTransformer model management, embedding generation

**Data Ingestion:**
- `scripts/build_content_db.py` (referenced but not in visible workspace)
- Data sources: `scrape/htw_student_data/*.json` (17 files), `HANS - Training Email Data.xlsx`

**Configuration:**
- `config.yaml` - All system parameters
- `.env` - Database URL, optional overrides

---

### 1.2 Data Flow for a Query

```python
# Entry point: api_server.py::ask_question()
1. FastAPI receives POST /ask with {"q": "user query"}
   └─> calls: hans_agent.process_query(query)

# Core orchestration: hans_db_agents.py::DatabaseRAGAgent.process_query()
2. Query Embedding
   └─> hansdb.embeddings.embed_single_text(query, model_name)
       ├─> Loads: BAAI/bge-base-en-v1.5 (singleton)
       ├─> Returns: np.ndarray[768] (L2-normalized)

3. Vector Retrieval
   └─> hansdb.retrieval.retrieve_top_k(conn, query, top_k=6)
       ├─> SQL: Unified UNION ALL query
       │   ├─> web_chunks: embedding <=> query_vector (cosine)
       │   └─> qa_pairs: question_embedding <=> query_vector
       ├─> ORDER BY score ASC LIMIT 6
       └─> Returns: List[Dict] with source_type, content, score, url, etc.

4. Context Building (hans_db_agents.py::_build_context_from_results)
   └─> Concatenates retrieved chunks with metadata:
       [Source 1 - WEB]
       Title: ...
       URL: ...
       Content: ...

5. LLM Prompting (hans_db_agents.py::process_query)
   └─> OllamaClient.chat(full_prompt, model="llama3:8b")
       ├─> URL: config['runtime']['ollama_base_url']
       │   = https://f2ki-h100-1.f2.htw-berlin.de:11435
       ├─> Payload: {"model": "llama3:8b", "prompt": ..., "stream": False}
       ├─> Timeout: 300s
       └─> Returns: response text

6. Post-Processing
   ├─> _post_process_sources(): Replace "(source web - 1)" with URLs
   └─> _calculate_confidence(): Compute confidence score

7. Response Assembly
   └─> Return: {
         "final_response": "...",
         "metadata": {
           "confidence_score": 0.67,
           "sources": [...],
           "model_used": "llama3:8b",
           "embedding_model": "BAAI/bge-base-en-v1.5"
         }
       }
```

---

### 1.3 Key Classes & Functions

**`hans_db_agents.py`:**
- `DatabaseRAGAgent` - Main orchestrator
  - `__init__(config)` - Initializes DB connection, loads config
  - `process_query(query: str) -> Dict` - **Main entry point**
  - `_build_context_from_results(results)` - Context formatting
  - `_build_system_prompt()` - Returns system prompt string
  - `_calculate_confidence(results, response)` - 6-factor confidence score
  - `_post_process_sources(response, results)` - URL replacement via regex
  - `_add_low_confidence_disclaimer(response, confidence_data)` - Adds warnings

- `OllamaClient` - Async HTTP client for Ollama
  - `chat(prompt: str, model: str) -> str` - POST to `/api/generate`

**`hansdb/retrieval.py`:**
- `retrieve_top_k(conn, query_text, top_k=6, model_name)` - **Main retrieval**
  - Uses UNION ALL to search web_chunks + qa_pairs
  - Returns sorted by cosine distance ASC
- `get_retrieval_stats(conn)` - Database statistics

**`hansdb/embeddings.py`:**
- `get_embedding_model(model_name)` - Singleton SentenceTransformer loader
- `embed_single_text(text, model_name)` - L2-normalized embedding
- `embed_and_normalize(texts, model_name)` - Batch embeddings

**`api_server.py`:**
- `ask_question(request: QueryRequest)` - FastAPI endpoint
  - Calls `hans_agent.process_query()`
  - Filters sources (only web sources with URLs shown in UI)
  - Converts confidence to percentage

---

### 1.4 Configuration Parameters

**From `config.yaml`:**

```yaml
# Embedding
model:
  embedding_model: BAAI/bge-base-en-v1.5
  embedding_dim: 768

# Chunking (ingestion-time)
ingestion:
  min_chars: 400
  chunk_chars: 1800
  chunk_overlap: 200
  skip_short: true

# Retrieval
retrieval:
  top_k: 6
  distance: cosine

# LLM
runtime:
  ollama_base_url: https://f2ki-h100-1.f2.htw-berlin.de:11435
  ollama_model: llama3:8b
  ollama_timeout: 300
  verify_ssl: false

# Database
database_tuning:
  ivfflat_probes: 10
```

**Environment Variables:**
- `DATABASE_URL` - PostgreSQL connection string (required)
- `HANS_API_BASE` - API endpoint for GUI (default: http://127.0.0.1:8080)
- `HTTP_PROXY`, `HTTPS_PROXY`, `NO_PROXY` - Proxy settings

---

### 1.5 Database Schema

**Tables (from `hansdb/retrieval.py` queries):**
- `documents` - Source metadata (id, title, url, source_type, source_file)
- `web_chunks` - Text chunks with embeddings (id, document_id, text, embedding, contacts, links)
- `qa_pairs` - Q&A from Excel (id, question, answer, question_embedding, tags, source_file)

**Vector Index:** IVFFlat on embeddings (cosine distance operator `<=>`)

---

## [2] DIAGNOSED QUALITY ISSUES (CODE-GROUNDED)

### Issue 1: Critically Insufficient Knowledge Base
**Severity: HIGH**

**Evidence from code:**
```python
# hans_db_agents.py:111
logger.info(f"Database initialized: {stats['documents']} docs, "
           f"{stats['web_chunks']} chunks, {stats['qa_pairs']} Q&A pairs")
# Actual output: 174 docs, 175 chunks, 4 Q&A pairs
```

**Problem:**
- **175 chunks from 174 documents** = 1.006 chunks/document
- This means nearly ALL documents fit in a single 1800-char chunk
- Expected: If docs average 5KB, should have ~480 chunks
- **Root cause**: Documents are either:
  1. Already very short (< 1800 chars)
  2. Chunking logic not triggering (bug in `build_content_db.py`)
  3. `skip_short=true` removing too much content

**Why it hurts quality:**
- Retrieval has very limited context to work with
- Missing granular information (1800-char chunks are too coarse)
- 4 Q&A pairs provide virtually no training signal

**Location:**
- Data ingestion: `scripts/build_content_db.py` (not visible, but controlled by `config.yaml:ingestion`)
- Config: `config.yaml` lines 14-19

---

### Issue 2: English-First Embedding Model for Bilingual Content
**Severity: HIGH**

**Evidence from code:**
```python
# config.yaml:22-24
model:
  embedding_model: BAAI/bge-base-en-v1.5  # ← English-optimized
  embedding_dim: 768

# hansdb/embeddings.py:16
def get_embedding_model(model_name: str = "BAAI/bge-base-en-v1.5"):
    # Model trained primarily on English corpus
```

**Problem:**
- BAAI/bge-base-en-v1.5 is explicitly English-first (trained on MS MARCO, NQ, etc.)
- HTW Berlin serves German and English content
- Sample data shows mixed language:
  ```json
  "title": "FAQ Studies & Application"  // English
  "Bewerbungsfrist für Masterstudiengänge"  // German
  "BAföG-Antrag"  // German administrative term
  ```

**Why it hurts quality:**
- German queries get poor embeddings → low similarity scores
- Administrative terms (Immatrikulation, Rückmeldung, BAföG) not well-represented
- Cross-lingual queries fail (e.g., "Wie bewerbe ich mich?" won't match English docs well)

**Location:**
- Model loading: `hansdb/embeddings.py:16-52`
- Config: `config.yaml:22-24`

---

### Issue 3: No Re-Ranking or Query Refinement
**Severity: MEDIUM-HIGH**

**Evidence from code:**
```python
# hansdb/retrieval.py:13-92
def retrieve_top_k(...):
    # Single-stage retrieval: vector search only
    query = """
    WITH q AS (SELECT CAST(%s AS vector) AS v)
    SELECT ... (wc.embedding <=> q.v) AS score
    FROM web_chunks wc ...
    UNION ALL
    SELECT ... (qa.question_embedding <=> q.v) AS score
    FROM qa_pairs qa ...
    ORDER BY score ASC LIMIT %s
    """
    # No re-ranking, no query expansion, no hybrid search
```

**Problem:**
- Initial vector search is the final ranking
- No cross-encoder to refine relevance
- No BM25 or keyword fallback for exact matches
- No query expansion (synonyms, typos, related terms)

**Why it hurts quality:**
- Vector search may surface semantically similar but contextually wrong chunks
- Exact term matches (e.g., "May 31 deadline") might rank below vaguer semantic matches
- No second chance to correct poor initial retrieval

**Location:**
- Retrieval: `hansdb/retrieval.py:13-92`
- Orchestration: `hans_db_agents.py:179-184` (calls `retrieve_top_k` once, no post-processing)

---

### Issue 4: Oversized Chunks Losing Granularity
**Severity: MEDIUM-HIGH**

**Evidence from code:**
```yaml
# config.yaml:15-18
ingestion:
  min_chars: 400
  chunk_chars: 1800  # ← Very large
  chunk_overlap: 200
  skip_short: true
```

**Problem:**
- 1800 characters ≈ 300-400 words ≈ 2-3 dense paragraphs
- This is 2-3× larger than typical RAG chunks (600-800 chars)
- Large chunks create multiple issues:
  1. **Diluted relevance**: A chunk about "deadlines AND fees AND programs" will have mediocre similarity to any single query
  2. **Lost context**: User asks "deadline for CS Master's" → retrieves 1800-char chunk covering all programs
  3. **LLM confusion**: Llama 3 8B gets 6 × 1800 chars = ~10.8KB context, making it harder to find the needle

**Why it hurts quality:**
- Precision suffers: Chunks contain irrelevant information
- Recall suffers: Specific facts buried in large chunks get lower similarity scores
- LLM must parse more noise to find the answer

**Location:**
- Config: `config.yaml:15-18`
- Applied during ingestion: `scripts/build_content_db.py` (not visible)

---

### Issue 5: Weak LLM (Llama 3 8B) with Generic Prompting
**Severity: MEDIUM**

**Evidence from code:**
```python
# config.yaml:33-34
runtime:
  ollama_model: llama3:8b  # ← 8B parameter model

# hans_db_agents.py:149-168
def _build_system_prompt(self):
    return """You are HANS, the HTW Berlin Student Services Assistant...
Guidelines:
1. Use ONLY the provided context to answer questions
2. If information isn't in the context, say "I don't have this information"
...
"""
# No few-shot examples, no structured output format, no CoT
```

**Problem:**
1. **Model size**: 8B is on the smaller end for complex instruction-following
   - Compared to: Llama 3.1 70B, GPT-4, Claude 3.5 (orders of magnitude larger)

2. **Prompt engineering**:
   - No few-shot examples showing desired answer format
   - No chain-of-thought reasoning
   - No explicit bilingual handling ("answer in the query language")
   - No structured output (JSON, bullets, citations)

3. **No sampling control**:
   ```python
   # hans_db_agents.py:68-70
   payload = {
       "model": model,
       "prompt": prompt,
       "stream": False
       # ← No temperature, top_p, or other parameters
   }
   ```

**Why it hurts quality:**
- Smaller models prone to:
  - Hallucination despite "use ONLY context" instruction
  - Poor instruction adherence
  - Inconsistent formatting
- Generic prompts don't guide the model toward HTW-specific answer patterns
- Unknown sampling parameters mean unpredictable behavior

**Location:**
- Model: `config.yaml:34`
- Prompting: `hans_db_agents.py:149-213`
- API call: `hans_db_agents.py:64-88`

---

### Issue 6: Retrieval-Biased Confidence Scoring
**Severity: MEDIUM**

**Evidence from code:**
```python
# hans_db_agents.py:317-400
def _calculate_confidence(self, results, response):
    # Confidence weights:
    weights = {
        'avg_similarity': 0.35,      # Retrieval metric
        'top_score': 0.25,            # Retrieval metric
        'consistency': 0.15,          # Retrieval metric
        'source_quality': 0.15,       # Retrieval metric (>0.7 threshold)
        'response_length': 0.05,      # Response metric
        'specificity': 0.05           # Response metric (simple checks)
    }
    # 90% weight on retrieval, 10% on response
```

**Problem:**
- Confidence is 90% based on retrieval scores, 10% on response quality
- **Good retrieval ≠ good answer**:
  - Example: Retrieved 6 chunks about "deadlines" (high scores) → but LLM generates wrong deadline → still gets high confidence

- Specificity checks are superficial:
  ```python
  'http' in response.lower(),  # Any URL
  any(char.isdigit() for char in response),  # Any digit
  '@' in response,  # Any @ symbol
  ```
  - Doesn't verify URLs are HTW domains
  - Doesn't check if dates/numbers are contextually correct

**Why it hurts quality:**
- High confidence on incorrect answers misleads users
- No semantic validation (does answer actually address query?)
- No factual consistency check against context

**Location:**
- Confidence calculation: `hans_db_agents.py:317-400`
- Thresholds: `hans_db_agents.py:372-381`

---

### Issue 7: Fragile Source Citation via Regex
**Severity: LOW-MEDIUM**

**Evidence from code:**
```python
# hans_db_agents.py:285-315
def _post_process_sources(self, response, results):
    # Replace patterns like "(source web - 1)"
    pattern = r'\(source\s+web\s*-?\s*(\d+)\)'
    response = re.sub(pattern, replace_source_ref, response, flags=re.IGNORECASE)

    # Also handle format without parentheses
    pattern2 = r'source\s+web\s*-?\s*(\d+)'
    # ...
```

**Problem:**
- System prompt (line 163) says: "Always cite sources using actual URLs when available, **not numbered references**"
- But LLM often generates numbered references anyway → regex tries to fix it
- **Fragile**: If LLM uses different format, citations fail:
  - "According to [1]..."
  - "Source: HTW website..."
  - "See the application page"

**Why it hurts quality:**
- Citations may be missing or malformed
- User can't verify information source
- Reduces trust in system

**Location:**
- Post-processing: `hans_db_agents.py:285-315`
- System prompt instruction: `hans_db_agents.py:163`

---

### Issue 8: IVFFlat Index with Moderate Probe Setting
**Severity: LOW-MEDIUM**

**Evidence from code:**
```yaml
# config.yaml:39-41
database_tuning:
  ivfflat_probes: 10  # Range: 1-100+
```

**Problem:**
- IVFFlat is an approximate nearest neighbor index (trades accuracy for speed)
- `probes=10` is moderate: searches 10 of ~sqrt(n_vectors) clusters
- With only 175 chunks, index may not be optimized at all (IVFFlat works best with 100K+ vectors)
- **Lower probes = faster but lower recall**: May miss relevant chunks

**Why it hurts quality:**
- With tiny dataset (175 chunks), exact search would be fast anyway
- IVFFlat approximation may hurt without providing speed benefit
- No measurement of recall@k to validate quality

**Location:**
- Config: `config.yaml:40`
- Used by pgvector internally (not directly in Python code)

---

### Issue 9: Top-K=6 Not Validated
**Severity: LOW**

**Evidence from code:**
```yaml
# config.yaml:27-29
retrieval:
  top_k: 6  # ← No justification
```

**Problem:**
- `top_k=6` appears arbitrary (no experimentation cited)
- May be suboptimal:
  - Too few: Misses relevant context for complex queries
  - Too many: Introduces noise, costs LLM context window
- No adaptive strategy (simple queries need fewer chunks, complex queries need more)

**Why it hurts quality:**
- May retrieve insufficient context for multi-part questions
- OR may waste context window on low-relevance chunks

**Location:**
- Config: `config.yaml:28`
- Used in: `hans_db_agents.py:174`, `hansdb/retrieval.py:17`

---

## [3] OFF-SERVER / COLAB EXPERIMENT DESIGN

### 3.1 Objective

Create a standalone, reproducible experimental environment to:
1. Test alternative embedding models (multilingual E5, multilingual MiniLM)
2. Test alternative LLMs (Llama 3.1 70B, GPT-4, Claude)
3. Measure retrieval quality (Precision@K, MRR)
4. Measure end-to-end answer quality (human eval + automated metrics)
5. Iterate quickly without HTW server dependencies

---

### 3.2 Minimal Reproducible Setup

**Files to Extract:**
```
hans_experiment/
├── config.yaml                    # Copy and modify
├── hansdb/
│   ├── __init__.py
│   ├── embeddings.py              # Modify for swappable models
│   └── retrieval.py               # Keep vector search logic
├── experiment_data/               # NEW: Lightweight data snapshot
│   ├── sample_documents.json      # 20-50 representative docs
│   ├── sample_chunks.json         # Precomputed chunks + embeddings
│   └── test_queries.json          # 20-30 test queries + expected answers
├── experiment_runner.py           # NEW: Main experiment script
└── requirements.txt               # Minimal dependencies
```

**Dependencies (`requirements.txt`):**
```
# Core
sentence-transformers>=2.2.0
numpy>=1.24.0
pandas>=2.0.0

# Vector search (in-memory for experiments)
faiss-cpu>=1.7.4  # or chromadb, qdrant-client

# LLM clients
openai>=1.0.0
anthropic>=0.5.0
huggingface-hub>=0.19.0

# Optional: local LLM
# transformers>=4.35.0
# torch>=2.0.0
# bitsandbytes  # for quantization

# Utilities
tqdm
pyyaml
python-dotenv
```

---

### 3.3 Google Colab Notebook Outline

**Notebook: `hans_offserver_experiments.ipynb`**

#### Cell 1: Environment Setup
```python
# Install dependencies
!pip install -q sentence-transformers faiss-cpu openai anthropic pandas tqdm

# Clone repo (or upload files)
!git clone https://github.com/your-org/hans.git /content/hans
%cd /content/hans

# Or upload experiment_data/ directly
from google.colab import files
uploaded = files.upload()  # Upload experiment_data.zip
!unzip -q experiment_data.zip
```

#### Cell 2: Load Experimental Data
```python
import json
import pandas as pd
import numpy as np

# Load sample documents (subset of HTW content)
with open('experiment_data/sample_documents.json') as f:
    documents = json.load(f)  # List[{id, title, url, content, ...}]

# Load test queries (with ground truth answers)
with open('experiment_data/test_queries.json') as f:
    test_queries = json.load(f)
    # Format: [
    #   {
    #     "query": "What is the application deadline for Master's CS?",
    #     "expected_answer_contains": ["May 31", "winter semester"],
    #     "relevant_doc_ids": [12, 45],
    #     "category": "deadline"
    #   },
    #   ...
    # ]

print(f"Loaded {len(documents)} documents")
print(f"Loaded {len(test_queries)} test queries")
```

#### Cell 3: Embedding Model Comparison
```python
from sentence_transformers import SentenceTransformer, util

# Define models to test
EMBEDDING_MODELS = {
    "current": "BAAI/bge-base-en-v1.5",
    "multilingual_e5": "intfloat/multilingual-e5-base",
    "multilingual_minilm": "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
}

# Chunk documents (simulate ingestion)
def chunk_text(text, chunk_size=800, overlap=150):
    """Better chunking than 1800 chars"""
    chunks = []
    start = 0
    while start < len(text):
        end = start + chunk_size
        chunk = text[start:end]
        if chunk:
            chunks.append(chunk)
        start += chunk_size - overlap
    return chunks

# Prepare corpus
corpus_chunks = []
chunk_metadata = []  # Track which doc each chunk belongs to

for doc in documents:
    content = doc['content']
    doc_chunks = chunk_text(content, chunk_size=800, overlap=150)
    for i, chunk in enumerate(doc_chunks):
        corpus_chunks.append(chunk)
        chunk_metadata.append({
            'doc_id': doc['id'],
            'chunk_idx': i,
            'title': doc['title'],
            'url': doc.get('url')
        })

print(f"Created {len(corpus_chunks)} chunks from {len(documents)} documents")

# Embed corpus with each model
import faiss

embeddings_by_model = {}
indexes_by_model = {}

for model_name, model_id in EMBEDDING_MODELS.items():
    print(f"\n[{model_name}] Loading {model_id}...")
    model = SentenceTransformer(model_id)

    # Embed corpus
    print(f"[{model_name}] Embedding {len(corpus_chunks)} chunks...")
    embeddings = model.encode(
        corpus_chunks,
        normalize_embeddings=True,
        show_progress_bar=True,
        batch_size=32
    )

    # Create FAISS index
    dimension = embeddings.shape[1]
    index = faiss.IndexFlatIP(dimension)  # Inner product (cosine with normalized vectors)
    index.add(embeddings.astype('float32'))

    embeddings_by_model[model_name] = embeddings
    indexes_by_model[model_name] = index

    print(f"[{model_name}] Index ready: {index.ntotal} vectors, {dimension} dims")
```

#### Cell 4: Retrieval Quality Evaluation
```python
def evaluate_retrieval(model_name, index, model, test_queries, top_k=6):
    """
    Measure retrieval quality:
    - Precision@K: % of retrieved chunks that are relevant
    - Recall@K: % of relevant chunks that were retrieved
    - MRR: Mean Reciprocal Rank of first relevant chunk
    """
    results = []

    for test_case in test_queries:
        query = test_case['query']
        relevant_doc_ids = set(test_case.get('relevant_doc_ids', []))

        # Embed query
        query_emb = model.encode([query], normalize_embeddings=True)

        # Search
        scores, indices = index.search(query_emb.astype('float32'), top_k)

        # Evaluate
        retrieved_doc_ids = [chunk_metadata[idx]['doc_id'] for idx in indices[0]]

        # Precision@K
        relevant_retrieved = len(set(retrieved_doc_ids) & relevant_doc_ids)
        precision = relevant_retrieved / top_k if relevant_doc_ids else 0

        # Recall@K
        recall = relevant_retrieved / len(relevant_doc_ids) if relevant_doc_ids else 0

        # MRR: Find rank of first relevant result
        mrr = 0
        for rank, doc_id in enumerate(retrieved_doc_ids, 1):
            if doc_id in relevant_doc_ids:
                mrr = 1.0 / rank
                break

        results.append({
            'query': query,
            'precision': precision,
            'recall': recall,
            'mrr': mrr,
            'top_scores': scores[0].tolist()[:3]
        })

    # Aggregate metrics
    avg_precision = np.mean([r['precision'] for r in results])
    avg_recall = np.mean([r['recall'] for r in results])
    mean_mrr = np.mean([r['mrr'] for r in results])

    return {
        'model': model_name,
        'precision@k': avg_precision,
        'recall@k': avg_recall,
        'MRR': mean_mrr,
        'per_query': results
    }

# Evaluate all models
retrieval_results = {}

for model_name in EMBEDDING_MODELS.keys():
    print(f"\n{'='*60}")
    print(f"Evaluating: {model_name}")
    print('='*60)

    index = indexes_by_model[model_name]
    model = SentenceTransformer(EMBEDDING_MODELS[model_name])

    eval_results = evaluate_retrieval(model_name, index, model, test_queries, top_k=6)
    retrieval_results[model_name] = eval_results

    print(f"Precision@6: {eval_results['precision@k']:.3f}")
    print(f"Recall@6: {eval_results['recall@k']:.3f}")
    print(f"MRR: {eval_results['MRR']:.3f}")

# Summary comparison
import pandas as pd

summary_df = pd.DataFrame([
    {
        'Model': model_name,
        'Precision@6': res['precision@k'],
        'Recall@6': res['recall@k'],
        'MRR': res['MRR']
    }
    for model_name, res in retrieval_results.items()
])

print("\n" + "="*60)
print("RETRIEVAL QUALITY COMPARISON")
print("="*60)
print(summary_df.to_string(index=False))
```

#### Cell 5: LLM Response Generation (Swappable Models)
```python
import os
from typing import Optional

class LLMClient:
    """Abstract interface for LLM calls"""

    def generate(self, prompt: str, max_tokens: int = 500) -> str:
        raise NotImplementedError

class OpenAIClient(LLMClient):
    def __init__(self, model="gpt-4", api_key: Optional[str] = None):
        from openai import OpenAI
        self.client = OpenAI(api_key=api_key or os.getenv("OPENAI_API_KEY"))
        self.model = model

    def generate(self, prompt: str, max_tokens: int = 500) -> str:
        response = self.client.chat.completions.create(
            model=self.model,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=max_tokens,
            temperature=0.7
        )
        return response.choices[0].message.content

class AnthropicClient(LLMClient):
    def __init__(self, model="claude-3-5-sonnet-20241022", api_key: Optional[str] = None):
        from anthropic import Anthropic
        self.client = Anthropic(api_key=api_key or os.getenv("ANTHROPIC_API_KEY"))
        self.model = model

    def generate(self, prompt: str, max_tokens: int = 500) -> str:
        response = self.client.messages.create(
            model=self.model,
            max_tokens=max_tokens,
            messages=[{"role": "user", "content": prompt}]
        )
        return response.content[0].text

class HuggingFaceClient(LLMClient):
    """For local/HF Inference API models"""
    def __init__(self, model_id="meta-llama/Meta-Llama-3-8B-Instruct"):
        from transformers import pipeline
        self.pipe = pipeline(
            "text-generation",
            model=model_id,
            device_map="auto",  # Colab GPU
            max_new_tokens=500
        )

    def generate(self, prompt: str, max_tokens: int = 500) -> str:
        outputs = self.pipe(prompt, max_new_tokens=max_tokens, do_sample=True)
        return outputs[0]['generated_text']

# Configure LLM
# Option 1: API-based (recommended for experiments)
os.environ["OPENAI_API_KEY"] = "your-key-here"  # Or use Colab secrets
llm = OpenAIClient(model="gpt-4")

# Option 2: Open-source via Anthropic
# os.environ["ANTHROPIC_API_KEY"] = "your-key-here"
# llm = AnthropicClient(model="claude-3-5-sonnet-20241022")

# Option 3: Local HF model (requires GPU)
# llm = HuggingFaceClient(model_id="meta-llama/Meta-Llama-3.1-70B-Instruct")
```

#### Cell 6: End-to-End RAG Pipeline
```python
def rag_pipeline(
    query: str,
    embedding_model_name: str,
    llm_client: LLMClient,
    top_k: int = 6
) -> dict:
    """
    Full RAG pipeline: embed query → retrieve → generate answer
    """
    # Get embedding model and index
    model = SentenceTransformer(EMBEDDING_MODELS[embedding_model_name])
    index = indexes_by_model[embedding_model_name]

    # Embed query
    query_emb = model.encode([query], normalize_embeddings=True)

    # Retrieve top-k chunks
    scores, indices = index.search(query_emb.astype('float32'), top_k)

    retrieved_chunks = []
    for idx, score in zip(indices[0], scores[0]):
        chunk_text = corpus_chunks[idx]
        metadata = chunk_metadata[idx]
        retrieved_chunks.append({
            'text': chunk_text,
            'score': float(score),
            'title': metadata['title'],
            'url': metadata.get('url'),
            'doc_id': metadata['doc_id']
        })

    # Build context (same format as HANS)
    context_parts = []
    for i, chunk in enumerate(retrieved_chunks, 1):
        context_part = f"[Source {i}]\n"
        context_part += f"Title: {chunk['title']}\n"
        if chunk['url']:
            context_part += f"URL: {chunk['url']}\n"
        context_part += f"Content: {chunk['text']}\n\n"
        context_parts.append(context_part)

    context = "".join(context_parts)

    # Build prompt (improved version)
    system_prompt = """You are HANS, the HTW Berlin Student Services Assistant.

Guidelines:
1. Use ONLY the provided context to answer questions
2. If information isn't in the context, say "I don't have this information"
3. Cite sources by including the URL in your answer
4. Be specific with dates, deadlines, and requirements
5. Answer in the same language as the question (English or German)

Format your answer as:
- Direct answer (1-2 sentences)
- Details (if available)
- Sources: [list URLs]
"""

    full_prompt = f"""{system_prompt}

CONTEXT:
{context}

QUERY: {query}

ANSWER:"""

    # Generate response
    answer = llm_client.generate(full_prompt, max_tokens=500)

    return {
        'query': query,
        'answer': answer,
        'retrieved_chunks': retrieved_chunks,
        'embedding_model': embedding_model_name,
        'llm_model': llm_client.model if hasattr(llm_client, 'model') else 'unknown'
    }

# Test on sample queries
sample_queries = [
    "What are the application deadlines for Master's programs?",
    "Wie viel kostet ein Studium an der HTW?",
    "What are the German language requirements?"
]

for query in sample_queries:
    print(f"\n{'='*80}")
    print(f"QUERY: {query}")
    print('='*80)

    result = rag_pipeline(
        query=query,
        embedding_model_name="multilingual_e5",  # Test best model
        llm_client=llm,
        top_k=6
    )

    print(f"\nANSWER:\n{result['answer']}")
    print(f"\nTOP SOURCES:")
    for i, chunk in enumerate(result['retrieved_chunks'][:3], 1):
        print(f"  {i}. {chunk['title']} (score: {chunk['score']:.3f})")
```

#### Cell 7: Experiment Comparison Matrix
```python
# Compare combinations of embedding models + LLMs
experiment_configs = [
    {"embedding": "current", "llm": "gpt-4"},
    {"embedding": "multilingual_e5", "llm": "gpt-4"},
    {"embedding": "multilingual_e5", "llm": "claude-3-5-sonnet"},
]

results_matrix = []

for config in experiment_configs:
    print(f"\nTesting: {config['embedding']} + {config['llm']}")

    llm_client = OpenAIClient(model=config['llm']) if 'gpt' in config['llm'] else AnthropicClient(model=config['llm'])

    for test_case in test_queries[:5]:  # Test on first 5
        result = rag_pipeline(
            query=test_case['query'],
            embedding_model_name=config['embedding'],
            llm_client=llm_client,
            top_k=6
        )

        # Manual quality rating (placeholder - would be human-evaluated)
        quality_score = evaluate_answer_quality(
            result['answer'],
            test_case['expected_answer_contains']
        )

        results_matrix.append({
            'embedding_model': config['embedding'],
            'llm_model': config['llm'],
            'query': test_case['query'],
            'answer': result['answer'],
            'quality_score': quality_score,
            'top_retrieval_score': result['retrieved_chunks'][0]['score']
        })

# Save results
results_df = pd.DataFrame(results_matrix)
results_df.to_csv('experiment_results.csv', index=False)
print("\nResults saved to experiment_results.csv")
```

---

### 3.4 Data Preparation Script

**Create `prepare_experiment_data.py` (run on HTW server once):**

```python
#!/usr/bin/env python3
"""
Extract sample data from live HANS database for off-server experiments
Run this on the HTW server with access to the database
"""

import psycopg
import json
import os
from hansdb.conn import load_config, get_db_connection

def extract_sample_data(output_dir="experiment_data", n_docs=50):
    """Extract representative sample of documents and chunks"""
    config = load_config()
    conn = get_db_connection(config)

    os.makedirs(output_dir, exist_ok=True)

    # Extract documents
    with conn.cursor() as cur:
        cur.execute("""
            SELECT id, title, url, source_type, source_file, metadata
            FROM documents
            LIMIT %s
        """, (n_docs,))

        documents = []
        for row in cur.fetchall():
            documents.append({
                'id': row[0],
                'title': row[1],
                'url': row[2],
                'source_type': row[3],
                'source_file': row[4],
                'metadata': row[5]
            })

    # Extract chunks for these documents
    doc_ids = [doc['id'] for doc in documents]

    with conn.cursor() as cur:
        cur.execute("""
            SELECT wc.id, wc.document_id, wc.text, d.title, d.url
            FROM web_chunks wc
            JOIN documents d ON d.id = wc.document_id
            WHERE wc.document_id = ANY(%s)
        """, (doc_ids,))

        chunks = []
        for row in cur.fetchall():
            chunks.append({
                'id': row[0],
                'document_id': row[1],
                'text': row[2],
                'doc_title': row[3],
                'doc_url': row[4]
            })

    # Save
    with open(f"{output_dir}/sample_documents.json", 'w') as f:
        json.dump(documents, f, indent=2)

    with open(f"{output_dir}/sample_chunks.json", 'w') as f:
        json.dump(chunks, f, indent=2)

    print(f"Extracted {len(documents)} documents, {len(chunks)} chunks")
    print(f"Saved to {output_dir}/")

    conn.close()

if __name__ == "__main__":
    extract_sample_data()
```

---

### 3.5 Gotchas & Mitigation

**Gotcha 1: Database Connection Hardcoded**
- **Issue**: `hansdb/conn.py` assumes PostgreSQL connection
- **Solution**: `experiment_runner.py` uses in-memory FAISS index instead

**Gotcha 2: Ollama Client Hardcoded**
- **Issue**: `hans_db_agents.py::OllamaClient` is tightly coupled to HTW server
- **Solution**: `LLMClient` abstraction (Cell 5) allows swapping API providers

**Gotcha 3: Large Model Downloads**
- **Issue**: Colab session may timeout downloading 70B models
- **Solution**: Use API-based models (OpenAI, Anthropic) for experiments, not local

**Gotcha 4: Embedding Model Cache**
- **Issue**: SentenceTransformer downloads models to `~/.cache/`
- **Solution**: Colab persists cache across cells, but clear if switching accounts

**Gotcha 5: Manual Evaluation Required**
- **Issue**: Automated metrics (BLEU, ROUGE) don't capture RAG quality well
- **Solution**: Include `evaluate_answer_quality()` stub for human ratings

---

## [4] RECOMMENDED MODEL & CONFIG CHANGES (WITH FILE PATHS)

### 4.1 Embedding Model Improvements

#### Change 1A: Add Multilingual Embedding Support
**Priority: HIGH**

**Recommended Models:**

1. **`intfloat/multilingual-e5-base`** (PRIMARY RECOMMENDATION)
   - **Why**:
     - Trained on 100+ languages including English and German
     - State-of-the-art on multilingual MTEB benchmark
     - 768 dimensions (same as current BGE)
     - Instruction-aware embeddings (can use query prefixes)
   - **Trade-offs**: Slightly slower than BGE (~10-15%)

2. **`sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2`** (LIGHTWEIGHT ALTERNATIVE)
   - **Why**:
     - Smaller model (120M params vs 278M for E5)
     - Faster inference
     - Still good multilingual performance
   - **Trade-offs**: Lower accuracy than E5, only 384 dimensions

3. **`Alibaba-NLP/gte-multilingual-base`** (EXPERIMENTAL)
   - **Why**: Newer model (2024), excellent MTEB scores
   - **Trade-offs**: Less tested, may require fine-tuning

**Code Changes:**

**File: `config.yaml`**
```yaml
# Add new section for model options
model:
  # Default embedding model
  embedding_model: intfloat/multilingual-e5-base  # ← CHANGE
  embedding_dim: 768  # ← Keep same

  # Alternative models (can be selected via env var)
  embedding_model_options:
    multilingual_e5: intfloat/multilingual-e5-base
    bge_english: BAAI/bge-base-en-v1.5
    multilingual_minilm: sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2
```

**File: `hansdb/embeddings.py`**
```python
# Lines 16-52: Modify get_embedding_model()

def get_embedding_model(model_name: str = None) -> SentenceTransformer:
    """
    Get or initialize the embedding model (singleton pattern) with proxy support

    Args:
        model_name: Name of the sentence-transformer model. If None, uses config default.

    Returns:
        Initialized SentenceTransformer model
    """
    global _embedding_model

    # Allow runtime override via env var
    if model_name is None:
        model_name = os.getenv('HANS_EMBEDDING_MODEL', "intfloat/multilingual-e5-base")

    if _embedding_model is None or _embedding_model.model_card_data.model_id != model_name:
        logger.info(f"Loading embedding model: {model_name}")

        # Configure proxy environment for model downloads
        original_proxies = {}
        if os.getenv('HTTP_PROXY'):
            original_proxies['http_proxy'] = os.environ.get('http_proxy')
            os.environ['http_proxy'] = os.getenv('HTTP_PROXY')
        if os.getenv('HTTPS_PROXY'):
            original_proxies['https_proxy'] = os.environ.get('https_proxy')
            os.environ['https_proxy'] = os.getenv('HTTPS_PROXY')

        try:
            _embedding_model = SentenceTransformer(model_name)

            # ADD: Query instruction for E5 models
            if "e5" in model_name.lower():
                logger.info("E5 model detected: will use query prefix 'query: ' for searches")

            logger.info(f"Embedding model loaded. Dimension: {_embedding_model.get_sentence_embedding_dimension()}")
        finally:
            # Restore original proxy settings
            for key, value in original_proxies.items():
                if value is None:
                    os.environ.pop(key, None)
                else:
                    os.environ[key] = value

    return _embedding_model

# NEW: Add query prefix for E5 models
def embed_single_text(text: str, model_name: str = None, is_query: bool = False) -> np.ndarray:
    """
    Generate L2-normalized embedding for a single text

    Args:
        text: Text string to embed
        model_name: Name of the embedding model to use
        is_query: If True and using E5 model, adds "query: " prefix

    Returns:
        L2-normalized embedding vector
    """
    model = get_embedding_model(model_name)

    # Add instruction prefix for E5 models
    if is_query and "e5" in str(model.model_card_data.model_id).lower():
        text = f"query: {text}"

    embeddings = embed_and_normalize([text], model_name)
    return embeddings[0]
```

**File: `hansdb/retrieval.py`**
```python
# Line 32: Update embed_single_text call

def retrieve_top_k(
    conn: psycopg.Connection,
    query_text: str,
    top_k: int = 6,
    model_name: str = None  # ← Allow None to use default
) -> List[Dict[str, Any]]:
    """
    Unified top-k retrieval that searches both web chunks and Q&A pairs
    """
    # Generate normalized query embedding WITH query prefix if E5
    query_embedding = embed_single_text(query_text, model_name, is_query=True)  # ← ADD is_query

    # Rest unchanged
    # ...
```

**Migration Steps:**
1. Re-embed all documents with new model:
   ```bash
   # On HTW server
   python scripts/build_content_db.py --force --embedding-model intfloat/multilingual-e5-base
   ```
2. Test retrieval quality on dev set
3. If dimension changed (e.g., 384 for MiniLM), update pgvector column:
   ```sql
   -- Only needed if changing dimensions
   ALTER TABLE web_chunks ALTER COLUMN embedding TYPE vector(384);
   ```

---

#### Change 1B: Add Embedding Model Benchmarking
**Priority: MEDIUM**

**New File: `scripts/benchmark_embeddings.py`**
```python
#!/usr/bin/env python3
"""
Compare retrieval quality across embedding models on test set
"""

import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent))

from hansdb.embeddings import embed_single_text, get_embedding_model
from hansdb.conn import load_config, get_db_connection
from hansdb.retrieval import get_retrieval_stats
import psycopg
import numpy as np

MODELS_TO_TEST = [
    "BAAI/bge-base-en-v1.5",
    "intfloat/multilingual-e5-base",
    "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
]

TEST_QUERIES = [
    ("What are admission requirements?", "EN"),
    ("Wie bewerbe ich mich?", "DE"),
    ("BAföG application deadline", "MIXED"),
    ("Tuition fees", "EN"),
    ("Semestertermine", "DE")
]

def benchmark_model(model_name: str, conn: psycopg.Connection):
    """Test retrieval quality for one model"""
    print(f"\n{'='*60}")
    print(f"Testing: {model_name}")
    print('='*60)

    results = []

    for query, lang in TEST_QUERIES:
        # Embed query
        query_emb = embed_single_text(query, model_name, is_query=True)
        query_vector = query_emb.tolist()

        # Retrieve (simplified - just web_chunks)
        with conn.cursor() as cur:
            cur.execute("""
                SELECT wc.text, (wc.embedding <=> %s) AS score
                FROM web_chunks wc
                ORDER BY wc.embedding <=> %s
                LIMIT 3
            """, (query_vector, query_vector))

            top_results = cur.fetchall()

        # Print top result
        if top_results:
            print(f"\n[{lang}] {query}")
            print(f"  Top score: {top_results[0][1]:.4f}")
            print(f"  Snippet: {top_results[0][0][:100]}...")

            results.append({
                'query': query,
                'lang': lang,
                'top_score': top_results[0][1],
                'avg_top3_score': np.mean([r[1] for r in top_results])
            })

    avg_score = np.mean([r['top_score'] for r in results])
    print(f"\nAverage top-1 score: {avg_score:.4f}")

    return results

if __name__ == "__main__":
    config = load_config()
    conn = get_db_connection(config)

    all_results = {}
    for model in MODELS_TO_TEST:
        all_results[model] = benchmark_model(model, conn)

    print("\n" + "="*60)
    print("SUMMARY")
    print("="*60)
    for model, results in all_results.items():
        avg = np.mean([r['top_score'] for r in results])
        print(f"{model}: {avg:.4f}")

    conn.close()
```

**Usage:**
```bash
python scripts/benchmark_embeddings.py
```

---

### 4.2 LLM Improvements

#### Change 2A: Abstract LLM Client Interface
**Priority: HIGH**

**Why**: Current code hard-codes Ollama client (`hans_db_agents.py:33-88`). Need clean abstraction to swap models.

**New File: `hansdb/llm_client.py`**
```python
"""
Unified LLM client interface supporting multiple providers
"""

import os
import logging
from abc import ABC, abstractmethod
from typing import Dict, Optional

logger = logging.getLogger(__name__)

class BaseLLMClient(ABC):
    """Abstract base class for LLM providers"""

    @abstractmethod
    async def generate(
        self,
        prompt: str,
        max_tokens: int = 500,
        temperature: float = 0.7,
        **kwargs
    ) -> str:
        """Generate response from prompt"""
        pass

    @abstractmethod
    def get_model_name(self) -> str:
        """Return model identifier"""
        pass


class OllamaClient(BaseLLMClient):
    """Ollama API client (original HANS implementation)"""

    def __init__(self, base_url: str, model: str = "llama3:8b", timeout: int = 300):
        self.base_url = base_url.rstrip('/')
        self.model = model
        self.timeout = timeout
        self._session = None

    async def __aenter__(self):
        import aiohttp
        ssl_context = False  # Disable SSL verification (HTW server)
        self._session = aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(total=self.timeout),
            connector=aiohttp.TCPConnector(ssl=ssl_context),
            trust_env=True
        )
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self._session:
            await self._session.close()

    async def generate(self, prompt: str, max_tokens: int = 500, temperature: float = 0.7, **kwargs) -> str:
        url = f"{self.base_url}/api/generate"
        payload = {
            "model": self.model,
            "prompt": prompt,
            "stream": False,
            "options": {
                "temperature": temperature,
                "num_predict": max_tokens
            }
        }

        try:
            async with self._session.post(url, json=payload) as response:
                if response.status == 200:
                    result = await response.json()
                    return result.get("response", "")
                else:
                    error_text = await response.text()
                    logger.error(f"Ollama generation failed: {response.status} - {error_text}")
                    return ""
        except Exception as e:
            logger.error(f"Ollama generation error: {e}")
            return ""

    def get_model_name(self) -> str:
        return f"ollama/{self.model}"


class OpenAIClient(BaseLLMClient):
    """OpenAI API client"""

    def __init__(self, model: str = "gpt-4", api_key: Optional[str] = None):
        try:
            from openai import AsyncOpenAI
        except ImportError:
            raise ImportError("openai package not installed. Run: pip install openai")

        self.client = AsyncOpenAI(api_key=api_key or os.getenv("OPENAI_API_KEY"))
        self.model = model

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.client.close()

    async def generate(self, prompt: str, max_tokens: int = 500, temperature: float = 0.7, **kwargs) -> str:
        try:
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=max_tokens,
                temperature=temperature
            )
            return response.choices[0].message.content
        except Exception as e:
            logger.error(f"OpenAI generation error: {e}")
            return ""

    def get_model_name(self) -> str:
        return f"openai/{self.model}"


class AnthropicClient(BaseLLMClient):
    """Anthropic Claude API client"""

    def __init__(self, model: str = "claude-3-5-sonnet-20241022", api_key: Optional[str] = None):
        try:
            from anthropic import AsyncAnthropic
        except ImportError:
            raise ImportError("anthropic package not installed. Run: pip install anthropic")

        self.client = AsyncAnthropic(api_key=api_key or os.getenv("ANTHROPIC_API_KEY"))
        self.model = model

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.client.close()

    async def generate(self, prompt: str, max_tokens: int = 500, temperature: float = 0.7, **kwargs) -> str:
        try:
            response = await self.client.messages.create(
                model=self.model,
                max_tokens=max_tokens,
                temperature=temperature,
                messages=[{"role": "user", "content": prompt}]
            )
            return response.content[0].text
        except Exception as e:
            logger.error(f"Anthropic generation error: {e}")
            return ""

    def get_model_name(self) -> str:
        return f"anthropic/{self.model}"


def create_llm_client(config: Dict) -> BaseLLMClient:
    """Factory function to create LLM client from config"""
    provider = config.get('provider', 'ollama')

    if provider == 'ollama':
        return OllamaClient(
            base_url=config['ollama_base_url'],
            model=config.get('ollama_model', 'llama3:8b'),
            timeout=config.get('ollama_timeout', 300)
        )
    elif provider == 'openai':
        return OpenAIClient(
            model=config.get('model', 'gpt-4'),
            api_key=config.get('api_key')
        )
    elif provider == 'anthropic':
        return AnthropicClient(
            model=config.get('model', 'claude-3-5-sonnet-20241022'),
            api_key=config.get('api_key')
        )
    else:
        raise ValueError(f"Unknown LLM provider: {provider}")
```

**File: `config.yaml` (UPDATE)**
```yaml
# Lines 31-36: Expand runtime config

runtime:
  # LLM provider: 'ollama', 'openai', 'anthropic'
  llm_provider: ollama  # ← NEW: Make configurable

  # Ollama settings (when provider = 'ollama')
  ollama_base_url: https://f2ki-h100-1.f2.htw-berlin.de:11435
  ollama_model: llama3:8b
  ollama_timeout: 300
  verify_ssl: false

  # OpenAI settings (when provider = 'openai')
  # openai_model: gpt-4
  # openai_api_key: ${OPENAI_API_KEY}  # From env

  # Anthropic settings (when provider = 'anthropic')
  # anthropic_model: claude-3-5-sonnet-20241022
  # anthropic_api_key: ${ANTHROPIC_API_KEY}  # From env

  # Generation parameters
  temperature: 0.7
  max_tokens: 500
```

**File: `hans_db_agents.py` (REFACTOR)**
```python
# Lines 33-88: REPLACE OllamaClient class

# OLD: Remove local OllamaClient class
# NEW: Import from hansdb.llm_client

from hansdb.llm_client import create_llm_client, BaseLLMClient

# Lines 90-118: Update DatabaseRAGAgent.__init__

class DatabaseRAGAgent:
    """Database-backed RAG agent for HTW Berlin student services"""

    def __init__(self, config: dict):
        self.config = config
        self.db_conn = None
        self.retrieval_config = config['retrieval']
        self.runtime_config = config['runtime']

        # Initialize database connection
        self._initialize_database()

        # NEW: Create LLM client
        self.llm_client = create_llm_client(self.runtime_config)
        logger.info(f"LLM client initialized: {self.llm_client.get_model_name()}")

# Lines 215-228: Update LLM call in process_query()

    async def process_query(self, query: str) -> Dict[str, Any]:
        """Process a user query and return response with metadata"""
        try:
            # ... (retrieval code unchanged)

            # Generate response using LLM client
            async with self.llm_client as llm:
                response = await llm.generate(
                    full_prompt,
                    max_tokens=self.runtime_config.get('max_tokens', 500),
                    temperature=self.runtime_config.get('temperature', 0.7)
                )

            # ... (post-processing unchanged)
```

---

#### Change 2B: Improve System Prompt
**Priority: HIGH**

**File: `hans_db_agents.py`**
```python
# Lines 149-168: REPLACE _build_system_prompt()

def _build_system_prompt(self) -> str:
    """Build improved system prompt for the LLM"""
    return """You are HANS, the HTW Berlin Student Services Assistant. You help students with:
- Application procedures and deadlines
- Academic calendar and semester dates
- Study programs and requirements
- Campus facilities and services
- International student support
- Financial aid (BAföG) and scholarships
- Administrative processes

GUIDELINES:
1. Use ONLY the provided context to answer questions - do NOT use external knowledge
2. If information isn't in the context, say "I don't have this information in my current knowledge base"
3. Answer in the SAME LANGUAGE as the question (English or German)
4. Be specific with dates, deadlines, and requirements
5. Cite sources by mentioning the URL (not "source 1")
6. If the context contains contradictory information, acknowledge it

OUTPUT FORMAT:
- Start with a direct answer (1-2 sentences)
- Provide details if available
- Include relevant URLs at the end
- Use clear formatting (bullet points for lists)

EXAMPLES:

Query: "What is the application deadline for Master's programs?"
Good Answer: "The application deadline for Master's programs at HTW Berlin is typically May 31 for the winter semester and November 30 for the summer semester. However, specific programs may have different deadlines, so please check the program page for exact dates. More information: https://www.htw-berlin.de/en/studies/application/"

Query: "Wie viel kostet ein Studium an der HTW?"
Good Answer: "An der HTW Berlin zahlen Sie pro Semester eine Semestergebühr, aber keine Studiengebühren. Die Semestergebühr beträgt ca. 300-350 Euro und deckt das Semesterticket und administrative Kosten ab. Weitere Informationen: https://www.htw-berlin.de/studium/organisation/semesterbeitrag/"

Context will be provided for each query. Base your responses solely on this context."""
```

---

### 4.3 Retrieval & Chunking Improvements

#### Change 3A: Optimize Chunk Size
**Priority: HIGH**

**File: `config.yaml`**
```yaml
# Lines 15-18: Update chunking config

ingestion:
  min_chars: 300         # ← Reduce from 400
  chunk_chars: 800       # ← REDUCE from 1800 (key change!)
  chunk_overlap: 150     # ← Reduce from 200 (proportional)
  skip_short: false      # ← DISABLE to keep more content
```

**Rationale:**
- 800 chars ≈ 150-200 words ≈ 1-2 paragraphs
- Smaller chunks = higher precision (less noise per chunk)
- More chunks from same content = better recall (more chances to match)

**Migration:**
```bash
# Re-ingest with new chunking
python scripts/build_content_db.py --force --chunk-size 800 --chunk-overlap 150
```

---

#### Change 3B: Increase Top-K and Add Re-Ranking
**Priority: MEDIUM-HIGH**

**File: `config.yaml`**
```yaml
# Lines 27-29: Update retrieval config

retrieval:
  top_k: 12              # ← INCREASE from 6
  distance: cosine
  rerank_top_n: 6        # ← NEW: Re-rank to 6 final chunks
  use_reranking: true    # ← NEW: Enable re-ranking
```

**New File: `hansdb/reranking.py`**
```python
"""
Cross-encoder re-ranking for improved retrieval precision
"""

import logging
from typing import List, Dict
from sentence_transformers import CrossEncoder

logger = logging.getLogger(__name__)

_reranker_model = None

def get_reranker(model_name: str = "cross-encoder/ms-marco-MiniLM-L-6-v2"):
    """Get or initialize cross-encoder model (singleton)"""
    global _reranker_model

    if _reranker_model is None:
        logger.info(f"Loading reranker model: {model_name}")
        _reranker_model = CrossEncoder(model_name)
        logger.info("Reranker model loaded")

    return _reranker_model

def rerank_results(
    query: str,
    results: List[Dict],
    top_n: int = 6,
    model_name: str = "cross-encoder/ms-marco-MiniLM-L-6-v2"
) -> List[Dict]:
    """
    Re-rank retrieval results using cross-encoder

    Args:
        query: User query
        results: List of retrieval results with 'content' field
        top_n: Number of results to return after re-ranking
        model_name: Cross-encoder model name

    Returns:
        Re-ranked results (top_n items)
    """
    if not results:
        return results

    reranker = get_reranker(model_name)

    # Prepare (query, document) pairs
    pairs = [(query, result['content']) for result in results]

    # Get relevance scores
    scores = reranker.predict(pairs)

    # Add rerank scores to results
    for result, score in zip(results, scores):
        result['rerank_score'] = float(score)
        result['original_score'] = result['score']  # Keep vector score

    # Sort by rerank score and return top_n
    reranked = sorted(results, key=lambda x: x['rerank_score'], reverse=True)

    logger.info(f"Re-ranked {len(results)} results → returning top {top_n}")
    return reranked[:top_n]
```

**File: `hans_db_agents.py`**
```python
# Add import at top
from hansdb.reranking import rerank_results

# Lines 179-184: Update retrieval in process_query()

    async def process_query(self, query: str) -> Dict[str, Any]:
        """Process a user query and return response with metadata"""
        try:
            # Retrieve relevant content from database
            initial_top_k = self.retrieval_config.get('top_k', 12)  # ← Get more initially
            model_name = self.config['model']['embedding_model']

            logger.info(f"Retrieving top {initial_top_k} results for query: {query[:50]}...")

            results = retrieve_top_k(
                self.db_conn,
                query,
                top_k=initial_top_k,
                model_name=model_name
            )

            # NEW: Re-rank if enabled
            if self.retrieval_config.get('use_reranking', False):
                rerank_top_n = self.retrieval_config.get('rerank_top_n', 6)
                logger.info(f"Re-ranking to top {rerank_top_n}")
                results = rerank_results(query, results, top_n=rerank_top_n)

            # Rest unchanged
            # ...
```

**Update `requirements.txt`:**
```
sentence-transformers>=2.2.0  # Already present
# Add for re-ranking:
# (CrossEncoder included in sentence-transformers)
```

---

### 4.4 Prioritized TODO Checklist

#### 🔴 HIGH PRIORITY (Do First)

- [ ] **[CRITICAL] Re-ingest data with smaller chunks** (800 chars, Issue #4)
  - File: `config.yaml` lines 15-18
  - Script: `python scripts/build_content_db.py --force --chunk-size 800`
  - Impact: +30-40% retrieval precision expected
  - Time: 2-4 hours (re-embedding)

- [ ] **[CRITICAL] Switch to multilingual embedding model** (Issue #2)
  - File: `hansdb/embeddings.py` lines 16-97
  - File: `config.yaml` line 23
  - Change: `BAAI/bge-base-en-v1.5` → `intfloat/multilingual-e5-base`
  - Impact: +50-60% German query quality expected
  - Time: 3-5 hours (code + re-embedding)

- [ ] **[HIGH] Abstract LLM client interface** (Issue #5)
  - New file: `hansdb/llm_client.py`
  - Modify: `hans_db_agents.py` lines 33-88, 215-228
  - Impact: Enables A/B testing with better models
  - Time: 2-3 hours

- [ ] **[HIGH] Improve system prompt** (Issue #5)
  - File: `hans_db_agents.py` lines 149-168
  - Add: Few-shot examples, bilingual instructions, structured output
  - Impact: +20-30% answer quality (especially format consistency)
  - Time: 1 hour

#### 🟡 MEDIUM PRIORITY (Do Next)

- [ ] **[MEDIUM] Add re-ranking layer** (Issue #3)
  - New file: `hansdb/reranking.py`
  - Modify: `hans_db_agents.py` lines 179-184
  - Config: `config.yaml` add reranking section
  - Impact: +15-20% precision
  - Time: 2-3 hours

- [ ] **[MEDIUM] Increase retrieval top_k to 12** (Issue #9)
  - File: `config.yaml` line 28
  - Change: `top_k: 6` → `top_k: 12`
  - Impact: +10% recall (if re-ranking enabled)
  - Time: 5 minutes + testing

- [ ] **[MEDIUM] Add embedding model benchmarking** (Issue #2)
  - New file: `scripts/benchmark_embeddings.py`
  - Impact: Data-driven model selection
  - Time: 2 hours

- [ ] **[MEDIUM] Create Colab experiment notebook** (Section 3)
  - New file: `experiments/hans_offserver_experiments.ipynb`
  - Impact: Fast iteration, API model testing
  - Time: 3-4 hours

#### 🟢 LOW PRIORITY (Nice to Have)

- [ ] **[LOW] Add temperature/sampling controls** (Issue #5)
  - File: `hansdb/llm_client.py` (already in proposed changes)
  - File: `config.yaml` add generation params
  - Impact: +5% consistency
  - Time: 30 minutes

- [ ] **[LOW] Improve confidence scoring** (Issue #6)
  - File: `hans_db_agents.py` lines 317-400
  - Add: Semantic similarity check (answer vs query)
  - Impact: Better confidence calibration
  - Time: 2-3 hours

- [ ] **[LOW] Optimize IVFFlat probes** (Issue #8)
  - File: `config.yaml` line 40
  - Experiment: `ivfflat_probes: [5, 10, 20, 50]`
  - Impact: Marginal (dataset too small)
  - Time: 1 hour

- [ ] **[LOW] Fix source citation regex** (Issue #7)
  - File: `hans_db_agents.py` lines 285-315
  - Improve: More robust URL extraction
  - Impact: Better citation reliability
  - Time: 1 hour

---

### 4.5 Estimated Impact Summary

| Change | Impact | Effort | Priority |
|--------|--------|--------|----------|
| Smaller chunks (800 chars) | 🔥🔥🔥 Very High | Medium | 🔴 Critical |
| Multilingual embeddings | 🔥🔥🔥 Very High | Medium | 🔴 Critical |
| LLM client abstraction | 🔥🔥 High | Low | 🔴 High |
| Improved prompts | 🔥🔥 High | Low | 🔴 High |
| Re-ranking layer | 🔥 Medium | Medium | 🟡 Medium |
| Increase top-k | 🔥 Medium | Very Low | 🟡 Medium |
| Colab experiments | 🔥 Medium | High | 🟡 Medium |
| Better confidence | 🔥 Low-Medium | Medium | 🟢 Low |

---

### 4.6 Recommended Experimentation Sequence

**Week 1: Foundation (Off-Server)**
1. Create Colab notebook with sample data
2. Test 3 embedding models (BGE, E5, MiniLM)
3. Test 2 LLMs (GPT-4, Claude 3.5)
4. Document baseline metrics

**Week 2: Quick Wins (On-Server)**
1. Switch to multilingual-e5-base
2. Re-chunk data to 800 chars
3. Improve system prompt
4. Deploy and measure

**Week 3: Advanced Features (On-Server)**
1. Implement LLM abstraction
2. Add re-ranking layer
3. A/B test configurations
4. Collect user feedback

**Week 4: Optimization**
1. Tune hyperparameters (top-k, temperature)
2. Fix edge cases
3. Create evaluation dashboard
4. Document findings

---

**END OF ANALYSIS**

This comprehensive analysis provides:
1. ✅ Code-grounded architecture understanding
2. ✅ Specific quality issues with file paths
3. ✅ Concrete Colab experiment design
4. ✅ Prioritized, actionable changes with code samples

Ready for implementation and professor review.
