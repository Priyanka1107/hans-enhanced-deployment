# HANS – Apache Hop Integration and Handover

## 1. Purpose

HANS is a staff-facing Retrieval-Augmented Generation (RAG) assistant for processing student-support emails at HTW Berlin.

It generates draft responses using retrieved HTW information and supporting sources.

Apache Hop is intended to act as the upstream workflow layer. It will read incoming emails, apply an initial relevance filter, and trigger HANS only for relevant cases.

HANS does not send emails automatically. All generated responses require staff review before sending.

---

## 2. Big-Picture Architecture

The planned workflow is:

```text
Incoming student email
        ↓
Apache Hop
        ↓
Initial relevance filter
        ↓
POST /v1/drafts
        ↓
HANS
        ↓
Input parsing and language detection
        ↓
Programme recognition
        ↓
Multi-topic detection
        ↓
Thread / follow-up handling
        ↓
Retrieval-query construction
        ↓
Semantic retrieval
        ↓
PostgreSQL + pgvector
        ↓
Cross-encoder reranking
        ↓
Official-source prioritisation and evidence filtering
        ↓
Configured generation model
        ↓
Draft generation
        ↓
Validation and citations
        ↓
Staff draft
        ↓
Human review
        ↓
Reply sent by staff
```

### Generation options

HANS is designed so that the generation backend can be changed without changing the Apache Hop integration.

Current and planned generation options are:

1. HTW-hosted Ollama model — currently used for testing
2. Shared MacBook local LLM through Ollama and Tailscale
3. Mistral Cloud API as an alternative/comparison option

---

## 3. Current Working Configuration

### Branch

`production-candidate/apache-hop-v1`

### Environment

`development`

### Generation provider

`htw_ollama`

### Current generation model

`mistral-small:24b`

### Current HTW Ollama endpoint

`https://f2ki-h100-1.f2.htw-berlin.de:11435`

### Embedding model

`BAAI/bge-base-en-v1.5`

### Vector storage and retrieval

`PostgreSQL + pgvector`

### Reranker

`cross-encoder/ms-marco-MiniLM-L-6-v2`

### Automatic sending

`false`

### Staff review

`required`

---

## 4. HANS Responsibilities

HANS currently performs:

- input parsing
- language detection
- programme recognition
- programme-state handling
- multi-topic detection
- follow-up and thread-context handling
- retrieval-query construction
- local BGE query embeddings
- PostgreSQL/pgvector semantic retrieval
- cross-encoder reranking
- duplicate-source handling
- programme-specific evidence handling
- official-source prioritisation
- evidence filtering
- staff-draft generation
- citation handling
- response validation
- mandatory human-review routing

The generation model does not perform the retrieval itself. HANS prepares the relevant evidence before sending the generation request to the configured model.

---

## 5. Apache Hop Responsibilities

Apache Hop should:

1. Read incoming email or ticket data.
2. Apply an initial scope/relevance criterion.
3. Skip unrelated emails.
4. Create the HANS JSON request.
5. Call `POST /v1/drafts`.
6. Receive the HANS JSON response.
7. Parse the returned fields.
8. Store or forward the result.
9. Later connect the output to the real staff-mailbox workflow.

Apache Hop does **not** need direct access to:

- PostgreSQL
- pgvector
- embedding models
- reranking models
- the Mistral API key
- Ollama model configuration
- HANS internal retrieval logic

The workflow integration should therefore remain independent of the generation model used by HANS.

---

## 6. HANS API

### Health endpoint

```text
GET /health
```

### Draft-generation endpoint

```text
POST /v1/drafts
```

### Legacy endpoint

```text
POST /email
```

The legacy `/email` endpoint is currently retained for compatibility with earlier integrations.

New workflow integrations should use:

```text
POST /v1/drafts
```

---

## 7. Authentication

Apache Hop must send the HANS integration key in the request header:

```text
X-HANS-API-Key: <integration-key>
```

The corresponding local environment variable is:

```text
HANS_INTERNAL_API_KEY
```

The real value must not be committed to Git or stored directly inside the Apache Hop pipeline definition.

The local `.env` file contains runtime credentials and is ignored by Git.

Apache Hop does not require access to the Mistral API key.

The separation is:

```text
Apache Hop
     │
     │ X-HANS-API-Key
     ▼
    HANS
     │
     │ Internal generation-provider configuration
     ▼
HTW Ollama / Local LLM / Mistral Cloud
```

---

## 8. Example Request

A synthetic example request is stored at:

```text
examples/apache_hop_request.example.json
```

The request contains fields such as:

```json
{
  "email_text": "Synthetic student email text",
  "student_email": "test.student@example.invalid",
  "subject": "Example subject",
  "thread_id": "EXAMPLE-THREAD-001",
  "email_id": "EXAMPLE-EMAIL-001",
  "language": "en",
  "top_k": 6
}
```

Only synthetic data should be stored in Git examples.

---

## 9. Example Response

