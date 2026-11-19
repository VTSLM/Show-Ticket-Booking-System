-- Generated snapshot of the full schema after database/migrations/0024. Do not edit by hand.
-- Regenerate with the steps in database/README.md.
--
-- PostgreSQL database dump
--

\restrict 91SaOmLBBahfsveXUeDdURvUusAfa32HcZEcnw5MBlx5QgVdwnFIGgS12UNji3g

-- Dumped from database version 16.15 (Ubuntu 16.15-0ubuntu0.24.04.1)
-- Dumped by pg_dump version 16.15 (Ubuntu 16.15-0ubuntu0.24.04.1)

SET statement_timeout = 0;
SET lock_timeout = 0;
SET idle_in_transaction_session_timeout = 0;
SET client_encoding = 'UTF8';
SET standard_conforming_strings = on;
SELECT pg_catalog.set_config('search_path', '', false);
SET check_function_bodies = false;
SET xmloption = content;
SET client_min_messages = warning;
SET row_security = off;

--
-- Name: pg_trgm; Type: EXTENSION; Schema: -; Owner: -
--

CREATE EXTENSION IF NOT EXISTS pg_trgm WITH SCHEMA public;


--
-- Name: EXTENSION pg_trgm; Type: COMMENT; Schema: -; Owner: -
--

COMMENT ON EXTENSION pg_trgm IS 'text similarity measurement and index searching based on trigrams';


--
-- Name: pgcrypto; Type: EXTENSION; Schema: -; Owner: -
--

CREATE EXTENSION IF NOT EXISTS pgcrypto WITH SCHEMA public;


--
-- Name: EXTENSION pgcrypto; Type: COMMENT; Schema: -; Owner: -
--

COMMENT ON EXTENSION pgcrypto IS 'cryptographic functions';


--
-- Name: booking_status; Type: TYPE; Schema: public; Owner: -
--

CREATE TYPE public.booking_status AS ENUM (
    'pending',
    'confirmed',
    'cancelled',
    'expired'
);


--
-- Name: event_status; Type: TYPE; Schema: public; Owner: -
--

CREATE TYPE public.event_status AS ENUM (
    'draft',
    'published',
    'inactive'
);


--
-- Name: event_type; Type: TYPE; Schema: public; Owner: -
--

CREATE TYPE public.event_type AS ENUM (
    'movie',
    'concert',
    'theatre',
    'other'
);


--
-- Name: payment_method; Type: TYPE; Schema: public; Owner: -
--

CREATE TYPE public.payment_method AS ENUM (
    'razorpay'
);


--
-- Name: payment_status; Type: TYPE; Schema: public; Owner: -
--

CREATE TYPE public.payment_status AS ENUM (
    'created',
    'pending',
    'successful',
    'failed',
    'refunded'
);


--
-- Name: seat_type; Type: TYPE; Schema: public; Owner: -
--

CREATE TYPE public.seat_type AS ENUM (
    'standard',
    'premium',
    'accessible'
);


--
-- Name: show_seat_status; Type: TYPE; Schema: public; Owner: -
--

CREATE TYPE public.show_seat_status AS ENUM (
    'available',
    'locked',
    'booked',
    'reserved'
);


--
-- Name: show_status; Type: TYPE; Schema: public; Owner: -
--

CREATE TYPE public.show_status AS ENUM (
    'scheduled',
    'cancelled',
    'completed'
);


--
-- Name: user_status; Type: TYPE; Schema: public; Owner: -
--

CREATE TYPE public.user_status AS ENUM (
    'active',
    'inactive',
    'blocked'
);


--
-- Name: get_show_seat_map(uuid); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.get_show_seat_map(p_show_id uuid) RETURNS TABLE(show_seat_id uuid, seat_id uuid, row_label character varying, seat_number integer, seat_type public.seat_type, price numeric, status public.show_seat_status, locked_until timestamp with time zone)
    LANGUAGE sql SECURITY DEFINER
    SET search_path TO 'public'
    AS $$
    select ss.id, s.id, s.row_label, s.seat_number, s.seat_type, ss.price,
           case when ss.status='locked' and ss.locked_until <= now()
                then 'available'::show_seat_status else ss.status end,
           case when ss.status='locked' and ss.locked_until <= now()
                then null else ss.locked_until end
    from show_seats ss
    join seats s on s.id=ss.seat_id
    where ss.show_id=p_show_id
    order by s.row_label,s.seat_number;
$$;


--
-- Name: lock_show_seats(uuid, uuid, uuid[], integer); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.lock_show_seats(p_show_id uuid, p_user_id uuid, p_seat_ids uuid[], p_lock_minutes integer DEFAULT 5) RETURNS TABLE(success boolean, message text, locked_count integer, total_amount numeric)
    LANGUAGE plpgsql SECURITY DEFINER
    SET search_path TO 'pg_catalog', 'public', 'pg_temp'
    AS $$
declare
    requested_count integer;
    distinct_count integer;
    available_count integer;
    calculated_total numeric;
begin
    requested_count := coalesce(cardinality(p_seat_ids), 0);
    if p_lock_minutes <= 0 then
        return query select false, 'Lock duration must be positive.', 0, 0::numeric;
        return;
    end if;
    if requested_count = 0 then
        return query select false, 'No seats were selected.', 0, 0::numeric;
        return;
    end if;

    select count(distinct requested.seat_id)::integer into distinct_count
    from unnest(p_seat_ids) as requested(seat_id);
    if distinct_count <> requested_count then
        return query select false, 'Duplicate seats were supplied.', 0, 0::numeric;
        return;
    end if;

    -- Lock every existing requested seat in stable order before checking status.
    -- This serializes concurrent seat selection and avoids the invalid aggregate
    -- SELECT ... FOR UPDATE used by migration 001.
    perform ss.id
    from show_seats ss
    where ss.show_id = p_show_id and ss.id = any(p_seat_ids)
    order by ss.id
    for update;

    select count(*)::integer, coalesce(sum(ss.price), 0)
      into available_count, calculated_total
    from show_seats ss
    where ss.show_id = p_show_id and ss.id = any(p_seat_ids)
      and (
        ss.status = 'available'
        or (ss.status = 'locked' and ss.locked_until <= now())
        or (ss.status = 'locked' and ss.locked_by = p_user_id)
      );

    if available_count <> requested_count then
        return query select false, 'One or more selected seats are unavailable.', 0, 0::numeric;
        return;
    end if;

    update show_seats
       set status = 'locked',
           locked_until = now() + make_interval(mins => p_lock_minutes),
           locked_by = p_user_id
     where show_id = p_show_id and id = any(p_seat_ids);

    return query select true, 'Seats locked successfully.', requested_count, calculated_total;
end;
$$;


