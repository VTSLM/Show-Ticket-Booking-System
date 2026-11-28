# Class Diagram: Users, Roles, and Identity

## 1. Description and Purpose
This diagram represents the structural model of the Identity and User Management domain. It models persistent database entities derived from `database/schema.sql` (migrations 0001, 0003, 0005, 0024) and their associations.

## 2. Class Diagram
```mermaid
classDiagram
    class User {
        +UUID id
        +String firebase_uid
        +String name
        +String email
        +String phone
        +UserStatus status
        +String avatar_url
        +Date date_of_birth
        +DateTime created_at
        +DateTime updated_at
        +isActive() bool
        +isBlocked() bool
    }

    class Role {
        +UUID id
        +String code
        +String name
    }

    class UserRole {
        +UUID user_id
        +UUID role_id
        +DateTime assigned_at
    }

    class UserSession {
        +UUID id
        +UUID user_id
        +String session_token
        +String ip_address
        +String user_agent
        +DateTime last_activity
        +DateTime expires_at
        +Boolean is_active
        +DateTime created_at
        +isExpired() bool
        +touch() void
    }

    class OrganizerProfile {
        +UUID id
        +UUID user_id
        +String organization_name
        +String business_type
        +String tax_id
        +String business_address
        +String verification_status
        +DateTime created_at
        +DateTime updated_at
    }

    class BankAccount {
        +UUID id
        +UUID organizer_id
        +String account_number_hash
        +String account_holder_name
        +String ifsc_code
        +Boolean is_verified
        +DateTime created_at
    }

    class UserStatus {
        <<enumeration>>
        active
        inactive
        blocked
    }

    %% Relationships
    User "1" --> "1" UserStatus : has status
    User "1" *-- "*" UserRole : has
    Role "1" --* "*" UserRole : assigned through
    User "1" *-- "*" UserSession : owns (cascade delete)
    User "1" o-- "0..1" OrganizerProfile : acts as
    OrganizerProfile "1" *-- "0..1" BankAccount : holds payout account
```

## 3. Relationship Explanations & Implementation Constraints
- **User to Role (Many-to-Many via `UserRole`):** Defined in SQL via the `user_roles` association table (`user_id REFERENCES users(id) ON DELETE CASCADE`, `role_id REFERENCES roles(id) ON DELETE RESTRICT`). Multiplicity is $1 \text{ to } *$.
- **User to UserSession (Composition `1` to `*`):** A user session cannot exist without a user (`user_sessions.user_id REFERENCES users(id) ON DELETE CASCADE`). Its lifetime is bound to the parent user. Inactivity timeout rules apply: Customer (30 min), Organizer (20 min), Admin (15 min).
- **User to OrganizerProfile (Aggregation `1` to `0..1`):** A user may optionally register an organizer profile. The user exists independently of the organizer profile.
- **OrganizerProfile to BankAccount (Composition `1` to `0..1`):** A registered bank account belongs to exactly one organizer profile and is deleted if the profile is removed.

## 4. Source Traceability
- Tables: `users`, `roles`, `user_roles`, `user_sessions`, `organizer_profiles`, `bank_accounts`.
- Backend Routers: `backend/routers/auth.py`, `backend/routers/admin_users.py`, `backend/routers/profile.py`.
- Backend Services: `backend/services/session_service.py`, `backend/services/bank_verification.py`.
- Dependencies: `backend/dependencies.py` (`get_current_user`, `require_role`).
