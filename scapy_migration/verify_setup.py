#!/usr/bin/env python3
"""
Verify setup before running migration.
Checks all prerequisites and reports status.
"""

import sys
from pathlib import Path
import yaml

def check_python_version():
    """Check Python version >= 3.8"""
    print("Checking Python version...", end=" ")
    if sys.version_info >= (3, 8):
        print(f"✓ {sys.version.split()[0]}")
        return True
    else:
        print(f"✗ {sys.version.split()[0]} (need >= 3.8)")
        return False


def check_packages():
    """Check required packages are installed"""
    print("\nChecking Python packages:")
    packages = {
        'sentence_transformers': 'sentence-transformers',
        'psycopg': 'psycopg[binary]',
        'yaml': 'pyyaml',
        'numpy': 'numpy'
    }

    all_ok = True
    for module, package in packages.items():
        try:
            __import__(module)
            print(f"  ✓ {package}")
        except ImportError:
            print(f"  ✗ {package} - run: pip3 install {package}")
            all_ok = False

    return all_ok


def check_objects_directory():
    """Check scapy objects directory exists"""
    print("\nChecking scapy objects directory...", end=" ")

    objects_dir = Path('../scapy/htw_scrape/outputs/objects')

    if not objects_dir.exists():
        print(f"✗ Not found: {objects_dir.absolute()}")
        return False

    json_files = list(objects_dir.glob('*.json'))
    if len(json_files) == 0:
        print(f"✗ No JSON files in {objects_dir}")
        return False

    print(f"✓ Found {len(json_files)} objects")
    return True


def check_config_file():
    """Check config.yaml exists and is valid"""
    print("\nChecking config.yaml...", end=" ")

    config_path = Path('../config.yaml')

    if not config_path.exists():
        print(f"✗ Not found: {config_path.absolute()}")
        print("  Create config.yaml or use --config flag")
        return False

    try:
        with open(config_path, 'r') as f:
            config = yaml.safe_load(f)

        # Check for required fields
        if 'database' not in config or 'url' not in config['database']:
            print("✗ Missing database.url in config")
            return False

        print("✓ Valid")
        return True
    except Exception as e:
        print(f"✗ Error loading: {e}")
        return False


def check_database_connection():
    """Check database connection"""
    print("\nChecking database connection...", end=" ")

    try:
        import psycopg
        import os

        # Try to load DATABASE_URL from .env.local
        env_file = Path('../.env.local')
        if env_file.exists():
            with open(env_file, 'r') as f:
                for line in f:
                    if line.startswith('DATABASE_URL='):
                        db_url = line.strip().split('=', 1)[1]
                        os.environ['DATABASE_URL'] = db_url
                        break

        db_url = os.environ.get('DATABASE_URL')
        if not db_url:
            print("✗ DATABASE_URL not set")
            print("  Set in .env.local or environment")
            return False

        # Try to connect
        conn = psycopg.connect(db_url)

        # Check if web_chunks table exists
        with conn.cursor() as cur:
            cur.execute("""
                SELECT COUNT(*) FROM information_schema.tables
                WHERE table_name = 'web_chunks'
            """)
            if cur.fetchone()[0] == 0:
                print("✗ web_chunks table not found")
                print("  Run database setup: bash scripts/start_local_db.sh")
                conn.close()
                return False

        conn.close()
        print("✓ Connected")
        return True

    except Exception as e:
        print(f"✗ Error: {e}")
        print("  Check PostgreSQL is running: docker ps | grep postgres")
        return False


def check_models_downloadable():
    """Check if models can be downloaded/loaded"""
    print("\nChecking model availability...", end=" ")

    try:
        from sentence_transformers import SentenceTransformer

        # Try to load BGE model (will download if needed)
        print("\n  Downloading BGE model (this may take a few minutes)...", end=" ")
        model = SentenceTransformer('BAAI/bge-base-en-v1.5')
        print("✓")

        # Try reranker
        print("  Downloading reranker model...", end=" ")
        from sentence_transformers import CrossEncoder
        reranker = CrossEncoder('cross-encoder/ms-marco-MiniLM-L-6-v2')
        print("✓")

        return True

    except Exception as e:
        print(f"✗ Error: {e}")
        print("  Check internet connection")
        return False


def main():
    print("=" * 60)
    print("HANS Scapy Migration - Setup Verification")
    print("=" * 60)

    checks = [
        ("Python version", check_python_version),
        ("Python packages", check_packages),
        ("Scapy objects", check_objects_directory),
        ("Config file", check_config_file),
        ("Database", check_database_connection),
        ("Models", check_models_downloadable),
    ]

    results = {}
    for name, check_func in checks:
        try:
            results[name] = check_func()
        except Exception as e:
            print(f"\n✗ {name} check failed: {e}")
            results[name] = False

    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)

    all_passed = all(results.values())

    for name, passed in results.items():
        status = "✓ PASS" if passed else "✗ FAIL"
        print(f"{status}: {name}")

    print("=" * 60)

    if all_passed:
        print("\n✓ All checks passed! Ready to run migration.")
        print("\nNext step:")
        print("  python3 migrate_scapy_to_db.py --objects-dir ../scapy/htw_scrape/outputs/objects --dry-run")
        return 0
    else:
        print("\n✗ Some checks failed. Fix issues above before proceeding.")
        return 1


if __name__ == '__main__':
    sys.exit(main())
