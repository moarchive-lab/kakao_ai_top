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

from agent import build_messages, fast_reply
from session_store import (
    check_database,
    clear_history,
    clear_user_data,
    get_history,
    save_turn,
)

logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"))
logger = logging.getLogger("kakao-skill")

MODEL = os.getenv("OPENAI_MODEL", "gpt-4.1-mini")
client = AsyncOpenAI(timeout=4.2, max_retries=0) if os.getenv("OPENAI_API_KEY") else None


async def answer(
    utterance: str,
    history: list[dict[str, str]],
) -> str:
    """Answer from deterministic policy first, then use the model for nuance."""
    instant = fast_reply(utterance)
    if instant:
        return instant
    if utterance.strip() == "처음부터":
        return "대화 기억을 초기화했어요. 주문·배송·환불·혜택·체험 중 어떤 도움이 필요하신가요?"
    if client is None:
        return (
            "현재 일반 정책 안내는 가능하지만 복합 문의를 처리할 AI 모델 연결이 준비되지 않았습니다. "
            "잠시 후 다시 문의하시거나 상담 담당자 확인을 요청해 주세요."
        )
    try:
        result = await client.responses.create(
            model=MODEL,
            input=build_messages(history, utterance),
            max_output_tokens=320,
        )
        return result.output_text.strip() or "답변을 준비하지 못했어요. 문의 대상과 원하시는 처리를 한 문장으로 다시 남겨 주세요."
    except Exception:
        logger.exception("Mission agent generation failed")
        return "지금은 확인이 지연되고 있어요. 잠시 후 다시 보내 주시거나 담당자 확인을 요청해 주세요."


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

        if user_id and "기록 삭제" in utterance:
            try:
                await asyncio.to_thread(clear_user_data, user_id)
                return JSONResponse(
                    kakao_response("저장된 조사 메모와 대화 기억을 삭제했어요. 카카오톡 채팅방의 과거 메시지는 별도로 남아 있을 수 있습니다.")
                )
            except Exception:
                logger.warning("Could not delete stored user data")
                return JSONResponse(kakao_response("기록을 삭제하지 못했어요. 잠시 후 다시 시도해 주세요."))

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
                logger.warning("Could not read stored context; continuing statelessly")
                history = []
                session_store_available = False
        else:
            # Never combine unrelated people into a shared anonymous history.
            history = []

        first_message = bool(user_id and not history and not reset_session)
        reply = await answer(utterance, history)
        if first_message:
            reply = (
                "안녕하세요, 교동마을 산지직송 AX 상담입니다. 대화 연결을 위해 최근 메시지를 저장하며, "
                "‘기록 삭제’를 입력하면 서버의 대화 기록을 지울 수 있어요. 비밀번호·인증번호는 보내지 마세요.\n\n"
                + reply
            )
        if session_store_available:
            try:
                await asyncio.to_thread(
                    save_turn,
                    user_id,
                    history,
                    "" if reset_session else utterance,
                    reply,
                )
            except Exception:
                logger.warning("Could not persist conversation")
        return JSONResponse(kakao_response(reply))
    except Exception:
        logger.exception("Kakao skill request failed")
        return JSONResponse(kakao_response("요청을 처리하지 못했어요. 잠시 후 다시 시도해 주세요."))
