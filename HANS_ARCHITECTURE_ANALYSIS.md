# HANS Architecture & Response Quality Analysis

**Document for:** Professor Review
**Prepared:** November 2025
**System:** HTW Berlin Student Services Assistant (HANS)
**Current Status:** Live deployment with quality concerns

---

## Executive Summary

HANS is a Retrieval-Augmented Generation (RAG) system designed to answer student inquiries about HTW Berlin services. The system uses:
- **PostgreSQL + pgvector** for vector storage
- **BAAI/bge-base-en-v1.5** for text embeddings (768-dimensional)
- **Llama 3 8B** for response generation
- **174 web documents** + **175 text chunks** + **4 Q&A pairs** as knowledge base

**Current Challenge:** Response quality issues requiring investigation across multiple components.

---

## 1. System Architecture Overview

### 1.1 High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                         USER QUERY                              │
└────────────────────────┬────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────────┐
│                   HANS GUI / API SERVER                         │
│  - FastAPI backend (api_server.py)                              │
│  - Tkinter GUI client (htw_assistant_api_gui.py)                │
│  - SSH Tunnel for remote access                                 │
└────────────────────────┬────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────────┐
│                   RAG ORCHESTRATION LAYER                       │
│  (hans_db_agents.py - DatabaseRAGAgent)                         │
│                                                                  │
│  1. Query Embedding                                             │
│  2. Retrieval Coordination                                      │
│  3. Context Building                                            │
│  4. LLM Prompting                                               │
│  5. Confidence Scoring                                          │
└─────┬───────────────────────────┬───────────────────────────────┘
      │                           │
      │ Embed Query               │ Generate Response
      │                           │
      ▼                           ▼
┌──────────────────┐    ┌──────────────────────────┐
│  EMBEDDING MODEL │    │      LLM (Ollama)        │
│  BAAI/bge-base   │    │     Llama 3 (8B)         │
│  768-dim vectors │    │  Remote H100 cluster     │
└────────┬─────────┘    └──────────────────────────┘
         │
         │ Vector similarity search
         ▼
┌─────────────────────────────────────────────────────────────────┐
│               POSTGRESQL + PGVECTOR DATABASE                    │
│                                                                  │
│  Tables:                                                         │
│  • documents (174 entries)      - Source metadata               │
│  • web_chunks (175 entries)     - Text chunks + embeddings      │
│  • qa_pairs (4 entries)         - Q&A from Excel + embeddings   │
│                                                                  │
│  Vector Index: IVFFlat (cosine distance)                        │
└─────────────────────────────────────────────────────────────────┘
                         ▲
                         │
                         │ Populated from
                         │
┌─────────────────────────────────────────────────────────────────┐
│                    DATA INGESTION PIPELINE                      │
│                                                                  │
│  Sources:                                                        │
│  • 17 JSON files (HTW website scrapes)                          │
│  • 1 Excel file (Q&A training data)                             │
│                                                                  │
│  Processing:                                                     │
│  • Text chunking (1800 chars, 200 overlap)                      │
│  • Embedding generation                                         │
│  • Database insertion                                           │
└─────────────────────────────────────────────────────────────────┘
```

---

## 2. Component Analysis

### 2.1 Data Ingestion Layer

**Location:** `scripts/build_content_db.py` (referenced but not visible in current workspace)

**Current Configuration** (from `config.yaml`):
```yaml
ingestion:
  min_chars: 400          # Minimum chunk size
  chunk_chars: 1800       # Target chunk size
  chunk_overlap: 200      # Overlap between chunks
  skip_short: true        # Skip chunks below minimum
