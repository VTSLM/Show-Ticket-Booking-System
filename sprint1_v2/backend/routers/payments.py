import hmac
import hashlib
import uuid
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import Optional
import asyncpg
import razorpay
from database import get_conn
from dependencies import get_current_user
from config import RAZORPAY_KEY_ID, RAZORPAY_KEY_SECRET

router = APIRouter(prefix="/api/payments", tags=["payments"])

def get_razorpay():
    return razorpay.Client(auth=(RAZORPAY_KEY_ID, RAZORPAY_KEY_SECRET))


class CreateOrderRequest(BaseModel):
    booking_id: str


@router.get("/booking/{booking_id}")
async def get_payment_for_booking(
    booking_id: str,
    current_user: dict = Depends(get_current_user),
    conn: asyncpg.Connection = Depends(get_conn)
):
    row = await conn.fetchrow(
        """SELECT p.*, b.total_amount, b.status as booking_status
           FROM payments p
           JOIN bookings b ON b.id = p.booking_id
           WHERE p.booking_id = $1 AND b.user_id = $2""",
        booking_id, str(current_user["id"])
    )
    if not row:
        raise HTTPException(status_code=404, detail="No payment found for this booking")
    return dict(row)


@router.post("/orders")
async def create_order(
    req: CreateOrderRequest,
    current_user: dict = Depends(get_current_user),
    conn: asyncpg.Connection = Depends(get_conn)
):
    booking = await conn.fetchrow(
        "SELECT * FROM bookings WHERE id=$1 AND user_id=$2",
        req.booking_id, str(current_user["id"])
    )
    if not booking:
        raise HTTPException(status_code=404, detail="Booking not found")
    if booking["status"] not in ("pending",):
        raise HTTPException(status_code=400, detail=f"Booking is {booking['status']}, cannot pay")

    amount_paise = round(float(booking["total_amount"]) * 100)
    client = get_razorpay()
    rz_order = client.order.create({
        "amount": amount_paise,
        "currency": "INR",
        "receipt": f"tf_{req.booking_id[:8]}",
        "notes": {"booking_id": req.booking_id}
    })

    # Upsert payment_orders
    await conn.execute(
        """INSERT INTO payment_orders
             (booking_id, razorpay_order_id, amount, currency, status, created_by)
           VALUES ($1,$2,$3,'INR','created',$4)
           ON CONFLICT (razorpay_order_id) DO UPDATE
             SET razorpay_order_id=$2, amount=$3, status='created', updated_at=now()""",
        req.booking_id, rz_order["id"], booking["total_amount"], str(current_user["id"])
    )

    return {
        "razorpay_order_id": rz_order["id"],
        "amount": amount_paise,
        "currency": "INR",
        "key_id": RAZORPAY_KEY_ID,
        "booking_id": req.booking_id
    }


class VerifyRequest(BaseModel):
    razorpay_order_id: str
    razorpay_payment_id: str
    razorpay_signature: str


@router.post("/orders/{booking_id}/verify")
async def verify_payment(
    booking_id: str,
    req: VerifyRequest,
    current_user: dict = Depends(get_current_user),
    conn: asyncpg.Connection = Depends(get_conn)
):
    # Verify signature
    expected = hmac.new(
        RAZORPAY_KEY_SECRET.encode(),
        f"{req.razorpay_order_id}|{req.razorpay_payment_id}".encode(),
        hashlib.sha256
    ).hexdigest()
    if not hmac.compare_digest(expected, req.razorpay_signature):
        raise HTTPException(status_code=400, detail="Invalid payment signature")

    # Validate booking ownership and pending state
    booking = await conn.fetchrow(
        "SELECT id, user_id, status FROM bookings WHERE id=$1",
        booking_id
    )
    if not booking:
        raise HTTPException(status_code=404, detail="Booking not found")
    if str(booking["user_id"]) != str(current_user["id"]):
        raise HTTPException(status_code=403, detail="Not your booking")
    if booking["status"] != "pending":
        raise HTTPException(status_code=400, detail=f"Booking is already {booking['status']}")

    # Validate order-to-booking binding
    order_row = await conn.fetchrow(
        "SELECT booking_id FROM payment_orders WHERE razorpay_order_id=$1",
        req.razorpay_order_id
    )
    if not order_row or str(order_row["booking_id"]) != booking_id:
        raise HTTPException(status_code=400, detail="Order ID does not match this booking")

    async with conn.transaction():
        # Update payment_orders status
        await conn.execute(
            """UPDATE payment_orders SET status='successful', updated_at=now()
               WHERE razorpay_order_id=$1""",
            req.razorpay_order_id
        )

        # Confirm booking
        await conn.execute(
            "UPDATE bookings SET status='confirmed', updated_at=now() WHERE id=$1",
            booking_id
        )

        # Mark seats as booked (fixed column name: locked_by not locked_by_user_id)
        await conn.execute(
            """UPDATE show_seats SET status='booked', locked_by=NULL, locked_until=NULL
               WHERE id IN (
                 SELECT show_seat_id FROM booking_seats WHERE booking_id=$1
               )""",
            booking_id
        )

        # Insert payment record
        payment_id = await conn.fetchval(
            """INSERT INTO payments
                (booking_id, transaction_id,
                amount, currency, payment_method, status, paid_at)
            VALUES ($1, $2,
                    (SELECT total_amount FROM bookings WHERE id=$1),
                    'INR', 'razorpay', 'successful', now())
            RETURNING id""",
            booking_id, req.razorpay_payment_id
        )

        # Insert receipt with payment_id FK (no booking_id column in receipts)
        receipt_number = f"TF-{booking_id[:8].upper()}-{req.razorpay_payment_id[-6:]}"
        await conn.execute(
            """INSERT INTO receipts (receipt_number, payment_id, issued_at)
               VALUES ($1,$2,now())
               ON CONFLICT (receipt_number) DO NOTHING""",
            receipt_number, payment_id
        )

    return {"status": "success", "booking_id": booking_id, "receipt_number": receipt_number}


@router.get("/receipts/{receipt_number}")
async def get_receipt(
    receipt_number: str,
    current_user: dict = Depends(get_current_user),
    conn: asyncpg.Connection = Depends(get_conn)
):
    row = await conn.fetchrow(
        """SELECT r.id, r.receipt_number, r.issued_at,
                  p.amount as total_amount, p.transaction_id as razorpay_payment_id,
                  b.id as booking_id, b.user_id
           FROM receipts r
           JOIN payments p ON p.id = r.payment_id
           JOIN bookings b ON b.id = p.booking_id
           WHERE r.receipt_number=$1 AND b.user_id=$2""",
        receipt_number, str(current_user["id"])
    )
    if not row:
        raise HTTPException(status_code=404, detail="Receipt not found")
    return dict(row)
