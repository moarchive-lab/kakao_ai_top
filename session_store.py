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
        # Supabase's transaction pooler may reuse a backend that already has a
        # psycopg-generated statement name. Disable server-side preparation.
        prepare_threshold=None,
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


def _case_record(row: tuple) -> dict:
    return {
        "case_id": row[0],
        "public_id": row[1],
        "category": row[2],
        "title": row[3],
        "summary": row[4],
        "status": row[5],
        "priority": row[6],
        "assignee_role": row[7],
        "requires_approval": row[8],
        "missing_fields": row[9] if not isinstance(row[9], str) else json.loads(row[9]),
        "created_at": row[10],
    }


def create_case(user_id: str, draft: dict) -> dict:
    """Persist a routed AX work item, audit event, and approval queue entry."""
    with _connect() as connection:
        # Serialize one user's intake briefly so a Kakao retry or double tap
        # cannot create duplicate work items.
        connection.execute("SELECT pg_advisory_xact_lock(hashtext(%s))", (user_id,))
        existing = connection.execute(
            """
            SELECT case_id, public_id, category, title, summary, status,
                   priority, assignee_role, requires_approval, missing_fields,
                   created_at
            FROM public.ax_cases
            WHERE user_id = %s AND category = %s AND summary = %s
              AND created_at >= NOW() - INTERVAL '2 minutes'
            ORDER BY created_at DESC
            LIMIT 1
            """,
            (user_id, draft["category"], draft["summary"]),
        ).fetchone()
        if existing:
            case = _case_record(existing)
            case["duplicate"] = True
            return case

        row = connection.execute(
            """
            INSERT INTO public.ax_cases (
                public_id, user_id, category, title, summary, status, priority,
                assignee_role, requires_approval, missing_fields
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING case_id, public_id, category, title, summary, status,
                      priority, assignee_role, requires_approval, missing_fields,
                      created_at
            """,
            (
                draft["public_id"],
                user_id,
                draft["category"],
                draft["title"],
                draft["summary"],
                draft["status"],
                draft["priority"],
                draft["assignee_role"],
                draft["requires_approval"],
                Jsonb(draft["missing_fields"]),
            ),
        ).fetchone()
        case = _case_record(row)
        case["duplicate"] = False
        connection.execute(
            """
            INSERT INTO public.ax_case_events (case_id, event_type, detail)
            VALUES (%s, 'CASE_CREATED', %s)
            """,
            (
                case["case_id"],
                Jsonb(
                    {
                        "category": case["category"],
                        "priority": case["priority"],
                        "assignee_role": case["assignee_role"],
                        "missing_fields": case["missing_fields"],
                    }
                ),
            ),
        )
        if draft.get("requires_approval") and draft.get("approver_role"):
            connection.execute(
                """
                INSERT INTO public.ax_approvals (case_id, approver_role, status)
                VALUES (%s, %s, 'PENDING')
                """,
                (case["case_id"], draft["approver_role"]),
            )
            case["approver_role"] = draft["approver_role"]
    return case


def list_recent_cases(user_id: str, limit: int = 5) -> list[dict]:
    safe_limit = max(1, min(limit, 10))
    with _connect() as connection:
        rows = connection.execute(
            """
            SELECT public_id, title, status, priority, assignee_role,
                   requires_approval, missing_fields, created_at
            FROM public.ax_cases
            WHERE user_id = %s
            ORDER BY created_at DESC
            LIMIT %s
            """,
            (user_id, safe_limit),
        ).fetchall()
    return [
        {
            "public_id": row[0],
            "title": row[1],
            "status": row[2],
            "priority": row[3],
            "assignee_role": row[4],
            "requires_approval": row[5],
            "missing_fields": row[6] if not isinstance(row[6], str) else json.loads(row[6]),
            "created_at": row[7],
        }
        for row in rows
    ]


def clear_user_data(user_id: str) -> None:
    with _connect() as connection:
        connection.execute("DELETE FROM public.ax_cases WHERE user_id = %s", (user_id,))
        connection.execute("DELETE FROM public.chatbot_sessions WHERE user_id = %s", (user_id,))


def clear_history(user_id: str) -> None:
    with _connect() as connection:
        connection.execute("DELETE FROM public.chatbot_sessions WHERE user_id = %s", (user_id,))


def check_database() -> bool:
    with _connect() as connection:
        connection.execute("SELECT 1 FROM public.chatbot_sessions LIMIT 1").fetchone()
        connection.execute("SELECT 1 FROM public.ax_cases LIMIT 1").fetchone()
        connection.execute("SELECT 1 FROM public.ax_case_events LIMIT 1").fetchone()
        connection.execute("SELECT 1 FROM public.ax_approvals LIMIT 1").fetchone()
    return True