```

**Data Sources:**

1. **Web Scrapes** (17 JSON files):
   - Source: HTW Berlin website
   - Structure: URL, title, main_content, contacts, dates_deadlines, requirements, procedures, links
   - Example: `faq.json`, `student_services_backup.json`, `summary.json`
   - Total documents: 174
   - Total chunks: 175

2. **Excel Q&A Data**:
   - Source: `HANS - Training Email Data.xlsx`
   - Structure: Question, Answer, Tags
   - Total pairs: 4 (⚠️ **Very small dataset**)

**⚠️ Potential Issues:**
1. **Minimal Q&A data**: Only 4 Q&A pairs is insufficient for training/reference
2. **Chunk size**: 1800 characters may be too large, losing granularity
3. **Overlap**: 200 characters overlap might miss context boundaries
4. **Web data quality**: Scraped web content may contain navigation elements, boilerplate text
5. **Data freshness**: No indication of when data was last updated

---

### 2.2 Embedding Model

**Model:** BAAI/bge-base-en-v1.5
**Dimensions:** 768
**Type:** Sentence Transformer (BERT-based)
**Language:** Primarily English-trained

**Strengths:**
- ✅ State-of-the-art for English semantic search
- ✅ Balanced between quality and performance
- ✅ Well-established benchmark performance

**⚠️ Potential Issues:**
1. **English-first model** for German university:
   - HTW Berlin content likely mixes English and German
   - Model trained primarily on English may struggle with:
     - German administrative terminology
     - Mixed-language queries
     - German compound words
     - German date formats (e.g., "Wintersemester")

2. **Domain mismatch**:
   - Model trained on general text corpus
   - Not specialized for academic/administrative German language
   - May not understand HTW-specific terminology:
     - "Rückmeldung" (re-registration)
     - "Immatrikulation" (enrollment)
     - "BAföG" (student financial aid)
     - "Studierendensekretariat" (student services office)

3. **Embedding quality**:
   - Current code: `normalize_embeddings=True` (L2 normalization)
   - Cosine distance used for similarity
   - No query/document-specific prompts (some models benefit from prefix prompts)

**Alternative Models to Consider:**
- `deutsche-telekom/gbert-base` - German BERT
- `sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2` - Multilingual
- `intfloat/multilingual-e5-base` - Better multilingual performance

---

### 2.3 Vector Database & Retrieval

**Database:** PostgreSQL 15 with pgvector extension
**Vector Index:** IVFFlat
**Distance Metric:** Cosine distance
**Configuration:**
```yaml
retrieval:
  top_k: 6                    # Retrieve 6 most similar chunks
  distance: cosine

database_tuning:
  ivfflat_probes: 10          # Search quality vs speed tradeoff
  connection_pool_size: 5
  connection_timeout: 30
```

**Retrieval Strategy** (from `hansdb/retrieval.py`):
```sql
-- Unified query searching both web chunks and Q&A pairs
SELECT * FROM (
  SELECT 'web', wc.text, wc.embedding <=> query_vector AS score
  FROM web_chunks wc
  UNION ALL
  SELECT 'excel', qa.answer, qa.question_embedding <=> query_vector AS score
  FROM qa_pairs qa
)
ORDER BY score ASC
LIMIT 6
```

**⚠️ Potential Issues:**

1. **Top-k = 6 may be suboptimal**:
   - Too few: Misses relevant context
   - Too many: Introduces noise, dilutes signal
   - No experimentation data showing optimal value

2. **No re-ranking**:
   - Initial retrieval is the final ranking
   - No cross-encoder or more sophisticated re-ranking
   - May surface tangentially related content

3. **No query expansion**:
   - Single-shot retrieval with original query
   - Missing synonyms, related terms, typos
   - Example: "BAföG" vs "financial aid" not connected

4. **Equal weighting of sources**:
   - Web chunks and Q&A pairs treated equally
   - Q&A pairs might deserve higher weight (human-curated)
   - No source type preference

5. **IVFFlat index limitations**:
   - `ivfflat_probes: 10` is moderate (range: 1-100+)
   - Lower probes = faster but less accurate
   - No indication of recall@k metrics

6. **Chunk boundaries**:
   - Fixed 1800-char chunks may split important context
   - No semantic-aware chunking (e.g., splitting on paragraphs, sections)
   - Overlap of 200 chars might not capture full context

---

### 2.4 LLM Generation

**Model:** Llama 3 8B
**Host:** Remote H100 cluster (https://f2ki-h100-1.f2.htw-berlin.de:11435)
**Interface:** Ollama API
**Timeout:** 300 seconds
**SSL Verification:** Disabled

**System Prompt** (from `hans_db_agents.py:149-168`):
```
You are HANS, the HTW Berlin Student Services Assistant. You help students with:
- Application procedures and deadlines
- Academic calendar and semester dates
- Study programs and requirements
- Campus facilities and services
- International student support
- Financial aid and scholarships
- Administrative processes

Guidelines:
1. Use ONLY the provided context to answer questions
2. If information isn't in the context, say "I don't have this information"
3. Always cite sources using actual URLs when available, not numbered references
4. Be helpful, accurate, and concise
5. For contact information or links, include them in your response
6. If asked about deadlines, be very specific about dates

