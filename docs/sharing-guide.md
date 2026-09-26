# Sharing and Submission Guide

## For the professor

Recommended files:

1. `deliverables/HANS_Project_Overview_and_Results.docx`
2. `deliverables/HANS_Technical_Architecture_Implementation_and_Evaluation.docx`

Upload both Word files to Google Drive. They can be opened with Google Docs and shared as normal Google Docs links. The architecture and Apache Hop figures are embedded inside the Word files, so the documents can be read without the repository folder structure.

## For technical/code review

Share the repository branch/tag together with the `docs/` folder. The Markdown files use relative links to the figures under `docs/diagrams/` and `docs/evidence/`.

## Recommended repository reference

- Tested behaviour: `6dafee6`
- End-to-end tag: `checkpoint-2026-09-25-final-e2e`
- Documentation/security hygiene can be committed later on top of the tested behavioural state.

## Important note

Do not share `.env`, `.env.local`, mailbox passwords, API keys or local secret files. Before broad repository access, rotate any credential that may have appeared in old Git history if it could still be valid.
