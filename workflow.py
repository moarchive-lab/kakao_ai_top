"""Deterministic AX workflow classification and customer-safe case summaries."""

from __future__ import annotations

import re
import secrets
from datetime import datetime
from zoneinfo import ZoneInfo


INTAKE_ACTIONS = {
    "배송 확인 접수": "SHIPPING",
    "혜택 확인 접수": "PROMOTION",
    "가예약 접수": "EXPERIENCE",
    "개인정보 요청 접수": "PRIVACY",
    "안전 검토 접수": "SAFETY",
    "품질 확인 접수": "QUALITY",
    "일반 문의 접수": "GENERAL",
}

CATEGORY_LABELS = {
    "SHIPPING": "배송 확인",
    "QUALITY": "상품 품질",
    "SAFETY": "식품 안전",
    "PROMOTION": "혜택·정산",
    "EXPERIENCE": "체험 가예약",
    "PRIVACY": "개인정보 요청",
    "GENERAL": "일반 상담",
}

STATUS_LABELS = {
    "RECEIVED": "접수됨",
    "IN_REVIEW": "담당자 검토 중",
    "AWAITING_APPROVAL": "승인 대기",
    "RESOLVED": "처리 완료",
    "REJECTED": "처리 불가",
    "CANCELLED": "접수 취소",
}


def intake_category(utterance: str) -> str | None:
    """Return the explicitly requested workflow category, if any."""
    normalized = re.sub(r"\s+", " ", utterance).strip()
    return INTAKE_ACTIONS.get(normalized)


def _latest_user_context(history: list[dict[str, str]]) -> str:
    for message in reversed(history):
        if message.get("role") != "user":
            continue
        content = str(message.get("content") or "").strip()
        if content and intake_category(content) is None:
            return content
    return ""


def _redact_credentials(text: str) -> str:
    """Keep operational details while refusing to persist credential-like values."""
    text = re.sub(
        r"(?i)(비밀번호|패스워드|password|otp|인증번호)\s*[:：=]?\s*\S+",
        lambda match: f"{match.group(1)} [저장하지 않음]",
        text,
    )
    return re.sub(r"\s+", " ", text).strip()[:1200]


def _has_order_reference(text: str) -> bool:
    return bool(
        re.search(r"(?i)(주문\s*번호|order)\s*[:：#-]?\s*[A-Z0-9-]{4,}", text)
        or re.search(r"\b[A-Z]{1,5}-\d{4,}\b", text, re.I)
    )


def _experience_missing_fields(text: str) -> list[str]:
    missing: list[str] = []
    if not re.search(r"(?:담당|책임|신청)자?\s*(?:성명|이름)?\s*[:：]?\s*[가-힣]{2,4}", text):
        missing.append("책임자 성명")
    if not re.search(r"01[016789][ -]?\d{3,4}[ -]?\d{4}", text):
        missing.append("연락처")
    if not re.search(r"\d+\s*명", text):
        missing.append("인솔자 포함 총인원")
    if not any(word in text for word in ("유아", "초등", "중등", "고등", "성인", "어르신", "연령대")):
        missing.append("연령대")
    date_count = len(re.findall(r"(?:\d{1,2}[./-])?\d{1,2}\s*일", text))
    if date_count < 2 and not ("1지망" in text and "2지망" in text):
        missing.append("희망일 1·2지망")
    return missing


def build_case_draft(
    category: str,
    history: list[dict[str, str]],
    utterance: str,
) -> dict:
    """Build an auditable routing decision from the user's recent context."""
    context = _latest_user_context(history)
    summary = _redact_credentials(context or utterance)
    combined = f"{context} {utterance}".lower()

    assignee = "이민준"
    priority = "NORMAL"
    requires_approval = False
    approver_role: str | None = None
    missing_fields: list[str] = []

    if category == "SHIPPING":
        assignee = "구방만"
        if not _has_order_reference(combined):
            missing_fields.append("주문번호")
    elif category == "QUALITY":
        assignee = "박수복"
        priority = "HIGH"
        if not _has_order_reference(combined):
            missing_fields.append("주문번호")
    elif category == "SAFETY":
        assignee = "이민준"
        priority = "URGENT"
        requires_approval = True
        approver_role = "고길동"
        if not _has_order_reference(combined):
            missing_fields.append("주문번호")
        if not any(word in combined for word in ("곰팡이", "부패", "이물", "복통", "배탈", "병원", "상했")):
            missing_fields.append("문제 증상 또는 상품 상태")
    elif category == "PROMOTION":
        assignee = "홍보라"
        if not _has_order_reference(combined):
            missing_fields.append("주문번호 또는 혜택 코드")
        if any(word in combined for word in ("12만원", "120,000", "무조건 무료배송", "예외", "분쟁")):
            priority = "HIGH"
            requires_approval = True
            approver_role = "고길동"
    elif category == "EXPERIENCE":
        assignee = "김청년"
        requires_approval = True
        approver_role = "고길동"
        missing_fields = _experience_missing_fields(combined)
    elif category == "PRIVACY":
        assignee = "이민준"
        priority = "HIGH"
        if not any(word in combined for word in ("정정", "삭제", "열람", "동의", "개인정보")):
            missing_fields.append("요청 유형(열람·정정·삭제)")
    elif category == "GENERAL" and not context:
        missing_fields.append("문의 내용")

    return {
        "public_id": f"AX-{datetime.now(ZoneInfo('Asia/Seoul')).strftime('%Y%m%d')}-{secrets.token_hex(3).upper()}",
        "category": category,
        "title": CATEGORY_LABELS[category],
        "summary": summary,
        "status": "RECEIVED",
        "priority": priority,
        "assignee_role": assignee,
        "requires_approval": requires_approval,
        "approver_role": approver_role,
        "missing_fields": missing_fields,
    }


def status_label(status: str) -> str:
    return STATUS_LABELS.get(status, status)