Context will be provided for each query. Base your responses solely on this context.
```

**Prompt Template** (from `hans_db_agents.py:206-213`):
```
{system_prompt}

CONTEXT:
{retrieved_chunks}

QUERY: {user_query}

ANSWER:
```

**⚠️ Potential Issues:**

1. **Model Size:**
   - 8B parameters is relatively small for instruction-following
   - Larger models (13B, 70B) typically produce better responses
   - Trade-off: 8B is faster, lower resource usage

2. **Context Window:**
   - Llama 3 8B context: ~8K tokens
   - With 6 chunks × ~1800 chars = ~10,800 characters (~3,000 tokens)
   - System prompt + query + response leaves limited space
   - **Risk:** Context truncation, losing important information

3. **Prompt Engineering:**
   - Relatively simple prompt structure
   - No few-shot examples showing desired output format
   - No explicit instruction for bilingual handling (English/German)
   - No chain-of-thought reasoning encouraged
   - No structured output format (e.g., JSON schema)

4. **Hallucination Mitigation:**
   - Prompt says "use ONLY provided context"
   - But no explicit penalty or verification mechanism
   - LLMs still prone to hallucination, especially with gaps in context

5. **Source Citation:**
   - Post-processing replaces numbered references with URLs
   - Fragile: Depends on LLM using specific format like "(source web - 1)"
   - May fail if LLM uses different citation format
   - Regex pattern: `r'\(source\s+web\s*-?\s*(\d+)\)'`

6. **No Temperature/Top-p Control:**
   - Code shows `"stream": False` but no sampling parameters
   - Default Ollama settings used (unknown temperature)
   - May lead to either too deterministic or too random outputs

7. **No Response Validation:**
   - Generated response not checked for:
     - Minimum quality thresholds
     - Factual consistency with context
     - Proper language (English expected for HTW EN pages)
     - Presence of required elements (e.g., dates for deadline questions)

---

### 2.5 Confidence Scoring

**Algorithm** (from `hans_db_agents.py:317-400`):

```python
confidence_score = (
    avg_similarity * 0.35 +      # Average retrieval score
    top_score * 0.25 +            # Best match score
    score_consistency * 0.15 +    # Score variance
    source_quality_ratio * 0.15 + # % of high-quality sources (>0.7)
    response_length * 0.05 +      # Response substantiveness
    specificity * 0.05            # URLs, emails, numbers present
)
```

**Confidence Levels:**
- Very High: ≥ 0.80
- High: ≥ 0.65
- Medium: ≥ 0.50
- Low: ≥ 0.30
- Very Low: < 0.30

**Disclaimers Added:**
- Very Low: "⚠️ Low Confidence Response: I found limited relevant information..."
- Low: "⚠️ Medium Confidence: The information above may not be complete..."

**⚠️ Potential Issues:**

1. **Retrieval-heavy weighting**:
   - 90% of score from retrieval metrics (avg, top, consistency, source quality)
   - Only 10% from response characteristics (length, specificity)
   - **Problem:** Good retrieval ≠ good response
   - LLM might generate poor answer from good context

2. **No semantic validation**:
   - Doesn't check if answer actually addresses the question
   - Example: High confidence if retrieved "deadline" content, even if answer is about wrong deadline

3. **Specificity indicators too simple**:
   ```python
   'http' in response.lower(),      # Any URL presence
   any(char.isdigit() for char in response),  # Any digit
   '@' in response,                  # Any @ symbol
   len([word for word in response.split() if word.endswith('.de')]) > 0
   ```
   - Presence ≠ relevance (random URL still counts)
   - Doesn't verify URLs are from HTW domain
   - Doesn't check if dates/numbers are contextually appropriate

4. **Threshold tuning**:
   - Thresholds (0.8, 0.65, 0.5, 0.3) appear arbitrary
   - No data-driven optimization
   - No user feedback loop to validate confidence accuracy

5. **No Ground Truth Evaluation:**
   - No test set with known correct answers
   - Can't measure:
     - Precision/Recall
     - F1 score
     - Mean Reciprocal Rank (MRR)
     - Answer accuracy

---

## 3. Data Flow Analysis

### 3.1 Query Processing Pipeline

```
USER QUERY: "What are the application deadlines for Master's programs?"
    │
    ▼
