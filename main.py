"""
Claude Code Python SDK Proxy Service
A FastAPI-based service that provides REST API access to Claude Code CLI
Uses Claude OAuth authentication instead of API keys
"""

import os
import logging
import asyncio
import subprocess
import json
from typing import Optional, List, Dict, Any
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, status, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from dotenv import load_dotenv

from auth_helper import ClaudeAuthHelper

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
    prompt: str = Field(..., description="The prompt/question to send to Claude")
    context: Optional[str] = Field(
        default=None,
        description="Optional context or system message"
    )
    model: Optional[str] = Field(
        default=None,
        description="Claude model to use (optional)"
    )


class ExecuteCommandRequest(BaseModel):
    command: str = Field(..., description="Claude Code command to execute")
    args: Optional[List[str]] = Field(
        default=None,
        description="Additional arguments for the command"
    )
    timeout: Optional[int] = Field(
        default=300,
        description="Command timeout in seconds"
    )


class ChatResponse(BaseModel):
    response: str
    status: str
    metadata: Optional[Dict[str, Any]] = None


class HealthResponse(BaseModel):
    status: str
    service: str
    version: str
    authenticated: bool


class LoginResponse(BaseModel):
    status: str
    message: str
    instructions: Optional[List[str]] = None


# Global auth helper
auth_helper: Optional[ClaudeAuthHelper] = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan handler"""
    global auth_helper

    # Startup
    logger.info("Initializing Claude Code SDK service...")
    auth_helper = ClaudeAuthHelper()

    # Check authentication status
    if auth_helper.is_authenticated():
        logger.info("✓ Authenticated with Claude Code")
    else:
        logger.warning("⚠ Not authenticated with Claude Code. Please login.")
        logger.warning("Run: docker exec -it claude-sdk-agent claude login")

    yield

    # Shutdown
    logger.info("Shutting down Claude Code SDK service")


# Initialize FastAPI app
app = FastAPI(
    title="Claude Code Python SDK Proxy",
    description="REST API wrapper for Claude Code CLI with OAuth authentication",
    version="2.0.0",
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


async def execute_claude_command(
    command: List[str],
    timeout: int = 300,
    input_text: Optional[str] = None
) -> Dict[str, Any]:
    """
    Execute a Claude Code command and return the result

    Args:
        command: Command and arguments as list
        timeout: Timeout in seconds
        input_text: Optional input to send to the command

    Returns:
        Dict with command output and status
    """
    try:
        process = await asyncio.create_subprocess_exec(
            *command,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            stdin=asyncio.subprocess.PIPE if input_text else None
        )

        try:
            stdout, stderr = await asyncio.wait_for(
                process.communicate(input=input_text.encode() if input_text else None),
                timeout=timeout
            )

            return {
                "status": "success" if process.returncode == 0 else "error",
                "returncode": process.returncode,
                "stdout": stdout.decode('utf-8', errors='replace'),
                "stderr": stderr.decode('utf-8', errors='replace')
            }

        except asyncio.TimeoutError:
            process.kill()
            await process.wait()
            return {
                "status": "timeout",
                "returncode": -1,
                "stdout": "",
                "stderr": f"Command timed out after {timeout} seconds"
            }

    except Exception as e:
        logger.error(f"Error executing command: {e}")
        return {
            "status": "error",
            "returncode": -1,
            "stdout": "",
            "stderr": str(e)
        }


@app.get("/", response_model=HealthResponse)
async def root():
    """Root endpoint - health check with auth status"""
    is_auth = auth_helper.is_authenticated() if auth_helper else False

    return {
        "status": "healthy",
        "service": os.getenv("SERVICE_NAME", "claude-code-sdk"),
        "version": "2.0.0",
        "authenticated": is_auth
    }


@app.get("/health", response_model=HealthResponse)
async def health_check():
    """Health check endpoint"""
    if auth_helper is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Auth helper not initialized"
        )

    is_auth = auth_helper.is_authenticated()

    return {
        "status": "healthy",
        "service": os.getenv("SERVICE_NAME", "claude-code-sdk"),
        "version": "2.0.0",
        "authenticated": is_auth
    }


@app.get("/auth/status")
async def auth_status():
    """Get authentication status"""
    if auth_helper is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Auth helper not initialized"
        )

    return auth_helper.get_auth_info()


@app.get("/auth/login-instructions")
async def get_login_instructions():
    """Get instructions for logging in"""
    if auth_helper is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Auth helper not initialized"
        )

    return await auth_helper.get_login_instructions()


@app.post("/auth/login")
async def login():
    """
    Initiate Claude Code login process

    Note: This is an interactive process. For full functionality,
    you need to exec into the container and run 'claude login' manually.
    """
    if auth_helper is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Auth helper not initialized"
        )

    result = await auth_helper.initiate_login()
    return result


@app.post("/auth/logout")
async def logout():
    """Logout from Claude Code"""
    if auth_helper is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Auth helper not initialized"
        )

    result = await auth_helper.logout()
    return result


@app.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    """
    Send a prompt to Claude Code and get a response

    This uses the Claude Code CLI to interact with Claude via OAuth
    """
    if auth_helper is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Auth helper not initialized"
        )

    if not auth_helper.is_authenticated():
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated with Claude Code. Please login first using /auth/login-instructions"
        )

    try:
        # Build the Claude Code command
        command = ['claude', 'chat']

        if request.model:
            command.extend(['--model', request.model])

        # Execute the command with the prompt as input
        result = await execute_claude_command(
            command=command,
            timeout=int(os.getenv("COMMAND_TIMEOUT", "300")),
            input_text=request.prompt
        )

        if result['status'] == 'success':
            return {
                "response": result['stdout'],
                "status": "success",
                "metadata": {
                    "model": request.model or "default",
                    "returncode": result['returncode']
                }
            }
        else:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Claude Code error: {result['stderr']}"
            )

    except Exception as e:
        logger.error(f"Error calling Claude Code: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error communicating with Claude Code: {str(e)}"
        )


@app.post("/execute")
async def execute_command(request: ExecuteCommandRequest):
    """
    Execute a custom Claude Code command

    This allows you to run any Claude Code CLI command
    """
    if auth_helper is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Auth helper not initialized"
        )

    if not auth_helper.is_authenticated():
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated with Claude Code. Please login first."
        )

    try:
        # Build command
        command = ['claude', request.command]
        if request.args:
            command.extend(request.args)

        # Execute
        result = await execute_claude_command(
            command=command,
            timeout=request.timeout or 300
        )

        return {
            "command": ' '.join(command),
            "status": result['status'],
            "returncode": result['returncode'],
            "output": result['stdout'],
            "error": result['stderr']
        }

    except Exception as e:
        logger.error(f"Error executing command: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error executing command: {str(e)}"
        )


@app.get("/version")
async def get_claude_version():
    """Get Claude Code version"""
    result = await execute_claude_command(['claude', '--version'], timeout=10)

    if result['status'] == 'success':
        return {
            "version": result['stdout'].strip(),
            "status": "success"
        }
    else:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get Claude Code version"
        )


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
