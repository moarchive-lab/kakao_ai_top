"""Kakao i Open Builder skill endpoint for the AI TOP 100 village AX mission."""

import asyncio
import hashlib
import logging
import os
from contextlib import asynccontextmanager

from dotenv import load_dotenv
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from openai import AsyncOpenAI

load_dotenv()

from agent import build_messages
from session_store import check_database, clear_history, get_history, save_turn

logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"))
logger = logging.getLogger("kakao-skill")

MODEL = os.getenv("OPENAI_MODEL", "gpt-4.1-mini")
client = AsyncOpenAI(timeout=2.8, max_retries=0) if os.getenv("OPENAI_API_KEY") else None


async def answer(utterance: str, history: list[dict[str, str]]) -> str:
    """Run the mission agent, or provide a useful setup response without a model key."""
    if utterance.strip() == "처음부터":
        return "새 인터뷰를 시작할게요. 교동마을과 갯마을 중 어느 마을에서 어떤 역할을 맡고 계신가요?"
    if client is None:
        return (
            "미션 인터뷰를 시작할 준비가 됐어요.\n"
            "AI 답변 모델 키가 아직 설정되지 않았습니다. 서버의 OPENAI_API_KEY를 설정해 주세요.\n"
            "먼저 교동마을/갯마을 중 어느 마을의 어떤 역할인지 알려주세요."
        )
    try:
        result = await client.responses.create(
            model=MODEL,
            input=build_messages(history, utterance),
            max_output_tokens=260,
        )
        return result.output_text.strip() or "답변을 만들지 못했어요. 다른 말로 질문해 주세요."
    except Exception:
        logger.exception("Mission agent generation failed")
        return "답변을 준비하는 중 잠시 문제가 생겼어요. 방금 내용을 다시 보내 주세요."


def kakao_response(text: str) -> dict:
    # Kakao skill response format v2.0; simpleText supports at most 1,000 characters.
    return {"version": "2.0", "template": {"outputs": [{"simpleText": {"text": text[:1000]}}]}}


@asynccontextmanager
async def lifespan(_: FastAPI):
    logger.info("Kakao skill server starting; model=%s; model_key_configured=%s", MODEL, client is not None)
    yield
    if client:
        await client.close()


app = FastAPI(title="AI TOP 100 Village AX Agent", lifespan=lifespan)


@app.get("/health")
async def health():
    # Do not return tokens, keys, or conversation contents from a public health endpoint.
    database_connected = False
    if os.getenv("DATABASE_URL"):
        try:
            database_connected = await asyncio.to_thread(check_database)
        except Exception:
            logger.warning("Database health check failed")
    ready = client is not None and database_connected
    return {
        "status": "ok" if ready else "setup_required",
        "model_configured": client is not None,
        "database_connected": database_connected,
    }


@app.post("/kakao/skill")
async def skill(request: Request):
    try:
        payload = await request.json()
        user_request = payload.get("userRequest") or {}
        utterance = str(user_request.get("utterance") or "").strip()[:4000]
        user = user_request.get("user") or {}
        raw_user_id = str(user.get("id") or "").strip()
        user_id = hashlib.sha256(raw_user_id.encode("utf-8")).hexdigest() if raw_user_id else ""
        if not utterance:
            return JSONResponse(kakao_response("질문 내용을 확인할 수 없어요. 다시 입력해 주세요."))

        reset_session = bool(user_id and utterance == "처음부터")
        session_store_available = bool(user_id)
        if reset_session:
            try:
                await asyncio.to_thread(clear_history, user_id)
            except Exception:
                logger.warning("Could not clear session; continuing with a new conversation")
                session_store_available = False
            history = []
        elif user_id:
            try:
                history = await asyncio.to_thread(get_history, user_id)
            except Exception:
                logger.warning("Could not read conversation history; continuing statelessly")
                history = []
                session_store_available = False
        else:
            # Never combine unrelated people into a shared anonymous history.
            history = []

        reply = await answer(utterance, history)
        if session_store_available:
            try:
                await asyncio.to_thread(save_turn, user_id, history, "" if reset_session else utterance, reply)
            except Exception:
                logger.warning("Could not persist conversation history")
        return JSONResponse(kakao_response(reply))
    except Exception:
        logger.exception("Kakao skill request failed")
        return JSONResponse(kakao_response("요청을 처리하지 못했어요. 잠시 후 다시 시도해 주세요."))
