from fastapi import APIRouter
from app.manager_layout_schemas import LayoutCreate, LayoutUpdate, BulkUpdate
from app.manager_layout_service import (
    list_screens, list_layouts, create_layout, get_layout,
    update_layout, bulk_update, fixture,
)

router = APIRouter(tags=["Manager Seat Layout"])

@router.get("/api/screens")
def screens():
    return list_screens()

@router.get("/api/layouts")
def layouts():
    return list_layouts()

@router.post("/api/layouts")
def create(payload: LayoutCreate):
    return create_layout(payload)

@router.get("/api/layouts/{layout_id}")
def read(layout_id: str):
    return get_layout(layout_id)

@router.put("/api/layouts/{layout_id}")
def update(layout_id: str, payload: LayoutUpdate):
    return update_layout(layout_id, payload)

@router.post("/api/layouts/{layout_id}/bulk-update")
def bulk(layout_id: str, payload: BulkUpdate):
    return bulk_update(layout_id, payload)

@router.get("/api/layouts/{layout_id}/fixture")
def get_fixture(layout_id: str):
    return fixture(layout_id)
