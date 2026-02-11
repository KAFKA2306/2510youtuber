"""Commands endpoint exposing configured workflow runners."""
from __future__ import annotations
from fastapi import APIRouter, Depends
from app.gui.api import schemas
from app.gui.api.deps import get_command_registry
from app.gui.jobs.registry import CommandRegistry
router = APIRouter()
@router.get("/", response_model=list[schemas.CommandSchema])
async def list_commands(registry: CommandRegistry = Depends(get_command_registry)) -> list[schemas.CommandSchema]:
    commands = []
    for command in registry.list():
        commands.append(
            schemas.CommandSchema(
                id=command.id,
                name=command.name,
                description=command.description,
                runner=command.runner,
                args=command.args,
                module=command.module,
                command=command.command,
                parameters=[
                    schemas.CommandParameterSchema(
                        name=param.name,
                        label=param.label,
                        required=param.required,
                        default=param.default,
                    )
                    for param in command.parameters
                ],
            )
        )
    return commands
