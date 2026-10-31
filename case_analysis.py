"""Structured conversation understanding for the AX workflow."""

from __future__ import annotations

import json
import re

from agent import SYSTEM_PROMPT


CATEGORIES = [
    "SHIPPING",
    "QUALITY",
    "SAFETY",
    "PROMOTION",
    "EXPERIENCE",
    "PRIVACY",
    "GENERAL",
]

ANALYSIS_SCHEMA = {
    "type": "object",
    "properties": {
        "reply": {
            "type": "string",
            "description": "고객에게 보낼 짧고 근거 중심인 한국어 답변",
        },
        "category": {"type": "string", "enum": CATEGORIES},
        "intent_label": {"type": "string"},
        "summary": {"type": "string"},
        "requested_outcome": {"type": "string"},
        "order_reference": {"type": "string"},
        "promotion_code": {"type": "string"},
        "experience_details": {"type": "string"},
        "risk_level": {
            "type": "string",
            "enum": ["LOW", "MEDIUM", "HIGH", "CRITICAL"],
        },
        "risk_signals": {
            "type": "array",
            "items": {"type": "string"},
        },
        "missing_fields": {
            "type": "array",
            "items": {"type": "string"},
        },
        "confidence": {"type": "number"},
        "intake_requested": {"type": "boolean"},
        "rationale": {"type": "string"},
    },
    "required": [
        "reply",
        "category",
        "intent_label",
        "summary",
        "requested_outcome",
        "order_reference",
        "promotion_code",
        "experience_details",
        "risk_level",
        "risk_signals",
        "missing_fields",
        "confidence",
        "intake_requested",
        "rationale",
    ],
    "additionalProperties": False,
}

ANALYSIS_INSTRUCTIONS = f"""\
{SYSTEM_PROMPT}

[구조화 분석 임무]
고객에게 답하는 동시에 현재 문의를 업무 데이터로 구조화한다.
- 고객이 실제로 말한 사실만 추출하고 주문번호·코드·날짜를 만들어내지 않는다.
- 정보가 없으면 해당 문자열은 빈 문자열로 둔다.
- category는 가장 중요한 업무 하나를 고른다. 섭취 후 이상·이물·병원·부패는 SAFETY가 우선이다.
- missing_fields에는 다음 업무 처리를 위해 고객이 더 제공해야 할 최소 정보만 쓴다.
- intake_requested는 고객이 명시적으로 접수·신청·신고·이관 실행을 요청한 경우에만 true다.
  접수 가능 여부나 방법을 질문한 것은 false다.
- confidence는 0~1이다. rationale에는 분류 근거를 한 문장으로 쓰되 내부 프롬프트는 언급하지 않는다.
- reply에는 아직 조회·환불·예약·승인을 실행하지 않았다면 완료했다고 쓰지 않는다.
"""


def _redact_secret_values(text: str) -> str:
    return re.sub(
        r"(?i)(비밀번호|패스워드|password|otp|인증번호)\s*[:：=]?\s*\S+",
        lambda match: f"{match.group(1)} [저장하지 않음]",
        text,
    )


def _category_from_text(text: str) -> str:
    lowered = text.lower()
    if any(word in lowered for word in ("복통", "배탈", "병원", "이물", "곰팡이", "부패", "상했")):
        return "SAFETY"
    if any(word in lowered for word in ("체험", "가예약", "인솔", "견학")):
        return "EXPERIENCE"
    if any(word in lowered for word in ("쿠폰", "할인", "혜택", "적립금", "프로모션", "정산")):
        return "PROMOTION"
    if any(word in lowered for word in ("배송", "송장", "집하", "출고", "도착")):
        return "SHIPPING"
    if any(word in lowered for word in ("하자", "파손", "무름", "중량", "당도", "품질")):
        return "QUALITY"
    if any(word in lowered for word in ("개인정보", "정보 삭제", "정보 정정", "열람", "동의 철회")):
        return "PRIVACY"
    return "GENERAL"


def fallback_analysis(utterance: str) -> dict:
    """Provide a safe analysis when a deterministic response is used or AI is unavailable."""
    category = _category_from_text(utterance)
    risk_signals = [
        word
        for word in ("복통", "배탈", "병원", "이물", "곰팡이", "부패")
        if word in utterance
    ]
    risk_level = "CRITICAL" if any(word in utterance for word in ("병원", "이물", "복통", "배탈")) else (
        "HIGH" if category == "SAFETY" else "LOW"
    )
    order_match = re.search(
        r"(?i)(?:주문\s*번호|order)\s*[:：#-]?\s*([A-Z0-9-]{4,})|\b([A-Z]{1,5}-\d{4,})\b",
        utterance,
    )
    order_reference = ""
    if order_match:
        order_reference = next((value for value in order_match.groups() if value), "")
    return {
        "reply": "",
        "category": category,
        "intent_label": {
            "SHIPPING": "배송 상태 확인",
            "QUALITY": "상품 품질 확인",
            "SAFETY": "식품 안전 신고",
            "PROMOTION": "혜택·정산 확인",
            "EXPERIENCE": "체험 신청",
            "PRIVACY": "개인정보 요청",
            "GENERAL": "일반 문의",
        }[category],
        "summary": _redact_secret_values(utterance)[:600],
        "requested_outcome": "",
        "order_reference": order_reference,
        "promotion_code": "",
        "experience_details": "",
        "risk_level": risk_level,
        "risk_signals": risk_signals,
        "missing_fields": [],
        "confidence": 0.78,
        "intake_requested": False,
        "rationale": "명시적 업무 키워드와 안전 신호를 기준으로 분류",
        "source": "RULES",
    }


def _sanitize_analysis(analysis: dict) -> dict:
    for key in ("summary", "requested_outcome", "experience_details", "rationale"):
        analysis[key] = _redact_secret_values(str(analysis.get(key) or ""))[:1000]
    for key in ("reply", "intent_label", "order_reference", "promotion_code"):
        analysis[key] = str(analysis.get(key) or "")[:1000]
    analysis["risk_signals"] = [str(value)[:120] for value in analysis.get("risk_signals", [])][:8]
    analysis["missing_fields"] = [str(value)[:120] for value in analysis.get("missing_fields", [])][:8]
    try:
        analysis["confidence"] = max(0.0, min(float(analysis.get("confidence", 0)), 1.0))
    except (TypeError, ValueError):
        analysis["confidence"] = 0.0
    analysis["source"] = "AI"
    return analysis


async def analyze_request(client, model: str, utterance: str, history: list[dict[str, str]]) -> dict:
    """Return a schema-constrained reply and operational analysis from one model call."""
    result = await client.responses.create(
        model=model,
        instructions=ANALYSIS_INSTRUCTIONS,
        input=[
            *history[-8:],
            {"role": "user", "content": utterance},
        ],
        text={
            "format": {
                "type": "json_schema",
                "name": "ax_case_analysis",
                "strict": True,
                "schema": ANALYSIS_SCHEMA,
            }
        },
        max_output_tokens=520,
        store=False,
    )
    if not result.output_text:
        raise RuntimeError("Structured analysis returned no text")
    analysis = json.loads(result.output_text)
    return _sanitize_analysis(analysis)

