"""Split and transfer tickets. Rules live in services/ticket_transfer.py.

GET  /api/transfers/booking/{booking_id}  seats of my booking + transfers I made from it
POST /api/transfers                       send seats to a user by email or phone
GET  /api/transfers/received              transfers sent to me (QR when accepted)
POST /api/transfers/{id}/accept|decline   recipient answers
POST /api/transfers/{id}/cancel           sender takes back a pending transfer
GET  /api/transfers/{id}/pdf              recipient's PDF ticket with their own QR
"""
import io
from typing import List

import asyncpg
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from database import get_conn
from dependencies import get_current_user, security
from firebase_admin_setup import verify_firebase_token
from fastapi.security import HTTPAuthorizationCredentials
from services import ticket_transfer as svc
from services.qr_service import generate_qr_bytes
from services.transfer_email_service import (
    send_ticket_ready_email,
    send_transfer_received_email,
    send_transfer_response_email,
    ticket_pdf,
)

router = APIRouter(prefix="/api/transfers", tags=["ticket transfers"])


class ZoneQuantity(BaseModel):
    booking_zone_id: str
    quantity: int = Field(..., strict=True, gt=0, le=2_147_483_647)


class TransferCreate(BaseModel):
    booking_id: str
    seat_ids: List[str] = Field(default_factory=list, max_length=50)
    zones: List[ZoneQuantity] = Field(default_factory=list, max_length=50)
    recipient: str = Field(..., min_length=1, max_length=255)


def _http(err: svc.TransferError) -> HTTPException:
    return HTTPException(status_code=err.status_code, detail=err.detail)


@router.get("/booking/{booking_id}")
async def booking_transfers(
    booking_id: str,
    user: dict = Depends(get_current_user),
    conn: asyncpg.Connection = Depends(get_conn),
):
    try:
        return await svc.booking_transfer_view(conn, str(user["id"]), booking_id)
    except svc.TransferError as e:
        raise _http(e)


@router.post("", status_code=201)
async def create_transfer(
    body: TransferCreate,
    background_tasks: BackgroundTasks,
    user: dict = Depends(get_current_user),
    conn: asyncpg.Connection = Depends(get_conn),
):
    try:
        transfer = await svc.create_transfer(
            conn, user, body.booking_id, body.seat_ids, body.recipient, [zone.model_dump() for zone in body.zones],
        )
    except svc.TransferError as e:
        raise _http(e)
    background_tasks.add_task(send_transfer_received_email, transfer)
    return {
        "id": transfer["id"],
        "status": transfer["status"],
        "recipient_name": transfer["recipient_name"],
        "seats": transfer["seats"],
        "message": ("Transfer created. They must sign up and verify their email to receive the tickets."
                    if transfer.get("invited") else
                    f"Transfer created for {transfer['recipient_name']}. "
                    "They need to accept before the seats move."),
    }


@router.get("/received")
async def received_transfers(
    user: dict = Depends(get_current_user),
    conn: asyncpg.Connection = Depends(get_conn),
    credentials: HTTPAuthorizationCredentials = Depends(security),
):
    claims = verify_firebase_token(credentials.credentials)
    if (claims.get("email_verified") is True and claims.get("email")
            and user.get("email", "").lower() == claims["email"].lower()):
        await svc.claim_verified_invitations(conn, str(user["id"]), claims["email"])
    items = await svc.list_received(conn, str(user["id"]))
    for item in items:
        item["qr_image"] = generate_qr_bytes(item["qr_data"]) if item["qr_data"] else None
    return items


async def _respond(transfer_id: str, accept: bool, user: dict, conn, background_tasks: BackgroundTasks):
    try:
        transfer = await svc.respond_to_transfer(conn, str(user["id"]), transfer_id, accept)
    except svc.TransferError as e:
        raise _http(e)
    background_tasks.add_task(send_transfer_response_email, transfer)
    if accept:
        # email the recipient their PDF ticket; never fail the accept because of it
        try:
            ticket = await svc.received_ticket_data(conn, str(user["id"]), transfer_id)
            background_tasks.add_task(send_ticket_ready_email, ticket)
        except svc.TransferError:
            pass
    return {"id": transfer_id, "status": transfer["status"]}


@router.post("/{transfer_id}/accept")
async def accept_transfer(
    transfer_id: str,
    background_tasks: BackgroundTasks,
    user: dict = Depends(get_current_user),
    conn: asyncpg.Connection = Depends(get_conn),
):
    return await _respond(transfer_id, True, user, conn, background_tasks)


@router.post("/{transfer_id}/decline")
async def decline_transfer(
    transfer_id: str,
    background_tasks: BackgroundTasks,
    user: dict = Depends(get_current_user),
    conn: asyncpg.Connection = Depends(get_conn),
):
    return await _respond(transfer_id, False, user, conn, background_tasks)


@router.post("/{transfer_id}/cancel")
async def cancel_transfer(
    transfer_id: str,
    user: dict = Depends(get_current_user),
    conn: asyncpg.Connection = Depends(get_conn),
):
    try:
        transfer = await svc.cancel_transfer(conn, str(user["id"]), transfer_id)
    except svc.TransferError as e:
        raise _http(e)
    return {"id": transfer_id, "status": transfer["status"]}


@router.get("/{transfer_id}/pdf")
async def received_ticket_pdf(
    transfer_id: str,
    user: dict = Depends(get_current_user),
    conn: asyncpg.Connection = Depends(get_conn),
):
    try:
        ticket = await svc.received_ticket_data(conn, str(user["id"]), transfer_id)
    except svc.TransferError as e:
        raise _http(e)
    return StreamingResponse(
        io.BytesIO(ticket_pdf(ticket)),
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="ticket_{transfer_id[:8]}.pdf"'},
    )
