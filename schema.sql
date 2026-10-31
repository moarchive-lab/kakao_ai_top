-- Run in Supabase Dashboard > SQL Editor. Safe to run again after schema updates.

CREATE TABLE IF NOT EXISTS public.chatbot_sessions (
    user_id TEXT PRIMARY KEY,
    history JSONB NOT NULL DEFAULT '[]'::jsonb,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS chatbot_sessions_updated_at_idx
    ON public.chatbot_sessions (updated_at DESC);

-- Keep app data out of Supabase's public Data API. The Vercel server uses the
-- server-side Postgres connection string, not an anon client key.
ALTER TABLE public.chatbot_sessions ENABLE ROW LEVEL SECURITY;