A real response generated from a successful synthetic HANS API test is stored at:

```text
examples/apache_hop_response.example.json
```

The response includes information such as:

- detected programme
- programme status
- detected topics
- retrieved sources
- generated staff draft
- citation information
- validation result
- quality/review information
- human-review requirement
- automatic-send status

The example response should contain synthetic test information only.

---

## 10. Starting HANS

From the repository root, activate the Python environment:

```powershell
.\.venv\Scripts\Activate.ps1
```

Set the project path and UTF-8 mode:

```powershell
$env:PYTHONPATH = (Get-Location).Path
$env:PYTHONUTF8 = "1"
```

Start the HANS API:

```powershell
python -m uvicorn enhanced_api_server:app `
  --host 127.0.0.1 `
  --port 8009
```

Keep this terminal running.

### Verify HANS from a second PowerShell window

Run:

```powershell
Invoke-RestMethod `
  -Uri "http://127.0.0.1:8009/health" |
  ConvertTo-Json -Depth 10
```

The currently verified configuration returns:

```json
{
  "status": "healthy",
  "service": "hans-enhanced-email-assistant",
  "environment": "development",
  "generation_provider": "htw_ollama",
  "generation_model": "mistral-small:24b",
  "embedding_model": "BAAI/bge-base-en-v1.5",
  "database": "operational",
  "automatic_send": false
}
```

---

## 11. Current Test Results

### 11.1 HTW Ollama connectivity

**PASS**

Verified model:

```text
mistral-small:24b
```

The HTW Ollama server returned HTTP 200 for a direct sequential model request.

The test confirmed:

- HTW Ollama endpoint reachable
- SSL verification enabled
- `mistral-small:24b` available
- model request accepted
- successful response received

---

### 11.2 Complete HANS email-processing pipeline

**PASS**

The complete HANS email-service test successfully used:

```text
HTW Ollama
→ mistral-small:24b
```

The test successfully performed:

- programme recognition
- programme-state confirmation
- multi-topic detection
- local BGE query embeddings
- PostgreSQL/pgvector semantic retrieval
- cross-encoder reranking
- programme-specific source selection
- official-source prioritisation
- draft generation using `mistral-small:24b`
- citation validation
- grounding validation
- mandatory staff-review routing

The tested enquiry contained four topics:

- application deadline
- required documents
- language of instruction
- study format

The programme was correctly identified as:

```text
Project Management and Data Science
```

Direct official programme sources were retrieved and prioritised.

The generated draft remained a staff-review draft.

---

### 11.3 HANS API

**PASS**

Authenticated request to:

```text
POST /v1/drafts
```

returned:

```text
HTTP 200
```

and a complete HANS JSON response.

The API test confirmed that the model-independent endpoint works with the current HTW-hosted `mistral-small:24b` backend.

---

### 11.4 API authentication

**PASS**

A missing or invalid:

```text
X-HANS-API-Key
```

returns:

```text
HTTP 401 Unauthorized
```

An authenticated request with the configured HANS integration key returned HTTP 200.

---

### 11.5 Safety configuration

**PASS**

Verified:

```text
automatic_send = false
```

and:

```text
staff review required = true
```

All generated responses remain drafts for human review.

---

## 12. Safety Behaviour

HANS does not automatically send generated responses.

All generated responses are treated as staff drafts and must be reviewed before sending.

The generation model is not trained or fine-tuned on incoming student emails during normal HANS operation.

HANS uses Retrieval-Augmented Generation (RAG):

```text
Student enquiry
      ↓
Retrieve relevant HTW evidence
      ↓
Provide selected evidence to the model
      ↓
