"""
Database-backed MCP Agent Architecture for HTW Berlin Student Services Assistant

This replaces the FAISS/pickle-based system with PostgreSQL + pgvector retrieval.
"""

import asyncio
import aiohttp
import json
import logging
import os
import re
from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass
import psycopg

from hansdb.conn import load_config, get_db_connection, ensure_schema
from hansdb.retrieval import retrieve_top_k, retrieve_multi_query, get_retrieval_stats

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@dataclass
class AgentResponse:
    """Structure for agent responses"""
    agent_name: str
    response: str
    confidence: float
    sources: List[str]
    metadata: Dict[str, Any]

class OllamaClient:
    """Client for interacting with Ollama API with proxy support"""
    
    def __init__(self, base_url: str, timeout: int = 300, verify_ssl: bool = True):
        self.base_url = base_url.rstrip('/')
        self.timeout = timeout
        self.verify_ssl = verify_ssl
        self._session = None
    
    async def __aenter__(self):
        # Configure proxy settings from environment
        proxy_config = {}
        if os.getenv('HTTP_PROXY'):
            proxy_config['http'] = os.getenv('HTTP_PROXY')
        if os.getenv('HTTPS_PROXY'):
            proxy_config['https'] = os.getenv('HTTPS_PROXY')
        
        # Create SSL context
        ssl_context = None if self.verify_ssl else False
        
        self._session = aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(total=self.timeout),
            connector=aiohttp.TCPConnector(ssl=ssl_context),
            trust_env=True  # This enables proxy detection from environment
        )
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self._session:
            await self._session.close()
    
    async def chat(self, prompt: str, model: str) -> str:
        """Generate response using Ollama generate API"""
        url = f"{self.base_url}/api/generate"
        payload = {
            "model": model,
            "prompt": prompt,
            "stream": False
        }
        
        try:
            logger.info(f"Sending chat request to {url} with model {model}")
            async with self._session.post(url, json=payload) as response:
                logger.info(f"Response status: {response.status}")
                if response.status == 200:
                    result = await response.json()
                    response_text = result.get("response", "")
                    logger.info(f"Chat response received: {len(response_text)} characters")
                    return response_text
                else:
                    error_text = await response.text()
                    logger.error(f"Chat generation failed: {response.status} - {error_text}")
                    return ""
        except Exception as e:
            logger.error(f"Chat generation error: {e}")
            return ""

