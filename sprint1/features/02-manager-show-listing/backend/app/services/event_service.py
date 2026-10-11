from typing import List, Optional
from fastapi import HTTPException, status
from app.database import fetch_all, fetch_one
from app.models import EventCreateRequest

async def list_events() -> List[dict]:
    query = """
        SELECT id::text, title, description, event_type::text, duration_minutes,
               language, genre, poster_url, status::text, created_at, updated_at
        FROM events
        ORDER BY created_at DESC;
    """
    return await fetch_all(query)

async def get_event_by_id(event_id: str) -> Optional[dict]:
    query = """
        SELECT id::text, title, description, event_type::text, duration_minutes,
               language, genre, poster_url, status::text, created_at, updated_at
        FROM events
        WHERE id = $1::uuid;
    """
    return await fetch_one(query, event_id)

async def create_event(data: EventCreateRequest) -> dict:
    query = """
        INSERT INTO events (
            title, description, event_type, duration_minutes, language, genre, poster_url, status
        )
        VALUES (
            $1, $2, $3::event_type, $4, $5, $6, $7, $8::event_status
        )
        RETURNING id::text, title, description, event_type::text, duration_minutes,
                  language, genre, poster_url, status::text, created_at, updated_at;
    """
    try:
        record = await fetch_one(
            query,
            data.title,
            data.description,
            data.event_type.value,
            data.duration_minutes,
            data.language,
            data.genre,
            data.poster_url,
            data.status.value,
        )
        if not record:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Database failed to return created event."
            )
        return record
    except Exception as e:
        err_msg = str(e)
        if "invalid input value for enum" in err_msg:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Invalid event enum value: {err_msg}"
            )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Error inserting event into database: {err_msg}"
        )