[1] QUERY EMBEDDING (BAAI/bge-base-en-v1.5)
    Input: "What are the application deadlines for Master's programs?"
    Output: [768-dimensional vector]
    │
    ▼
[2] VECTOR SIMILARITY SEARCH (PostgreSQL + pgvector)
    Query: SELECT top 6 chunks WHERE embedding <=> query_vector
    Results: [
      {score: 0.23, text: "Master's application deadline: May 31..."},
      {score: 0.31, text: "Application periods differ by program..."},
      {score: 0.45, text: "HTW Berlin operates 80 programs..."},
      ...
    ]
    │
    ▼
[3] CONTEXT BUILDING
    Concatenate retrieved chunks with metadata:

    [Source 1 - WEB]
    Title: Master's Programs
    URL: https://htw-berlin.de/master-programs
    Content: Master's application deadline: May 31 for winter semester...

    [Source 2 - WEB]
    Title: FAQ Studies & Application
    URL: https://htw-berlin.de/faq
    Content: Application periods differ by degree type...

    ... (4 more chunks)
    │
    ▼
[4] LLM PROMPTING (Llama 3 8B via Ollama)
    System Prompt: "You are HANS, HTW Berlin Assistant..."
    Context: [6 concatenated chunks, ~10KB text]
    Query: "What are the application deadlines for Master's programs?"
    │
    ▼
[5] RESPONSE GENERATION
    Raw LLM Output: "The application deadlines for Master's programs at HTW
    Berlin vary depending on the specific program. Generally, for winter
    semester admission, the deadline is May 31. For summer semester, it's
    November 30. However, you should check the specific program page for
    exact dates (source web - 1)."
    │
    ▼
[6] POST-PROCESSING
    • Replace "(source web - 1)" with actual URL
    • Calculate confidence score (e.g., 0.67 = "high")
    • Add disclaimer if confidence < 0.3
    │
    ▼
[7] FINAL RESPONSE
    {
      "final_response": "The application deadlines for Master's programs...",
      "metadata": {
        "query": "What are the application deadlines...",
        "results_found": 6,
        "confidence_score": 0.67,
        "confidence_level": "high",
        "sources": [
          {"url": "https://htw-berlin.de/...", "score": 0.23},
          ...
        ]
      }
    }
```

---

### 3.2 Failure Modes & Edge Cases

**Scenario 1: Query outside knowledge base**
- Query: "What is the weather forecast for next week?"
- Expected: "I don't have this information"
- Risk: LLM hallucinates answer despite no relevant context
- Current mitigation: System prompt instruction (weak enforcement)

**Scenario 2: Ambiguous query**
- Query: "What are the requirements?"
- Problem: Requirements for what? (Admission? Graduation? Visa?)
- Current behavior: Retrieves general "requirements" text
- Risk: Answer is generic, not actually helpful

**Scenario 3: Multilingual query**
- Query: "Wie bewerbe ich mich für ein Masterstudium?" (German)
- Problem: Embedding model is English-first
- Risk: Poor retrieval, semantic drift in embedding space

**Scenario 4: Outdated information**
- Query: "What is the deadline for summer 2025?"
- Problem: Data scraped in 2024, may be outdated
- Current mitigation: None (no timestamp checking)

**Scenario 5: Contradictory information**
- Context chunk 1: "Deadline is May 31"
- Context chunk 2: "Deadline is June 15"
- Problem: LLM must resolve conflict
- Current behavior: May include both, causing confusion

**Scenario 6: Long context overflow**
- 6 chunks × 1800 chars = ~10,800 characters
- Llama 3 8B context: 8K tokens (~32K characters)
- Risk: With system prompt + query, context might be truncated
- Current mitigation: None

---

## 4. Known Data Statistics

**From Deployment Logs:**
```
Database initialized:
  • 174 documents
  • 175 web chunks
  • 4 Q&A pairs