class DatabaseRAGAgent:
    """Database-backed RAG agent for HTW Berlin student services"""
    
    # Prompt used to decompose multi-part questions into self-contained sub-queries.
    # Kept short so the LLM responds fast; /no_think disables qwen3 chain-of-thought.
    DECOMPOSE_PROMPT = """You are a query decomposition assistant for a university student services chatbot.

Given a user question, decide whether it contains MULTIPLE distinct sub-questions.
- If YES: return a JSON array of 2-4 self-contained sub-queries. Each sub-query MUST include all relevant context from the original (programme name, degree level, nationality, qualification, etc.) so it can be searched independently.
- If NO (the question is about a single topic): return a JSON array with just the original question.

Rules:
- Output ONLY the JSON array, nothing else.
- Do NOT add explanations or markdown.
- Keep each sub-query concise (one sentence).

Examples:

User: "I'm an EU citizen with an IB diploma. I want to apply for the Cyber Security and Business Bachelor at HTW Berlin. Do I need uni-assist? Is a motivation letter required?"
["What is the application process for EU citizens applying for the Cyber Security and Business Bachelor at HTW Berlin?", "Do EU citizens with an International Baccalaureate need to apply through uni-assist for HTW Berlin?", "Is a motivation letter required for the Cyber Security and Business Bachelor at HTW Berlin?"]

User: "What are the admission requirements for the IT Master programme?"
["What are the admission requirements for the IT Master programme at HTW Berlin?"]

User: "When is the deadline for applying, and what documents do I need for the Data Science Master?"
["What is the application deadline for the Data Science Master at HTW Berlin?", "What documents are required for the Data Science Master application at HTW Berlin?"]

User question: """

    def __init__(self, config: dict):
        self.config = config
        self.db_conn = None
        self.retrieval_config = config['retrieval']
        self.runtime_config = config['runtime']
        self.decomposition_config = config.get('query_decomposition', {})

        # Initialize database connection
        self._initialize_database()
    
    def _initialize_database(self):
        """Initialize database connection and verify schema"""
        try:
            self.db_conn = get_db_connection(self.config)
            ensure_schema(self.db_conn, self.config['schema_version'])
            
            # Log database stats
            stats = get_retrieval_stats(self.db_conn)
            logger.info(f"Database initialized: {stats['documents']} docs, "
                       f"{stats['web_chunks']} chunks, {stats['qa_pairs']} Q&A pairs")
        
        except Exception as e:
            logger.error(f"Database initialization failed: {e}")
            raise RuntimeError(
                "Database missing/out-of-date. Run scripts/build_content_db.py --force"
            ) from e
    
    def _build_context_from_results(self, results: List[Dict]) -> str:
        """Build context string from retrieval results"""
        context_parts = []
        
        for i, result in enumerate(results, 1):
            source_type = result['source_type']
            title = result.get('title', 'N/A')
            content = result['content']
            url = result.get('url', '')
            
            context_part = f"[Source {i} - {source_type.upper()}]\n"
            if title and title != 'N/A':
                context_part += f"Title: {title}\n"
            if url:
                context_part += f"URL: {url}\n"
            
            # Add contacts and links for web sources
            if source_type == 'web':
                contacts = result.get('contacts')
                links = result.get('links')
                if contacts:
                    context_part += f"Contacts: {json.dumps(contacts)}\n"
                if links:
                    context_part += f"Related Links: {json.dumps(links)}\n"
            
            context_part += f"Content: {content}\n\n"
            context_parts.append(context_part)
        
        return "".join(context_parts)
    
    def _build_system_prompt(self) -> str:
        """Build system prompt for the Ollama model"""
        return """You are "HANS", an AI assistant for the Student Services and degree programmes at HTW Berlin.

Your job is to answer questions about:
- application deadlines
- admission and language requirements
- fees and funding
- study structure and organisation
- other official information for applicants and students

Follow these rules STRICTLY:

1. Language and style
   - ALWAYS answer in ENGLISH, even if the question is in German or mixed.
   - Be concise and clear: at most 2 short paragraphs and one short bullet list.
   - Use simple language that is easy for international students to understand.

2. STRICT grounding — use ONLY the provided context
   - You will receive a set of "sources" (snippets and URLs) from HTW Berlin websites and internal documents.
   - Base your answer ONLY on information that is EXPLICITLY STATED in these sources.
   - If the user asks about a specific programme and that programme is NOT mentioned by name in any source, you MUST say: "I do not have specific information about [programme name] in the sources available to me."
   - Do NOT apply rules, exemptions, or requirements from one programme to another programme.
   - Do NOT generalise from one source to cover a different situation unless the source explicitly says it applies generally.

3. No hallucinations or invented details
   - Do NOT invent deadlines, fees, ECTS values, language test scores, exemptions, or programme names.
   - Do NOT state exemptions or special rules (e.g. "proof is not required if…") unless the source EXPLICITLY contains that exact rule.
   - If information is not in the provided sources, say "This is not stated in the available sources" rather than inferring or guessing.
   - Never fabricate URLs. Only use URLs that appear in the provided sources.

4. How to process the sources
   - Before writing your answer, carefully read EACH source and identify specific facts relevant to the question (e.g. exact test scores, deadlines, programme names, requirements).
   - If a source mentions the specific programme the user asked about, prioritise that source's details.
   - Include specific numbers, dates, and test scores from the sources when they are relevant — do not summarise them away.

5. Structure of your answer
   - Start with a 1–3 sentence direct answer to the question.
   - If helpful, add a short bullet list with key points (e.g. main requirements, important dates, or steps).
   - If important information is missing from the context, clearly state what is missing and recommend where the student can look next (e.g. application portal, programme page, or Student Services contact).
   - When you cannot answer fully, be specific about WHAT information is missing rather than giving vague advice.

6. Referencing sources
   - When relevant, mention the type of source in natural language, for example:
     "According to the HTW Berlin application portal…" or
     "On the official page for Master's applications…"
   - You do NOT need to list all URLs in the answer, but you should not contradict the provided documents.

If you truly cannot answer the question from the context, say so honestly. Be specific: state what the sources DO cover and what they do NOT cover. Then suggest that the student check the official HTW Berlin website or contact Student Services.

Make sure your final answer is focused, helpful, and not longer than approximately 150–200 words.

Context will be provided for each query. Base your responses solely on this context."""

    async def _decompose_query(self, query: str) -> Optional[List[str]]:
        """
        Use the LLM to split a multi-part question into self-contained sub-queries.
        Returns None on failure (caller should fall back to single-query retrieval).
        """
        if not self.decomposition_config.get('enabled', False):
            return None

        decompose_model = self.decomposition_config.get(
            'model', self.runtime_config['ollama_model']
        )

        prompt = self.DECOMPOSE_PROMPT + query + "\n/no_think"

        try:
            async with OllamaClient(
                self.runtime_config['ollama_base_url'],
                self.decomposition_config.get('timeout', 60),
                self.runtime_config.get('verify_ssl', True)
            ) as ollama:
                raw = await ollama.chat(prompt, decompose_model)

            if not raw:
                logger.warning("Decomposition returned empty response")
                return None

            # Clean up the raw response before JSON parsing
            raw = raw.strip()

            # Strip <think>...</think> block if present (qwen3 chain-of-thought)
            think_match = re.search(r'<think>.*?</think>', raw, re.DOTALL)
            if think_match:
                raw = raw[think_match.end():].strip()

            # Strip markdown fences if present
            if raw.startswith("```"):
                raw = raw.split("\n", 1)[-1]  # drop first line
                raw = raw.rsplit("```", 1)[0]  # drop last fence
                raw = raw.strip()

            logger.info(f"Decomposition raw output: {raw[:300]}")
            sub_queries = json.loads(raw)

            if not isinstance(sub_queries, list) or len(sub_queries) == 0:
                logger.warning(f"Decomposition returned invalid format: {raw[:200]}")
                return None

            # Sanity: cap at 4 sub-queries, each must be a non-empty string
            sub_queries = [str(sq).strip() for sq in sub_queries[:4] if str(sq).strip()]

            if len(sub_queries) <= 1:
                # Single topic — no benefit from multi-query
                logger.info("Decomposition: single-topic query, skipping multi-query")
                return None

            logger.info(f"Decomposed into {len(sub_queries)} sub-queries:")
            for i, sq in enumerate(sub_queries):
                logger.info(f"  [{i+1}] {sq}")

            return sub_queries

        except json.JSONDecodeError as e:
            logger.warning(f"Decomposition JSON parse failed: {e}")
            return None
        except Exception as e:
            logger.warning(f"Decomposition failed: {e}. Falling back to single query.")
            return None

    async def process_query(self, query: str) -> Dict[str, Any]:
        """Process a user query and return response with metadata"""
        try:
            # Retrieve relevant content from database
            top_k = self.retrieval_config['top_k']
            top_k_db = self.retrieval_config.get('top_k_db', top_k)
            min_score = self.retrieval_config.get('min_score', 0.0)
            reranker_config = self.retrieval_config.get('reranker', None)
            model_name = self.config['model']['embedding_model']

            # --- Query decomposition: split multi-part questions ---
            sub_queries = await self._decompose_query(query)

            if sub_queries:
                # Multi-query retrieval path
                logger.info(f"Using multi-query retrieval with {len(sub_queries)} sub-queries")
                results = retrieve_multi_query(
                    self.db_conn,
                    sub_queries,
                    top_k=top_k,
                    model_name=model_name,
                    min_score=min_score,
                    reranker_config=reranker_config,
                    top_k_db=top_k_db
                )
            else:
                # Single-query retrieval path (fallback or simple query)
                logger.info(f"Retrieving top {top_k_db} candidates (final: {top_k}) for query: {query[:50]}...")
                results = retrieve_top_k(
                    self.db_conn,
                    query,
                    top_k=top_k,
                    model_name=model_name,
                    min_score=min_score,
                    reranker_config=reranker_config,
                    top_k_db=top_k_db
                )
            
            if not results:
                logger.warning("No relevant results found")
                return {
                    'final_response': "I don't have any relevant information to answer your question. Please check the HTW Berlin website or contact student services directly.",
                    'metadata': {
                        'query': query,
                        'results_found': 0,
                        'confidence_score': 0.0,
                        'confidence_level': 'none',
                        'confidence_factors': {'no_results': True},
                        'sources': []
                    }
                }
            
            # Build context from results
            context = self._build_context_from_results(results)
            
            # Build prompt
            system_prompt = self._build_system_prompt()
            
            full_prompt = f"""{system_prompt}

CONTEXT:
{context}

QUERY: {query}

ANSWER:"""
            
            # Generate response using Ollama
            async with OllamaClient(
                self.runtime_config['ollama_base_url'],
                self.runtime_config['ollama_timeout'],
                self.runtime_config.get('verify_ssl', True)
            ) as ollama:
                
                response = await ollama.chat(
                    full_prompt,
                    self.runtime_config['ollama_model']
                )
                
                # Post-process response to replace numbered source references with actual URLs
                response = self._post_process_sources(response, results)

            # Extract and strip <think> block from models that use chain-of-thought
            # (e.g. qwen3). Save reasoning for analysis, show only the answer.
            import re
            think_match = re.search(r'<think>(.*?)</think>', response, re.DOTALL)
            think_reasoning = think_match.group(1).strip() if think_match else None
            if think_match:
                response = response[:think_match.start()] + response[think_match.end():]
                response = response.strip()

            if not response:
                return {
                    'final_response': "I'm sorry, I encountered an error generating a response. Please try again.",
                    'metadata': {
                        'query': query,
                        'results_found': len(results),
                        'confidence_score': 0.0,
                        'confidence_level': 'unknown',
                        'error': 'ollama_generation_failed'
                    }
                }
            
            # Calculate confidence and extract sources
            confidence_data = self._calculate_confidence(results, response)
            
            # Check if confidence is too low for reliable response
            if confidence_data['score'] < 0.3:
                logger.warning(f"Low confidence response ({confidence_data['score']:.3f}) - adding disclaimer")
                response = self._add_low_confidence_disclaimer(response, confidence_data)
            
            sources = []
            for result in results:
                source_info = {
                    'type': result['source_type'],
                    'title': result.get('title'),
                    'url': result.get('url'),
                    'score': result['score']
                }
                sources.append(source_info)
            
            return {
                'final_response': response,
                'metadata': {
                    'query': query,
                    'results_found': len(results),
                    'confidence_score': confidence_data['score'],
                    'confidence_level': confidence_data['level'],
                    'confidence_factors': confidence_data['factors'],
                    'sources': sources,
                    'model_used': self.runtime_config['ollama_model'],
                    'embedding_model': model_name,
                    'top_k': top_k,
                    'think_reasoning': think_reasoning,
                    'sub_queries': sub_queries
                }
            }
        
        except Exception as e:
            logger.error(f"Query processing failed: {e}")
            return {
                'final_response': "I'm sorry, I encountered an error processing your query. Please try again later.",
                'metadata': {
                    'query': query,
                    'error': str(e)
                }
            }
    
    def _post_process_sources(self, response: str, results: List[Dict]) -> str:
        """Replace numbered source references with actual URLs"""
        # Build mapping of source numbers to URLs
        source_url_map = {}
        for i, result in enumerate(results, 1):
            url = result.get('url', '')
            source_type = result['source_type']
            if url:
                source_url_map[i] = {
                    'url': url,
                    'type': source_type,
                    'title': result.get('title', 'N/A')
                }
        
        # Replace patterns like "(source web - 1)", "(source web-1)", "source web 1", etc.
        def replace_source_ref(match):
            source_num = int(match.group(1))
            if source_num in source_url_map:
                source_info = source_url_map[source_num]
                return f"({source_info['url']})"
            return match.group(0)  # Return original if no URL found
        
        # Pattern to match various formats of numbered source references
        pattern = r'\(source\s+web\s*-?\s*(\d+)\)'
        response = re.sub(pattern, replace_source_ref, response, flags=re.IGNORECASE)
        
        # Also handle format without parentheses
        pattern2 = r'source\s+web\s*-?\s*(\d+)'
        response = re.sub(pattern2, lambda m: source_url_map.get(int(m.group(1)), {}).get('url', m.group(0)) if int(m.group(1)) in source_url_map else m.group(0), response, flags=re.IGNORECASE)
        
        return response
    
    def _calculate_confidence(self, results: List[Dict], response: str) -> Dict[str, Any]:
        """Calculate confidence score based on retrieval quality and response characteristics"""
        if not results:
            return {
                'score': 0.0,
                'level': 'none',
                'factors': {'no_results': True}
            }
        
        # Factor 1: Average similarity score (0.0 to 1.0)
        # Note: result['score'] is cosine DISTANCE (lower = better)
        # Convert to similarity: 1 - distance
        similarity_scores = [1.0 - result['score'] for result in results]
        avg_similarity = sum(similarity_scores) / len(similarity_scores)

        # Factor 2: Top result quality (highest similarity score)
        top_score = max(similarity_scores)

        # Factor 3: Score consistency (how similar are the top results)
        score_consistency = 1.0 - (max(similarity_scores) - min(similarity_scores)) if len(similarity_scores) > 1 else 1.0

        # Factor 4: Number of sources with good similarity (score > 0.6)
        # Threshold calibrated for BGE-base-en-v1.5 where good matches score 0.60-0.75
        high_quality_sources = sum(1 for score in similarity_scores if score > 0.6)
        source_quality_ratio = high_quality_sources / len(similarity_scores)
        
        # Factor 5: Response length as indicator of substantive answer
        response_length_factor = min(len(response.strip()) / 100, 1.0)  # Cap at 1.0 for responses > 100 chars
        
        # Factor 6: Presence of specific information (URLs, dates, numbers)
        specificity_indicators = [
            'http' in response.lower(),
            any(char.isdigit() for char in response),
            '@' in response,  # email addresses
            len([word for word in response.split() if word.endswith('.de')]) > 0  # German domains
        ]
        specificity_factor = sum(specificity_indicators) / len(specificity_indicators)
        
        # Weighted confidence calculation
        weights = {
            'avg_similarity': 0.35,
            'top_score': 0.25,
            'consistency': 0.15,
            'source_quality': 0.15,
            'response_length': 0.05,
            'specificity': 0.05
        }
        
        confidence_score = (
            avg_similarity * weights['avg_similarity'] +
            top_score * weights['top_score'] +
            score_consistency * weights['consistency'] +
            source_quality_ratio * weights['source_quality'] +
            response_length_factor * weights['response_length'] +
            specificity_factor * weights['specificity']
        )
        
        # Determine confidence level
        if confidence_score >= 0.8:
            confidence_level = 'very_high'
        elif confidence_score >= 0.65:
            confidence_level = 'high'
        elif confidence_score >= 0.5:
            confidence_level = 'medium'
        elif confidence_score >= 0.3:
            confidence_level = 'low'
        else:
            confidence_level = 'very_low'
        
        # Compile factors for transparency
        factors = {
            'avg_similarity_score': round(avg_similarity, 3),
            'top_similarity_score': round(top_score, 3),
            'score_consistency': round(score_consistency, 3),
            'high_quality_sources': high_quality_sources,
            'total_sources': len(results),
            'response_length': len(response.strip()),
            'has_urls': 'http' in response.lower(),
            'has_numbers': any(char.isdigit() for char in response),
            'has_contacts': '@' in response
        }
        
        return {
            'score': round(confidence_score, 3),
            'level': confidence_level,
            'factors': factors
        }
    
    def _add_low_confidence_disclaimer(self, response: str, confidence_data: Dict) -> str:
        """Add disclaimer for low confidence responses"""
        confidence_level = confidence_data['level']
        
        if confidence_level == 'very_low':
            disclaimer = "\n\n⚠️ **Low Confidence Response**: I found limited relevant information for your question. Please verify this information independently or contact HTW Berlin directly for accurate details."
        elif confidence_level == 'low':
            disclaimer = "\n\n⚠️ **Medium Confidence**: The information above may not be complete. For the most accurate details, please check the official HTW Berlin website."
        else:
            return response  # No disclaimer needed for medium+ confidence
        
        return response + disclaimer
    
    def close(self):
        """Close database connection"""
        if self.db_conn:
            self.db_conn.close()
            self.db_conn = None

