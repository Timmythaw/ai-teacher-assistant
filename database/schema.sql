create table public.assessments (
  id uuid not null default gen_random_uuid (),
  original_filename text null,
  pdf_path text null,
  options jsonb null,
  result jsonb null,
  google_form jsonb null,
  created_at timestamp with time zone null default now(),
  user_id text null,
  constraint assessments_pkey primary key (id),
  constraint assessments_user_id_fkey foreign KEY (user_id) references users (id) on delete CASCADE
) TABLESPACE pg_default;

create index IF not exists idx_assessments_user_id on public.assessments using btree (user_id) TABLESPACE pg_default;




create table public.assessments (
  id uuid not null default gen_random_uuid (),
  original_filename text null,
  pdf_path text null,
  options jsonb null,
  result jsonb null,
  google_form jsonb null,
  created_at timestamp with time zone null default now(),
  user_id text null,
  constraint assessments_pkey primary key (id),
  constraint assessments_user_id_fkey foreign KEY (user_id) references users (id) on delete CASCADE
) TABLESPACE pg_default;

create index IF not exists idx_assessments_user_id on public.assessments using btree (user_id) TABLESPACE pg_default;



create table public.assessments (
  id uuid not null default gen_random_uuid (),
  original_filename text null,
  pdf_path text null,
  options jsonb null,
  result jsonb null,
  google_form jsonb null,
  created_at timestamp with time zone null default now(),
  user_id text null,
  constraint assessments_pkey primary key (id),
  constraint assessments_user_id_fkey foreign KEY (user_id) references users (id) on delete CASCADE
) TABLESPACE pg_default;

create index IF not exists idx_assessments_user_id on public.assessments using btree (user_id) TABLESPACE pg_default;



create table public.assessments (
  id uuid not null default gen_random_uuid (),
  original_filename text null,
  pdf_path text null,
  options jsonb null,
  result jsonb null,
  google_form jsonb null,
  created_at timestamp with time zone null default now(),
  user_id text null,
  constraint assessments_pkey primary key (id),
  constraint assessments_user_id_fkey foreign KEY (user_id) references users (id) on delete CASCADE
) TABLESPACE pg_default;

create index IF not exists idx_assessments_user_id on public.assessments using btree (user_id) TABLESPACE pg_default;



create table public.assessments (
  id uuid not null default gen_random_uuid (),
  original_filename text null,
  pdf_path text null,
  options jsonb null,
  result jsonb null,
  google_form jsonb null,
  created_at timestamp with time zone null default now(),
  user_id text null,
  constraint assessments_pkey primary key (id),
  constraint assessments_user_id_fkey foreign KEY (user_id) references users (id) on delete CASCADE
) TABLESPACE pg_default;

create index IF not exists idx_assessments_user_id on public.assessments using btree (user_id) TABLESPACE pg_default;