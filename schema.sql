-- Run once in Supabase Dashboard > SQL Editor before deploying the Vercel app.
CREATE TABLE IF NOT EXISTS public.chatbot_sessions (
    user_id TEXT PRIMARY KEY,
    history JSONB NOT NULL DEFAULT '[]'::jsonb,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS chatbot_sessions_updated_at_idx
    ON public.chatbot_sessions (updated_at DESC);
