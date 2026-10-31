"""Supabase Postgres memory for short-lived Vercel functions."""

import json
import os

import psycopg
from psycopg.types.json import Jsonb


def _connect() -> psycopg.Connection:
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        raise RuntimeError("DATABASE_URL is not configured")
    return psycopg.connect(
        database_url,
        connect_timeout=1,
        prepare_threshold=0,
        sslmode="require",
    )


def get_history(user_id: str) -> list[dict[str, str]]:
    with _connect() as connection:
        row = connection.execute(
            "SELECT history FROM public.chatbot_sessions WHERE user_id = %s",
            (user_id,),
        ).fetchone()
    if not row:
        return []
    history = row[0]
    return json.loads(history) if isinstance(history, str) else history


def save_turn(
    user_id: str,
    history: list[dict[str, str]],
    user_text: str,
    answer: str,
) -> None:
    additions = []
    if user_text:
        additions.append({"role": "user", "content": user_text})
    additions.append({"role": "assistant", "content": answer})
    updated_history = [*history, *additions][-12:]
    with _connect() as connection:
        connection.execute(
            """
            INSERT INTO public.chatbot_sessions (user_id, history, updated_at)
            VALUES (%s, %s, NOW())
            ON CONFLICT (user_id) DO UPDATE
            SET history = EXCLUDED.history, updated_at = NOW()
            """,
            (user_id, Jsonb(updated_history)),
        )


def clear_user_data(user_id: str) -> None:
    with _connect() as connection:
        connection.execute("DELETE FROM public.chatbot_sessions WHERE user_id = %s", (user_id,))
        connection.execute("DELETE FROM public.mission_evidence WHERE user_id = %s", (user_id,))


def clear_history(user_id: str) -> None:
    with _connect() as connection:
        connection.execute("DELETE FROM public.chatbot_sessions WHERE user_id = %s", (user_id,))


def check_database() -> bool:
    with _connect() as connection:
        connection.execute("SELECT 1 FROM public.chatbot_sessions LIMIT 1").fetchone()
        connection.execute("SELECT 1 FROM public.mission_evidence LIMIT 1").fetchone()
    return True