```

**⚠️ Critical Observation:**
- **175 web chunks from 174 documents** = ~1.006 chunks per document
- This suggests:
  1. Most documents are NOT being chunked (fit in 1800 char limit)
  2. Documents might be too short, lacking detail
  3. OR: Chunking logic is not triggering properly

**Expected vs Actual:**
- If 174 documents average 5KB each → ~870KB total content
- At 1800 char/chunk → should be ~480 chunks
- **Actual: 175 chunks** → Discrepancy suggests data quality issue

---

## 5. Identified Issues & Root Cause Hypotheses

### 5.1 DATA QUALITY ISSUES (High Probability)

**Symptoms:**
- Very few chunks (175) relative to source documents (174)
- Only 4 Q&A pairs (extremely limited training data)
- Unknown data freshness

**Root Causes:**
1. **Web scraping quality:**
   - May contain boilerplate (headers, footers, navigation)
   - Duplicate content across pages
   - Missing critical information (removed by scraper)

2. **Chunking problems:**
   - 1800-char chunks too large (losing granularity)
   - Not splitting long documents properly
   - Skip_short=true removing too much content

3. **Minimal Q&A data:**
   - 4 pairs insufficient for any meaningful examples
   - Missing diverse question phrasings
   - No coverage of common student queries

**Testing Recommendations:**
```sql
-- Check chunk size distribution
SELECT
  LENGTH(text) as chunk_length,
  COUNT(*)
FROM web_chunks
GROUP BY LENGTH(text)
ORDER BY chunk_length;

-- Check if most documents only have 1 chunk
SELECT
  document_id,
  COUNT(*) as chunk_count
FROM web_chunks
GROUP BY document_id
HAVING COUNT(*) = 1;

-- Check Q&A coverage
SELECT
  tags,
  COUNT(*)
FROM qa_pairs
GROUP BY tags;
```

---

### 5.2 EMBEDDING MODEL ISSUES (Medium-High Probability)

**Symptoms:**
- Retrieval returning irrelevant content
- Low similarity scores even for relevant queries
- Better performance on English queries than German

**Root Causes:**
1. **Language mismatch:**
   - BAAI/bge-base-en-v1.5 optimized for English
   - HTW content likely bilingual (English/German)
   - German terminology not well-represented in embedding space

2. **Domain specificity:**
   - Model trained on general corpus
   - Academic/administrative German not in training data

**Testing Recommendations:**
```python
# Compare embedding similarity for known-relevant pairs
from hansdb.embeddings import embed_single_text

# Test case 1: English
q1 = "application deadline"
doc1 = "The application deadline for Master's programs is May 31"

# Test case 2: German
q2 = "Bewerbungsfrist"
doc2 = "Die Bewerbungsfrist für Masterstudiengänge ist der 31. Mai"

# Test case 3: Mixed
q3 = "BAföG application"
doc3 = "BAföG-Antrag muss bis 31. März eingereicht werden"

# Calculate cosine similarity
import numpy as np

def cosine_sim(v1, v2):
    return np.dot(v1, v2) / (np.linalg.norm(v1) * np.linalg.norm(v2))

emb_q1 = embed_single_text(q1)
emb_doc1 = embed_single_text(doc1)
sim1 = cosine_sim(emb_q1, emb_doc1)

# Compare: Should see higher sim1 than sim2, indicating English bias
```

---

### 5.3 RETRIEVAL CONFIGURATION ISSUES (Medium Probability)

**Symptoms:**
- Retrieved chunks don't answer the question
- Missing relevant information
- Too much irrelevant context

**Root Causes:**
1. **Top-k = 6 not optimal:**
   - May need more chunks for complex queries
   - Or fewer for simple queries

2. **No re-ranking:**
   - Initial vector search might surface tangentially related content
   - No second-stage relevance filtering

3. **Fixed retrieval strategy:**
   - Doesn't adapt to query type
   - Factual queries vs. procedural queries need different approaches

**Testing Recommendations:**
```python
# Experiment with different top_k values
test_query = "What are the admission requirements for Computer Science Master's?"

for k in [3, 6, 10, 15]:
    results = retrieve_top_k(conn, test_query, top_k=k)
    print(f"Top-{k} results:")
    for r in results:
        print(f"  Score: {r['score']:.3f} | {r['content'][:100]}...")

    # Manually evaluate: Do more chunks help or hurt?