--
-- Name: prevent_venue_audit_mutation(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.prevent_venue_audit_mutation() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
BEGIN
    RAISE EXCEPTION 'venue verification audit rows are immutable';
END;
$$;


--
-- Name: reject_audit_log_mutation(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.reject_audit_log_mutation() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
BEGIN
    RAISE EXCEPTION 'audit_log is append-only';
END;
$$;


--
-- Name: release_expired_show_seat_locks(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.release_expired_show_seat_locks() RETURNS integer
    LANGUAGE plpgsql SECURITY DEFINER
    SET search_path TO 'public'
    AS $$
declare released_count integer;
begin
    update show_seats
    set status='available',locked_until=null,locked_by=null
    where status='locked' and locked_until <= now();
    get diagnostics released_count=row_count;
    return released_count;
end;
$$;


--
-- Name: release_show_seat_locks(uuid, uuid, uuid[]); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.release_show_seat_locks(p_show_id uuid, p_user_id uuid, p_seat_ids uuid[]) RETURNS integer
    LANGUAGE plpgsql SECURITY DEFINER
    SET search_path TO 'public'
    AS $$
declare released_count integer;
begin
    update show_seats
    set status='available',locked_until=null,locked_by=null
    where show_id=p_show_id and id=any(p_seat_ids)
      and status='locked' and locked_by=p_user_id;
    get diagnostics released_count=row_count;
    return released_count;
end;
$$;


--
-- Name: set_payment_order_updated_at(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.set_payment_order_updated_at() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
begin new.updated_at = now(); return new; end;
$$;


--
-- Name: set_updated_at(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.set_updated_at() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
begin new.updated_at = now(); return new; end;
$$;


SET default_tablespace = '';

SET default_table_access_method = heap;

--
-- Name: admin_audit_log; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.admin_audit_log (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    admin_id uuid,
    target_user_id uuid,
    action text NOT NULL,
    details jsonb DEFAULT '{}'::jsonb NOT NULL,
    reason text,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT admin_audit_log_action_check CHECK ((action = ANY (ARRAY['role_added'::text, 'role_removed'::text, 'status_changed'::text, 'manager_approved'::text, 'manager_rejected'::text])))
);


--
-- Name: ai_review_summaries; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.ai_review_summaries (
    event_id uuid NOT NULL,
    audience_summary text NOT NULL,
    critic_summary text NOT NULL,
    overall_summary text NOT NULL,
    audience_liked jsonb DEFAULT '[]'::jsonb NOT NULL,
    audience_disliked jsonb DEFAULT '[]'::jsonb NOT NULL,
    critic_liked jsonb DEFAULT '[]'::jsonb NOT NULL,
    critic_disliked jsonb DEFAULT '[]'::jsonb NOT NULL,
    audience_rating numeric(4,2) DEFAULT 0 NOT NULL,
    critic_rating numeric(4,2) DEFAULT 0 NOT NULL,
    overall_rating numeric(4,2) DEFAULT 0 NOT NULL,
    review_count integer DEFAULT 0 NOT NULL,
    source_review_updated_at timestamp with time zone,
    generated_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL
);


--
-- Name: audit_log; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.audit_log (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    actor_id uuid,
    actor_role character varying(50) NOT NULL,
    action character varying(100) NOT NULL,
    entity_type character varying(50) NOT NULL,
    entity_id uuid NOT NULL,
    before jsonb,
    after jsonb,
    reason text DEFAULT ''::text NOT NULL,
    at timestamp with time zone DEFAULT now() NOT NULL
);


--
-- Name: bank_accounts; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.bank_accounts (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    organizer_id uuid NOT NULL,
    holder_name character varying(255) NOT NULL,
    ifsc character varying(20) NOT NULL,
    account_masked character varying(30) NOT NULL,
    account_hash character varying(128) NOT NULL,
    verified boolean DEFAULT false NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL
);


--
-- Name: booking_seats; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.booking_seats (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    booking_id uuid NOT NULL,
    show_seat_id uuid NOT NULL,
    unit_price numeric(10,2) NOT NULL,
    CONSTRAINT booking_seats_unit_price_check CHECK ((unit_price >= (0)::numeric))
);


--
-- Name: booking_zones; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.booking_zones (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    booking_id uuid NOT NULL,
    zone_id uuid NOT NULL,
    quantity integer NOT NULL,
    unit_price numeric(10,2) NOT NULL,
    created_at timestamp with time zone DEFAULT now(),
    CONSTRAINT booking_zones_quantity_check CHECK ((quantity > 0)),
    CONSTRAINT booking_zones_unit_price_check CHECK ((unit_price >= (0)::numeric))
);


--
-- Name: bookings; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.bookings (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    booking_number character varying(50) NOT NULL,
    user_id uuid NOT NULL,
    show_id uuid NOT NULL,
    total_amount numeric(10,2) NOT NULL,
    currency character varying(3) DEFAULT 'INR'::character varying NOT NULL,
    status public.booking_status DEFAULT 'pending'::public.booking_status NOT NULL,
    booked_at timestamp with time zone,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    cancelled_at timestamp with time zone,
    cancellation_reason text,
    cancellation_notes text,
    cancellation_charge numeric(10,2) DEFAULT 0.00,
    refund_amount numeric(10,2) DEFAULT 0.00,
    refund_status character varying(50) DEFAULT 'NOT_APPLICABLE'::character varying,
    CONSTRAINT bookings_total_amount_check CHECK ((total_amount >= (0)::numeric))
);


--
-- Name: cancellation_policies; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.cancellation_policies (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    name character varying(100) NOT NULL,
    description text,
    cutoff_hours integer DEFAULT 2 NOT NULL,
    deduction_percentage numeric(5,2) DEFAULT 0.00 NOT NULL,
    flat_cancellation_fee numeric(10,2) DEFAULT 0.00 NOT NULL,
    is_refundable boolean DEFAULT true NOT NULL,
    is_default boolean DEFAULT false NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL
);


--
-- Name: checklist_templates; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.checklist_templates (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    case_type character varying(20) NOT NULL,
    state character varying(100) DEFAULT '*'::character varying NOT NULL,
    required_document_types jsonb DEFAULT '[]'::jsonb NOT NULL,
    validity_rules jsonb DEFAULT '{}'::jsonb NOT NULL,
    updated_by uuid,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT checklist_templates_case_type_check CHECK (((case_type)::text = ANY ((ARRAY['ORGANIZER'::character varying, 'VENUE'::character varying, 'LISTING'::character varying])::text[])))
);


--
-- Name: duplicate_fingerprints; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.duplicate_fingerprints (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    kind character varying(50) NOT NULL,
    salted_hash character varying(128) NOT NULL,
    case_id uuid NOT NULL,
    case_type character varying(30) DEFAULT 'ORGANIZER'::character varying NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT duplicate_fingerprints_case_type_check CHECK (((case_type)::text = ANY ((ARRAY['ORGANIZER'::character varying, 'VENUE'::character varying, 'LISTING'::character varying])::text[])))
);


--
-- Name: events; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.events (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    title character varying(200) NOT NULL,
    description text,
    event_type public.event_type NOT NULL,
    duration_minutes integer,
    language character varying(50),
    genre character varying(100),
    poster_url text,
    status public.event_status DEFAULT 'draft'::public.event_status NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    backdrop_url text,
    imdb_score numeric(3,1) DEFAULT 8.2,
    metacritic_score integer DEFAULT 71,
    age_rating character varying(20) DEFAULT '7+'::character varying,
    match_rate integer DEFAULT 94,
    organizer_id uuid,
    cast_crew jsonb DEFAULT '[]'::jsonb,
    artists jsonb DEFAULT '[]'::jsonb,
    formats text[] DEFAULT ARRAY['2D'::text],
    certificate character varying(20) DEFAULT 'UA'::character varying,
    release_date date,
    terms_and_conditions text,
    CONSTRAINT events_duration_minutes_check CHECK (((duration_minutes IS NULL) OR (duration_minutes > 0)))
);


--
-- Name: listing_reports; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.listing_reports (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    event_id uuid NOT NULL,
    reported_by uuid NOT NULL,
    reason_code character varying(40) NOT NULL,
    note text,
    status character varying(20) DEFAULT 'OPEN'::character varying NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT listing_reports_status_check CHECK (((status)::text = ANY ((ARRAY['OPEN'::character varying, 'IN_REVIEW'::character varying, 'RESOLVED'::character varying, 'DISMISSED'::character varying])::text[])))
);


--
-- Name: listing_reviews; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.listing_reviews (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    event_id uuid NOT NULL,
    show_id uuid,
    status character varying(30) DEFAULT 'SUBMITTED'::character varying NOT NULL,
    reviewer_id uuid,
    reason text,
    conflict_summary jsonb DEFAULT '{}'::jsonb NOT NULL,
    reviewed_at timestamp with time zone,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT listing_reviews_status_check CHECK (((status)::text = ANY ((ARRAY['SUBMITTED'::character varying, 'IN_REVIEW'::character varying, 'CHANGES_REQUESTED'::character varying, 'APPROVED'::character varying, 'REJECTED'::character varying, 'FLAGGED'::character varying, 'REMOVED'::character varying])::text[])))
);


--
-- Name: notifications; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.notifications (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    user_id uuid NOT NULL,
    event_name character varying(100) NOT NULL,
    payload jsonb DEFAULT '{}'::jsonb NOT NULL,
    read_at timestamp with time zone,
    emailed_at timestamp with time zone,
    created_at timestamp with time zone DEFAULT now() NOT NULL
);


--
-- Name: organizer_profiles; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.organizer_profiles (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    user_id uuid NOT NULL,
    legal_name character varying(255) NOT NULL,
    business_type character varying(50) NOT NULL,
    state character varying(100),
    pan_masked character varying(20),
    gstin_masked character varying(20),
    verification_status character varying(30) DEFAULT 'PENDING'::character varying NOT NULL,
    trust_tier character varying(50) DEFAULT 'TIER_1'::character varying NOT NULL,
    reviewer_id uuid,
    claimed_at timestamp with time zone,
    claim_expires_at timestamp with time zone,
    reviewer_comments text,
    rejection_reason text,
    suspension_reason text,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT organizer_profiles_business_type_check CHECK (((business_type)::text = ANY ((ARRAY['INDIVIDUAL'::character varying, 'SOLE_PROPRIETOR'::character varying, 'COMPANY'::character varying, 'LLP'::character varying, 'TRUST'::character varying])::text[]))),
    CONSTRAINT organizer_profiles_verification_status_check CHECK (((verification_status)::text = ANY ((ARRAY['DRAFT'::character varying, 'SUBMITTED'::character varying, 'IN_REVIEW'::character varying, 'PENDING'::character varying, 'CHANGES_REQUESTED'::character varying, 'APPROVED'::character varying, 'REJECTED'::character varying, 'SUSPENDED'::character varying, 'EXPIRED'::character varying])::text[])))
);


--
-- Name: payment_orders; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.payment_orders (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    booking_id uuid NOT NULL,
    razorpay_order_id character varying(100) NOT NULL,
    amount numeric(10,2) NOT NULL,
    currency character varying(3) DEFAULT 'INR'::character varying NOT NULL,
    status character varying(32) DEFAULT 'created'::character varying NOT NULL,
    created_by uuid NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT payment_orders_amount_check CHECK ((amount > (0)::numeric)),
    CONSTRAINT payment_orders_status_check CHECK (((status)::text = ANY ((ARRAY['creating'::character varying, 'created'::character varying, 'verification_pending'::character varying, 'authorized'::character varying, 'successful'::character varying, 'successful_needs_review'::character varying, 'failed'::character varying, 'cancelled'::character varying])::text[])))
);


--
-- Name: payments; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.payments (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    booking_id uuid NOT NULL,
    transaction_id character varying(100),
    amount numeric(10,2) NOT NULL,
    currency character varying(3) DEFAULT 'INR'::character varying NOT NULL,
    payment_method public.payment_method DEFAULT 'razorpay'::public.payment_method NOT NULL,
    status public.payment_status DEFAULT 'created'::public.payment_status NOT NULL,
    paid_at timestamp with time zone,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    payment_order_id uuid,
    razorpay_payment_id character varying(100),
    provider_method character varying(32),
    provider_created_at timestamp with time zone,
    signature_verified_at timestamp with time zone,
    failure_reason text,
    razorpay_refund_id character varying(100),
    refunded_amount numeric(10,2),
    refunded_at timestamp with time zone,
    CONSTRAINT payments_amount_check CHECK ((amount >= (0)::numeric))
);


--
-- Name: receipts; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.receipts (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    receipt_number character varying(50) NOT NULL,
    payment_id uuid NOT NULL,
    issued_at timestamp with time zone DEFAULT now() NOT NULL,
    pdf_url text
);


--
-- Name: refunds; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.refunds (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    booking_id uuid NOT NULL,
    payment_id uuid,
    user_id uuid NOT NULL,
    amount numeric(10,2) NOT NULL,
    cancellation_charge numeric(10,2) DEFAULT 0.00 NOT NULL,
    currency character varying(10) DEFAULT 'INR'::character varying NOT NULL,
    status character varying(50) DEFAULT 'PENDING'::character varying NOT NULL,
    razorpay_payment_id character varying(100),
    razorpay_refund_id character varying(100),
    failure_reason text,
    retry_count integer DEFAULT 0 NOT NULL,
    last_retried_at timestamp with time zone,
    retried_by uuid,
    policy_snapshot jsonb DEFAULT '{}'::jsonb NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    completed_at timestamp with time zone
);


--
-- Name: review_comments; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.review_comments (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    review_id uuid NOT NULL,
    user_id uuid NOT NULL,
    content text NOT NULL,
    is_pinned boolean DEFAULT false NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    parent_comment_id uuid,
    CONSTRAINT review_comments_content_check CHECK ((length(TRIM(BOTH FROM content)) > 0))
);


--
-- Name: review_deletions; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.review_deletions (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    review_id uuid NOT NULL,
    event_id uuid NOT NULL,
    user_id uuid NOT NULL,
    rating numeric(3,1) NOT NULL,
    headline character varying(255) NOT NULL,
    content text NOT NULL,
    sections_json jsonb,
    media_url text,
    is_spoiler boolean DEFAULT false NOT NULL,
    version integer NOT NULL,
    published_at timestamp with time zone NOT NULL,
    last_updated_at timestamp with time zone NOT NULL,
    versions_snapshot jsonb DEFAULT '[]'::jsonb NOT NULL,
    comments_snapshot jsonb DEFAULT '[]'::jsonb NOT NULL,
    upvotes_count integer DEFAULT 0 NOT NULL,
    deleted_by uuid,
    deleted_at timestamp with time zone DEFAULT now() NOT NULL
);


--
-- Name: review_reports; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.review_reports (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    review_id uuid NOT NULL,
    reporter_id uuid NOT NULL,
    reason character varying(20) NOT NULL,
    details text,
    status character varying(20) DEFAULT 'open'::character varying NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    resolved_at timestamp with time zone,
    resolved_by uuid,
    CONSTRAINT review_reports_details_check CHECK (((details IS NULL) OR (length(details) <= 500))),
    CONSTRAINT review_reports_reason_check CHECK (((reason)::text = ANY ((ARRAY['spam'::character varying, 'abusive'::character varying, 'spoiler'::character varying, 'off_topic'::character varying, 'other'::character varying])::text[]))),
    CONSTRAINT review_reports_status_check CHECK (((status)::text = ANY ((ARRAY['open'::character varying, 'dismissed'::character varying, 'reviewed'::character varying])::text[])))
);


--
-- Name: review_upvotes; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.review_upvotes (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    review_id uuid NOT NULL,
    user_id uuid NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL
);


--
-- Name: review_versions; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.review_versions (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    review_id uuid NOT NULL,
    version_number integer NOT NULL,
    rating numeric(3,1) NOT NULL,
    headline character varying(255) NOT NULL,
    content text NOT NULL,
    sections_json jsonb,
    is_spoiler boolean DEFAULT false NOT NULL,
    change_summary character varying(255),
    created_at timestamp with time zone DEFAULT now() NOT NULL
);


--
-- Name: reviews; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.reviews (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    event_id uuid NOT NULL,
    user_id uuid NOT NULL,
    rating numeric(3,1) NOT NULL,
    headline character varying(255) NOT NULL,
    content text NOT NULL,
    sections_json jsonb,
    media_url text,
    is_spoiler boolean DEFAULT false NOT NULL,
    is_draft boolean DEFAULT false NOT NULL,
    scheduled_for timestamp with time zone,
    version integer DEFAULT 1 NOT NULL,
    published_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT reviews_rating_check CHECK (((rating >= 1.0) AND (rating <= 10.0)))
);


--
-- Name: roles; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.roles (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    code character varying(50) NOT NULL,
    name character varying(100) NOT NULL
);


--
-- Name: screens; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.screens (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    venue_id uuid NOT NULL,
    name character varying(100) NOT NULL,
    capacity integer NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    layout_type character varying(50) DEFAULT 'cinema'::character varying,
    stage_position character varying(30) DEFAULT 'front'::character varying,
    layout_config jsonb,
    CONSTRAINT screens_capacity_check CHECK ((capacity > 0))
);


--
-- Name: seats; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.seats (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    screen_id uuid NOT NULL,
    row_label character varying(5) NOT NULL,
    seat_number integer NOT NULL,
    seat_type public.seat_type DEFAULT 'standard'::public.seat_type NOT NULL,
    x_pos numeric(8,2),
    y_pos numeric(8,2),
    section_name character varying(100),
    CONSTRAINT seats_seat_number_check CHECK ((seat_number > 0))
);


--
-- Name: show_seats; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.show_seats (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    show_id uuid NOT NULL,
    seat_id uuid NOT NULL,
    price numeric(10,2) NOT NULL,
    status public.show_seat_status DEFAULT 'available'::public.show_seat_status NOT NULL,
    locked_until timestamp with time zone,
    locked_by uuid,
    locked_price numeric(10,2),
    CONSTRAINT show_seats_check CHECK ((((status = 'locked'::public.show_seat_status) AND (locked_until IS NOT NULL) AND (locked_by IS NOT NULL)) OR (status <> 'locked'::public.show_seat_status))),
    CONSTRAINT show_seats_price_check CHECK ((price >= (0)::numeric))
);


--
-- Name: show_zones; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.show_zones (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    show_id uuid NOT NULL,
    name character varying(100) NOT NULL,
    zone_type character varying(50) DEFAULT 'standing'::character varying NOT NULL,
    total_capacity integer NOT NULL,
    booked_count integer DEFAULT 0 NOT NULL,
    locked_count integer DEFAULT 0 NOT NULL,
    price numeric(10,2) NOT NULL,
    color_hex character varying(20) DEFAULT '#287cff'::character varying,
    display_order integer DEFAULT 1,
    created_at timestamp with time zone DEFAULT now(),
    polygon_coords jsonb,
    x_pos numeric(8,2),
    y_pos numeric(8,2),
    width numeric(8,2),
    height numeric(8,2),
    CONSTRAINT chk_show_zone_capacity CHECK (((booked_count + locked_count) <= total_capacity)),
    CONSTRAINT show_zones_booked_count_check CHECK ((booked_count >= 0)),
    CONSTRAINT show_zones_locked_count_check CHECK ((locked_count >= 0)),
    CONSTRAINT show_zones_price_check CHECK ((price >= (0)::numeric)),
    CONSTRAINT show_zones_total_capacity_check CHECK ((total_capacity > 0))
);


--
-- Name: shows; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.shows (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    event_id uuid NOT NULL,
    screen_id uuid NOT NULL,
    start_time timestamp with time zone NOT NULL,
    end_time timestamp with time zone NOT NULL,
    status public.show_status DEFAULT 'scheduled'::public.show_status NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    dynamic_pricing boolean DEFAULT false NOT NULL,
    terms_and_conditions text,
    base_price numeric(10,2) DEFAULT 0 NOT NULL,
    cancellation_policy_id uuid,
    CONSTRAINT shows_check CHECK ((end_time > start_time))
);


--
-- Name: support_messages; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.support_messages (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    request_id uuid NOT NULL,
    sender_id uuid NOT NULL,
    is_admin boolean DEFAULT false NOT NULL,
    message text NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT support_messages_message_check CHECK ((length(TRIM(BOTH FROM message)) > 0))
);


--
-- Name: support_requests; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.support_requests (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    request_number character varying(30) NOT NULL,
    user_id uuid NOT NULL,
    booking_id uuid,
    category character varying(20) NOT NULL,
    subject character varying(150) NOT NULL,
    status character varying(20) DEFAULT 'open'::character varying NOT NULL,
    priority character varying(10) DEFAULT 'normal'::character varying NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    resolved_at timestamp with time zone,
    CONSTRAINT support_requests_category_check CHECK (((category)::text = ANY ((ARRAY['payment'::character varying, 'booking'::character varying, 'refund'::character varying, 'account'::character varying, 'other'::character varying])::text[]))),
    CONSTRAINT support_requests_priority_check CHECK (((priority)::text = ANY ((ARRAY['low'::character varying, 'normal'::character varying, 'high'::character varying])::text[]))),
    CONSTRAINT support_requests_status_check CHECK (((status)::text = ANY ((ARRAY['open'::character varying, 'in_progress'::character varying, 'resolved'::character varying, 'closed'::character varying])::text[])))
);


--
-- Name: terms_acceptances; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.terms_acceptances (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    user_id uuid NOT NULL,
    show_id uuid NOT NULL,
    booking_id uuid,
    terms_hash character varying(64) NOT NULL,
    terms_text text NOT NULL,
    accepted_at timestamp with time zone DEFAULT now() NOT NULL
);


--
-- Name: tickets; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.tickets (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    booking_id uuid NOT NULL,
    user_id uuid NOT NULL,
    show_id uuid NOT NULL,
    qr_code_data text NOT NULL,
    status character varying(20) DEFAULT 'valid'::character varying NOT NULL,
    is_used boolean DEFAULT false NOT NULL,
    used_at timestamp with time zone,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT tickets_check CHECK ((((is_used = false) AND (used_at IS NULL)) OR ((is_used = true) AND (used_at IS NOT NULL)))),
    CONSTRAINT tickets_status_check CHECK (((status)::text = ANY ((ARRAY['valid'::character varying, 'used'::character varying, 'cancelled'::character varying])::text[])))
);


--
-- Name: trust_tier_rules; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.trust_tier_rules (
    tier character varying(50) NOT NULL,
    max_live_shows integer DEFAULT 1 NOT NULL,
    payout_hold_days integer DEFAULT 7 NOT NULL,
    rules jsonb DEFAULT '{}'::jsonb NOT NULL,
    description text,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT trust_tier_rules_max_live_shows_check CHECK ((max_live_shows >= 0)),
    CONSTRAINT trust_tier_rules_payout_hold_days_check CHECK ((payout_hold_days >= 0))
);


--
-- Name: user_roles; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.user_roles (
    user_id uuid NOT NULL,
    role_id uuid NOT NULL,
    assigned_at timestamp with time zone DEFAULT now() NOT NULL
);


--
-- Name: users; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.users (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    firebase_uid character varying(255) NOT NULL,
    name character varying(100) NOT NULL,
    email character varying(255) NOT NULL,
    phone character varying(20),
    status public.user_status DEFAULT 'active'::public.user_status NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    birthdate date,
    is_verified boolean DEFAULT false,
    publication character varying(255),
    avatar_url text,
    bio text
);


--
-- Name: venue_case_documents; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.venue_case_documents (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    case_id uuid NOT NULL,
    uploaded_by uuid NOT NULL,
    kind text NOT NULL,
    original_filename text NOT NULL,
    content_type text NOT NULL,
    size_bytes integer NOT NULL,
    storage_key text NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT venue_case_documents_kind_check CHECK ((kind = ANY (ARRAY['venue_photo'::text, 'seating_plan'::text]))),
    CONSTRAINT venue_case_documents_size_bytes_check CHECK ((size_bytes > 0))
);


--
-- Name: venue_compliance; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.venue_compliance (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    venue_id uuid NOT NULL,
    applicant_user_id uuid NOT NULL,
    licence_no_masked character varying(30),
    licence_hash character varying(128),
    licence_authority character varying(200),
    licence_valid_to date,
    fire_noc_valid_to date,
    electrical_valid_to date,
    licensed_capacity integer NOT NULL,
    ownership_type character varying(30) NOT NULL,
    ownership_doc_id uuid,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT venue_compliance_licensed_capacity_check CHECK ((licensed_capacity > 0)),
    CONSTRAINT venue_compliance_ownership_type_check CHECK (((ownership_type)::text = ANY ((ARRAY['OWNER'::character varying, 'LEASE'::character varying, 'MANAGER'::character varying])::text[])))
);


--
-- Name: venue_verification_audit; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.venue_verification_audit (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    case_id uuid NOT NULL,
    case_version integer NOT NULL,
    actor_id uuid NOT NULL,
    action text NOT NULL,
    old_status text NOT NULL,
    new_status text NOT NULL,
    reason text,
    metadata jsonb DEFAULT '{}'::jsonb NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL
);


--
-- Name: venue_verification_cases; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.venue_verification_cases (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    venue_id uuid NOT NULL,
    applicant_id uuid NOT NULL,
    status text DEFAULT 'draft'::text NOT NULL,
    reviewer_id uuid,
    claim_expires_at timestamp with time zone,
    reviewer_comments text,
    version integer DEFAULT 1 NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT venue_verification_cases_status_check CHECK ((status = ANY (ARRAY['draft'::text, 'submitted'::text, 'in_review'::text, 'approved'::text, 'rejected'::text, 'changes_requested'::text, 'expired'::text]))),
    CONSTRAINT venue_verification_cases_version_check CHECK ((version > 0))
);


--
-- Name: venues; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.venues (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    name character varying(200) NOT NULL,
    address text,
    city character varying(100) NOT NULL,
    state character varying(100),
    pincode character varying(10),
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    verification_status text DEFAULT 'unverified'::text NOT NULL,
    licensed_capacity integer,
    license_expiry date,
    noc_expiry date,
    CONSTRAINT venues_licensed_capacity_check CHECK (((licensed_capacity IS NULL) OR (licensed_capacity > 0)))
);


--
-- Name: verification_cases; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.verification_cases (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    case_type character varying(20) NOT NULL,
    subject_id uuid NOT NULL,
    applicant_user_id uuid NOT NULL,
    status character varying(30) DEFAULT 'DRAFT'::character varying NOT NULL,
    submitted_at timestamp with time zone,
    claimed_by uuid,
    claim_expires_at timestamp with time zone,
    decided_by uuid,
    decided_at timestamp with time zone,
    decision_reason text,
    row_version integer DEFAULT 1 NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT verification_cases_case_type_check CHECK (((case_type)::text = ANY ((ARRAY['ORGANIZER'::character varying, 'VENUE'::character varying, 'LISTING'::character varying])::text[]))),
    CONSTRAINT verification_cases_check CHECK (((claimed_by IS NULL) = (claim_expires_at IS NULL))),
    CONSTRAINT verification_cases_row_version_check CHECK ((row_version > 0)),
    CONSTRAINT verification_cases_status_check CHECK (((status)::text = ANY ((ARRAY['DRAFT'::character varying, 'SUBMITTED'::character varying, 'IN_REVIEW'::character varying, 'CHANGES_REQUESTED'::character varying, 'APPROVED'::character varying, 'REJECTED'::character varying, 'SUSPENDED'::character varying, 'EXPIRED'::character varying])::text[])))
);


--
-- Name: verification_documents; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.verification_documents (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    case_id uuid NOT NULL,
    case_type character varying(30) NOT NULL,
    doc_type character varying(50) NOT NULL,
    version integer DEFAULT 1 NOT NULL,
    storage_ref text NOT NULL,
    doc_number_masked character varying(50),
    issued_by character varying(255),
    valid_to date,
    review_status character varying(30) DEFAULT 'PENDING'::character varying NOT NULL,
    reviewer_comment text,
    uploaded_by uuid,
    uploaded_at timestamp with time zone DEFAULT now() NOT NULL,
    reviewed_by uuid,
    reviewed_at timestamp with time zone,
    CONSTRAINT verification_documents_case_type_check CHECK (((case_type)::text = ANY ((ARRAY['ORGANIZER'::character varying, 'VENUE'::character varying, 'LISTING'::character varying])::text[]))),
    CONSTRAINT verification_documents_doc_type_check CHECK (((doc_type)::text = ANY ((ARRAY['PAN'::character varying, 'GST_CERTIFICATE'::character varying, 'BANK_PROOF'::character varying, 'SIGNATORY_ID'::character varying, 'AUTHORISATION_LETTER'::character varying, 'BUSINESS_REGISTRATION'::character varying, 'CINEMA_LICENCE'::character varying, 'FIRE_NOC'::character varying, 'ELECTRICAL_CERT'::character varying, 'OCCUPANCY_CERT'::character varying, 'OWNERSHIP_PROOF'::character varying, 'OTHER'::character varying])::text[]))),
    CONSTRAINT verification_documents_review_status_check CHECK (((review_status)::text = ANY ((ARRAY['PENDING'::character varying, 'APPROVED'::character varying, 'REJECTED'::character varying, 'CHANGES_REQUESTED'::character varying])::text[]))),
    CONSTRAINT verification_documents_version_check CHECK ((version > 0))
);


--
-- Name: wishlists; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.wishlists (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    user_id uuid NOT NULL,
    event_id uuid NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL
);


--
-- Name: admin_audit_log admin_audit_log_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.admin_audit_log
    ADD CONSTRAINT admin_audit_log_pkey PRIMARY KEY (id);


--
-- Name: ai_review_summaries ai_review_summaries_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.ai_review_summaries
    ADD CONSTRAINT ai_review_summaries_pkey PRIMARY KEY (event_id);


--
-- Name: audit_log audit_log_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.audit_log
    ADD CONSTRAINT audit_log_pkey PRIMARY KEY (id);


--
-- Name: bank_accounts bank_accounts_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.bank_accounts
    ADD CONSTRAINT bank_accounts_pkey PRIMARY KEY (id);


--
-- Name: booking_seats booking_seats_booking_id_show_seat_id_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.booking_seats
    ADD CONSTRAINT booking_seats_booking_id_show_seat_id_key UNIQUE (booking_id, show_seat_id);


--
-- Name: booking_seats booking_seats_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.booking_seats
    ADD CONSTRAINT booking_seats_pkey PRIMARY KEY (id);


--
-- Name: booking_zones booking_zones_booking_id_zone_id_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.booking_zones
    ADD CONSTRAINT booking_zones_booking_id_zone_id_key UNIQUE (booking_id, zone_id);


--
-- Name: booking_zones booking_zones_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.booking_zones
    ADD CONSTRAINT booking_zones_pkey PRIMARY KEY (id);


--
-- Name: bookings bookings_booking_number_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.bookings
    ADD CONSTRAINT bookings_booking_number_key UNIQUE (booking_number);


--
-- Name: bookings bookings_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.bookings
    ADD CONSTRAINT bookings_pkey PRIMARY KEY (id);


--
-- Name: cancellation_policies cancellation_policies_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.cancellation_policies
    ADD CONSTRAINT cancellation_policies_pkey PRIMARY KEY (id);


--
-- Name: checklist_templates checklist_templates_case_type_state_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.checklist_templates
    ADD CONSTRAINT checklist_templates_case_type_state_key UNIQUE (case_type, state);


--
-- Name: checklist_templates checklist_templates_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.checklist_templates
    ADD CONSTRAINT checklist_templates_pkey PRIMARY KEY (id);


--
-- Name: duplicate_fingerprints duplicate_fingerprints_kind_salted_hash_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.duplicate_fingerprints
    ADD CONSTRAINT duplicate_fingerprints_kind_salted_hash_key UNIQUE (kind, salted_hash);


--
-- Name: duplicate_fingerprints duplicate_fingerprints_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.duplicate_fingerprints
    ADD CONSTRAINT duplicate_fingerprints_pkey PRIMARY KEY (id);


--
-- Name: events events_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.events
    ADD CONSTRAINT events_pkey PRIMARY KEY (id);


--
-- Name: listing_reports listing_reports_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.listing_reports
    ADD CONSTRAINT listing_reports_pkey PRIMARY KEY (id);


--
-- Name: listing_reviews listing_reviews_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.listing_reviews
    ADD CONSTRAINT listing_reviews_pkey PRIMARY KEY (id);


--
-- Name: notifications notifications_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.notifications
    ADD CONSTRAINT notifications_pkey PRIMARY KEY (id);


--
-- Name: organizer_profiles organizer_profiles_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.organizer_profiles
    ADD CONSTRAINT organizer_profiles_pkey PRIMARY KEY (id);


--
-- Name: payment_orders payment_orders_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.payment_orders
    ADD CONSTRAINT payment_orders_pkey PRIMARY KEY (id);


--
-- Name: payment_orders payment_orders_razorpay_order_id_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.payment_orders
    ADD CONSTRAINT payment_orders_razorpay_order_id_key UNIQUE (razorpay_order_id);


--
-- Name: payments payments_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.payments
    ADD CONSTRAINT payments_pkey PRIMARY KEY (id);


--
-- Name: receipts receipts_payment_id_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.receipts
    ADD CONSTRAINT receipts_payment_id_key UNIQUE (payment_id);


--
-- Name: receipts receipts_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.receipts
    ADD CONSTRAINT receipts_pkey PRIMARY KEY (id);


--
-- Name: receipts receipts_receipt_number_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.receipts
    ADD CONSTRAINT receipts_receipt_number_key UNIQUE (receipt_number);


--
-- Name: refunds refunds_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.refunds
    ADD CONSTRAINT refunds_pkey PRIMARY KEY (id);


--
-- Name: refunds refunds_razorpay_refund_id_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.refunds
    ADD CONSTRAINT refunds_razorpay_refund_id_key UNIQUE (razorpay_refund_id);


--
-- Name: review_comments review_comments_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.review_comments
    ADD CONSTRAINT review_comments_pkey PRIMARY KEY (id);


--
-- Name: review_deletions review_deletions_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.review_deletions
    ADD CONSTRAINT review_deletions_pkey PRIMARY KEY (id);


--
-- Name: review_reports review_reports_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.review_reports
    ADD CONSTRAINT review_reports_pkey PRIMARY KEY (id);


--
-- Name: review_upvotes review_upvotes_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.review_upvotes
    ADD CONSTRAINT review_upvotes_pkey PRIMARY KEY (id);


--
-- Name: review_versions review_versions_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.review_versions
    ADD CONSTRAINT review_versions_pkey PRIMARY KEY (id);


--
-- Name: reviews reviews_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.reviews
    ADD CONSTRAINT reviews_pkey PRIMARY KEY (id);


--
-- Name: roles roles_code_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.roles
    ADD CONSTRAINT roles_code_key UNIQUE (code);


--
-- Name: roles roles_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.roles
    ADD CONSTRAINT roles_pkey PRIMARY KEY (id);


--
-- Name: screens screens_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.screens
    ADD CONSTRAINT screens_pkey PRIMARY KEY (id);


--
-- Name: screens screens_venue_id_name_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.screens
    ADD CONSTRAINT screens_venue_id_name_key UNIQUE (venue_id, name);


--
-- Name: seats seats_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.seats
    ADD CONSTRAINT seats_pkey PRIMARY KEY (id);


--
-- Name: seats seats_screen_id_row_label_seat_number_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.seats
    ADD CONSTRAINT seats_screen_id_row_label_seat_number_key UNIQUE (screen_id, row_label, seat_number);


--
-- Name: show_seats show_seats_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.show_seats
    ADD CONSTRAINT show_seats_pkey PRIMARY KEY (id);


--
-- Name: show_seats show_seats_show_id_seat_id_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.show_seats
    ADD CONSTRAINT show_seats_show_id_seat_id_key UNIQUE (show_id, seat_id);


--
-- Name: show_zones show_zones_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.show_zones
    ADD CONSTRAINT show_zones_pkey PRIMARY KEY (id);


--
-- Name: shows shows_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.shows
    ADD CONSTRAINT shows_pkey PRIMARY KEY (id);


--
-- Name: support_messages support_messages_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.support_messages
    ADD CONSTRAINT support_messages_pkey PRIMARY KEY (id);


--
-- Name: support_requests support_requests_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.support_requests
    ADD CONSTRAINT support_requests_pkey PRIMARY KEY (id);


--
-- Name: support_requests support_requests_request_number_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.support_requests
    ADD CONSTRAINT support_requests_request_number_key UNIQUE (request_number);


--
-- Name: terms_acceptances terms_acceptances_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.terms_acceptances
    ADD CONSTRAINT terms_acceptances_pkey PRIMARY KEY (id);


--
-- Name: tickets tickets_booking_id_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.tickets
    ADD CONSTRAINT tickets_booking_id_key UNIQUE (booking_id);


--
-- Name: tickets tickets_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.tickets
    ADD CONSTRAINT tickets_pkey PRIMARY KEY (id);


--
-- Name: trust_tier_rules trust_tier_rules_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.trust_tier_rules
    ADD CONSTRAINT trust_tier_rules_pkey PRIMARY KEY (tier);


--
-- Name: reviews unique_event_user_review; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.reviews
    ADD CONSTRAINT unique_event_user_review UNIQUE (event_id, user_id);


--
-- Name: review_reports unique_review_reporter; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.review_reports
    ADD CONSTRAINT unique_review_reporter UNIQUE (review_id, reporter_id);


--
-- Name: review_upvotes unique_review_user_upvote; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.review_upvotes
    ADD CONSTRAINT unique_review_user_upvote UNIQUE (review_id, user_id);


--
-- Name: review_versions unique_review_version; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.review_versions
    ADD CONSTRAINT unique_review_version UNIQUE (review_id, version_number);


--
-- Name: user_roles user_roles_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.user_roles
    ADD CONSTRAINT user_roles_pkey PRIMARY KEY (user_id, role_id);


--
-- Name: users users_email_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.users
    ADD CONSTRAINT users_email_key UNIQUE (email);


--
-- Name: users users_firebase_uid_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.users
    ADD CONSTRAINT users_firebase_uid_key UNIQUE (firebase_uid);


--
-- Name: users users_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.users
    ADD CONSTRAINT users_pkey PRIMARY KEY (id);


--
-- Name: venue_case_documents venue_case_documents_case_id_kind_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.venue_case_documents
    ADD CONSTRAINT venue_case_documents_case_id_kind_key UNIQUE (case_id, kind);


--
-- Name: venue_case_documents venue_case_documents_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.venue_case_documents
    ADD CONSTRAINT venue_case_documents_pkey PRIMARY KEY (id);


--
-- Name: venue_case_documents venue_case_documents_storage_key_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.venue_case_documents
    ADD CONSTRAINT venue_case_documents_storage_key_key UNIQUE (storage_key);


--
-- Name: venue_compliance venue_compliance_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.venue_compliance
    ADD CONSTRAINT venue_compliance_pkey PRIMARY KEY (id);


--
-- Name: venue_compliance venue_compliance_venue_id_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.venue_compliance
    ADD CONSTRAINT venue_compliance_venue_id_key UNIQUE (venue_id);


--
-- Name: venue_verification_audit venue_verification_audit_case_id_case_version_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.venue_verification_audit
    ADD CONSTRAINT venue_verification_audit_case_id_case_version_key UNIQUE (case_id, case_version);


--
-- Name: venue_verification_audit venue_verification_audit_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.venue_verification_audit
    ADD CONSTRAINT venue_verification_audit_pkey PRIMARY KEY (id);


--
-- Name: venue_verification_cases venue_verification_cases_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.venue_verification_cases
    ADD CONSTRAINT venue_verification_cases_pkey PRIMARY KEY (id);


--
-- Name: venues venues_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.venues
    ADD CONSTRAINT venues_pkey PRIMARY KEY (id);


--
-- Name: verification_cases verification_cases_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.verification_cases
    ADD CONSTRAINT verification_cases_pkey PRIMARY KEY (id);


--
-- Name: verification_documents verification_documents_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.verification_documents
    ADD CONSTRAINT verification_documents_pkey PRIMARY KEY (id);


--
-- Name: wishlists wishlists_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.wishlists
    ADD CONSTRAINT wishlists_pkey PRIMARY KEY (id);


--
-- Name: wishlists wishlists_user_id_event_id_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.wishlists
    ADD CONSTRAINT wishlists_user_id_event_id_key UNIQUE (user_id, event_id);


--
-- Name: idx_admin_audit_log_admin; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_admin_audit_log_admin ON public.admin_audit_log USING btree (admin_id, created_at DESC);


--
-- Name: idx_admin_audit_log_target; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_admin_audit_log_target ON public.admin_audit_log USING btree (target_user_id, created_at DESC);


--
-- Name: idx_ai_review_summaries_generated_at; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_ai_review_summaries_generated_at ON public.ai_review_summaries USING btree (generated_at);


--
-- Name: idx_audit_log_actor; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_audit_log_actor ON public.audit_log USING btree (actor_id, at DESC);


--
-- Name: idx_audit_log_entity; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_audit_log_entity ON public.audit_log USING btree (entity_type, entity_id, at DESC);


--
-- Name: idx_bank_accounts_account_hash; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_bank_accounts_account_hash ON public.bank_accounts USING btree (account_hash);


--
-- Name: idx_bank_accounts_organizer_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_bank_accounts_organizer_id ON public.bank_accounts USING btree (organizer_id);


--
-- Name: idx_booking_seats_show_seat_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_booking_seats_show_seat_id ON public.booking_seats USING btree (show_seat_id);


--
-- Name: idx_booking_zones_booking_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_booking_zones_booking_id ON public.booking_zones USING btree (booking_id);


--
-- Name: idx_bookings_show_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_bookings_show_id ON public.bookings USING btree (show_id);


--
-- Name: idx_bookings_user_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_bookings_user_id ON public.bookings USING btree (user_id);


--
-- Name: idx_dup_fingerprints_case; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_dup_fingerprints_case ON public.duplicate_fingerprints USING btree (case_id, case_type);


--
-- Name: idx_events_genre_trgm; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_events_genre_trgm ON public.events USING gin (genre public.gin_trgm_ops);


--
-- Name: idx_events_organizer_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_events_organizer_id ON public.events USING btree (organizer_id);


--
-- Name: idx_events_title_trgm; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_events_title_trgm ON public.events USING gin (title public.gin_trgm_ops);


--
-- Name: idx_listing_reports_queue; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_listing_reports_queue ON public.listing_reports USING btree (status, created_at);


--
-- Name: idx_listing_reviews_queue; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_listing_reviews_queue ON public.listing_reviews USING btree (status, created_at);


--
-- Name: idx_notifications_read_at; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_notifications_read_at ON public.notifications USING btree (read_at);


--
-- Name: idx_notifications_user_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_notifications_user_id ON public.notifications USING btree (user_id);


--
-- Name: idx_notifications_user_unread; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_notifications_user_unread ON public.notifications USING btree (user_id, created_at DESC) WHERE (read_at IS NULL);


--
-- Name: idx_organizer_profiles_business_type; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_organizer_profiles_business_type ON public.organizer_profiles USING btree (business_type);


--
-- Name: idx_organizer_profiles_user_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_organizer_profiles_user_id ON public.organizer_profiles USING btree (user_id);


--
-- Name: idx_organizer_profiles_user_legal_name; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX idx_organizer_profiles_user_legal_name ON public.organizer_profiles USING btree (user_id, legal_name);


--
-- Name: idx_organizer_profiles_verification_status; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_organizer_profiles_verification_status ON public.organizer_profiles USING btree (verification_status);


--
-- Name: idx_payment_orders_booking_created; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_payment_orders_booking_created ON public.payment_orders USING btree (booking_id, created_at DESC);


--
-- Name: idx_payment_orders_created_by; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_payment_orders_created_by ON public.payment_orders USING btree (created_by);


--
-- Name: idx_payments_booking_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_payments_booking_id ON public.payments USING btree (booking_id);


--
-- Name: idx_payments_payment_order_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_payments_payment_order_id ON public.payments USING btree (payment_order_id);


--
-- Name: idx_payments_transaction_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_payments_transaction_id ON public.payments USING btree (transaction_id);


--
-- Name: idx_refunds_booking_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_refunds_booking_id ON public.refunds USING btree (booking_id);


--
-- Name: idx_refunds_rzp_refund_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_refunds_rzp_refund_id ON public.refunds USING btree (razorpay_refund_id);


--
-- Name: idx_refunds_status; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_refunds_status ON public.refunds USING btree (status);


--
-- Name: idx_refunds_user_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_refunds_user_id ON public.refunds USING btree (user_id);


--
-- Name: idx_review_comments_parent; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_review_comments_parent ON public.review_comments USING btree (parent_comment_id);


--
-- Name: idx_review_comments_review_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_review_comments_review_id ON public.review_comments USING btree (review_id);


--
-- Name: idx_review_deletions_event_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_review_deletions_event_id ON public.review_deletions USING btree (event_id);


--
-- Name: idx_review_deletions_user_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_review_deletions_user_id ON public.review_deletions USING btree (user_id);


--
-- Name: idx_review_reports_review_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_review_reports_review_id ON public.review_reports USING btree (review_id);


--
-- Name: idx_review_reports_status; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_review_reports_status ON public.review_reports USING btree (status);


--
-- Name: idx_review_upvotes_review_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_review_upvotes_review_id ON public.review_upvotes USING btree (review_id);


--
-- Name: idx_review_versions_review_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_review_versions_review_id ON public.review_versions USING btree (review_id);


--
-- Name: idx_reviews_event_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_reviews_event_id ON public.reviews USING btree (event_id);


--
-- Name: idx_reviews_published_at; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_reviews_published_at ON public.reviews USING btree (published_at DESC);


--
-- Name: idx_reviews_scheduled_for; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_reviews_scheduled_for ON public.reviews USING btree (scheduled_for) WHERE (scheduled_for IS NOT NULL);


--
-- Name: idx_reviews_user_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_reviews_user_id ON public.reviews USING btree (user_id);


--
-- Name: idx_screens_venue_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_screens_venue_id ON public.screens USING btree (venue_id);


--
-- Name: idx_seats_screen_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_seats_screen_id ON public.seats USING btree (screen_id);


--
-- Name: idx_show_seats_locked_until; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_show_seats_locked_until ON public.show_seats USING btree (locked_until) WHERE (status = 'locked'::public.show_seat_status);


--
-- Name: idx_show_seats_show_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_show_seats_show_id ON public.show_seats USING btree (show_id);


--
-- Name: idx_show_seats_status; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_show_seats_status ON public.show_seats USING btree (show_id, status);


--
-- Name: idx_show_zones_show_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_show_zones_show_id ON public.show_zones USING btree (show_id);


--
-- Name: idx_shows_event_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_shows_event_id ON public.shows USING btree (event_id);


--
-- Name: idx_shows_screen_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_shows_screen_id ON public.shows USING btree (screen_id);


--
-- Name: idx_shows_start_time; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_shows_start_time ON public.shows USING btree (start_time);


--
-- Name: idx_support_messages_request_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_support_messages_request_id ON public.support_messages USING btree (request_id);


--
-- Name: idx_support_requests_status; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_support_requests_status ON public.support_requests USING btree (status);


--
-- Name: idx_support_requests_user_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_support_requests_user_id ON public.support_requests USING btree (user_id);


--
-- Name: idx_terms_acceptances_booking; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_terms_acceptances_booking ON public.terms_acceptances USING btree (booking_id);


--
-- Name: idx_terms_acceptances_user_show; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_terms_acceptances_user_show ON public.terms_acceptances USING btree (user_id, show_id);


--
-- Name: idx_tickets_booking_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_tickets_booking_id ON public.tickets USING btree (booking_id);


--
-- Name: idx_tickets_qr_code; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_tickets_qr_code ON public.tickets USING btree (qr_code_data);


--
-- Name: idx_tickets_user_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_tickets_user_id ON public.tickets USING btree (user_id);


--
-- Name: idx_user_roles_role_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_user_roles_role_id ON public.user_roles USING btree (role_id);


--
-- Name: idx_venue_cases_applicant; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_venue_cases_applicant ON public.venue_verification_cases USING btree (applicant_id, updated_at DESC);


--
-- Name: idx_venue_cases_queue; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_venue_cases_queue ON public.venue_verification_cases USING btree (status, created_at);


--
-- Name: idx_venue_compliance_expiry; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_venue_compliance_expiry ON public.venue_compliance USING btree (licence_valid_to);


--
-- Name: idx_venues_city_trgm; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_venues_city_trgm ON public.venues USING gin (city public.gin_trgm_ops);


--
-- Name: idx_venues_name_trgm; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_venues_name_trgm ON public.venues USING gin (name public.gin_trgm_ops);


--
-- Name: idx_verification_cases_applicant; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_verification_cases_applicant ON public.verification_cases USING btree (applicant_user_id, created_at DESC);


--
-- Name: idx_verification_cases_claim; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_verification_cases_claim ON public.verification_cases USING btree (claim_expires_at) WHERE ((status)::text = 'IN_REVIEW'::text);


--
-- Name: idx_verification_cases_queue; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_verification_cases_queue ON public.verification_cases USING btree (status, submitted_at);


--
-- Name: idx_verification_docs_case; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_verification_docs_case ON public.verification_documents USING btree (case_id, case_type);


--
-- Name: idx_verification_docs_case_doc; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_verification_docs_case_doc ON public.verification_documents USING btree (case_id, doc_type, version DESC);


--
-- Name: idx_verification_docs_doc_type; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_verification_docs_doc_type ON public.verification_documents USING btree (doc_type);


--
-- Name: idx_verification_docs_review_status; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_verification_docs_review_status ON public.verification_documents USING btree (review_status);


--
-- Name: idx_verification_docs_reviewed_by; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_verification_docs_reviewed_by ON public.verification_documents USING btree (reviewed_by);


--
-- Name: idx_verification_docs_uploaded_by; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_verification_docs_uploaded_by ON public.verification_documents USING btree (uploaded_by);


--
-- Name: idx_wishlists_user; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_wishlists_user ON public.wishlists USING btree (user_id, created_at DESC);


--
-- Name: uq_one_unresolved_payment_order_per_booking; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX uq_one_unresolved_payment_order_per_booking ON public.payment_orders USING btree (booking_id) WHERE ((status)::text = ANY ((ARRAY['creating'::character varying, 'created'::character varying, 'verification_pending'::character varying, 'authorized'::character varying, 'successful_needs_review'::character varying])::text[]));


--
-- Name: uq_payment_orders_razorpay_order_id; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX uq_payment_orders_razorpay_order_id ON public.payment_orders USING btree (razorpay_order_id);


--
-- Name: uq_payments_razorpay_payment_id; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX uq_payments_razorpay_payment_id ON public.payments USING btree (razorpay_payment_id) WHERE (razorpay_payment_id IS NOT NULL);


--
-- Name: uq_verification_cases_active_subject; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX uq_verification_cases_active_subject ON public.verification_cases USING btree (case_type, subject_id) WHERE ((status)::text = ANY ((ARRAY['SUBMITTED'::character varying, 'IN_REVIEW'::character varying, 'CHANGES_REQUESTED'::character varying])::text[]));


--
-- Name: audit_log trg_audit_log_no_update_delete; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER trg_audit_log_no_update_delete BEFORE DELETE OR UPDATE ON public.audit_log FOR EACH ROW EXECUTE FUNCTION public.reject_audit_log_mutation();


--
-- Name: bank_accounts trg_bank_accounts_updated_at; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER trg_bank_accounts_updated_at BEFORE UPDATE ON public.bank_accounts FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();


--
-- Name: bookings trg_bookings_updated_at; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER trg_bookings_updated_at BEFORE UPDATE ON public.bookings FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();


--
-- Name: events trg_events_updated_at; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER trg_events_updated_at BEFORE UPDATE ON public.events FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();


--
-- Name: organizer_profiles trg_organizer_profiles_updated_at; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER trg_organizer_profiles_updated_at BEFORE UPDATE ON public.organizer_profiles FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();


--
-- Name: payment_orders trg_payment_orders_updated_at; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER trg_payment_orders_updated_at BEFORE UPDATE ON public.payment_orders FOR EACH ROW EXECUTE FUNCTION public.set_payment_order_updated_at();


--
-- Name: shows trg_shows_updated_at; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER trg_shows_updated_at BEFORE UPDATE ON public.shows FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();


--
-- Name: trust_tier_rules trg_trust_tier_rules_updated_at; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER trg_trust_tier_rules_updated_at BEFORE UPDATE ON public.trust_tier_rules FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();


--
-- Name: users trg_users_updated_at; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER trg_users_updated_at BEFORE UPDATE ON public.users FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();


--
-- Name: venues trg_venues_updated_at; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER trg_venues_updated_at BEFORE UPDATE ON public.venues FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();


--
-- Name: venue_verification_audit venue_audit_no_delete; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER venue_audit_no_delete BEFORE DELETE ON public.venue_verification_audit FOR EACH ROW EXECUTE FUNCTION public.prevent_venue_audit_mutation();


--
-- Name: venue_verification_audit venue_audit_no_update; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER venue_audit_no_update BEFORE UPDATE ON public.venue_verification_audit FOR EACH ROW EXECUTE FUNCTION public.prevent_venue_audit_mutation();


--
-- Name: admin_audit_log admin_audit_log_admin_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.admin_audit_log
    ADD CONSTRAINT admin_audit_log_admin_id_fkey FOREIGN KEY (admin_id) REFERENCES public.users(id) ON DELETE SET NULL;


--
-- Name: admin_audit_log admin_audit_log_target_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.admin_audit_log
    ADD CONSTRAINT admin_audit_log_target_user_id_fkey FOREIGN KEY (target_user_id) REFERENCES public.users(id) ON DELETE SET NULL;


--
-- Name: ai_review_summaries ai_review_summaries_event_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.ai_review_summaries
    ADD CONSTRAINT ai_review_summaries_event_id_fkey FOREIGN KEY (event_id) REFERENCES public.events(id) ON DELETE CASCADE;


--
-- Name: audit_log audit_log_actor_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.audit_log
    ADD CONSTRAINT audit_log_actor_id_fkey FOREIGN KEY (actor_id) REFERENCES public.users(id) ON DELETE SET NULL;


--
-- Name: bank_accounts bank_accounts_organizer_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.bank_accounts
    ADD CONSTRAINT bank_accounts_organizer_id_fkey FOREIGN KEY (organizer_id) REFERENCES public.organizer_profiles(id) ON DELETE CASCADE;


--
-- Name: booking_seats booking_seats_booking_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.booking_seats
    ADD CONSTRAINT booking_seats_booking_id_fkey FOREIGN KEY (booking_id) REFERENCES public.bookings(id) ON DELETE CASCADE;


--
-- Name: booking_seats booking_seats_show_seat_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.booking_seats
    ADD CONSTRAINT booking_seats_show_seat_id_fkey FOREIGN KEY (show_seat_id) REFERENCES public.show_seats(id) ON DELETE RESTRICT;


--
-- Name: booking_zones booking_zones_booking_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.booking_zones
    ADD CONSTRAINT booking_zones_booking_id_fkey FOREIGN KEY (booking_id) REFERENCES public.bookings(id) ON DELETE CASCADE;


--
-- Name: booking_zones booking_zones_zone_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.booking_zones
    ADD CONSTRAINT booking_zones_zone_id_fkey FOREIGN KEY (zone_id) REFERENCES public.show_zones(id) ON DELETE RESTRICT;


--
-- Name: bookings bookings_show_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.bookings
    ADD CONSTRAINT bookings_show_id_fkey FOREIGN KEY (show_id) REFERENCES public.shows(id) ON DELETE RESTRICT;


--
-- Name: bookings bookings_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.bookings
    ADD CONSTRAINT bookings_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(id) ON DELETE RESTRICT;


--
-- Name: checklist_templates checklist_templates_updated_by_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.checklist_templates
    ADD CONSTRAINT checklist_templates_updated_by_fkey FOREIGN KEY (updated_by) REFERENCES public.users(id) ON DELETE SET NULL;


--
-- Name: events events_organizer_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.events
    ADD CONSTRAINT events_organizer_id_fkey FOREIGN KEY (organizer_id) REFERENCES public.organizer_profiles(id) ON DELETE RESTRICT;


--
-- Name: listing_reports listing_reports_event_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.listing_reports
    ADD CONSTRAINT listing_reports_event_id_fkey FOREIGN KEY (event_id) REFERENCES public.events(id) ON DELETE RESTRICT;


--
-- Name: listing_reports listing_reports_reported_by_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.listing_reports
    ADD CONSTRAINT listing_reports_reported_by_fkey FOREIGN KEY (reported_by) REFERENCES public.users(id) ON DELETE RESTRICT;


--
-- Name: listing_reviews listing_reviews_event_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.listing_reviews
    ADD CONSTRAINT listing_reviews_event_id_fkey FOREIGN KEY (event_id) REFERENCES public.events(id) ON DELETE RESTRICT;


--
-- Name: listing_reviews listing_reviews_reviewer_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.listing_reviews
    ADD CONSTRAINT listing_reviews_reviewer_id_fkey FOREIGN KEY (reviewer_id) REFERENCES public.users(id) ON DELETE SET NULL;


--
-- Name: listing_reviews listing_reviews_show_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.listing_reviews
    ADD CONSTRAINT listing_reviews_show_id_fkey FOREIGN KEY (show_id) REFERENCES public.shows(id) ON DELETE RESTRICT;


--
-- Name: notifications notifications_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.notifications
    ADD CONSTRAINT notifications_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(id) ON DELETE CASCADE;


--
-- Name: organizer_profiles organizer_profiles_reviewer_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.organizer_profiles
    ADD CONSTRAINT organizer_profiles_reviewer_id_fkey FOREIGN KEY (reviewer_id) REFERENCES public.users(id) ON DELETE SET NULL;


--
-- Name: organizer_profiles organizer_profiles_trust_tier_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.organizer_profiles
    ADD CONSTRAINT organizer_profiles_trust_tier_fkey FOREIGN KEY (trust_tier) REFERENCES public.trust_tier_rules(tier) ON DELETE RESTRICT;


--
-- Name: organizer_profiles organizer_profiles_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.organizer_profiles
    ADD CONSTRAINT organizer_profiles_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(id) ON DELETE CASCADE;


--
-- Name: payment_orders payment_orders_booking_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.payment_orders
    ADD CONSTRAINT payment_orders_booking_id_fkey FOREIGN KEY (booking_id) REFERENCES public.bookings(id) ON DELETE RESTRICT;


--
-- Name: payment_orders payment_orders_created_by_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.payment_orders
    ADD CONSTRAINT payment_orders_created_by_fkey FOREIGN KEY (created_by) REFERENCES public.users(id) ON DELETE RESTRICT;


--
-- Name: payments payments_booking_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.payments
    ADD CONSTRAINT payments_booking_id_fkey FOREIGN KEY (booking_id) REFERENCES public.bookings(id) ON DELETE RESTRICT;


--
-- Name: payments payments_payment_order_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.payments
    ADD CONSTRAINT payments_payment_order_id_fkey FOREIGN KEY (payment_order_id) REFERENCES public.payment_orders(id) ON DELETE RESTRICT;


--
-- Name: receipts receipts_payment_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.receipts
    ADD CONSTRAINT receipts_payment_id_fkey FOREIGN KEY (payment_id) REFERENCES public.payments(id) ON DELETE RESTRICT;


--
-- Name: refunds refunds_booking_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.refunds
    ADD CONSTRAINT refunds_booking_id_fkey FOREIGN KEY (booking_id) REFERENCES public.bookings(id) ON DELETE CASCADE;


--
-- Name: refunds refunds_payment_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.refunds
    ADD CONSTRAINT refunds_payment_id_fkey FOREIGN KEY (payment_id) REFERENCES public.payments(id) ON DELETE SET NULL;


--
-- Name: refunds refunds_retried_by_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.refunds
    ADD CONSTRAINT refunds_retried_by_fkey FOREIGN KEY (retried_by) REFERENCES public.users(id) ON DELETE SET NULL;


--
-- Name: refunds refunds_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.refunds
    ADD CONSTRAINT refunds_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(id) ON DELETE CASCADE;


--
-- Name: review_comments review_comments_parent_comment_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.review_comments
    ADD CONSTRAINT review_comments_parent_comment_id_fkey FOREIGN KEY (parent_comment_id) REFERENCES public.review_comments(id) ON DELETE CASCADE;


--
-- Name: review_comments review_comments_review_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.review_comments
    ADD CONSTRAINT review_comments_review_id_fkey FOREIGN KEY (review_id) REFERENCES public.reviews(id) ON DELETE CASCADE;


--
-- Name: review_comments review_comments_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.review_comments
    ADD CONSTRAINT review_comments_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(id) ON DELETE CASCADE;


--
-- Name: review_reports review_reports_reporter_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.review_reports
    ADD CONSTRAINT review_reports_reporter_id_fkey FOREIGN KEY (reporter_id) REFERENCES public.users(id) ON DELETE CASCADE;


--
-- Name: review_reports review_reports_resolved_by_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.review_reports
    ADD CONSTRAINT review_reports_resolved_by_fkey FOREIGN KEY (resolved_by) REFERENCES public.users(id) ON DELETE SET NULL;


--
-- Name: review_reports review_reports_review_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.review_reports
    ADD CONSTRAINT review_reports_review_id_fkey FOREIGN KEY (review_id) REFERENCES public.reviews(id) ON DELETE CASCADE;


--
-- Name: review_upvotes review_upvotes_review_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.review_upvotes
    ADD CONSTRAINT review_upvotes_review_id_fkey FOREIGN KEY (review_id) REFERENCES public.reviews(id) ON DELETE CASCADE;


--
-- Name: review_upvotes review_upvotes_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.review_upvotes
    ADD CONSTRAINT review_upvotes_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(id) ON DELETE CASCADE;


--
-- Name: review_versions review_versions_review_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.review_versions
    ADD CONSTRAINT review_versions_review_id_fkey FOREIGN KEY (review_id) REFERENCES public.reviews(id) ON DELETE CASCADE;


--
-- Name: reviews reviews_event_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.reviews
    ADD CONSTRAINT reviews_event_id_fkey FOREIGN KEY (event_id) REFERENCES public.events(id) ON DELETE CASCADE;


--
-- Name: reviews reviews_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.reviews
    ADD CONSTRAINT reviews_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(id) ON DELETE CASCADE;


--
-- Name: screens screens_venue_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.screens
    ADD CONSTRAINT screens_venue_id_fkey FOREIGN KEY (venue_id) REFERENCES public.venues(id) ON DELETE CASCADE;


--
-- Name: seats seats_screen_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.seats
    ADD CONSTRAINT seats_screen_id_fkey FOREIGN KEY (screen_id) REFERENCES public.screens(id) ON DELETE CASCADE;


--
-- Name: show_seats show_seats_locked_by_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.show_seats
    ADD CONSTRAINT show_seats_locked_by_fkey FOREIGN KEY (locked_by) REFERENCES public.users(id) ON DELETE SET NULL;


--
-- Name: show_seats show_seats_seat_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.show_seats
    ADD CONSTRAINT show_seats_seat_id_fkey FOREIGN KEY (seat_id) REFERENCES public.seats(id) ON DELETE RESTRICT;


--
-- Name: show_seats show_seats_show_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.show_seats
    ADD CONSTRAINT show_seats_show_id_fkey FOREIGN KEY (show_id) REFERENCES public.shows(id) ON DELETE CASCADE;


--
-- Name: show_zones show_zones_show_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.show_zones
    ADD CONSTRAINT show_zones_show_id_fkey FOREIGN KEY (show_id) REFERENCES public.shows(id) ON DELETE CASCADE;


--
-- Name: shows shows_cancellation_policy_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.shows
    ADD CONSTRAINT shows_cancellation_policy_id_fkey FOREIGN KEY (cancellation_policy_id) REFERENCES public.cancellation_policies(id) ON DELETE SET NULL;


--
-- Name: shows shows_event_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.shows
    ADD CONSTRAINT shows_event_id_fkey FOREIGN KEY (event_id) REFERENCES public.events(id) ON DELETE RESTRICT;


--
-- Name: shows shows_screen_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.shows
    ADD CONSTRAINT shows_screen_id_fkey FOREIGN KEY (screen_id) REFERENCES public.screens(id) ON DELETE RESTRICT;


--
-- Name: support_messages support_messages_request_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.support_messages
    ADD CONSTRAINT support_messages_request_id_fkey FOREIGN KEY (request_id) REFERENCES public.support_requests(id) ON DELETE CASCADE;


--
-- Name: support_messages support_messages_sender_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.support_messages
    ADD CONSTRAINT support_messages_sender_id_fkey FOREIGN KEY (sender_id) REFERENCES public.users(id) ON DELETE CASCADE;


--
-- Name: support_requests support_requests_booking_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.support_requests
    ADD CONSTRAINT support_requests_booking_id_fkey FOREIGN KEY (booking_id) REFERENCES public.bookings(id) ON DELETE SET NULL;


--
-- Name: support_requests support_requests_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.support_requests
    ADD CONSTRAINT support_requests_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(id) ON DELETE CASCADE;


--
-- Name: terms_acceptances terms_acceptances_booking_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.terms_acceptances
    ADD CONSTRAINT terms_acceptances_booking_id_fkey FOREIGN KEY (booking_id) REFERENCES public.bookings(id) ON DELETE CASCADE;


--
-- Name: terms_acceptances terms_acceptances_show_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.terms_acceptances
    ADD CONSTRAINT terms_acceptances_show_id_fkey FOREIGN KEY (show_id) REFERENCES public.shows(id) ON DELETE CASCADE;


--
-- Name: terms_acceptances terms_acceptances_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.terms_acceptances
    ADD CONSTRAINT terms_acceptances_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(id) ON DELETE CASCADE;


--
-- Name: tickets tickets_booking_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.tickets
    ADD CONSTRAINT tickets_booking_id_fkey FOREIGN KEY (booking_id) REFERENCES public.bookings(id) ON DELETE CASCADE;


--
-- Name: tickets tickets_show_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.tickets
    ADD CONSTRAINT tickets_show_id_fkey FOREIGN KEY (show_id) REFERENCES public.shows(id) ON DELETE CASCADE;


--
-- Name: tickets tickets_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.tickets
    ADD CONSTRAINT tickets_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(id) ON DELETE CASCADE;


--
-- Name: user_roles user_roles_role_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.user_roles
    ADD CONSTRAINT user_roles_role_id_fkey FOREIGN KEY (role_id) REFERENCES public.roles(id) ON DELETE RESTRICT;


--
-- Name: user_roles user_roles_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.user_roles
    ADD CONSTRAINT user_roles_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(id) ON DELETE CASCADE;


--
-- Name: venue_case_documents venue_case_documents_case_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.venue_case_documents
    ADD CONSTRAINT venue_case_documents_case_id_fkey FOREIGN KEY (case_id) REFERENCES public.venue_verification_cases(id) ON DELETE RESTRICT;


--
-- Name: venue_case_documents venue_case_documents_uploaded_by_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.venue_case_documents
    ADD CONSTRAINT venue_case_documents_uploaded_by_fkey FOREIGN KEY (uploaded_by) REFERENCES public.users(id) ON DELETE RESTRICT;


--
-- Name: venue_compliance venue_compliance_applicant_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.venue_compliance
    ADD CONSTRAINT venue_compliance_applicant_user_id_fkey FOREIGN KEY (applicant_user_id) REFERENCES public.users(id) ON DELETE RESTRICT;


--
-- Name: venue_compliance venue_compliance_venue_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.venue_compliance
    ADD CONSTRAINT venue_compliance_venue_id_fkey FOREIGN KEY (venue_id) REFERENCES public.venues(id) ON DELETE CASCADE;


--
-- Name: venue_verification_audit venue_verification_audit_actor_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.venue_verification_audit
    ADD CONSTRAINT venue_verification_audit_actor_id_fkey FOREIGN KEY (actor_id) REFERENCES public.users(id) ON DELETE RESTRICT;


--
-- Name: venue_verification_audit venue_verification_audit_case_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.venue_verification_audit
    ADD CONSTRAINT venue_verification_audit_case_id_fkey FOREIGN KEY (case_id) REFERENCES public.venue_verification_cases(id) ON DELETE RESTRICT;


--
-- Name: venue_verification_cases venue_verification_cases_applicant_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.venue_verification_cases
    ADD CONSTRAINT venue_verification_cases_applicant_id_fkey FOREIGN KEY (applicant_id) REFERENCES public.users(id) ON DELETE RESTRICT;


--
-- Name: venue_verification_cases venue_verification_cases_reviewer_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.venue_verification_cases
    ADD CONSTRAINT venue_verification_cases_reviewer_id_fkey FOREIGN KEY (reviewer_id) REFERENCES public.users(id) ON DELETE RESTRICT;


--
-- Name: venue_verification_cases venue_verification_cases_venue_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.venue_verification_cases
    ADD CONSTRAINT venue_verification_cases_venue_id_fkey FOREIGN KEY (venue_id) REFERENCES public.venues(id) ON DELETE RESTRICT;


--
-- Name: verification_cases verification_cases_applicant_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.verification_cases
    ADD CONSTRAINT verification_cases_applicant_user_id_fkey FOREIGN KEY (applicant_user_id) REFERENCES public.users(id) ON DELETE RESTRICT;


--
-- Name: verification_cases verification_cases_claimed_by_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.verification_cases
    ADD CONSTRAINT verification_cases_claimed_by_fkey FOREIGN KEY (claimed_by) REFERENCES public.users(id) ON DELETE SET NULL;


--
-- Name: verification_cases verification_cases_decided_by_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.verification_cases
    ADD CONSTRAINT verification_cases_decided_by_fkey FOREIGN KEY (decided_by) REFERENCES public.users(id) ON DELETE SET NULL;


--
-- Name: verification_documents verification_documents_reviewed_by_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.verification_documents
    ADD CONSTRAINT verification_documents_reviewed_by_fkey FOREIGN KEY (reviewed_by) REFERENCES public.users(id) ON DELETE SET NULL;


--
-- Name: verification_documents verification_documents_uploaded_by_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.verification_documents
    ADD CONSTRAINT verification_documents_uploaded_by_fkey FOREIGN KEY (uploaded_by) REFERENCES public.users(id) ON DELETE SET NULL;


--
-- Name: wishlists wishlists_event_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.wishlists
    ADD CONSTRAINT wishlists_event_id_fkey FOREIGN KEY (event_id) REFERENCES public.events(id) ON DELETE CASCADE;


--
-- Name: wishlists wishlists_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.wishlists
    ADD CONSTRAINT wishlists_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(id) ON DELETE CASCADE;


--
-- Name: admin_audit_log; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.admin_audit_log ENABLE ROW LEVEL SECURITY;

--
-- Name: audit_log; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.audit_log ENABLE ROW LEVEL SECURITY;

--
-- Name: bank_accounts; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.bank_accounts ENABLE ROW LEVEL SECURITY;

--
-- Name: booking_seats; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.booking_seats ENABLE ROW LEVEL SECURITY;

--
-- Name: bookings; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.bookings ENABLE ROW LEVEL SECURITY;

--
-- Name: cancellation_policies; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.cancellation_policies ENABLE ROW LEVEL SECURITY;

--
-- Name: checklist_templates; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.checklist_templates ENABLE ROW LEVEL SECURITY;

--
-- Name: duplicate_fingerprints; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.duplicate_fingerprints ENABLE ROW LEVEL SECURITY;

--
-- Name: events; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.events ENABLE ROW LEVEL SECURITY;

--
-- Name: listing_reports; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.listing_reports ENABLE ROW LEVEL SECURITY;

--
-- Name: listing_reviews; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.listing_reviews ENABLE ROW LEVEL SECURITY;

--
-- Name: notifications; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.notifications ENABLE ROW LEVEL SECURITY;

--
-- Name: organizer_profiles; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.organizer_profiles ENABLE ROW LEVEL SECURITY;

--
-- Name: payment_orders; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.payment_orders ENABLE ROW LEVEL SECURITY;

--
-- Name: payments; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.payments ENABLE ROW LEVEL SECURITY;

--
-- Name: receipts; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.receipts ENABLE ROW LEVEL SECURITY;

--
-- Name: refunds; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.refunds ENABLE ROW LEVEL SECURITY;

--
-- Name: review_comments; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.review_comments ENABLE ROW LEVEL SECURITY;

--
-- Name: review_deletions; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.review_deletions ENABLE ROW LEVEL SECURITY;

--
-- Name: review_reports; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.review_reports ENABLE ROW LEVEL SECURITY;

--
-- Name: review_upvotes; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.review_upvotes ENABLE ROW LEVEL SECURITY;

--
-- Name: review_versions; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.review_versions ENABLE ROW LEVEL SECURITY;

--
-- Name: reviews; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.reviews ENABLE ROW LEVEL SECURITY;

--
-- Name: screens; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.screens ENABLE ROW LEVEL SECURITY;

--
-- Name: seats; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.seats ENABLE ROW LEVEL SECURITY;

--
-- Name: show_seats; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.show_seats ENABLE ROW LEVEL SECURITY;

--
-- Name: shows; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.shows ENABLE ROW LEVEL SECURITY;

--
-- Name: support_messages; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.support_messages ENABLE ROW LEVEL SECURITY;

--
-- Name: support_requests; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.support_requests ENABLE ROW LEVEL SECURITY;

--
-- Name: trust_tier_rules; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.trust_tier_rules ENABLE ROW LEVEL SECURITY;

--
-- Name: users; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.users ENABLE ROW LEVEL SECURITY;

--
-- Name: venue_case_documents; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.venue_case_documents ENABLE ROW LEVEL SECURITY;

--
-- Name: venue_compliance; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.venue_compliance ENABLE ROW LEVEL SECURITY;

--
-- Name: venue_verification_audit; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.venue_verification_audit ENABLE ROW LEVEL SECURITY;

--
-- Name: venue_verification_cases; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.venue_verification_cases ENABLE ROW LEVEL SECURITY;

--
-- Name: venues; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.venues ENABLE ROW LEVEL SECURITY;

--
-- Name: verification_cases; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.verification_cases ENABLE ROW LEVEL SECURITY;

--
-- Name: verification_documents; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.verification_documents ENABLE ROW LEVEL SECURITY;

--
-- Name: wishlists; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.wishlists ENABLE ROW LEVEL SECURITY;

--
-- PostgreSQL database dump complete
--

\unrestrict 91SaOmLBBahfsveXUeDdURvUusAfa32HcZEcnw5MBlx5QgVdwnFIGgS12UNji3g