class MainDatabaseAgent:
    """Main agent using database-backed RAG system"""
    
    def __init__(self):
        self.config = load_config()
        self.rag_agent = DatabaseRAGAgent(self.config)
    
    async def process_query(self, query: str) -> Dict[str, Any]:
        """Process query using database RAG"""
        return await self.rag_agent.process_query(query)
    
    def close(self):
        """Clean up resources"""
        self.rag_agent.close()

# Compatibility functions for existing code
def get_database_agent():
    """Get a database-backed agent instance"""
    return MainDatabaseAgent()

async def process_query_with_database(query: str) -> Dict[str, Any]:
    """Process a query using the database-backed system"""
    agent = get_database_agent()
    try:
        return await agent.process_query(query)
    finally:
        agent.close()

# Migration helpers
def check_database_ready() -> Tuple[bool, str]:
    """Check if database is ready for use"""
    try:
        config = load_config()
        conn = get_db_connection(config)
        ensure_schema(conn, config['schema_version'])
        
        stats = get_retrieval_stats(conn)
        conn.close()
        
        if stats['web_chunks'] == 0 and stats['qa_pairs'] == 0:
            return False, "Database is empty. Run scripts/build_content_db.py to populate."
        
        return True, f"Database ready: {stats['documents']} docs, {stats['web_chunks']} chunks, {stats['qa_pairs']} Q&A pairs"
    
    except Exception as e:
        return False, str(e)

# Test function
async def test_database_agent():
    """Test the database agent functionality"""
    logger.info("Testing database agent...")
    
    # Check database status
    is_ready, message = check_database_ready()
    if not is_ready:
        logger.error(f"Database not ready: {message}")
        return
    
    logger.info(f"Database status: {message}")
    
    # Test queries
    test_queries = [
        "How do I apply to HTW Berlin?",
        "What are the language requirements?",
        "When are the application deadlines?"
    ]
    
    agent = get_database_agent()
    
    try:
        for query in test_queries:
            logger.info(f"Testing query: {query}")
            result = await agent.process_query(query)
            
            logger.info(f"Results found: {result['metadata'].get('results_found', 0)}")
            logger.info(f"Response length: {len(result['final_response'])} chars")
            print(f"\nQuery: {query}")
            print(f"Response: {result['final_response'][:200]}...")
            print("-" * 50)
    
    finally:
        agent.close()

if __name__ == "__main__":
    asyncio.run(test_database_agent())