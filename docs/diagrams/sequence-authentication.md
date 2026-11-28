# Sequence Diagram: User Authentication, Session Validation, and Inactivity Tracking

## 1. Description and Purpose
This sequence diagram models user authentication, Firebase token exchange, role resolution, server-side inactivity session management, and automatic role-based session termination.

## 2. Sequence Diagram
```mermaid
sequenceDiagram
    autonumber
    actor User as User (Browser)
    participant NextJS as Next.js (AuthContext)
    participant FirebaseAuth as Firebase Auth SDK
    participant AuthCtrl as auth.py (API)
    participant Dep as dependencies.py (FastAPI)
    participant SessionSvc as session_service.py
    participant DB as PostgreSQL 16

    %% 1. Login & Token Acquisition
    User ->> NextJS: Enter email & password -> Click "Login"
    NextJS ->> FirebaseAuth: signInWithEmailAndPassword(email, password)
    FirebaseAuth -->> NextJS: UserCredential with Firebase ID Token (JWT)

    %% 2. Token Exchange & Session Creation
    NextJS ->> AuthCtrl: POST /api/auth/verify-token {id_token}
    AuthCtrl ->> FirebaseAuth: verify_id_token(id_token)
    FirebaseAuth -->> AuthCtrl: Decoded token {uid: "fb_123", email: "user@test.com"}
    
    AuthCtrl ->> DB: SELECT * FROM users WHERE firebase_uid = 'fb_123'
    DB -->> AuthCtrl: User record (id, name, status='active')
    AuthCtrl ->> DB: SELECT code FROM roles JOIN user_roles ON ... WHERE user_id = user.id
    DB -->> AuthCtrl: Roles ['customer']

    AuthCtrl ->> SessionSvc: create_session(user_id, role='customer', ip, user_agent)
    Note over SessionSvc: Inactivity limit: Customer 30m, Manager 20m, Admin 15m
    SessionSvc ->> DB: INSERT INTO user_sessions (user_id, session_token, expires_at=NOW()+30m, is_active=true)
    DB -->> SessionSvc: session_id
    AuthCtrl -->> NextJS: 200 OK {user, roles, session_id: "sess_abc"}
    NextJS ->> NextJS: Store session_id in sessionStorage, broadcast via BroadcastChannel

    %% 3. Subsequent Authenticated Request
    User ->> NextJS: Navigate to /bookings
    NextJS ->> Dep: GET /api/bookings (Headers: Authorization: Bearer <JWT>, X-Session-ID: sess_abc)
    Dep ->> FirebaseAuth: verify_id_token(token)
    FirebaseAuth -->> Dep: uid = 'fb_123'
    
    Dep ->> SessionSvc: validate_session(session_id, user_id)
    SessionSvc ->> DB: SELECT * FROM user_sessions WHERE id=$session_id AND user_id=$user_id
    DB -->> SessionSvc: Session row
    
    alt Session Valid & Active
        SessionSvc ->> DB: UPDATE user_sessions SET last_activity=NOW(), expires_at=NOW()+30m WHERE id=$session_id
        Dep ->> DB: Fetch roles and check active status
        Dep -->> NextJS: Authorize request -> Return Booking List
        NextJS -->> User: Display Bookings Page
    else Session Inactivity Expired
        SessionSvc ->> DB: UPDATE user_sessions SET is_active=false WHERE id=$session_id
        SessionSvc -->> Dep: Session Expired
        Dep -->> NextJS: 401 Unauthorized {"detail": "Session expired due to inactivity"}
        NextJS ->> NextJS: Trigger global sessionExpiryHandler()
        NextJS -->> User: Show SessionTimeoutModal -> Redirect to /auth/login?reason=inactivity
    end
```

## 3. Important Implementation Notes
- **Server-Enforced Inactivity:** Inactivity is enforced authoritatively on the backend within `dependencies.py` and `session_service.py`. A valid Firebase ID token is rejected with HTTP 401 if the corresponding server session record has expired or was revoked.
- **Configurable Role-Based Inactivity Limits:** Customer (30 minutes), Manager/Organizer (20 minutes), and Administrator (15 minutes).
- **Multi-Tab Synchronization:** `BroadcastChannel('ticketflow_session')` synchronizes active sessions across all browser tabs. If a user logs out or times out in one tab, all other tabs immediately transition to the logged-out state.
