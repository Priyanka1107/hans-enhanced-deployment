#!/usr/bin/env python3
"""
Database-backed HTW Berlin Student Services Assistant Launcher

This launches the database-backed version of HANS that replaces FAISS/pickle 
with PostgreSQL + pgvector retrieval.
"""

import sys
import os
import subprocess
import asyncio
from pathlib import Path

# Add project root to path
sys.path.append(str(Path(__file__).parent))

from hans_db_agents import check_database_ready, get_database_agent

def check_requirements():
    """Check if all required packages are installed"""
    required_packages = [
        ('pandas', 'pandas'),
        ('numpy', 'numpy'),
        ('openpyxl', 'openpyxl'),
        ('aiohttp', 'aiohttp'),
        ('psycopg', 'psycopg[binary]'),
        ('sentence_transformers', 'sentence-transformers'), 
        ('dotenv', 'python-dotenv'),
        ('yaml', 'pyyaml')
    ]
    
    missing_packages = []
    
    for import_name, package_name in required_packages:
        try:
            __import__(import_name)
        except ImportError:
            missing_packages.append(package_name)
    
    if missing_packages:
        print("Missing required packages:")
        for pkg in missing_packages:
            print(f"  - {pkg}")
        
        print("\nTo install missing packages, run:")
        print(f"pip install {' '.join(missing_packages)}")
        return False
    
    return True

def check_database_status():
    """Check database connectivity and readiness"""
    print("Checking database status...")
    
    try:
        is_ready, message = check_database_ready()
        
        if is_ready:
            print(f"✅ Database ready: {message}")
            return True
        else:
            print(f"❌ Database not ready: {message}")
            return False
    
    except Exception as e:
        print(f"❌ Database check failed: {e}")
        return False

def check_config_files():
    """Check if required configuration files exist"""
    required_files = [
        "config.yaml",
        ".env"
    ]
    
    missing_files = []
    
    for file_path in required_files:
        if not Path(file_path).exists():
            missing_files.append(file_path)
    
    if missing_files:
        print("Missing configuration files:")
        for file in missing_files:
            print(f"  - {file}")
        print("\nPlease ensure all configuration files are present.")
        return False
    
    return True

def print_setup_instructions():
    """Print database setup instructions"""
    print("\n" + "="*60)
    print("DATABASE SETUP REQUIRED")
    print("="*60)
    print("The database-backed system requires setup. Please follow these steps:")
    print()
    print("1. Install PostgreSQL and create a database:")
    print("   createdb hans")
    print()
    print("2. Install pgvector extension:")
    print("   psql -d hans -c 'CREATE EXTENSION vector;'")
    print()  
    print("3. Update DATABASE_URL in .env file:")
    print("   DATABASE_URL=postgresql://user:password@localhost:5432/hans")
    print()
    print("4. Set up database schema:")
    print("   psql \"$DATABASE_URL\" -f db/ddl.sql")
    print()
    print("5. Build content database:")
    print("   python scripts/build_content_db.py")
    print()
    print("6. Validate setup (optional):")
    print("   python scripts/validate_db.py")
    print()
    print("7. Re-run this launcher:")
    print("   python launch_assistant_db.py")
    print("="*60)

async def test_system():
    """Test the database system with a sample query"""
    print("\nTesting system with sample query...")
    
    try:
        agent = get_database_agent()
        
        test_query = "How do I apply to HTW Berlin?"
        print(f"Query: {test_query}")
        
        result = await agent.process_query(test_query)
        
        print(f"✅ System test successful!")
        print(f"Response length: {len(result['final_response'])} characters")
        print(f"Sources found: {result['metadata'].get('results_found', 0)}")
        
        agent.close()
        return True
    
    except Exception as e:
        print(f"❌ System test failed: {e}")
        return False

def launch_gui():
    """Launch the GUI version with database backend"""
    try:
        print("Launching GUI with database backend...")
        
        # Check if GUI file exists and update it to use database
        gui_files = [
            "htw_assistant_gui.py",
            "htw_assistant_gui_simple.py"
        ]
        
        gui_file = None
        for gf in gui_files:
            if Path(gf).exists():
                gui_file = gf
                break
        
        if gui_file:
            print(f"Found GUI file: {gui_file}")
            print("Note: You may need to update the GUI file to use hans_db_agents instead of mcp_agents")
            subprocess.run([sys.executable, gui_file])
        else:
            print("No GUI file found. Running console version...")
            launch_console()
    
    except KeyboardInterrupt:
        print("\nGUI closed by user.")
    except Exception as e:
        print(f"GUI launch failed: {e}")
        print("Falling back to console mode...")
        launch_console()

async def launch_console():
    """Launch console interface with database backend"""
    print("="*60)
    print("HTW BERLIN STUDENT SERVICES ASSISTANT (Database Version)")
    print("="*60)
    print("Type 'quit' or 'exit' to stop")
    print()
    
    agent = get_database_agent()
    
    try:
        while True:
            try:
                query = input("You: ").strip()
                
                if query.lower() in ['quit', 'exit', 'q']:
                    break
                
                if not query:
                    continue
                
                print("HANS: Processing your query...")
                
                result = await agent.process_query(query)
                response = result['final_response']
                metadata = result['metadata']
                
                print(f"HANS: {response}")
                
                # Show metadata if sources found
                if metadata.get('results_found', 0) > 0:
                    print(f"\n[Found {metadata['results_found']} relevant sources]")
                
                print("-" * 60)
            
            except KeyboardInterrupt:
                break
            except Exception as e:
                print(f"Error processing query: {e}")
                print("Please try again.")
    
    finally:
        agent.close()
        print("\nGoodbye!")

def main():
    """Main launcher function"""
    print("HTW Berlin Student Services Assistant (Database Version)")
    print("Initializing...")
    
    # Check requirements
    if not check_requirements():
        print("Please install missing requirements first.")
        return 1
    
    # Check config files
    if not check_config_files():
        print("Please set up configuration files first.")
        return 1
    
    # Check database
    if not check_database_status():
        print_setup_instructions()
        return 1
    
    # Run system test
    if not asyncio.run(test_system()):
        print("System test failed. Please check your setup.")
        return 1
    
    # Ask user which interface to use
    print("\nSelect interface:")
    print("1. GUI (recommended)")
    print("2. Console")
    
    try:
        choice = input("Enter choice (1 or 2): ").strip()
        
        if choice == "1":
            launch_gui()
        elif choice == "2":
            asyncio.run(launch_console())
        else:
            print("Invalid choice. Launching console interface...")
            asyncio.run(launch_console())
    
    except KeyboardInterrupt:
        print("\nExiting...")
    
    return 0

if __name__ == "__main__":
    sys.exit(main())