"""
Database connection management for HANS
"""

import os
import psycopg
import logging
from typing import Optional
from pathlib import Path
import yaml
from dotenv import load_dotenv

# Load environment variables with priority:
# 1. Current working directory .env.local (for experiments/baseline_copy)
# 2. Project root .env.local (for main project development)
# 3. Current working directory .env
# 4. Project root .env (default for main project)
project_root = Path(__file__).parent.parent
cwd = Path.cwd()

env_locations = [
    cwd / ".env.local",           # 1. CWD .env.local (highest priority)
    project_root / ".env.local",  # 2. Project root .env.local
    cwd / ".env",                 # 3. CWD .env
    project_root / ".env"         # 4. Project root .env
]

for env_file in env_locations:
    if env_file.exists():
        load_dotenv(env_file)
        break
else:
    # Last resort: try dotenv auto-discovery
    load_dotenv()

logger = logging.getLogger(__name__)

def load_config() -> dict:
    """Load configuration from config.yaml with environment variable substitution"""
    config_path = os.getenv("HANS_CONFIG_PATH", "config.yaml")

    try:
        with open(config_path, 'r') as f:
            content = f.read()
            # Replace environment variables in the format ${VAR_NAME}
            import re

            # Track missing variables
            missing_vars = []

            def replace_env_var(match):
                var_name = match.group(1)
                value = os.getenv(var_name)
                if value is None:
                    missing_vars.append(var_name)
                    return match.group(0)  # Keep original for error message
                return value

            content = re.sub(r'\$\{([^}]+)\}', replace_env_var, content)

            # Raise error if any variables were missing
            if missing_vars:
                raise ValueError(
                    f"Missing required environment variables: {', '.join(missing_vars)}. "
                    f"Please set them in your environment or .env.local file."
                )

            config = yaml.safe_load(content)
            return config
    except FileNotFoundError:
        logger.error(f"Configuration file not found: {config_path}")
        raise
    except yaml.YAMLError as e:
        logger.error(f"Error parsing configuration file: {e}")
        raise

def get_db_connection(config: Optional[dict] = None) -> psycopg.Connection:
    """
    Get database connection with proper configuration
    """
    if config is None:
        config = load_config()
    
    database_url = config["database"]["url"]
    
    if not database_url:
        raise ValueError("DATABASE_URL not found in environment or config")
    
    try:
        conn = psycopg.connect(database_url)
        
        # Set ivfflat.probes for better vector search performance
        probes = config.get("database_tuning", {}).get("ivfflat_probes", 10)
        with conn.cursor() as cur:
            cur.execute(f"SET ivfflat.probes = {probes}")
        
        conn.commit()
        logger.info("Database connection established")
        return conn
    
    except psycopg.Error as e:
        logger.error(f"Database connection failed: {e}")
        raise

def ensure_schema(conn: psycopg.Connection, required_version: int) -> None:
    """
    Ensure database schema matches the required version
    
    Args:
        conn: Database connection
        required_version: Required schema version from config
    
    Raises:
        RuntimeError: If schema version doesn't match
    """
    try:
        with conn.cursor() as cur:
            # Check if meta table exists and get schema version
            cur.execute("""
                SELECT EXISTS (
                    SELECT FROM information_schema.tables 
                    WHERE table_name = 'meta'
                )
            """)
            
            table_exists = cur.fetchone()[0]
            
            if not table_exists:
                raise RuntimeError(
                    "Database missing/out-of-date. Run scripts/build_content_db.py --force"
                )
            
            # Get current schema version
            cur.execute("SELECT value FROM meta WHERE key = 'schema_version'")
            result = cur.fetchone()
            
            if not result:
                raise RuntimeError(
                    "Database missing/out-of-date. Run scripts/build_content_db.py --force"
                )
            
            current_version = int(result[0])
            
            if current_version != required_version:
                raise RuntimeError(
                    f"Database schema version mismatch. "
                    f"Expected: {required_version}, Found: {current_version}. "
                    f"Run scripts/build_content_db.py --force"
                )
            
            logger.info(f"Schema version {current_version} verified")
    
    except psycopg.Error as e:
        logger.error(f"Schema verification failed: {e}")
        raise RuntimeError(
            "Database missing/out-of-date. Run scripts/build_content_db.py --force"
        ) from e

def check_database_status(config: Optional[dict] = None) -> tuple[bool, str]:
    """
    Check database connectivity and schema status
    
    Returns:
        (is_ready, message)
    """
    if config is None:
        config = load_config()
    
    try:
        conn = get_db_connection(config)
        required_version = config["schema_version"]
        
        ensure_schema(conn, required_version)
        conn.close()
        
        return True, "Database is ready"
    
    except Exception as e:
        return False, str(e)