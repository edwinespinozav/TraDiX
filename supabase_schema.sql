-- XStock · esquema de usuarios, invitaciones y uso
-- Pega todo este archivo en Supabase → SQL Editor → New query → Run.

create table if not exists public.profiles (
  email          text primary key,
  name           text,
  role           text not null default 'user',      -- 'admin' | 'user'
  status         text not null default 'active',    -- 'active' | 'suspended' | 'deleted'
  plan           text not null default 'beta',      -- base para suscripciones futuras
  ai_quota       integer not null default 10,
  ai_used        integer not null default 0,
  invite_code    text,
  auth_provider  text,
  created_at     timestamptz default now(),
  last_login     timestamptz,
  login_count    integer not null default 0,
  notes          text,
  password_hash  text
);
alter table public.profiles add column if not exists password_hash text;

create table if not exists public.invitations (
  code          text primary key,
  email         text,                 -- opcional: invitación solo para ese correo
  ai_quota      integer not null default 10,
  max_uses      integer not null default 1,
  uses          integer not null default 0,
  expires_at    timestamptz,
  created_by    text,
  created_at    timestamptz default now(),
  note          text,
  revoked       boolean not null default false,
  inviter_name  text
);

create table if not exists public.usage_events (
  id      bigint generated always as identity primary key,
  email   text,
  kind    text,                         -- 'login' | 'signup' | 'analysis' | 'scan' | 'ai_report'
  detail  text,
  at      timestamptz default now()
);
create index if not exists usage_events_email_at on public.usage_events (email, at desc);
create index if not exists usage_events_at on public.usage_events (at desc);

create table if not exists public.watchlist (
  email   text not null,
  ticker  text not null,
  data    jsonb,
  primary key (email, ticker)
);

-- Seguridad: solo el servidor (clave service_role guardada en los Secrets de Streamlit) accede a estas tablas.
alter table public.profiles     enable row level security;
alter table public.invitations  enable row level security;
alter table public.usage_events enable row level security;
alter table public.watchlist    enable row level security;

-- Perfil de trader y ajustes técnicos (onboarding)
alter table public.profiles add column if not exists trader_profile     text;   -- day | swing | position | fundamental | crypto
alter table public.profiles add column if not exists technical_settings text;   -- JSON con medias, RSI, MACD, ADX, Bollinger, Fibonacci
alter table public.profiles add column if not exists default_tf         text;   -- temporalidad por defecto (mínimo 30m)
