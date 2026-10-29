from fastapi import APIRouter, HTTPException
from sqlalchemy import text

from app.api.deps import SessionDep

router = APIRouter(tags=["Health"])


@router.get("/health", summary="Liveness probe")
async def liveness():
    return {"status": "ok"}


@router.get("/health/ready", summary="Readiness probe (checks DB)")
async def readiness(session: SessionDep):
    try:
        await session.execute(text("SELECT 1"))
    except Exception as exc:
        raise HTTPException(status_code=503, detail="database unavailable") from exc
    return {"status": "ready"}