```

---

### 5.4 LLM GENERATION ISSUES (Medium Probability)

**Symptoms:**
- Responses don't fully answer the question
- Hallucinated information
- Poor formatting or structure
- Mixing up similar topics

**Root Causes:**
1. **Model size (8B) limitations:**
   - Smaller models weaker at instruction-following
   - Less robust to ambiguous prompts

2. **Prompt engineering:**
   - No few-shot examples
   - No structured output format
   - No explicit bilingual handling

3. **Context overload:**
   - 6 chunks × 1800 chars might overwhelm smaller model
   - Important info buried in noise

**Testing Recommendations:**
```python
# Test with different prompt structures
prompts = {
    "current": current_system_prompt,

    "with_examples": """
{current_prompt}

EXAMPLE 1:
Query: "What is the application deadline?"
Context: "The deadline for Bachelor's applications is July 15..."
Answer: "The application deadline for Bachelor's programs is July 15. [URL]"

EXAMPLE 2:
Query: "How do I apply?"
Context: [no relevant info]
Answer: "I don't have specific information about the application process..."

Now answer the user's query:
""",

    "structured": """
{current_prompt}

Provide your answer in this structure:
1. Direct answer (1-2 sentences)
2. Details (if available)
3. Sources (URLs)
4. Next steps (if applicable)
"""
}

# Compare response quality
```

---

### 5.5 CONFIDENCE SCORING ISSUES (Low-Medium Probability)

**Symptoms:**
- High confidence on poor responses
- Low confidence on good responses
- Inconsistent confidence levels

**Root Causes:**
1. **Retrieval-biased scoring:**
   - 90% weight on retrieval metrics
   - Good retrieval ≠ good answer

2. **No ground truth validation:**
   - Confidence thresholds arbitrary
   - Not calibrated against real user feedback

**Testing Recommendations:**
```python
# Manual evaluation of confidence accuracy
test_queries = [
    ("What is the tuition fee?", expected_answer, expected_confidence),
    ("When are exams?", expected_answer, expected_confidence),
    # ... 50-100 test cases
]

for query, expected, expected_conf in test_queries:
    result = await agent.process_query(query)
    actual_conf = result['metadata']['confidence_score']

    # Evaluate:
    # 1. Is answer correct? (manual check)
    # 2. Does confidence match correctness?
    # 3. Build confusion matrix
```

---

## 6. Diagnostic Recommendations

### 6.1 Immediate Diagnostics (This Week)

**1. Data Quality Audit:**
```bash
# Check chunk size distribution
psql $DATABASE_URL -c "
  SELECT
    MIN(LENGTH(text)) as min_len,
    AVG(LENGTH(text))::int as avg_len,
    MAX(LENGTH(text)) as max_len,
    COUNT(*) as total
  FROM web_chunks;
"

# Check document coverage
psql $DATABASE_URL -c "
  SELECT
    d.source_file,
    d.title,
    COUNT(wc.id) as chunk_count
  FROM documents d
  LEFT JOIN web_chunks wc ON wc.document_id = d.id
  GROUP BY d.id, d.source_file, d.title
  ORDER BY chunk_count;
"

# Inspect Q&A data
psql $DATABASE_URL -c "SELECT * FROM qa_pairs;"
```

**2. Retrieval Quality Test:**
```python
# Test 20 diverse queries
test_queries = [
    "application deadline",
    "Bewerbungsfrist",
    "BAföG",
    "tuition fees",
    "Master admission requirements",
    # ... 15 more
]

for query in test_queries:
    results = retrieve_top_k(conn, query, top_k=10)
    print(f"\nQuery: {query}")
    for i, r in enumerate(results[:3], 1):
        print(f"  #{i} (score {r['score']:.3f}): {r['content'][:150]}...")

    # Manual evaluation:
    # - Are top results actually relevant?
    # - What are typical similarity scores?
    # - Are scores <0.5 still useful?
```

**3. Embedding Model Comparison:**
```python
# Compare 3 models on same queries
models = [
    "BAAI/bge-base-en-v1.5",           # Current
    "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2",  # Multilingual
    "intfloat/multilingual-e5-base"     # Better multilingual
]

test_queries = [
    ("What are admission requirements?", "EN"),
    ("Wie bewerbe ich mich?", "DE"),
    ("BAföG application deadline", "MIXED")
]

# For each model, embed queries and measure retrieval performance
# Compare: Precision@3, Recall@10, MRR
```

**4. LLM Response Quality Spot Check:**
```python
# Test current system on 10 queries, manually evaluate
queries = [
    "What is the application deadline for Master's in Computer Science?",
    "How much does it cost to study at HTW?",
    "What are the German language requirements?",
    # ... 7 more diverse queries
]

