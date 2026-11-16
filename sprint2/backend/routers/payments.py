import hmac
import hashlib
import logging
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from starlette.concurrency import run_in_threadpool
from requests.exceptions import RequestException
import asyncpg
import razorpay
from database import get_conn
from dependencies import get_current_user
from config import RAZORPAY_KEY_ID, RAZORPAY_KEY_SECRET

from services.terms_service import resolve_show_terms, check_terms_acceptance

router = APIRouter(prefix="/api/payments", tags=["payments"])
logger = logging.getLogger(__name__)

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
    user_id = str(current_user["id"])
    async with conn.transaction():
        # Serialize checkout requests for the same booking, including retries.
        booking = await conn.fetchrow(
            "SELECT * FROM bookings WHERE id = $1 AND user_id = $2 FOR UPDATE",
            req.booking_id, user_id,
        )
        if not booking:
            raise HTTPException(status_code=404, detail="Booking not found")
        if booking["status"] != "pending":
            raise HTTPException(status_code=400, detail=f"Booking is {booking['status']}, cannot pay")

        amount_paise = round(booking["total_amount"] * 100)
        if amount_paise <= 0:
            raise HTTPException(status_code=400, detail="Online payment requires a booking total greater than ₹0.")

        show_meta = await conn.fetchrow(
            """SELECT sh.terms_and_conditions AS show_terms, e.terms_and_conditions AS event_terms
               FROM shows sh JOIN events e ON e.id = sh.event_id WHERE sh.id = $1::uuid""",
            booking["show_id"],
        )
        _, active_hash, _ = resolve_show_terms(
            show_meta.get("show_terms") if show_meta else None,
            show_meta.get("event_terms") if show_meta else None,
        )
        if not await check_terms_acceptance(conn, user_id, str(booking["show_id"]), active_hash, req.booking_id):
            raise HTTPException(
                status_code=403,
                detail="Show Terms and Conditions must be accepted before initiating payment.",
            )

        order_id = await conn.fetchval(
            """SELECT razorpay_order_id FROM payment_orders
               WHERE booking_id = $1 AND status = 'created' AND amount = $2
               ORDER BY created_at DESC LIMIT 1""",
            req.booking_id, booking["total_amount"],
        )
        if not order_id:
            try:
                order = await run_in_threadpool(
                    get_razorpay().order.create,
                    {
                        "amount": amount_paise,
                        "currency": "INR",
                        "receipt": f"tf_{req.booking_id[:8]}",
                        "notes": {"booking_id": req.booking_id},
                    },
                    timeout=10,
                )
            except razorpay.errors.BadRequestError as exc:
                logger.warning("Razorpay rejected order creation for booking %s", req.booking_id)
                raise HTTPException(
                    status_code=502, detail="Razorpay could not open checkout. Please try again or contact support."
                ) from exc
            except (razorpay.errors.ServerError, razorpay.errors.GatewayError, RequestException) as exc:
                logger.warning("Razorpay order creation unavailable for booking %s", req.booking_id)
                raise HTTPException(
                    status_code=503, detail="Razorpay is temporarily unavailable. Please try again shortly."
                ) from exc

            order_id = order["id"]
            await conn.execute(
                """INSERT INTO payment_orders
                   (booking_id, razorpay_order_id, amount, currency, status, created_by)
                   VALUES ($1, $2, $3, 'INR', 'created', $4)""",
                req.booking_id, order_id, booking["total_amount"], user_id,
            )

    return {
        "razorpay_order_id": order_id,
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
    # Recheck ownership, the order and the signature before confirming or replaying a payment.
    async with conn.transaction():
        booking = await conn.fetchrow(
            "SELECT user_id, status FROM bookings WHERE id = $1::uuid FOR UPDATE",
            booking_id,
        )
        if not booking:
            raise HTTPException(status_code=404, detail="Booking not found")
        if str(booking["user_id"]) != str(current_user["id"]):
            raise HTTPException(status_code=403, detail="Not your booking")
        if not await conn.fetchval(
            "SELECT id FROM payment_orders WHERE razorpay_order_id = $1 AND booking_id = $2::uuid",
            req.razorpay_order_id, booking_id,
        ):
            raise HTTPException(status_code=400, detail="Payment order does not match booking")

        expected = hmac.new(
            RAZORPAY_KEY_SECRET.encode(),
            f"{req.razorpay_order_id}|{req.razorpay_payment_id}".encode(),
            hashlib.sha256,
        ).hexdigest()
        if not hmac.compare_digest(expected, req.razorpay_signature):
            raise HTTPException(status_code=400, detail="Invalid payment signature")

        if booking["status"] == "confirmed":
            receipt_number = await conn.fetchval(
                """SELECT r.receipt_number FROM receipts r
                   JOIN payments p ON p.id = r.payment_id
                   WHERE p.booking_id = $1 AND p.transaction_id = $2 AND p.status = 'successful'""",
                booking_id, req.razorpay_payment_id,
            )
            if receipt_number:
                return {"status": "success", "booking_id": booking_id, "receipt_number": receipt_number}
        if booking["status"] != "pending":
            raise HTTPException(status_code=400, detail="Booking is not in pending state")

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
        """SELECT r.*, b.total_amount, b.user_id,
                  p.transaction_id as razorpay_payment_id
           FROM receipts r
           JOIN payments p ON p.id = r.payment_id
           JOIN bookings b ON b.id = p.booking_id
           WHERE r.receipt_number=$1 AND b.user_id=$2""",
        receipt_number, str(current_user["id"])
    )
    if not row:
        raise HTTPException(status_code=404, detail="Receipt not found")
    return dict(row)
