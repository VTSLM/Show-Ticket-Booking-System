# Sequence Diagram: Seat-Lock Concurrency and Conflict Resolution

## 1. Description and Purpose
This diagram illustrates the race condition scenario where two users (User A and User B) attempt to lock the exact same seat simultaneously. It details how the atomic database query, rollbacks, HTTP 409 status handling, WebSocket broadcasting, and PostgreSQL `pg_notify` cooperate to guarantee consistency across multi-instance backend deployments.

## 2. Sequence Diagram
```mermaid
sequenceDiagram
    autonumber
    actor UserA as User A (Browser)
    actor UserB as User B (Browser)
    participant ClientA as Next.js (Client A)
    participant ClientB as Next.js (Client B)
    participant Server1 as FastAPI Instance 1
    participant Server2 as FastAPI Instance 2
    participant WSHub as WebSocket Manager
    participant DB as PostgreSQL 16 (Engine)

    Note over UserA, UserB: Both User A and User B view the same show seat map concurrently

    %% Simultaneous Click
    UserA ->> ClientA: Clicks Seat S1
    UserB ->> ClientB: Clicks Seat S1 (within milliseconds)
    
    ClientA -->> UserA: S1 marked Pending (Amber)
    ClientB -->> UserB: S1 marked Pending (Amber)

    par User A Request via Server 1
        ClientA ->> Server1: POST /api/seats/{showId}/lock {seat_ids: ["S1"]}
    and User B Request via Server 2
        ClientB ->> Server2: POST /api/seats/{showId}/lock {seat_ids: ["S1"]}
    end

    %% Database Concurrency Arbitration
    critical Database Row Lock Acquisition
        Server1 ->> DB: UPDATE show_seats SET status='locked', locked_by=$UserA, locked_until=NOW()+10m<br/>WHERE id='S1' AND show_id=$showId<br/>AND (status='available' OR (status='locked' AND locked_until < NOW()) OR (status='locked' AND locked_by=$UserA))
        DB -->> Server1: UPDATE 1 (User A acquires the lock)
        Server2 ->> DB: UPDATE show_seats SET status='locked', locked_by=$UserB, locked_until=NOW()+10m<br/>WHERE id='S1' AND show_id=$showId<br/>AND (status='available' OR (status='locked' AND locked_until < NOW()) OR (status='locked' AND locked_by=$UserB))
        DB -->> Server2: UPDATE 0 (Predicate evaluated to false: seat is already locked by User A)
    end

    %% User A Success Flow
    Server1 ->> DB: SELECT pg_notify('seat_events', '{"show_id": "...", "instance_id": "inst-1", "message": {"type": "lock", "seat_ids": ["S1"]}}')
    Server1 ->> WSHub: Local broadcast {"type": "lock", "seat_ids": ["S1"]}
    Server1 -->> ClientA: 200 OK {"locked": ["S1"], "locked_until": "..."}
    ClientA -->> UserA: S1 marked 'mine' (Blue), added to selected list

    %% User B Conflict & Rollback Flow
    Note over Server2: S1 not in acquired list -> failed = ["S1"]
    opt Rollback any partially acquired seats
        Server2 ->> DB: UPDATE show_seats SET status='available' WHERE id=ANY(locked) AND locked_by=$UserB
    end
    Server2 -->> ClientB: 409 Conflict {"detail": "Seats unavailable: ['S1']"}
    ClientB -->> UserB: Clean pending state, restore S1 to 'locked', show toast: "Seats unavailable"

    %% Real-Time Cross-Instance Sync
    DB -->> Server2: pg_notify payload received on 'seat_events' channel
    Server2 ->> WSHub: Relay remote broadcast to local WebSockets (instance_id != current)
    WSHub -->> ClientB: WebSocket Message {"type": "lock", "seat_ids": ["S1"]}
    ClientB -->> UserB: S1 rendered as Locked (Grey/Red, disabled)
```

## 3. Concurrency Protection Mechanisms
- **Single Atomic UPDATE:** TicketFlow uses a single atomic `UPDATE` with a composite `WHERE` clause rather than separate `SELECT FOR UPDATE` followed by `UPDATE`. If the row is already locked by another user, the statement matches zero rows (`UPDATE 0`).
- **Partial Lock Rollback:** If a user requests multiple seats `["S1", "S2"]` and only one succeeds, the failed array triggers an immediate rollback releasing the successfully acquired subset to prevent orphan locks.
- **Cross-Instance Notification (`pg_notify`):** When Instance 1 handles User A's lock, Instance 2 receives the notification via PostgreSQL LISTEN and pushes the update to User B's open WebSocket connection without polling.
