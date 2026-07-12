# Scapy Migration - Complete Package Index

## 🚀 Start Here

1. **New to this project?** → Read [QUICKSTART.md](QUICKSTART.md) (5-minute setup)
2. **Ready to migrate?** → Follow [MIGRATION_GUIDE.md](MIGRATION_GUIDE.md) (step-by-step)
3. **Want technical details?** → See [README.md](README.md) (full documentation)
4. **Implementation overview?** → Read [IMPLEMENTATION_SUMMARY.md](IMPLEMENTATION_SUMMARY.md)

## 📁 File Organization

### Documentation (4 files)
- **[QUICKSTART.md](QUICKSTART.md)** - 5-minute quick start guide ⚡
- **[MIGRATION_GUIDE.md](MIGRATION_GUIDE.md)** - Step-by-step migration with troubleshooting
- **[README.md](README.md)** - Complete technical documentation
- **[IMPLEMENTATION_SUMMARY.md](IMPLEMENTATION_SUMMARY.md)** - Design decisions and architecture

### Executable Scripts (3 files)
- **[verify_setup.py](verify_setup.py)** - Pre-flight checks for all dependencies
- **[migrate_scapy_to_db.py](migrate_scapy_to_db.py)** - Main migration pipeline
- **[evaluate_retrieval.py](evaluate_retrieval.py)** - Retrieval quality evaluation

### Core Modules (4 files)
- **[text_cleaning.py](text_cleaning.py)** - Breadcrumb removal and quality checks
- **[signal_extraction.py](signal_extraction.py)** - Extract dates, amounts, requirements
- **[embedding_builder.py](embedding_builder.py)** - Build enriched embedding text
- **[chunking.py](chunking.py)** - Smart chunking with boundary detection

### Configuration & Data (3 files)
- **[requirements.txt](requirements.txt)** - Python dependencies
- **[test_queries.json](test_queries.json)** - 25 test queries for evaluation
- **[__init__.py](__init__.py)** - Package initialization

## 🎯 Usage Paths

### Path 1: Quick Migration (Recommended)
```
QUICKSTART.md → verify_setup.py → migrate_scapy_to_db.py → evaluate_retrieval.py
```

### Path 2: Careful Migration (For Production)
```
README.md → MIGRATION_GUIDE.md → verify_setup.py →
migrate_scapy_to_db.py --dry-run → Review report →
migrate_scapy_to_db.py → evaluate_retrieval.py
```

### Path 3: Understanding First
```
IMPLEMENTATION_SUMMARY.md → README.md → Source code review → Migration
```

## 📊 What Each Script Does

### verify_setup.py
```bash
python3 verify_setup.py
```
**Checks:**
- Python version >= 3.8
- Required packages installed
- Scapy objects directory exists (170 files)
- Config file valid
- Database connection works
- Models can be downloaded

**Output:** ✓/✗ for each check + summary

---

### migrate_scapy_to_db.py
```bash
# Dry run (no DB changes)
python3 migrate_scapy_to_db.py \
    --objects-dir ../scapy/htw_scrape/outputs/objects \
    --dry-run

# Full migration
python3 migrate_scapy_to_db.py \
    --objects-dir ../scapy/htw_scrape/outputs/objects
```

**Does:**
1. Loads 170 JSON objects
2. Cleans text (removes breadcrumbs)
3. Builds enriched embedding text
4. Enriches thin objects with related content
5. Chunks into 1000-char pieces
6. Embeds with BGE (no prefixes)
7. Stores in PostgreSQL
8. Generates CSV report

**Output:**
- migration_report.csv
- 170 documents in DB
- 800-1200 chunks in DB

---

### evaluate_retrieval.py
```bash
python3 evaluate_retrieval.py \
    --queries test_queries.json \
    --output evaluation_results.json
```

**Does:**
1. Runs 25 test queries
2. Vector search (top 30 candidates)
3. Reranking (top 10 results)
4. Checks if expected object types found
5. Calculates success rate

**Output:**
- evaluation_results.json
- Success rate 70-85% expected

## 🔧 Module Details

### text_cleaning.py
- `clean_full_text(text)` - Remove breadcrumbs, normalize whitespace
- `is_thin(embedding_text, full_text)` - Detect sparse content
- `calculate_content_quality(text)` - Quality metrics

