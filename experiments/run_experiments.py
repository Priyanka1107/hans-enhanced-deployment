#!/usr/bin/env python3
"""
HANS RAG Experiment Runner

This script sends test queries to the HANS API and logs responses for comparison.

Prerequisites:
1. Start the API server from the baseline_copy directory:
   cd hans_experiments/baseline_copy
   python api_server.py

2. In another terminal, run this script:
   python experiments/run_experiments.py
"""

import json
import requests
import sys
from pathlib import Path
from datetime import datetime

# Configuration
API_URL = "http://localhost:8080/ask"
TEST_QUERIES_FILE = Path(__file__).parent / "test_queries.json"
RESULTS_DIR = Path(__file__).parent / "results"

def load_test_queries():
    """Load test queries from JSON file."""
    with open(TEST_QUERIES_FILE, 'r', encoding='utf-8') as f:
        return json.load(f)

def send_query(query: str, timeout: int = 60):
    """Send a query to the HANS API and return the response."""
    try:
        response = requests.post(
            API_URL,
            json={"q": query, "max_sources": 10},
            timeout=timeout
        )
        response.raise_for_status()
        return response.json()
    except requests.exceptions.ConnectionError:
        print(f"❌ ERROR: Could not connect to API at {API_URL}")
        print("   Make sure the API server is running:")
        print("   cd hans_experiments/baseline_copy && python api_server.py")
        sys.exit(1)
    except requests.exceptions.Timeout:
        return {"error": "Request timed out", "query": query}
    except Exception as e:
        return {"error": str(e), "query": query}

def format_response(query: str, response: dict, index: int):
    """Format API response for readable output."""
    output = [
        f"\n{'='*80}",
        f"Query {index + 1}: {query}",
        f"{'='*80}",
    ]

    if "error" in response:
        output.append(f"❌ ERROR: {response['error']}")
    else:
        output.append(f"\n📝 ANSWER:")
        output.append(f"{response.get('answer', 'N/A')}")
        output.append(f"\n📊 CONFIDENCE: {response.get('confidence_pct', 'N/A')}%")

        sources = response.get('sources', [])
        if sources:
            output.append(f"\n📚 SOURCES ({len(sources)}):")
            for i, source in enumerate(sources, 1):
                title = source.get('title', 'N/A')
                url = source.get('url', 'N/A')
                output.append(f"   {i}. {title} - {url}")
        else:
            output.append("\n📚 SOURCES: None")

    return "\n".join(output)

def save_results(results: list, experiment_name: str = None):
    """Save experiment results to a JSON file."""
    RESULTS_DIR.mkdir(exist_ok=True)

    if experiment_name is None:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        experiment_name = f"experiment_{timestamp}"

    results_file = RESULTS_DIR / f"{experiment_name}.json"

    with open(results_file, 'w', encoding='utf-8') as f:
        json.dump(results, f, indent=2, ensure_ascii=False)

    print(f"\n💾 Results saved to: {results_file}")

def main():
    print("🚀 HANS RAG Experiment Runner")
    print(f"API endpoint: {API_URL}")
    print(f"Test queries: {TEST_QUERIES_FILE}")

    # Check API health
    try:
        health_response = requests.get("http://localhost:8080/health", timeout=5)
        if health_response.status_code == 200:
            print("✅ API server is healthy\n")
        else:
            print(f"⚠️  API health check returned status {health_response.status_code}\n")
    except:
        print("❌ Cannot reach API server. Please start it first:")
        print("   cd hans_experiments/baseline_copy && python api_server.py\n")
        sys.exit(1)

    # Load queries
    queries = load_test_queries()
    print(f"📋 Loaded {len(queries)} test queries\n")

    # Run experiments
    results = []
    for i, query in enumerate(queries):
        print(f"⏳ Processing query {i + 1}/{len(queries)}...", end="\r")
        response = send_query(query)

        result = {
            "query": query,
            "response": response,
            "timestamp": datetime.now().isoformat()
        }
        results.append(result)

        # Print formatted output
        print(format_response(query, response, i))

    # Save results
    experiment_name = input("\n📝 Enter experiment name (press Enter for auto-generated): ").strip()
    if not experiment_name:
        experiment_name = None

    save_results(results, experiment_name)

    print("\n✅ Experiment completed!")
    print(f"   Total queries: {len(queries)}")
    print(f"   Successful: {sum(1 for r in results if 'error' not in r['response'])}")
    print(f"   Failed: {sum(1 for r in results if 'error' in r['response'])}")

if __name__ == "__main__":
    main()
