# HANS Experimental Setup - Complete Guide for New PC

**Purpose**: This guide helps you set up the improved HANS system on a brand new computer, even if you've never used Docker or databases before.

---

## 📋 What is This?

HANS is an AI assistant that answers questions about HTW Berlin student services (applications, fees, deadlines, etc.). This experimental version includes 4 major improvements:

1. **Better text chunking** - Breaks documents into smaller, more focused pieces
2. **Smarter retrieval** - Finds more relevant information (fetches 30 candidates, picks best 10)
3. **Improved prompts** - Gives clearer, more honest answers in English
4. **Multilingual embeddings + reranking** - Understands German questions better and filters out noise

---

## 🎯 What You'll End Up With

After following this guide, you'll have:
- A local copy of the HANS system running on your computer
- A PostgreSQL database with all the content indexed
- An API server that answers questions
- Test scripts to verify everything works

---

## 📦 What You Need to Install (Prerequisites)

### 1. **Python 3.8 or newer**

**What it is**: The programming language HANS is written in.

**Why you need it**: To run all the Python scripts (API server, database setup, experiments).

**How to check if you have it**:
```bash
python3 --version
```

**If you don't have it**:
- **Mac**: Open Terminal and run `brew install python3` (if you have Homebrew) or download from [python.org](https://www.python.org/downloads/)
- **Linux**: Run `sudo apt-get install python3 python3-pip` (Ubuntu/Debian) or `sudo yum install python3 python3-pip` (RedHat/CentOS)
- **Windows**: Download from [python.org](https://www.python.org/downloads/) and install

---

### 2. **Docker Desktop**

**What it is**: A tool that runs software in isolated "containers" - think of it like a mini virtual machine.

**Why you need it**: HANS needs a PostgreSQL database (a system for storing and searching data). Docker makes it incredibly easy to run PostgreSQL without complicated installation.

**How to check if you have it**:
```bash
docker --version
```

**If you don't have it**:
- **Mac**: Download Docker Desktop from [docker.com/products/docker-desktop](https://www.docker.com/products/docker-desktop)
- **Linux**: Follow instructions at [docs.docker.com/engine/install](https://docs.docker.com/engine/install/)
- **Windows**: Download Docker Desktop from [docker.com/products/docker-desktop](https://www.docker.com/products/docker-desktop)

**After installing**: Open Docker Desktop and let it start. You should see a whale icon in your system tray.

---

### 3. **PostgreSQL Client Tools** (specifically `psql`)

**What it is**: A command-line tool to talk to PostgreSQL databases.

**Why you need it**: The setup scripts use `psql` to create tables and load data into the database.

**How to check if you have it**:
```bash
psql --version
```

**If you don't have it**:
- **Mac**: Run `brew install postgresql` (installs the client tools, not the full server)
- **Linux**: Run `sudo apt-get install postgresql-client` (Ubuntu/Debian) or `sudo yum install postgresql` (RedHat/CentOS)
- **Windows**: Download from [postgresql.org/download/windows](https://www.postgresql.org/download/windows/) and choose "Command Line Tools"

---

### 4. **Git** (optional, but recommended)

**What it is**: A tool for copying and managing code.

**Why you need it**: Makes it easy to transfer the HANS files from one computer to another.

**How to check if you have it**:
```bash
git --version
```

**If you don't have it**:
- Download from [git-scm.com](https://git-scm.com/downloads)

---

## 📂 Getting the Files

### Option A: Copy from USB/Network Drive

If you have the files on a USB drive or network location:

```bash
# Navigate to where you want to put HANS
cd ~/Desktop  # or any folder you prefer

# Copy the folder
cp -r /path/to/usb/hans_experiments/baseline_copy ./Hans_DB_Experimental

# Go into the folder
cd Hans_DB_Experimental
```

### Option B: Transfer via SCP (if copying from another computer)

```bash
# On the NEW computer, run this command
# Replace 'old-computer-ip' with the IP address of the old computer
# Replace 'username' with your username on the old computer
scp -r username@old-computer-ip:/Users/koware/Desktop/HANS/Hans_DB/hans_experiments/baseline_copy ~/Desktop/Hans_DB_Experimental
```

---

## 🔧 Step-by-Step Setup

### Step 1: Install Python Dependencies

**What this does**: Installs all the Python libraries HANS needs (like AI models, web server, database connector).

```bash
# Make sure you're in the HANS folder
cd ~/Desktop/Hans_DB_Experimental  # adjust path if different

# Install everything from requirements.txt
pip3 install -r requirements.txt
```

**This will install**:
- `sentence-transformers` - For embeddings (converting text to numbers for similarity search)
- `psycopg` - For connecting to PostgreSQL
- `fastapi` - For the web API
- `aiohttp` - For making HTTP requests
- And several other libraries

**Expected time**: 2-5 minutes depending on your internet speed.

---

### Step 2: Start the PostgreSQL Database

**What this does**: Creates a Docker container with PostgreSQL + pgvector (a plugin for searching similar text).

**Why port 5433**: The default PostgreSQL port is 5432, but we use 5433 to avoid conflicts if you already have PostgreSQL running on your computer.

```bash
# Make the script executable (Mac/Linux only)
chmod +x scripts/start_local_db.sh

# Run the script
bash scripts/start_local_db.sh
```

**What happens**:
1. Docker downloads the `pgvector/pgvector:pg16` image (~200MB) - only happens first time
2. Creates a container named `hans-pg` running PostgreSQL 16
3. Maps port 5433 on your computer to port 5432 inside the container
4. Creates a persistent volume `hans_pgdata` so your data isn't lost when the container stops

**Expected output**:
```
🐘 Starting local PostgreSQL + pgvector for HANS experiments...
🏗️ Creating new PostgreSQL container 'hans-pg'...
⏳ Waiting for PostgreSQL to initialize...
✅ PostgreSQL container created and running
📍 Connection: postgresql://postgres:postgres@localhost:5433/hans
```

**Troubleshooting**:
- If you see "port 5433 is already in use", either stop whatever is using that port, or edit `scripts/start_local_db.sh` to use a different port (like 5434), then also update `.env.local` to match
- If Docker isn't running, you'll see "Cannot connect to the Docker daemon". Open Docker Desktop first.

---

### Step 3: Initialize the Database Schema and Load Data

**What this does**:
1. Creates the database tables (places to store documents, chunks, Q&A pairs)
2. Enables the pgvector extension (for similarity search)
3. Processes all your content files (web pages, Excel Q&A)
4. Generates embeddings using the multilingual-e5-base model
5. Stores everything in the database with vector indexes

**Why this takes time**: The system has to:
- Read ~175 documents from your data files
- Break them into 800-character chunks
- Convert each chunk into a 768-dimensional vector using AI
- Insert thousands of records into the database
- Build vector indexes for fast search

```bash
# Load environment variables (tells Python where the database is)
export $(grep -v '^#' .env.local | xargs)

# Make the script executable (Mac/Linux only)
chmod +x scripts/init_local_db.sh

# Run the initialization script
bash scripts/init_local_db.sh
```

**What happens**:
1. **Enables pgvector extension** (~1 second)
2. **Creates tables** from `db/ddl.sql` (~1 second):
   - `documents` - Stores metadata about each source document
   - `web_chunks` - Stores text chunks from web pages with their embeddings
   - `qa_pairs` - Stores Q&A pairs with their embeddings
   - Vector indexes for fast similarity search
3. **Runs ingestion** (`scripts/build_content_db.py --force`) (~5-10 minutes):
   - Downloads the `intfloat/multilingual-e5-base` model (~500MB, first time only)
   - Processes JSON files from `pages/` directory
   - Processes Excel files (Q&A training data)
   - Generates embeddings with "passage: " prefix (special for E5 models)
   - Inserts into database

**Expected output**:
```
🔧 Initializing local HANS database...
📍 Database URL: postgresql://postgres:postgres@localhost:5433/hans
🔌 Testing database connection...
✅ Database connection successful
📦 Enabling pgvector extension...
✅ pgvector extension enabled
📋 Applying database schema from db/ddl.sql...
✅ Schema applied successfully
📚 Running content ingestion (this may take a few minutes)...

[You'll see progress messages like:]
Processing document 1/174...
Processing document 2/174...
...
Generated 1250 chunks from 174 documents
Embedding chunks (this may take a while)...
...

✅ Local database initialization complete!

📊 Database summary:
 documents | web_chunks | qa_pairs
-----------+------------+----------
       174 |       1250 |       85
```

**Troubleshooting**:
- **"DATABASE_URL environment variable not set"**: You forgot to run the `export` command. Run it and try again.
- **"Cannot connect to database"**: Make sure Step 2 (start_local_db.sh) completed successfully and the container is running (`docker ps` should show `hans-pg`)
- **"psql command not found"**: You need to install PostgreSQL client tools (see Prerequisites section)
- **Out of memory**: The embedding model needs ~2GB RAM. Close other applications if needed.

---

### Step 4: Start the HANS API Server

**What this does**: Starts a web server that listens for questions and returns answers using the RAG (Retrieval-Augmented Generation) system.

**The pipeline**:
1. You send a question (e.g., "What is the semester fee?")
2. Server converts your question to an embedding (with "query: " prefix)
3. Searches the database for the 30 most similar chunks
4. **Reranks** those 30 using a cross-encoder model to find the truly relevant ones
5. Keeps the best 10 chunks
6. Feeds those 10 chunks + your question to the LLM (Llama 3 via Ollama)
7. LLM generates an answer following the strict system prompt (English-only, concise, grounded)
8. Returns the answer + confidence score + sources

```bash
# Make sure environment variables are still set
export $(grep -v '^#' .env.local | xargs)

# Start the API server
python api_server.py
```

**Expected output**:
```
INFO:     Starting HANS API server on 127.0.0.1:8080
INFO:     Loading embedding model: intfloat/multilingual-e5-base
INFO:     Loading reranker model: cross-encoder/ms-marco-MiniLM-L-6-v2
✅ HANS agent initialized successfully
INFO:     Uvicorn running on http://127.0.0.1:8080 (Press CTRL+C to quit)
```

**First startup**: Takes 10-20 seconds to load both AI models into memory.

**Keep this terminal open** - the server needs to keep running.

---

### Step 5: Test the System

**What this does**: Runs 10 test queries through the system to verify everything works and to see the quality of answers.

**Open a NEW terminal window** (keep the API server running in the first one).

```bash
# Navigate to the HANS folder
cd ~/Desktop/Hans_DB_Experimental  # adjust path if different

# Load environment variables
export $(grep -v '^#' .env.local | xargs)

# Run the experiment
python experiments/run_experiments.py
```

**What happens**:
1. Checks if the API is running (health check)
2. Loads 10 test queries from `experiments/test_queries.json`
3. Sends each query to the API
4. Displays the results in a formatted way
5. Asks you to name the experiment (type any name, e.g., "first_test")
6. Saves results to `experiments/results/first_test.json`

**Expected output**:
```
🔧 HANS RAG Experiment Runner
API endpoint: http://localhost:8080/ask
Test queries: experiments/test_queries.json
✅ API server is healthy

📚 Loaded 10 test queries

================================================================================
Query 1: What is the application deadline for Master's programs?
================================================================================

📄 ANSWER:
The application deadlines for Master's programs at HTW Berlin vary by program
and intake period. Generally, summer semester applications are due around
mid-January, while winter semester applications are due around mid-July.
However, these dates can differ for specific programs, so I recommend checking
the official HTW Berlin website or contacting Student Services directly for
the exact deadline for your chosen program.

📊 CONFIDENCE: 75%

📚 SOURCES (10):
  1. Application Process - Master's Programs - https://www.htw-berlin.de/...
  2. Deadlines and Important Dates - https://www.htw-berlin.de/...
  ...

================================================================================
[... 9 more queries ...]
================================================================================

✅ Enter experiment name (press Enter for auto-generated): first_test

💾 Results saved to: experiments/results/first_test.json

✅ Experiment completed!
  Total queries: 10
  Successful: 10
  Failed: 0
```

---

## 🎉 Success! What Now?

### Stopping Everything

**Stop the API server**:
- Go to the terminal where `api_server.py` is running
- Press `Ctrl+C`

**Stop the database**:
```bash
docker stop hans-pg
```

**Stop and remove everything** (database + data):
```bash
docker stop hans-pg
docker rm hans-pg
docker volume rm hans_pgdata
```

---

### Restarting Later

**Start the database**:
```bash
cd ~/Desktop/Hans_DB_Experimental
bash scripts/start_local_db.sh
```

**Start the API**:
```bash
export $(grep -v '^#' .env.local | xargs)
python api_server.py
```

That's it! The data is already in the database, you don't need to re-initialize.

---

## 📊 Understanding the Files

### Configuration Files

**`.env.local`** - Database connection string
```
DATABASE_URL=postgresql://postgres:postgres@localhost:5433/hans
```

**`config.yaml`** - All system settings
```yaml
model:
  embedding_model: intfloat/multilingual-e5-base  # Multilingual AI model
  embedding_dim: 768                              # Vector size

ingestion:
  chunk_chars: 800      # Break documents into 800-char pieces
  chunk_overlap: 150    # Overlap by 150 chars for context
  min_chars: 300        # Keep chunks at least 300 chars
  skip_short: false     # Don't throw away short pieces

retrieval:
  top_k_db: 30          # Fetch 30 candidates from database
  top_k: 10             # Keep best 10 after reranking
  min_score: 0.0        # No score filtering (keep all candidates)
  reranker:
    enabled: true       # Use cross-encoder reranking
    model_name: cross-encoder/ms-marco-MiniLM-L-6-v2
    max_rerank: 30
```

---

### Data Files

**`pages/`** - JSON files scraped from HTW Berlin website
- Each file contains HTML content from a web page
- Ingestion script extracts text and breaks it into chunks

**`*.xlsx`** - Excel files with Q&A pairs
- Training data with questions and answers
- Used to improve answer quality on common questions

---

### Core Code Files

**`hans_db_agents.py`** - The main RAG orchestrator
- Loads configuration
- Calls retrieval system
- Formats context for LLM
- Contains the system prompt (rules for answering)

**`hansdb/embeddings.py`** - Converts text to vectors
- Uses `sentence-transformers` library
- Special functions for E5 models:
  - `embed_query()` - Adds "query: " prefix
  - `embed_passages()` - Adds "passage: " prefix

**`hansdb/retrieval.py`** - Searches the database
- Performs vector similarity search
- Applies reranking with cross-encoder
- Filters and sorts results

**`api_server.py`** - Web server
- Built with FastAPI
- Endpoints:
  - `GET /health` - Check if server is running
  - `POST /ask` - Send a question, get an answer

---

## 🐛 Common Problems

### "Port 5433 is already in use"

**Problem**: Another program is using port 5433.

**Solution**: Either stop that program, or use a different port:

1. Edit `scripts/start_local_db.sh`:
   - Change `-p 5433:5432` to `-p 5434:5432`
2. Edit `.env.local`:
   - Change `localhost:5433` to `localhost:5434`
3. Re-run the database startup

---

### "Cannot connect to the Docker daemon"

**Problem**: Docker Desktop isn't running.

**Solution**:
1. Open Docker Desktop
2. Wait for it to fully start (whale icon should be steady, not animated)
3. Try again

---

### "Model download is stuck"

**Problem**: The first time you run ingestion, it downloads ~500MB of AI models. If your internet is slow or interrupted, it might seem stuck.

**Solution**:
- Be patient, it can take 5-10 minutes on slow connections
- Check your internet connection
- If truly stuck, press `Ctrl+C`, delete the cached models, and try again:
  ```bash
  rm -rf ~/.cache/huggingface/
  ```

---

### "Out of memory" during ingestion

**Problem**: The embedding model needs ~2GB RAM. If your computer is low on memory, Python might crash.

**Solution**:
- Close other applications (browsers, IDEs, etc.)
- Increase your system's swap space
- If on a very old computer, consider using a smaller model (ask for help with this)

---

### Answers are poor quality

**Problem**: The system gives bad answers or says "I don't have this information" when it should know.

**Possible causes**:
1. **Database wasn't properly initialized**: Re-run `bash scripts/init_local_db.sh`
2. **Wrong data files**: Make sure the `pages/` folder and Excel files were copied correctly
3. **Ollama LLM not running**: The system expects Llama 3 via Ollama on `localhost:11434`. If you don't have this, you'll need to set it up separately (see Ollama documentation)

---

## 🔍 What Are The 4 Changes?

### Change 1: Better Chunking (from ~1800 to 800 characters)

**What it was**: Documents were broken into large 1800-character chunks.

**Problem**: Large chunks contain lots of unrelated information, making it hard to find the exact answer.

**What we changed**:
- Reduced chunk size to 800 characters
- Lowered minimum size to 300 (keep more small pieces)
- Set overlap to 150 characters

**Why it helps**: Smaller chunks = more precise retrieval = less noise in the context given to the LLM.

---

### Change 2: Smarter Retrieval (10 sources + filtering)

**What it was**: Fetched 6 sources, no filtering.

**Problem**: 6 sources might miss relevant information; no mechanism to filter out weak matches.

**What we changed**:
- Fetch 10 sources instead of 6 (more context for LLM)
- Added `min_score` filter (currently set to 0.0 but ready to use)

**Why it helps**: More sources = better coverage; filtering capability = can tune precision vs recall.

---

### Change 3: Better System Prompt (English-only, concise, grounded)

**What it was**: Generic assistant prompt.

**Problem**: Answers were sometimes in German, too verbose, or contained hallucinations.

**What we changed**: Complete rewrite with strict rules:
- ALWAYS answer in English
- Maximum 2 paragraphs + 1 bullet list (~150-180 words)
- Never invent facts (deadlines, fees, etc.)
- Explicitly say when information is missing
- Acknowledge when things vary by program

**Why it helps**: Consistent, trustworthy answers that international students can understand.

---

### Change 4: Multilingual Embeddings + Reranking

**What it was**:
- English-only embedding model (BAAI/bge-base-en-v1.5)
- No reranking (just trust the vector search)

**Problem**:
- German questions matched poorly with English documents
- Vector search sometimes retrieves off-topic chunks

**What we changed**:
- Upgraded to `intfloat/multilingual-e5-base` (understands 100+ languages)
- Added cross-encoder reranker:
  1. Fetch 30 candidates from database (cast a wide net)
  2. Rerank with semantic similarity model (filter out noise)
  3. Keep best 10 (precision)

**Why it helps**:
- German/multilingual questions work better
- Reranking dramatically improves relevance
- Fewer hallucinations because LLM gets better context

---

## 📚 Learn More

- **System prompt**: See `hans_db_agents.py` line ~151 for the exact rules given to the LLM
- **Retrieval pipeline**: See `hansdb/retrieval.py` for the two-stage search + rerank logic
- **Experiments README**: See `experiments/README.md` for detailed documentation of all 4 changes
- **Configuration**: See `config.yaml` for all tunable parameters

---

## 💡 Tips for Best Results

1. **Update your data files regularly** - If HTW Berlin changes their website or policies, re-scrape and re-run ingestion
2. **Tune the min_score filter** - Currently set to 0.0 (off). Try values like 0.3 or 0.5 to filter weak matches
3. **Monitor answer quality** - Run experiments regularly and review the results
4. **Adjust chunk size** - If answers seem to lack context, try 1000 chars; if too much noise, try 600 chars
5. **Experiment with top_k** - More sources (15-20) might help complex questions; fewer (5-8) might reduce noise

---

## 🆘 Getting Help

If you're stuck:
1. Check the "Common Problems" section above
2. Review the terminal output for error messages
3. Check that all prerequisites are installed and working
4. Verify the data files are present and not corrupted
5. Try the Docker troubleshooting: `docker ps`, `docker logs hans-pg`

---

**Good luck! 🚀**