### signal_extraction.py
- `extract_euro_amounts(text)` - EUR amounts (€350, 350 EUR)
- `extract_date_ranges(text)` - DD.MM.YYYY, Month DD
- `extract_key_actions(text)` - Modal verb sentences
- `extract_required_documents(text)` - Document lists
- `extract_eligibility_cues(text)` - Requirements
- `extract_program_facts(text)` - Language, ECTS, duration
- `build_signal_block(obj, text)` - Type-specific enrichment

### embedding_builder.py
- `build_embedding_text(obj, obj_by_id)` - Main function
  - Section 1: Identity (type, id, title, URL, notes)
  - Section 2: Type-specific signals
  - Section 3: Related pages
  - Section 4: Full cleaned text
  - Section 5: Thin enrichment (if needed)
- `select_best_related_object()` - Smart selection
- `extract_related_content_excerpt()` - Borrow 1200-2000 chars

### chunking.py
- `chunk_embedding_text()` - 1000-char chunks
- `find_sentence_boundary()` - Smart boundary detection
- `is_chunk_valid()` - Quality filter (40% alphanumeric)
- `create_chunk_dict()` - Attach metadata
- `merge_adjacent_chunks()` - Optional post-retrieval

## 📈 Expected Results

### Migration Statistics
- **Objects processed**: 170
- **Objects enriched**: 30-50 (20-30%)
- **Still thin after enrichment**: 5-15 (< 10%)
- **Total chunks**: 800-1200
- **Average chunks per object**: 4-8
- **Migration time**: 1-4 minutes

### Database Contents
- **documents table**: 170 records
- **web_chunks table**: 800-1200 records
- **Embedding dimension**: 768 (BGE)
- **Total storage**: ~50-100 MB

### Retrieval Quality
- **Test queries**: 25
- **Expected success rate**: 70-85%
- **Top-10 recall**: Should contain relevant object types

## 🐛 Common Issues

| Issue | File to Check |
|-------|---------------|
| Setup problems | verify_setup.py output |
| Migration errors | migrate_scapy_to_db.py logs |
| Thin objects | migration_report.csv |
| Low success rate | evaluation_results.json |
| Database issues | MIGRATION_GUIDE.md troubleshooting |
| Code questions | Source file docstrings |

## 📚 Additional Resources

### In Parent Directory
- `../config.yaml` - Database and model configuration
- `../.env.local` - DATABASE_URL and credentials
- `../scapy/htw_scrape/outputs/objects/` - Source JSON objects (170 files)
- `../scapy/htw_scrape/outputs/objects/ENRICHMENT_ASSESSMENT_REPORT.md` - Pre-migration analysis

### External
- BGE Model: https://huggingface.co/BAAI/bge-base-en-v1.5
- Reranker: https://huggingface.co/cross-encoder/ms-marco-MiniLM-L-6-v2
- PostgreSQL + pgvector: https://github.com/pgvector/pgvector

## ✅ Success Checklist

Before migration:
- [ ] Read QUICKSTART.md or MIGRATION_GUIDE.md
- [ ] Run verify_setup.py (all checks pass)
- [ ] Backup database
- [ ] Review existing data size

During migration:
- [ ] Run dry-run first
- [ ] Review migration_report.csv
- [ ] Check < 10% still thin
- [ ] Run full migration

After migration:
- [ ] Verify database counts (170 docs, 800+ chunks)
- [ ] Run evaluation (success rate > 70%)
- [ ] Test API with real queries
- [ ] Update retrieval code (remove e5 prefixes)
- [ ] Monitor production performance

## 🎓 Learning Path

1. **Beginner**: QUICKSTART.md → Run scripts → Done
2. **Intermediate**: MIGRATION_GUIDE.md → README.md → Customize
3. **Advanced**: IMPLEMENTATION_SUMMARY.md → Source code → Extend

## 📞 Support

- **Questions about setup?** → See MIGRATION_GUIDE.md troubleshooting
- **Want to understand design?** → Read IMPLEMENTATION_SUMMARY.md
- **Need to modify behavior?** → Source files have detailed docstrings
- **Found a bug?** → Check logs, review CSV reports

---

**Package Version:** 1.0.0
**Created:** 2026-01-25
**Total Files:** 14 (3 executables, 4 modules, 4 docs, 3 config/data)
**Total Lines of Code:** ~1,500
**Ready for Production:** ✅
