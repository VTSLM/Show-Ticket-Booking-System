-- 0026: audit log for admin actions on user accounts (#138).
-- One row per change: who did it, to whom, what changed, why and when.
CREATE TABLE IF NOT EXISTS public.admin_audit_log (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    admin_id uuid REFERENCES public.users(id) ON DELETE SET NULL,
    target_user_id uuid REFERENCES public.users(id) ON DELETE SET NULL,
    action text NOT NULL
        CHECK (action IN ('role_added', 'role_removed', 'status_changed',
                          'manager_approved', 'manager_rejected')),
    details jsonb NOT NULL DEFAULT '{}'::jsonb,
    reason text,
    created_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_admin_audit_log_target
    ON public.admin_audit_log (target_user_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_admin_audit_log_admin
    ON public.admin_audit_log (admin_id, created_at DESC);

-- Only the backend (service role) reads and writes this table.
ALTER TABLE public.admin_audit_log ENABLE ROW LEVEL SECURITY;
