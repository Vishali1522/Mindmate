-- MindMate Supabase schema
-- Run this once in Supabase Dashboard -> SQL Editor.
-- This app uses a server-side Supabase key from Streamlit Secrets.
-- Keep the key PRIVATE and never commit it to GitHub.

create table if not exists public.users (
    mindmate_id text primary key,
    name text not null,
    age integer,
    class_name text,
    subjects text,
    password_hash text not null,
    recovery_hash text not null,
    theme text default 'System',
    created_at timestamptz not null default now()
);

create table if not exists public.checkins (
    id text primary key,
    mindmate_id text not null references public.users(mindmate_id) on delete cascade,
    created_at timestamptz not null default now(),
    study_pressure integer,
    marks_pressure integer,
    family_pressure integer,
    peer_pressure integer,
    workload_pressure integer,
    free_time integer,
    sleep integer,
    stress_score double precision,
    category text,
    detected_factors text,
    feeling_text text
);

create table if not exists public.todos (
    id text primary key,
    mindmate_id text not null references public.users(mindmate_id) on delete cascade,
    task text not null,
    done integer default 0,
    created_at timestamptz not null default now()
);

create table if not exists public.timetables (
    id text primary key,
    mindmate_id text not null references public.users(mindmate_id) on delete cascade,
    title text not null,
    schedule_json text not null,
    created_at timestamptz not null default now()
);

create index if not exists idx_checkins_mindmate_id on public.checkins(mindmate_id);
create index if not exists idx_todos_mindmate_id on public.todos(mindmate_id);
create index if not exists idx_timetables_mindmate_id on public.timetables(mindmate_id);

-- For this school-project architecture, the Streamlit server uses the
-- Supabase server-side key and filters every query by mindmate_id.
-- Do not expose the server-side key in the browser or GitHub.