Generate staff draft
```

The generation model itself remains unchanged.

The retrieved evidence and the selected source applicability remain important because a semantically relevant source may still be incorrect for a different programme, degree level, application route, or administrative stage.

---

## 13. Known Limitations

The current implementation has the following known limitations:

- The current HTW Ollama research server is an interim test environment and is not the planned permanent production host.
- Shared MacBook local-LLM access through Ollama and Tailscale is not yet integrated.
- Performance of the shared MacBook under concurrent requests has not yet been evaluated.
- Large Mistral Cloud testing is pending a new valid API key.
- The previous Mistral API key currently returns HTTP 401 and should not be used.
- Apache Hop integration is still being implemented.
- The first Apache Hop workflow will use synthetic CSV email input.
- Real mailbox integration has not yet been implemented.
- Production monitoring has not yet been added.
- Final repository cleanup is still pending.
- Final staff/demo UI cleanup is still pending.
- Several historical Qwen-specific references remain in legacy tests, backup files, configuration defaults, and the existing demo UI.
- These legacy references do not affect the currently verified runtime, which uses `mistral-small:24b`.
- Institutional privacy/security review remains required before operational use.

---

## 14. Current Repository Cleanup Note

The current branch was intentionally kept largely intact while the new deployment-oriented API and generation-provider integration were being tested.

Several research, thesis-testing, legacy, and Qwen-specific files still remain.

Examples include:

- historical Qwen references
- older local-LLM tests
- backup files
- thesis/evaluation artefacts
- previous n8n-related components
- older baseline interfaces
- Qwen-specific UI wording

These items should not be removed blindly while the Apache Hop integration is still being validated.

After the Apache Hop flow works, a dedicated production cleanup should:

1. identify active runtime files
2. remove or archive thesis-only evaluation components
3. remove obsolete n8n integration files from this deployment branch
4. remove unnecessary backup artefacts
5. simplify the current staff/demo UI
6. replace remaining model-specific UI wording with model-neutral wording
7. review configuration defaults
8. verify that no credentials are tracked
9. run complete regression tests again

Historical development information can remain available through Git history and frozen research branches.

---

## 15. Current Result Summary

The current deployment-oriented HANS version successfully runs the complete email-processing RAG pipeline using the HTW-hosted:

```text
mistral-small:24b
```

model.

The verified pipeline includes:

```text
Input email
→ programme recognition
→ multi-topic detection
→ local BGE embeddings
→ PostgreSQL/pgvector semantic retrieval
→ cross-encoder reranking
→ official-source prioritisation
→ evidence filtering
→ Mistral draft generation
→ citation and grounding validation
→ mandatory staff review
```

The stable workflow integration endpoint is:

```text
POST /v1/drafts
```

The endpoint is model-independent.

The generation backend can therefore later be changed from:

```text
HTW Ollama research server
```

to:

```text
Shared MacBook local LLM
```

or:

```text
Mistral Cloud API
```

without changing the Apache Hop request/response interface.

Automatic sending remains disabled.

The next implementation step is to connect Apache Hop using synthetic CSV emails.

After this workflow is validated, the synthetic CSV input can be replaced by the real mailbox connection.

---

## 16. Planned Apache Hop Demo

The first Apache Hop demonstration should remain intentionally simple.

```text
test_emails.csv
       ↓
Apache Hop
       ↓
Initial admissions relevance criterion
       ↓
      / \
     /   \
irrelevant relevant
   ↓        ↓
 skip   create JSON
            ↓
      POST /v1/drafts
            ↓
       HANS response
            ↓
       parse JSON
            ↓
        save result
```

### Expected initial behaviour

Relevant admissions email:

```text
MPMD application question
→ relevant
→ HANS called
→ HTTP 200
→ HANS response stored
```

Irrelevant email:

```text
Cafeteria opening-hours question
→ irrelevant
→ HANS not called
```

The initial Apache Hop implementation should not connect to the real Outlook/shared mailbox yet.

The CSV-based pipeline should first prove that filtering and HANS API integration work correctly.

---

## 17. Planned Model Migration

### Current

```text
HANS
→ HTW Ollama research server
→ mistral-small:24b
```

### Planned local model

```text
HANS
→ Tailscale
→ shared MacBook
→ Ollama
→ local LLM
```

Only the model endpoint and model configuration should need to change.

Apache Hop should continue calling:

```text
POST /v1/drafts
```

without being aware of which model HANS uses.

### Mistral Cloud alternative

When a valid Mistral API key becomes available:

```text
HANS
→ Mistral API
→ large Mistral model
```

The same HANS test cases should then be repeated for quality comparison.

---

## 18. Next Steps

1. Finalise the Apache Hop integration files.
2. Verify the example request and real synthetic response.
3. Build the Apache Hop CSV-input pipeline.
4. Add the first relevance-filtering criterion.
5. Connect Apache Hop to `POST /v1/drafts`.
6. Parse the HANS JSON response.
7. Save the returned result.
8. Verify that irrelevant emails are filtered before HANS is called.
9. Add additional synthetic regression scenarios.
10. Integrate the shared MacBook Ollama endpoint through Tailscale.
11. Evaluate local-model response quality.
12. Evaluate local-model performance and concurrent-request behaviour.
13. Test a large Mistral Cloud model when a valid API key becomes available.
14. Connect the real mailbox.
15. Perform final repository cleanup.
16. Perform final staff/demo UI cleanup.
17. Remove or archive thesis-only and obsolete integration components.
18. Run the complete regression test suite.
19. Update this document with the final Apache Hop results.
20. Prepare the stable handover branch for Appy.
21. Complete the required institutional privacy/security review before operational use.

---

## 19. Important Notes for Handover

The Apache Hop integration should rely only on the HANS API contract.

Appy does not need:

- the Mistral API key
- Ollama credentials
- database credentials
- embedding-model configuration
- direct pgvector access

The main workflow contract is:

```text
Apache Hop
      ↓
X-HANS-API-Key
      ↓
POST /v1/drafts
      ↓
HANS JSON response
```

The underlying generation provider remains an internal HANS concern.

Do not commit:

- `.env`
- real API keys
- real student emails
- mailbox credentials
- production database credentials
- local runtime logs containing personal data

Use synthetic test data in Git examples and demonstrations.