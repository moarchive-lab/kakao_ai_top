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


def _message_button(label: str, message: str) -> dict:
    return {"label": label[:14], "action": "message", "messageText": message}


def kakao_response(text: str, utterance: str = "") -> dict:
    """Build a contextual Kakao text card with useful next-step buttons."""
    query = utterance.lower()
    title = "🌿 교동마을 AX 안내"
    suggestions = [
        ("배송 문의", "배송 상태가 궁금해요"),
        ("혜택 문의", "현재 사용할 수 있는 혜택을 알려주세요"),
        ("체험 문의", "체험 예약 방법을 알려주세요"),
    ]

    if any(word in query for word in ("송장", "배송", "도착", "출고", "집하")):
        title = "📦 배송 상태 안내"
        suggestions = [
            ("배송 단계", "송장 등록부터 배송 완료까지 단계를 알려주세요"),
            ("주소 변경", "배송지 변경이 가능한지 알려주세요"),
            ("지연 대응", "배송이 지연될 때 선택할 수 있는 방법을 알려주세요"),
        ]
    elif any(word in query for word in ("쿠폰", "할인", "혜택", "적립금", "프로모션")):
        title = "🎟️ 혜택 적용 안내"
        suggestions = [
            ("중복 기준", "할인과 쿠폰 중복 기준을 알려주세요"),
            ("현재 혜택", "현재 사용할 수 있는 혜택을 알려주세요"),
            ("적용 실패", "쿠폰이 적용되지 않는 이유를 확인하고 싶어요"),
        ]
    elif any(word in query for word in ("체험", "가예약", "예약", "인솔")):
        title = "🌱 체험 가예약 안내"
        suggestions = [
            ("준비물", "체험 준비물을 알려주세요"),
            ("예약 절차", "체험 예약 절차를 알려주세요"),
            ("취소 기준", "체험 취소와 환불 기준을 알려주세요"),
        ]
    elif any(word in query for word in ("비밀번호", "인증번호", "개인정보", "다른 사람", "타인", "주소", "연락처")):
        title = "🔒 개인정보 보호 안내"
        suggestions = [
            ("본인 확인", "본인 확인에 필요한 정보를 알려주세요"),
            ("정보 정정", "내 개인정보를 정정하고 싶어요"),
            ("기록 삭제", "기록 삭제"),
        ]
    elif any(word in query for word in ("곰팡이", "부패", "상했", "아픈", "이물", "병원")):
        title = "⚠️ 안전 우선 안내"
        suggestions = [
            ("사진 준비", "품질 문제 사진은 어떻게 찍어야 하나요?"),
            ("환불 기준", "하자 상품 환불 기준을 알려주세요"),
            ("재배송", "하자 상품 재배송 절차를 알려주세요"),
        ]

    if len(text) <= 390:
        output = {
            "textCard": {
                "title": title,
                "description": text,
                "buttons": [_message_button(label, message) for label, message in suggestions[:3]],
            }
        }
    else:
        output = {"simpleText": {"text": text[:1000]}}

    return {
        "version": "2.0",
        "template": {
            "outputs": [output],
            "quickReplies": [
                _message_button(label, message) for label, message in suggestions[:3]
            ],
        },
    }


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
                    kakao_response("저장된 서버 대화 기억을 삭제했어요. 카카오톡 채팅방의 과거 메시지는 별도로 남아 있을 수 있습니다.")
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

        reply = await answer(utterance, history)
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
        return JSONResponse(kakao_response(reply, utterance))
    except Exception:
        logger.exception("Kakao skill request failed")
        return JSONResponse(kakao_response("요청을 처리하지 못했어요. 잠시 후 다시 시도해 주세요."))
