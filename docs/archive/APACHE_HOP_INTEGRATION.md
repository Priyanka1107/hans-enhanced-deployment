# Apache Hop -> HANS integration contract

## Health
GET /health

No API key is required. Confirm `status=healthy`, the expected `generation_provider`, `generation_model`, database status, and `automatic_send=false`.

## Draft endpoint
POST /v1/drafts

Legacy compatibility endpoint: POST /email

Headers:
- Content-Type: application/json
- X-HANS-API-Key: <configured HANS internal service key>

Request fields:
- email_text (required string)
- student_email (optional string)
- subject (optional string)
- thread_id (optional string)
- email_id (optional string)
- language (optional string)
- top_k (integer 3-10, default 6)

Main response fields:
- is_followup
- followup_type
- flagged_for_human
- thread_id
- email_id
- email_context
- detected_topics
- staff_draft
- citations
- sources
- validation
- quality
- conflicts
- timing
- automatic_send

Expected safety property: `automatic_send` is always false in this PoC.

## Error handling
- 400: application-level input error
- 401: invalid HANS internal API key
- 422: request schema validation error
- 500: HANS processing/generation failure; route to manual review
- 503: HANS authentication/service/database initialization is unavailable

## Provider independence
Apache Hop does not need the Mistral API key or Ollama credentials. It only calls HANS. HANS chooses the configured generation provider internally.
