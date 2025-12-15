create table public.assessments (
  id uuid not null default gen_random_uuid (),
  original_filename text null,
  pdf_path text null,
  options jsonb null,
  result jsonb null,
  google_form jsonb null,
  created_at timestamp with time zone null default now(),
  constraint assessments_pkey primary key (id)
) TABLESPACE pg_default;


create table public.assessments (
  id uuid not null default gen_random_uuid (),
  original_filename text null,
  pdf_path text null,
  options jsonb null,
  result jsonb null,
  google_form jsonb null,
  created_at timestamp with time zone null default now(),
  constraint assessments_pkey primary key (id)
) TABLESPACE pg_default;


create table public.assessments (
  id uuid not null default gen_random_uuid (),
  original_filename text null,
  pdf_path text null,
  options jsonb null,
  result jsonb null,
  google_form jsonb null,
  created_at timestamp with time zone null default now(),
  constraint assessments_pkey primary key (id)
) TABLESPACE pg_default;



create table public.assessments (
  id uuid not null default gen_random_uuid (),
  original_filename text null,
  pdf_path text null,
  options jsonb null,
  result jsonb null,
  google_form jsonb null,
  created_at timestamp with time zone null default now(),
  constraint assessments_pkey primary key (id)
) TABLESPACE pg_default;