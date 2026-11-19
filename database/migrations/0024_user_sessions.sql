-- 0024_user_sessions.sql
-- Server-side session management for role-based inactivity timeout and automatic logout

CREATE TABLE IF NOT EXISTS user_sessions (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id uuid NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    role varchar(50) NOT NULL DEFAULT 'customer',
    timeout_seconds integer NOT NULL,
    last_activity_at timestamptz NOT NULL DEFAULT now(),
    created_at timestamptz NOT NULL DEFAULT now(),
    revoked_at timestamptz,
    ip_address varchar(100),
    user_agent text
);

CREATE INDEX IF NOT EXISTS idx_user_sessions_user_id ON user_sessions(user_id);
CREATE INDEX IF NOT EXISTS idx_user_sessions_last_activity ON user_sessions(last_activity_at);
CREATE INDEX IF NOT EXISTS idx_user_sessions_revoked_at ON user_sessions(revoked_at);

-- Enable RLS
ALTER TABLE user_sessions ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Users can view their own sessions"
    ON user_sessions FOR SELECT
    USING (auth.uid()::text = (SELECT firebase_uid FROM users WHERE id = user_sessions.user_id));
