# Qwen Runtime Profiling Study

## Purpose

This branch is diagnostic only. It starts from the frozen 8/8 candidate and does not change retrieval limits, prompts, validation rules, topic logic, model settings, or draft output.

## 9–19 November audit

- No application commits occurred from 9–12 November.
- On 13 November, HANS added the HTW LiteLLM generation client and provider selection for Qwen. This is the major runtime/provider change in the period.
- On 16 November, deterministic scope routing, credit-recognition topic handling, answer-completeness checks, and mailbox integration were added. These can change which enquiries reach generation or how many topics are detected, but they do not by themselves explain long model generation time.
- On 18 November, additional safety/attachment/mailbox tests and UI work were added. The latency-study settings made existing retrieval/evidence values configurable while preserving the accepted defaults: standard top-k 5, high-risk top-k 8, final source limit 8, and 1800 evidence characters per document.
- The optional Qwen thinking switch was added on 18 November. Blank preserves the provider default.

## Historical controls

The September Llama 3.1 8B final RC1 artefact records:
- MM-003 German: 2334 prompt + 486 completion = 2820 total tokens; 58.193 s generation.
- MM-008 dual citizen: 3005 prompt + 379 completion = 3384 total tokens; 55.257 s generation.

The MM-008 wording is reused as a control and as one of the new realistic scenarios, making it especially useful for provider comparison.

## Measurements

The profiling runner records:
- final documents selected for generation;
- per-topic retrieved/selected source counts;
- prompt, completion and total tokens;
- provider reasoning tokens/details when supplied;
- separate reasoning-content character count when supplied;
- system/user prompt character counts;
- raw completion vs visible completion character counts;
- generation seconds and completion tokens/second;
- final staff-draft length and quality/validation output.

No prompt text or model behavior is altered by these measurements.


## Direct tiny-prompt probe

Use `scripts/probe_qwen_runtime.py` to separate HANS prompt/retrieval cost from the Qwen inference runtime.

The probe sends only:

- system: `You are a concise diagnostic assistant.`
- user: `Reply with exactly: OK`

By default it runs provider-default thinking and thinking-disabled back to back and reports elapsed seconds plus provider token/reasoning counts. This script does not change HANS runtime configuration.
