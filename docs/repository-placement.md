# Placing the documentation in the HANS repository

## Reference worktree

The final worktree recorded by this package is `C:\Working_Student\HTW\HANS_Project\hans-hop-e2e-finalization`. The final acceptance artefact was committed at `9fee966` on `fix/2026-09-23-final-quality-hardening`. Check the current branch and working tree before copying because this package cannot establish the present state of that Windows worktree.

## Copy map from the extracted package root

| Package path | Destination relative to the HANS repository root |
|---|---|
| `README.md` and `MANIFEST.md` | Root |
| `docs/` including figures, evidence and archive | `docs/`, preserving paths |
| `deliverables/` | `deliverables/` |
| `evaluation/results/*.json` | `evaluation/results/`; compare existing files before replacing |

Use a documentation branch based on the final tested/hygiene state, inspect `git status` first, then copy the directory tree. Review changed and untracked files, check the Markdown links and compare hashes for JSON files that already exist. The JSON files in this package are recorded evidence; copying them must not create a new evaluation claim. Commit documentation separately from the tested application behaviour. Keep `6dafee6` as the behavioural reference and `251fddf` as later repository hygiene. Do not merge the feature branch into `main` solely to install these documents; review its broader diff and intended integration first.

After the Word review, import the two deliverables as native Google Docs and verify diagrams, tables, page breaks and sharing access. Uploading a DOCX without conversion does not by itself establish a native Google Doc.