for query in queries:
    result = await agent.process_query(query)
    print(f"\n{'='*60}")
    print(f"Query: {query}")
    print(f"Confidence: {result['metadata']['confidence_score']} "
          f"({result['metadata']['confidence_level']})")
    print(f"Response: {result['final_response'][:300]}...")
    print(f"Sources: {len(result['metadata']['sources'])}")

    # Manually evaluate:
    # ✓ Correct? ✓ Complete? ✓ Relevant? ✓ Well-formatted?
```

---

### 6.2 Short-Term Experiments (Next 2 Weeks)

**Experiment 1: Optimize Chunking**
- **Hypothesis:** 1800-char chunks too large, losing granularity
- **Test:**
  ```yaml
  # config.yaml variations
  chunk_chars: [800, 1200, 1800, 2500]
  chunk_overlap: [100, 200, 400]
  ```
- **Measure:** Retrieval precision, answer quality
- **Success:** Better relevance of retrieved chunks

**Experiment 2: Increase Top-K**
- **Hypothesis:** 6 chunks insufficient for complex queries
- **Test:**
  ```python
  top_k_values = [3, 6, 10, 15, 20]
  ```
- **Measure:** Answer completeness, confidence scores
- **Success:** More complete answers without noise

**Experiment 3: Test Multilingual Embedding**
- **Hypothesis:** English-first model hurts German query performance
- **Test:** Replace `BAAI/bge-base-en-v1.5` with `intfloat/multilingual-e5-base`
- **Measure:** Retrieval quality for DE/EN/mixed queries
- **Success:** Similar or better performance on German queries

**Experiment 4: Improve Prompt Engineering**
- **Hypothesis:** LLM needs better guidance
- **Test:**
  - Add 3-5 few-shot examples
  - Request structured output format
  - Explicitly state bilingual capability
- **Measure:** Answer quality, formatting consistency
- **Success:** Fewer hallucinations, better structure

**Experiment 5: Add Re-Ranking**
- **Hypothesis:** Initial retrieval surfaces wrong content
- **Test:** Add cross-encoder re-ranking after vector retrieval
  ```python
  from sentence_transformers import CrossEncoder

  # After vector retrieval:
  reranker = CrossEncoder('cross-encoder/ms-marco-MiniLM-L-6-v2')
  scores = reranker.predict([(query, chunk['content']) for chunk in results])
  # Re-sort by reranker scores
  ```
- **Measure:** Retrieval precision@3
- **Success:** Higher relevance in top-3 results

---

### 6.3 Medium-Term Improvements (Next Month)

**1. Expand Knowledge Base:**
- **Goal:** More comprehensive coverage
- **Actions:**
  - Re-scrape HTW website for newer content
  - Add more Q&A pairs from real student inquiries (target: 100+)
  - Include program-specific handbooks/PDFs
  - Add semester-specific information (dates, events)

**2. Implement Evaluation Framework:**
- **Goal:** Quantitative quality measurement
- **Actions:**
  ```python
  # Create test set
  test_set = [
      {
          "query": "What is the application deadline for Master's CS?",
          "expected_answer_contains": ["May 31", "winter semester"],
          "expected_sources": ["htw-berlin.de/master-programs"],
          "category": "deadline"
      },
      # ... 50-100 test cases across categories
  ]

  # Automated evaluation metrics
  def evaluate_system(test_set):
      metrics = {
          'answer_accuracy': [],      # Human-labeled correct/incorrect
          'source_relevance': [],     # Are cited sources on-topic?
          'confidence_calibration': [],  # Confidence vs correctness correlation
          'response_time': []
      }

      for test in test_set:
          result = process_query(test['query'])
          # Calculate metrics...

      return metrics
  ```

**3. User Feedback Loop:**
- **Goal:** Real-world quality signal
- **Actions:**
  - Add "Was this helpful?" button to GUI
  - Collect thumbs up/down on responses
  - Store feedback with query + response in DB
  - Weekly review of low-rated responses

**4. Hybrid Retrieval:**
- **Goal:** Better recall
- **Actions:**
  - Combine vector search with keyword search (BM25)
  - Fusion of both result sets
  - Code:
    ```python
    # Vector retrieval
    vector_results = retrieve_top_k_cosine(query, k=10)

    # Keyword retrieval (BM25 via PostgreSQL full-text search)
    keyword_results = retrieve_top_k_bm25(query, k=10)

    # Reciprocal Rank Fusion
    fused_results = reciprocal_rank_fusion([vector_results, keyword_results])
    ```

---

## 7. Quality Improvement Roadmap

### Phase 1: Diagnostics (Week 1)
- [ ] Run all diagnostic queries (Section 6.1)
- [ ] Manual evaluation of 20 test queries
- [ ] Document current baseline performance
- [ ] Identify top 3 issues

### Phase 2: Quick Wins (Weeks 2-3)
- [ ] Experiment #3: Test multilingual embedding model
- [ ] Experiment #4: Improve prompts (add examples)
- [ ] Optimize top-k value based on data
- [ ] Fix any obvious data quality issues found

### Phase 3: Systematic Testing (Week 4)
- [ ] Build evaluation test set (50 queries)
- [ ] Implement automated evaluation script
- [ ] Test all 5 experiments systematically
- [ ] Compare results, choose best config

### Phase 4: Data Expansion (Weeks 5-6)
- [ ] Re-scrape HTW website
- [ ] Collect more Q&A pairs (target: 100+)
- [ ] Re-chunk with optimized parameters
- [ ] Rebuild database, re-test

### Phase 5: Advanced Features (Weeks 7-8)
- [ ] Implement re-ranking
- [ ] Add hybrid retrieval (vector + BM25)
- [ ] Tune confidence scoring with real data
- [ ] Add user feedback mechanism

---

## 8. Recommended Professor Discussion Points

### Questions to Explore:

1. **Is response quality poor across the board, or for specific query types?**
   - Example categories: Deadlines, Procedures, Fees, Requirements, General Info
   - Helps narrow down if issue is data, retrieval, or generation

2. **Are there specific questions where HANS fails consistently?**
   - Can build focused test cases
   - Might reveal systematic gaps (e.g., all German queries fail)

3. **What does "poor quality" mean specifically?**
   - Incorrect facts?
   - Incomplete information?
   - Irrelevant information?
   - Poor formatting?
   - Wrong language?
   - Outdated information?

4. **Do we have access to real user queries + feedback?**
   - Gold mine for evaluation
   - Can identify common failure modes

5. **What are resource constraints?**
   - Can we use larger LLM (13B, 70B)?
   - Can we expand data collection?
   - Can we implement re-ranking (more compute)?

6. **What is acceptable latency?**
   - Current: ~5-30 seconds
   - Trade-off: Better models = slower
   - Can guide optimization strategy

### Proposed Investigation Plan:

**Week 1:** Run diagnostics, establish baseline metrics
**Week 2:** Test hypotheses (embedding, prompts, top-k)
**Week 3:** Present findings and recommendations
**Week 4+:** Implement improvements iteratively

---

## 9. Technical Specifications Summary

| Component | Current Configuration | Potential Issues |
|-----------|----------------------|------------------|
| **Embedding Model** | BAAI/bge-base-en-v1.5 (768-dim) | English-first, domain mismatch |
| **Vector DB** | PostgreSQL + pgvector, IVFFlat | Moderate index quality (probes=10) |
| **Chunking** | 1800 chars, 200 overlap | Too large, semantic boundaries ignored |
| **Retrieval** | Top-6, cosine distance | No re-ranking, fixed strategy |
| **LLM** | Llama 3 8B | Small model, generic prompts |
| **Knowledge Base** | 174 docs, 175 chunks, 4 QA | Very small, minimal QA data |
| **Confidence** | 90% retrieval-based | No semantic validation |
| **Languages** | English/German mixed | No explicit bilingual handling |

---

## 10. Conclusion

HANS is a well-architected RAG system with solid foundations (PostgreSQL, pgvector, modern embeddings, open-source LLM). However, several factors may contribute to suboptimal response quality:

**Most Likely Issues (Priority Order):**
1. **Minimal knowledge base** (175 chunks, 4 QA pairs) - Not enough data
2. **English-first embedding model** - Language mismatch for German content
3. **Large chunk size** (1800 chars) - Losing contextual granularity
4. **No retrieval re-ranking** - Surfacing wrong context
5. **Simple prompt engineering** - LLM needs better guidance

**Recommended Next Steps:**
1. Run diagnostic queries to establish baseline
2. Test multilingual embedding model
3. Collect more Q&A training data
4. Experiment with chunk sizes and top-k
5. Implement systematic evaluation framework

The architecture is sound; quality improvement likely requires **better data, better embeddings, and tuned retrieval** rather than fundamental redesign.

---

**Document Version:** 1.0
**Last Updated:** November 2025
**Contact:** [Your contact info]
