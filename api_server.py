#!/usr/bin/env python3
"""
FastAPI Server for HANS (HTW Berlin Student Services Assistant)

Provides headless HTTP service for staff access to the database-backed RAG system.
Implements JSON API and simple HTML interface as specified for Apptainer deployment.
"""

import os
import logging
import asyncio
from typing import Dict, Any, Optional, List
from datetime import datetime

from fastapi import FastAPI, Request, HTTPException, Form
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import uvicorn

# Import Hans database agent
from hans_db_agents import get_database_agent, check_database_ready

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Pydantic models for API
class QueryRequest(BaseModel):
    q: str
    max_sources: Optional[int] = 10

class SourceInfo(BaseModel):
    title: Optional[str]
    url: Optional[str]
    type: str

class QueryResponse(BaseModel):
    answer: str
    sources: List[SourceInfo]
    confidence_pct: int
    metadata: Optional[Dict[str, Any]] = None

# FastAPI app
app = FastAPI(
    title="HANS API",
    description="HTW Berlin Student Services Assistant API",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

# Add CORS middleware for browser access
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global agent instance
hans_agent = None
agent_init_error = None

@app.on_event("startup")
async def startup_event():
    """Initialize HANS agent on startup"""
    global hans_agent, agent_init_error
    
    logger.info("Starting HANS API server...")
    
    try:
        # Check database status
        is_ready, message = check_database_ready()
        if not is_ready:
            agent_init_error = f"Database not ready: {message}"
            logger.error(agent_init_error)
            return
        
        # Initialize agent
        hans_agent = get_database_agent()
        logger.info("HANS agent initialized successfully")
        
    except Exception as e:
        agent_init_error = f"Failed to initialize HANS agent: {str(e)}"
        logger.error(agent_init_error)

@app.on_event("shutdown")
async def shutdown_event():
    """Clean up on shutdown"""
    global hans_agent
    
    if hans_agent:
        hans_agent.close()
        logger.info("HANS agent closed")

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    if agent_init_error:
        return JSONResponse(
            status_code=503,
            content={"status": "error", "message": agent_init_error}
        )
    
    if hans_agent is None:
        return JSONResponse(
            status_code=503,
            content={"status": "error", "message": "Agent not initialized"}
        )
    
    return {"status": "ok", "timestamp": datetime.now().isoformat()}

@app.post("/ask", response_model=QueryResponse)
async def ask_question(request: QueryRequest):
    """
    Process a question and return answer with sources
    
    Returns JSON with:
    - answer: Generated response text
    - sources: List of source information (title, url, type)
    - confidence_pct: Confidence percentage (0-100)
    - metadata: Additional processing information (optional)
    """
    if agent_init_error:
        raise HTTPException(status_code=503, detail=agent_init_error)
    
    if hans_agent is None:
        raise HTTPException(status_code=503, detail="Agent not initialized")
    
    if not request.q or not request.q.strip():
        raise HTTPException(status_code=400, detail="Query parameter 'q' is required and cannot be empty")
    
    try:
        # Process query
        logger.info(f"Processing query: {request.q[:50]}...")
        result = await hans_agent.process_query(request.q.strip())
        
        # Extract sources (only web sources with URLs per UI policy)
        sources = []
        metadata = result.get('metadata', {})
        source_data = metadata.get('sources', [])
        
        for source in source_data:
            # UI policy: show only real web links, no Excel items
            if source.get('type') == 'web' and source.get('url'):
                sources.append(SourceInfo(
                    title=source.get('title'),
                    url=source.get('url'),
                    type=source.get('type', 'web')
                ))
        
        # Convert confidence score to percentage
        confidence_score = metadata.get('confidence_score', 0.0)
        confidence_pct = min(100, max(0, int(confidence_score * 100)))
        
        logger.info(f"Query processed successfully. Confidence: {confidence_pct}%, Sources: {len(sources)}")
        
        return QueryResponse(
            answer=result['final_response'],
            sources=sources,
            confidence_pct=confidence_pct,
            metadata=metadata if request.max_sources is None else None  # Include metadata only if requested
        )
    
    except Exception as e:
        logger.error(f"Query processing failed: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error processing query")

@app.get("/", response_class=HTMLResponse)
async def root():
    """Serve simple HTML form for manual testing"""
    html_content = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>HANS - HTW Berlin Student Services Assistant</title>
    <style>
        body {
            font-family: Arial, sans-serif;
            max-width: 1000px;
            margin: 0 auto;
            padding: 20px;
            background-color: #f5f5f5;
        }
        .container {
            background-color: white;
            padding: 30px;
            border-radius: 10px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
        }
        .header {
            text-align: center;
            margin-bottom: 30px;
            padding-bottom: 20px;
            border-bottom: 2px solid #e0e0e0;
        }
        .header h1 {
            color: #333;
            margin: 0 0 10px 0;
        }
        .header p {
            color: #666;
            font-size: 16px;
        }
        .form-group {
            margin-bottom: 20px;
        }
        label {
            display: block;
            margin-bottom: 8px;
            font-weight: bold;
            color: #333;
        }
        textarea {
            width: 100%;
            padding: 12px;
            border: 2px solid #ddd;
            border-radius: 5px;
            font-size: 16px;
            font-family: Arial, sans-serif;
            resize: vertical;
            min-height: 100px;
        }
        textarea:focus {
            outline: none;
            border-color: #007bff;
        }
        button {
            background-color: #007bff;
            color: white;
            padding: 12px 24px;
            border: none;
            border-radius: 5px;
            font-size: 16px;
            cursor: pointer;
            transition: background-color 0.3s;
        }
        button:hover {
            background-color: #0056b3;
        }
        button:disabled {
            background-color: #ccc;
            cursor: not-allowed;
        }
        .loading {
            display: none;
            text-align: center;
            color: #666;
            font-style: italic;
            margin: 20px 0;
        }
        .response {
            margin-top: 30px;
            padding: 20px;
            background-color: #f8f9fa;
            border-radius: 5px;
            display: none;
        }
        .response h3 {
            color: #333;
            margin-top: 0;
        }
        .answer {
            background-color: white;
            padding: 15px;
            border-radius: 5px;
            margin: 15px 0;
            line-height: 1.6;
        }
        .sources {
            margin-top: 20px;
        }
        .source-item {
            background-color: white;
            padding: 10px;
            margin: 5px 0;
            border-radius: 5px;
            border-left: 4px solid #007bff;
        }
        .confidence {
            display: inline-block;
            padding: 5px 10px;
            border-radius: 15px;
            color: white;
            font-weight: bold;
            margin-left: 10px;
        }
        .confidence.high { background-color: #28a745; }
        .confidence.medium { background-color: #ffc107; color: #333; }
        .confidence.low { background-color: #dc3545; }
        .error {
            background-color: #f8d7da;
            color: #721c24;
            padding: 15px;
            border-radius: 5px;
            margin-top: 20px;
            display: none;
        }
        .api-info {
            margin-top: 40px;
            padding: 20px;
            background-color: #e9ecef;
            border-radius: 5px;
            font-size: 14px;
        }
        .api-info h4 {
            margin-top: 0;
            color: #495057;
        }
        .api-info code {
            background-color: #f8f9fa;
            padding: 2px 6px;
            border-radius: 3px;
            color: #e83e8c;
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>HANS</h1>
            <p>HTW Berlin Student Services Assistant</p>
        </div>
        
        <form id="questionForm">
            <div class="form-group">
                <label for="question">Your Question:</label>
                <textarea id="question" name="question" placeholder="Ask me about HTW Berlin student services, applications, deadlines, programs, campus facilities, or any other student-related topics..." required></textarea>
            </div>
            <button type="submit" id="submitBtn">Ask HANS</button>
        </form>
        
        <div class="loading" id="loading">
            🤔 HANS is thinking about your question...
        </div>
        
        <div class="response" id="response">
            <h3>Answer: <span class="confidence" id="confidence"></span></h3>
            <div class="answer" id="answer"></div>
            <div class="sources" id="sources"></div>
        </div>
        
        <div class="error" id="error"></div>
        
        <div class="api-info">
            <h4>API Information</h4>
            <p><strong>JSON API Endpoint:</strong> <code>POST /ask</code></p>
            <p><strong>Request:</strong> <code>{"q": "your question here"}</code></p>
            <p><strong>Health Check:</strong> <code>GET /health</code></p>
            <p><strong>Documentation:</strong> <a href="/docs" target="_blank">OpenAPI Docs</a></p>
        </div>
    </div>

    <script>
        const form = document.getElementById('questionForm');
        const loading = document.getElementById('loading');
        const response = document.getElementById('response');
        const error = document.getElementById('error');
        const submitBtn = document.getElementById('submitBtn');

        form.addEventListener('submit', async (e) => {
            e.preventDefault();
            
            const question = document.getElementById('question').value.trim();
            if (!question) return;

            // Show loading state
            loading.style.display = 'block';
            response.style.display = 'none';
            error.style.display = 'none';
            submitBtn.disabled = true;
            submitBtn.textContent = 'Processing...';

            try {
                const apiResponse = await fetch('/ask', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                    },
                    body: JSON.stringify({ q: question })
                });

                if (!apiResponse.ok) {
                    throw new Error(`API Error: ${apiResponse.status} ${apiResponse.statusText}`);
                }

                const data = await apiResponse.json();
                
                // Display answer
                document.getElementById('answer').textContent = data.answer;
                
                // Display confidence
                const confidenceEl = document.getElementById('confidence');
                confidenceEl.textContent = `${data.confidence_pct}%`;
                confidenceEl.className = 'confidence ' + getConfidenceLevel(data.confidence_pct);
                
                // Display sources
                const sourcesEl = document.getElementById('sources');
                if (data.sources && data.sources.length > 0) {
                    sourcesEl.innerHTML = '<h4>Sources:</h4>' + 
                        data.sources.map(source => 
                            `<div class="source-item">
                                <strong>${source.title || 'HTW Berlin'}</strong><br>
                                <a href="${source.url}" target="_blank">${source.url}</a>
                            </div>`
                        ).join('');
                } else {
                    sourcesEl.innerHTML = '<h4>Sources:</h4><p>No web sources available for this response.</p>';
                }
                
                response.style.display = 'block';

            } catch (err) {
                error.textContent = 'Error: ' + err.message;
                error.style.display = 'block';
            } finally {
                loading.style.display = 'none';
                submitBtn.disabled = false;
                submitBtn.textContent = 'Ask HANS';
            }
        });

        function getConfidenceLevel(pct) {
            if (pct >= 70) return 'high';
            if (pct >= 40) return 'medium';
            return 'low';
        }
    </script>
</body>
</html>
    """
    return html_content

@app.post("/ask-form", response_class=HTMLResponse)
async def ask_form(question: str = Form(...)):
    """Handle form submissions and redirect back to main page with results"""
    try:
        # Process the query using the API endpoint logic
        request = QueryRequest(q=question)
        result = await ask_question(request)
        
        # Return a simple results page (could redirect to main page with query params instead)
        return f"""
<!DOCTYPE html>
<html>
<head>
    <title>HANS - Answer</title>
    <style>
        body {{ font-family: Arial, sans-serif; max-width: 800px; margin: 0 auto; padding: 20px; }}
        .answer {{ background: #f0f0f0; padding: 15px; border-radius: 5px; margin: 15px 0; }}
        .sources {{ margin-top: 20px; }}
        .source {{ background: #f8f8f8; padding: 10px; margin: 5px 0; border-left: 3px solid #007bff; }}
        .confidence {{ font-weight: bold; color: {"green" if result.confidence_pct >= 70 else "orange" if result.confidence_pct >= 40 else "red"}; }}
    </style>
</head>
<body>
    <h1>HANS Answer</h1>
    <p><strong>Your Question:</strong> {question}</p>
    <p><strong>Confidence:</strong> <span class="confidence">{result.confidence_pct}%</span></p>
    
    <div class="answer">
        {result.answer}
    </div>
    
    <div class="sources">
        <h3>Sources:</h3>
        {"".join(f'<div class="source"><strong>{source.title or "HTW Berlin"}</strong><br><a href="{source.url}" target="_blank">{source.url}</a></div>' for source in result.sources)}
    </div>
    
    <p><a href="/">← Ask Another Question</a></p>
</body>
</html>
        """
    except Exception as e:
        return f"""
<!DOCTYPE html>
<html>
<head><title>HANS - Error</title></head>
<body>
    <h1>Error</h1>
    <p>Sorry, there was an error processing your question: {str(e)}</p>
    <p><a href="/">← Try Again</a></p>
</body>
</html>
        """

def main():
    """Main function to run the server"""
    # Get configuration from environment
    bind_host = os.getenv("HANS_BIND", "127.0.0.1")
    bind_port = int(os.getenv("HANS_PORT", "8080"))
    
    logger.info(f"Starting HANS API server on {bind_host}:{bind_port}")
    
    # Run with uvicorn
    uvicorn.run(
        "api_server:app",
        host=bind_host,
        port=bind_port,
        log_level="info",
        access_log=True
    )

if __name__ == "__main__":
    main()