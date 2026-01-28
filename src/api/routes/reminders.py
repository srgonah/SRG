"""
Reminder management endpoints.
"""

from datetime import date

from fastapi import APIRouter, Depends, HTTPException, status

from src.api.dependencies import get_rem_store
from src.application.dto.requests import CreateReminderRequest, UpdateReminderRequest
from src.application.dto.responses import (
    ErrorResponse,
    ReminderListResponse,
    ReminderResponse,
)
from src.core.entities.reminder import Reminder
from src.infrastructure.storage.sqlite import SQLiteReminderStore

router = APIRouter(prefix="/api/reminders", tags=["reminders"])


def _entity_to_response(reminder: Reminder) -> ReminderResponse:
    """Convert entity to response DTO."""
    return ReminderResponse(
        id=reminder.id or 0,
        title=reminder.title,
        message=reminder.message,
        due_date=reminder.due_date,
        is_done=reminder.is_done,
        is_overdue=reminder.is_overdue,
        linked_entity_type=reminder.linked_entity_type,
        linked_entity_id=reminder.linked_entity_id,
        created_at=reminder.created_at,
        updated_at=reminder.updated_at,
    )


@router.post(
    "",
    response_model=ReminderResponse,
    status_code=status.HTTP_201_CREATED,
    responses={422: {"model": ErrorResponse}},
)
async def create_reminder(
    request: CreateReminderRequest,
    store: SQLiteReminderStore = Depends(get_rem_store),
) -> ReminderResponse:
    """Create a new reminder."""
    try:
        due_date = date.fromisoformat(request.due_date)
    except ValueError:
        raise HTTPException(
            status_code=422,
            detail=f"Invalid due_date format: {request.due_date}",
        )

    reminder = Reminder(
        title=request.title,
        message=request.message,
        due_date=due_date,
        linked_entity_type=request.linked_entity_type,
        linked_entity_id=request.linked_entity_id,
    )

    created = await store.create(reminder)
    return _entity_to_response(created)


@router.get(
    "",
    response_model=ReminderListResponse,
)
async def list_reminders(
    include_done: bool = False,
    limit: int = 100,
    offset: int = 0,
    store: SQLiteReminderStore = Depends(get_rem_store),
) -> ReminderListResponse:
    """List reminders with optional done filter."""
    reminders = await store.list_reminders(
        include_done=include_done, limit=limit, offset=offset
    )
    return ReminderListResponse(
        reminders=[_entity_to_response(r) for r in reminders],
        total=len(reminders),
    )


@router.get(
    "/upcoming",
    response_model=ReminderListResponse,
)
async def list_upcoming_reminders(
    within_days: int = 7,
    limit: int = 100,
    store: SQLiteReminderStore = Depends(get_rem_store),
) -> ReminderListResponse:
    """List upcoming reminders within the given number of days."""
    reminders = await store.list_upcoming(within_days=within_days, limit=limit)
    return ReminderListResponse(
        reminders=[_entity_to_response(r) for r in reminders],
        total=len(reminders),
    )


@router.get(
    "/{reminder_id}",
    response_model=ReminderResponse,
    responses={404: {"model": ErrorResponse}},
)
async def get_reminder(
    reminder_id: int,
    store: SQLiteReminderStore = Depends(get_rem_store),
) -> ReminderResponse:
    """Get a reminder by ID."""
    reminder = await store.get(reminder_id)
    if reminder is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Reminder not found: {reminder_id}",
        )
    return _entity_to_response(reminder)


@router.put(
    "/{reminder_id}",
    response_model=ReminderResponse,
    responses={404: {"model": ErrorResponse}},
)
async def update_reminder(
    reminder_id: int,
    request: UpdateReminderRequest,
    store: SQLiteReminderStore = Depends(get_rem_store),
) -> ReminderResponse:
    """Update a reminder (edit fields or mark done)."""
    existing = await store.get(reminder_id)
    if existing is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Reminder not found: {reminder_id}",
        )

    if request.title is not None:
        existing.title = request.title
    if request.message is not None:
        existing.message = request.message
    if request.due_date is not None:
        try:
            existing.due_date = date.fromisoformat(request.due_date)
        except ValueError:
            raise HTTPException(
                status_code=422,
                detail=f"Invalid due_date: {request.due_date}",
            )
    if request.is_done is not None:
        existing.is_done = request.is_done
    if request.linked_entity_type is not None:
        existing.linked_entity_type = request.linked_entity_type
    if request.linked_entity_id is not None:
        existing.linked_entity_id = request.linked_entity_id

    updated = await store.update(existing)
    return _entity_to_response(updated)


@router.delete(
    "/{reminder_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_reminder(
    reminder_id: int,
    store: SQLiteReminderStore = Depends(get_rem_store),
) -> None:
    """Delete a reminder."""
    result = await store.delete(reminder_id)
    if not result:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Reminder not found: {reminder_id}",
        )
