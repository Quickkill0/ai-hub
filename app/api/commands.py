"""
REST API for slash commands.

Provides endpoints for:
- Listing available commands (for autocomplete)
- Getting command details
- Executing non-interactive custom commands
"""

import logging
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from app.db import database
from app.core.config import settings
from app.core.slash_commands import (
    discover_commands, get_command_by_name, get_all_commands,
    is_interactive_command, parse_command_input, SlashCommand
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/commands", tags=["Commands"])


class CommandInfo(BaseModel):
    """Command information for API responses"""
    name: str
    display: str
    description: str
    argument_hint: Optional[str] = None
    type: str  # "custom" or "interactive"
    source: Optional[str] = None  # "project" or "user" for custom commands
    namespace: Optional[str] = None


class CommandListResponse(BaseModel):
    """Response for command list endpoint"""
    commands: List[CommandInfo]
    count: int


class CommandDetailResponse(BaseModel):
    """Detailed command information"""
    name: str
    display: str
    description: str
    content: Optional[str] = None  # Prompt content (only for custom commands)
    argument_hint: Optional[str] = None
    type: str
    source: Optional[str] = None
    namespace: Optional[str] = None
    allowed_tools: List[str] = []
    model: Optional[str] = None
    is_interactive: bool = False


class ExecuteCommandRequest(BaseModel):
    """Request to execute a custom command"""
    command: str  # Command with arguments, e.g., "/fix-issue 123 high"
    session_id: str


class ExecuteCommandResponse(BaseModel):
    """Response from command execution"""
    success: bool
    message: str
    expanded_prompt: Optional[str] = None
    is_interactive: bool = False


def get_working_dir_for_project(project_id: Optional[str]) -> str:
    """Get the working directory for a project"""
    if project_id:
        project = database.get_project(project_id)
        if project:
            return str(settings.workspace_dir / project["path"])
    return str(settings.workspace_dir)


@router.get("/", response_model=CommandListResponse)
async def list_commands(
    project_id: Optional[str] = Query(None, description="Project ID to get commands for")
):
    """
    List all available slash commands.

    Returns both custom commands from the project's .claude/commands/
    directory and built-in interactive commands like /rewind.
    """
    working_dir = get_working_dir_for_project(project_id)
    commands = get_all_commands(working_dir)

    return CommandListResponse(
        commands=[CommandInfo(**cmd) for cmd in commands],
        count=len(commands)
    )


@router.get("/{command_name}", response_model=CommandDetailResponse)
async def get_command(
    command_name: str,
    project_id: Optional[str] = Query(None, description="Project ID")
):
    """
    Get detailed information about a specific command.

    The command_name should not include the leading slash.
    """
    # Check if it's an interactive command
    if is_interactive_command(command_name):
        from app.core.slash_commands import INTERACTIVE_COMMANDS
        info = INTERACTIVE_COMMANDS.get(command_name)
        if info:
            return CommandDetailResponse(
                name=command_name,
                display=f"/{command_name}",
                description=info["description"],
                type="interactive",
                is_interactive=True
            )

    # Look for custom command
    working_dir = get_working_dir_for_project(project_id)
    cmd = get_command_by_name(working_dir, command_name)

    if not cmd:
        raise HTTPException(status_code=404, detail=f"Command not found: {command_name}")

    return CommandDetailResponse(
        name=cmd.name,
        display=cmd.get_display_name(),
        description=cmd.description,
        content=cmd.content,
        argument_hint=cmd.argument_hint,
        type="custom",
        source=cmd.source,
        namespace=cmd.namespace,
        allowed_tools=cmd.allowed_tools,
        model=cmd.model,
        is_interactive=False
    )


@router.post("/execute", response_model=ExecuteCommandResponse)
async def execute_command(request: ExecuteCommandRequest):
    """
    Execute a custom slash command.

    For custom commands, this expands the prompt with arguments
    and returns the expanded prompt for the client to send as a query.

    For interactive commands (like /rewind), this returns is_interactive=True
    and the client should use the CLI WebSocket endpoint instead.
    """
    # Parse command input
    command_name, arguments = parse_command_input(request.command)

    if not command_name:
        raise HTTPException(status_code=400, detail="Invalid command format")

    # Check if it's an interactive command
    if is_interactive_command(command_name):
        return ExecuteCommandResponse(
            success=True,
            message=f"Command /{command_name} requires interactive terminal",
            is_interactive=True
        )

    # Get session to find project
    session = database.get_session(request.session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    project_id = session.get("project_id")
    working_dir = get_working_dir_for_project(project_id)

    # Get command
    cmd = get_command_by_name(working_dir, command_name)
    if not cmd:
        raise HTTPException(status_code=404, detail=f"Command not found: {command_name}")

    # Check if arguments are required but not provided
    if cmd.argument_hint and not arguments:
        return ExecuteCommandResponse(
            success=False,
            message=f"Command requires arguments: {cmd.argument_hint}",
            expanded_prompt=None
        )

    # Expand the prompt
    expanded_prompt = cmd.expand_prompt(arguments)

    return ExecuteCommandResponse(
        success=True,
        message="Command expanded successfully",
        expanded_prompt=expanded_prompt,
        is_interactive=False
    )


@router.post("/sync-after-rewind")
async def sync_after_rewind(
    session_id: str = Query(..., description="Session ID"),
    checkpoint_message: str = Query(..., description="The user message text at the checkpoint"),
    restore_option: int = Query(..., description="Restore option (1-4)")
):
    """
    Sync our chat database after a rewind operation completes.

    This is called by the frontend after the user completes a /rewind
    in the CLI terminal. It deletes messages after the selected checkpoint
    to keep our chat in sync with Claude's context.

    Options:
    1 = Restore code and conversation - delete messages after checkpoint
    2 = Restore conversation - delete messages after checkpoint
    3 = Restore code - don't delete messages (code-only revert)
    4 = Never mind - don't delete anything
    """
    if restore_option not in [1, 2, 3, 4]:
        raise HTTPException(status_code=400, detail="Invalid restore option")

    # Option 3 and 4 don't require chat sync
    if restore_option in [3, 4]:
        return {
            "success": True,
            "message": "No chat sync needed for this option",
            "deleted_count": 0
        }

    # Get session
    session = database.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    # Get all messages for this session
    messages = database.get_session_messages(session_id)

    # Find the checkpoint message (user message matching the checkpoint text)
    checkpoint_index = -1
    for i, msg in enumerate(messages):
        if msg["role"] == "user" and checkpoint_message in msg["content"]:
            checkpoint_index = i
            break

    if checkpoint_index == -1:
        # Try partial match
        for i, msg in enumerate(messages):
            if msg["role"] == "user" and (
                msg["content"].startswith(checkpoint_message[:50]) or
                checkpoint_message.startswith(msg["content"][:50])
            ):
                checkpoint_index = i
                break

    if checkpoint_index == -1:
        logger.warning(f"Could not find checkpoint message: {checkpoint_message[:50]}...")
        return {
            "success": False,
            "message": "Could not find checkpoint message in chat history",
            "deleted_count": 0
        }

    # Delete all messages after the checkpoint
    messages_to_delete = messages[checkpoint_index + 1:]
    deleted_count = 0

    for msg in messages_to_delete:
        try:
            database.delete_session_message(session_id, msg["id"])
            deleted_count += 1
        except Exception as e:
            logger.error(f"Failed to delete message {msg['id']}: {e}")

    logger.info(f"Synced chat after rewind: deleted {deleted_count} messages after checkpoint")

    return {
        "success": True,
        "message": f"Deleted {deleted_count} messages after checkpoint",
        "deleted_count": deleted_count,
        "checkpoint_index": checkpoint_index
    }
