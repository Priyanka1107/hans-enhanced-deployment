#!/usr/bin/env python3
"""
HANS Database Validation Script

Smoke test for the database-backed RAG system.
Validates embeddings, retrieval, and overall system health.
"""

import sys
import logging
from pathlib import Path
from typing import Dict, Any

# Add project root to Python path
sys.path.append(str(Path(__file__).parent.parent))

from hansdb.conn import load_config, get_db_connection, check_database_status
from hansdb.retrieval import retrieve_top_k, get_retrieval_stats
from hansdb.embeddings import embed_single_text

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class DatabaseValidator:
    """Validates database setup and functionality"""
    
    def __init__(self, config: dict):
        self.config = config
        self.conn = None
        self.test_results = {}
    
    def connect(self) -> bool:
        """Test database connection"""
        logger.info("Testing database connection...")
        
        try:
            self.conn = get_db_connection(self.config)
            self.test_results['connection'] = True
            logger.info("✅ Database connection successful")
            return True
        except Exception as e:
            self.test_results['connection'] = False
            logger.error(f"❌ Database connection failed: {e}")
            return False
    
    def validate_schema(self) -> bool:
        """Validate database schema and version"""
        logger.info("Validating database schema...")
        
        try:
            is_ready, message = check_database_status(self.config)
            
            if is_ready:
                self.test_results['schema'] = True
                logger.info("✅ Database schema validation passed")
                return True
            else:
                self.test_results['schema'] = False
                logger.error(f"❌ Database schema validation failed: {message}")
                return False
        
        except Exception as e:
            self.test_results['schema'] = False
            logger.error(f"❌ Schema validation error: {e}")
            return False
    
    def check_data_availability(self) -> bool:
        """Check if data is available in the database"""
        logger.info("Checking data availability...")
        
        try:
            stats = get_retrieval_stats(self.conn)
            
            self.test_results['data_stats'] = stats
            
            if stats['documents'] > 0 or stats['web_chunks'] > 0 or stats['qa_pairs'] > 0:
                logger.info("✅ Data found in database:")
                logger.info(f"   Documents: {stats['documents']}")
                logger.info(f"   Web chunks: {stats['web_chunks']}")
                logger.info(f"   Q&A pairs: {stats['qa_pairs']}")
                self.test_results['data_availability'] = True
                return True
            else:
                logger.warning("⚠️  No data found in database")
                logger.warning("   Run scripts/build_content_db.py to populate the database")
                self.test_results['data_availability'] = False
                return False
        
        except Exception as e:
            self.test_results['data_availability'] = False
            logger.error(f"❌ Data availability check failed: {e}")
            return False
    
    def test_embedding_generation(self) -> bool:
        """Test embedding generation"""
        logger.info("Testing embedding generation...")
        
        try:
            test_text = "How do I enroll at HTW Berlin?"
            embedding = embed_single_text(test_text, self.config['model']['embedding_model'])
            
            expected_dim = self.config['model']['embedding_dim']
            actual_dim = len(embedding)
            
            if actual_dim == expected_dim:
                logger.info(f"✅ Embedding generation successful (dimension: {actual_dim})")
                self.test_results['embedding'] = True
                return True
            else:
                logger.error(f"❌ Embedding dimension mismatch. Expected: {expected_dim}, Got: {actual_dim}")
                self.test_results['embedding'] = False
                return False
        
        except Exception as e:
            self.test_results['embedding'] = False
            logger.error(f"❌ Embedding generation failed: {e}")
            return False
    
    def test_retrieval(self) -> bool:
        """Test retrieval functionality"""
        logger.info("Testing retrieval functionality...")
        
        test_queries = [
            "How do I enroll at HTW Berlin?",
            "What are the language requirements for international students?",
            "When is the application deadline?"
        ]
        
        try:
            for i, query in enumerate(test_queries):
                logger.info(f"Testing query {i+1}: {query}")
                
                results = retrieve_top_k(
                    self.conn, 
                    query, 
                    top_k=3,
                    model_name=self.config['model']['embedding_model']
                )
                
                logger.info(f"   Found {len(results)} results:")
                
                for j, result in enumerate(results):
                    source_type = result['source_type']
                    score = result['score']
                    title = result.get('title', 'N/A')
                    url = result.get('url', 'N/A')
                    content_preview = result['content'][:100] + "..." if len(result['content']) > 100 else result['content']
                    
                    logger.info(f"     {j+1}. [{source_type}] {title} (score: {score:.3f})")
                    logger.info(f"        URL: {url}")
                    logger.info(f"        Content: {content_preview}")
                    
                    # Check contacts and links for web sources
                    if source_type == 'web':
                        contacts = result.get('contacts')
                        links = result.get('links')
                        if contacts:
                            logger.info(f"        Contacts: {len(contacts)} entries")
                        if links:
                            logger.info(f"        Links: {len(links)} entries")
                
                logger.info("")  # Empty line for readability
            
            self.test_results['retrieval'] = True
            logger.info("✅ Retrieval testing completed successfully")
            return True
        
        except Exception as e:
            self.test_results['retrieval'] = False
            logger.error(f"❌ Retrieval testing failed: {e}")
            return False
    
    def test_vector_search_performance(self) -> bool:
        """Test vector search performance"""
        logger.info("Testing vector search performance...")
        
        try:
            import time
            
            query = "What are the admission requirements?"
            num_tests = 5
            times = []
            
            for i in range(num_tests):
                start_time = time.time()
                results = retrieve_top_k(self.conn, query, top_k=6)
                end_time = time.time()
                
                query_time = end_time - start_time
                times.append(query_time)
                
                logger.info(f"   Query {i+1}: {query_time:.3f}s, {len(results)} results")
            
            avg_time = sum(times) / len(times)
            logger.info(f"✅ Average query time: {avg_time:.3f}s")
            
            self.test_results['performance'] = {
                'avg_query_time': avg_time,
                'all_times': times
            }
            
            return True
        
        except Exception as e:
            self.test_results['performance'] = False
            logger.error(f"❌ Performance testing failed: {e}")
            return False
    
    def run_all_tests(self) -> Dict[str, Any]:
        """Run all validation tests"""
        logger.info("Starting HANS Database Validation")
        logger.info("=" * 50)
        
        tests = [
            ('Database Connection', self.connect),
            ('Schema Validation', self.validate_schema),
            ('Data Availability', self.check_data_availability),
            ('Embedding Generation', self.test_embedding_generation),
            ('Retrieval Functionality', self.test_retrieval),
            ('Vector Search Performance', self.test_vector_search_performance)
        ]
        
        passed = 0
        total = len(tests)
        
        for test_name, test_func in tests:
            logger.info(f"\n--- {test_name} ---")
            success = test_func()
            if success:
                passed += 1
        
        # Summary
        logger.info("\n" + "=" * 50)
        logger.info("VALIDATION SUMMARY")
        logger.info("=" * 50)
        logger.info(f"Tests passed: {passed}/{total}")
        
        if passed == total:
            logger.info("🎉 All tests passed! Database is ready for production use.")
        else:
            logger.warning(f"⚠️  {total - passed} test(s) failed. Review the errors above.")
        
        # Close connection
        if self.conn:
            self.conn.close()
        
        return self.test_results

def main():
    """Main validation function"""
    try:
        # Load configuration
        config = load_config()
        
        # Run validation
        validator = DatabaseValidator(config)
        results = validator.run_all_tests()
        
        # Exit with appropriate code
        all_passed = all([
            results.get('connection', False),
            results.get('schema', False),
            results.get('embedding', False),
            results.get('retrieval', False)
        ])
        
        if all_passed:
            sys.exit(0)
        else:
            sys.exit(1)
    
    except Exception as e:
        logger.error(f"Validation failed: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()