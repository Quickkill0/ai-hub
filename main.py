"""
Claude Python SDK Proxy Service
A FastAPI-based service that provides REST API access to Claude AI
"""

import os
import logging
from typing import Optional, List, Dict, Any
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from anthropic import Anthropic
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO").upper(),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


# Pydantic models for request/response
class Message(BaseModel):
    role: str = Field(..., description="Role of the message sender (user or assistant)")
    content: str = Field(..., description="Content of the message")


class ChatRequest(BaseModel):
    messages: List[Message] = Field(..., description="List of messages in the conversation")
    model: Optional[str] = Field(
        default=None,
        description="Claude model to use (defaults to env DEFAULT_MODEL)"
    )
    max_tokens: Optional[int] = Field(
        default=None,
        description="Maximum tokens in response (defaults to env MAX_TOKENS)"
    )
    temperature: Optional[float] = Field(
        default=None,
        description="Temperature for response generation (defaults to env TEMPERATURE)"
    )
    system: Optional[str] = Field(
        default=None,
        description="System prompt to guide Claude's behavior"
    )


class ChatResponse(BaseModel):
    id: str
    role: str
    content: str
    model: str
    stop_reason: Optional[str]
    usage: Dict[str, int]


class HealthResponse(BaseModel):
    status: str
    service: str
    version: str


# Global client instance
claude_client: Optional[Anthropic] = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan handler"""
    global claude_client

    # Startup
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        logger.error("ANTHROPIC_API_KEY not set in environment variables")
        raise RuntimeError("ANTHROPIC_API_KEY is required")

    claude_client = Anthropic(api_key=api_key)
    logger.info("Claude SDK initialized successfully")

    yield

    # Shutdown
    logger.info("Shutting down Claude SDK service")


# Initialize FastAPI app
app = FastAPI(
    title="Claude Python SDK Proxy",
    description="REST API wrapper for Anthropic's Claude AI",
    version="1.0.0",
    lifespan=lifespan
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure based on your security needs
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/", response_model=HealthResponse)
async def root():
    """Root endpoint - health check"""
    return {
        "status": "healthy",
        "service": os.getenv("SERVICE_NAME", "claude-proxy-sdk"),
        "version": "1.0.0"
    }


@app.get("/health", response_model=HealthResponse)
async def health_check():
    """Health check endpoint"""
    if claude_client is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Claude client not initialized"
        )

    return {
        "status": "healthy",
        "service": os.getenv("SERVICE_NAME", "claude-proxy-sdk"),
        "version": "1.0.0"
    }


@app.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    """
    Send a message to Claude and get a response

    This endpoint accepts a conversation history and returns Claude's response.
    """
    if claude_client is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Claude client not initialized"
        )

    try:
        # Get configuration from request or environment
        model = request.model or os.getenv("DEFAULT_MODEL", "claude-sonnet-4-5-20250929")
        max_tokens = request.max_tokens or int(os.getenv("MAX_TOKENS", "4096"))
        temperature = request.temperature or float(os.getenv("TEMPERATURE", "1.0"))

        # Convert messages to Claude format
        messages = [{"role": msg.role, "content": msg.content} for msg in request.messages]

        # Prepare API call parameters
        api_params = {
            "model": model,
            "max_tokens": max_tokens,
            "temperature": temperature,
            "messages": messages
        }

        # Add system prompt if provided
        if request.system:
            api_params["system"] = request.system

        # Call Claude API
        logger.info(f"Sending request to Claude with model: {model}")
        response = claude_client.messages.create(**api_params)

        # Extract text content from response
        content_text = ""
        for block in response.content:
            if hasattr(block, 'text'):
                content_text += block.text

        # Format response
        return {
            "id": response.id,
            "role": response.role,
            "content": content_text,
            "model": response.model,
            "stop_reason": response.stop_reason,
            "usage": {
                "input_tokens": response.usage.input_tokens,
                "output_tokens": response.usage.output_tokens
            }
        }

    except Exception as e:
        logger.error(f"Error calling Claude API: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error communicating with Claude: {str(e)}"
        )


@app.get("/models")
async def list_models():
    """List available Claude models"""
    return {
        "models": [
            {
                "id": "claude-sonnet-4-5-20250929",
                "name": "Claude Sonnet 4.5",
                "description": "Most advanced Claude model"
            },
            {
                "id": "claude-3-7-sonnet-20250219",
                "name": "Claude 3.7 Sonnet",
                "description": "Powerful and balanced model"
            },
            {
                "id": "claude-3-5-haiku-20241022",
                "name": "Claude 3.5 Haiku",
                "description": "Fast and efficient model"
            },
            {
                "id": "claude-3-opus-20240229",
                "name": "Claude 3 Opus",
                "description": "Previous generation top-tier model"
            }
        ]
    }


if __name__ == "__main__":
    import uvicorn

    host = os.getenv("HOST", "0.0.0.0")
    port = int(os.getenv("PORT", "8000"))

    uvicorn.run(
        "main:app",
        host=host,
        port=port,
        reload=False,
        log_level=os.getenv("LOG_LEVEL", "info").lower()
    )
