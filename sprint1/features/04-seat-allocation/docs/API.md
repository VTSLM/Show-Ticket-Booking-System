# API Reference — Seat Allocation (Feature 04)

Base URL: `http://localhost:8001`  
Interactive docs: `http://localhost:8001/docs`

---

## REST Endpoints

### `GET /api/shows/{show_id}/seats`
Returns all seats for a show with current statuses.

**Response:**
```json
{
  "show_id": "show-demo-001",
  "max_seats_per_booking": 6,
  "seats": [
    {
      "id": "V1-S1",
      "row": "V1",
      "number": 1,
      "section": "VIP",
      "status": "available",
      "price": 1500,
      "locked_by": null,
      "expires_at": null
    }
  ]
}
```

---

### `POST /api/seats/lock`
Atomically locks all requested seats for the given user.  
**All-or-nothing**: returns 409 if ANY seat is unavailable.

**Request:**
```json
{
  "show_id": "show-demo-001",
  "seat_ids": ["V1-S1", "V1-S2"],
  "user_id": "user-demo-khushi"
}
```

**Success (200):**
```json
{
  "success": true,
  "locked_seat_ids": ["V1-S1", "V1-S2"],
  "expires_at": "2026-10-13T14:30:00+00:00",
  "lock_duration_minutes": 5
}
```

**Conflict (409):**
```json
{
  "detail": {
    "message": "Some seats are no longer available.",
    "failed_seat_ids": ["V1-S1"]
  }
}
```

---

### `POST /api/seats/release`
Manually releases locked seats (user cancels selection).

**Request:**
```json
{
  "show_id": "show-demo-001",
  "seat_ids": ["V1-S1", "V1-S2"],
  "user_id": "user-demo-khushi"
}
```

---

### `POST /api/seats/confirm`
Post-payment confirmation. Re-verifies lock validity, then transitions `locked → booked`.

**Request:** same shape as lock.

**Success (200):**
```json
{
  "success": true,
  "booking_id": "BKG-00001",
  "booking": {
    "booking_id": "BKG-00001",
    "user_id": "user-demo-khushi",
    "seat_ids": ["V1-S1", "V1-S2"],
    "total_price": 3000,
    "status": "confirmed",
    "created_at": "2026-10-13T14:25:00+00:00"
  }
}
```

**Lock expired (409):**
```json
{
  "detail": {
    "message": "Your seat hold has expired. Please go back and re-select.",
    "error_code": "LOCK_EXPIRED"
  }
}
```

---

### `POST /api/bookings/cancel`
Cancels a confirmed booking; releases seats back to `available`.

**Request:**
```json
{
  "booking_id": "BKG-00001",
  "user_id": "user-demo-khushi"
}
```

---

### `GET /api/bookings/{booking_id}?user_id=...`
Get a specific booking (ownership check enforced).

---

### `GET /api/users/{user_id}/bookings`
Get all bookings for a user.

---

## WebSocket

### `WS /ws/{show_id}`
Real-time seat status updates.

**Server → Client (on any seat status change):**
```json
{
  "type": "SEAT_UPDATE",
  "seat_id": "G1-S3",
  "status": "locked"
}
```

Possible statuses: `available`, `locked`, `booked`
