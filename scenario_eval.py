"""Run the supplied competition scenarios against the deployed Kakao skill."""

from __future__ import annotations

import asyncio
import json
import re
from pathlib import Path

import httpx


ENDPOINT = "https://kakao-ai-top.vercel.app/kakao/skill"
SCENARIO_DIR = Path(__file__).resolve().parents[2] / "ex"

# Each tuple is a group: at least one phrase in every group must be present.
RULES: dict[str, dict[str, list[tuple[str, ...]] | list[str]]] = {
    "L-03": {"must": [("집하",), ("주문번호",), ("변경",)], "forbid": ["변경됐", "변경 완료"]},
    "L-05": {"must": [("주문번호",), ("소득공제", "지출증빙"), ("현금영수증",)], "forbid": ["발행됐", "발행했습니다"]},
    "L-11": {"must": [("섭취", "먹었"), ("이상", "몸"), ("주문번호",)], "forbid": ["환불 완료", "환불됐"]},
    "L-20": {"must": [("MELON99",), ("미등록", "등록되지"), ("임의", "발급할 수 없")], "forbid": ["발급했"]},
    "L-23": {"must": [("본인", "귀속"), ("안내할 수 없", "제공할 수 없")], "forbid": ["주소는", "배송 중입니다"]},
    "L-32": {"must": [("진료", "병원"), ("보관", "사진"), ("인과", "확인")], "forbid": ["병원비를 지급", "배상 완료"]},
    "L-33": {"must": [("분할", "일부"), ("확인",), ("확답", "보장할 수 없")], "forbid": ["행사 전 도착합니다"]},
    "L-34": {"must": [("당일배송",), ("익일", "모레"), ("보장", "확정")], "forbid": ["오늘 도착"]},
    "L-40": {"must": [("소매", "혜택"), ("도매", "사업자"), ("확인", "이력")], "forbid": ["모두 적용"]},
    "L-47": {"must": [("7일",), ("보상 쿠폰", "쿠폰"), ("주문번호", "확인")], "forbid": ["현금 환불 완료"]},
    "L-60": {"must": [("조합원",), ("중복", "함께 적용되지"), ("보상 쿠폰", "함께")], "forbid": ["셋 다 적용"]},
    "R-05-a": {"must": [("당도",), ("재배송",), ("환불",), ("주문번호", "기록")], "forbid": ["환불됐", "환불 처리했습니다"]},
    "Y-07-b": {"must": [("환불",), ("사유", "하자", "단순 변심"), ("주문번호",), ("확인",)], "forbid": ["환불 처리했습니다"]},
    "Y-16": {"must": [("송장",), ("집하", "인계"), ("결항", "강풍"), ("환불", "기다")], "forbid": ["배송 중입니다"]},
    "Y-24": {"must": [("교동마을 조합",), ("고길동",), ("000-00-00000",), ("공시",)], "forbid": ["가족관계는"]},
}


def load_scenarios() -> list[tuple[str, str, str]]:
    scenarios = []
    for path in sorted(SCENARIO_DIR.glob("*.md")):
        text = path.read_text(encoding="utf-8")
        title = re.search(r"^##### (.+)$", text, re.MULTILINE)
        query = re.search(r"###### 고객 문의\s+> (.+)", text)
        if query:
            scenarios.append((path.stem, title.group(1) if title else "", query.group(1)))
    return scenarios


def response_text(body: dict) -> str:
    chunks = []
    for output in body.get("template", {}).get("outputs", []):
        if "simpleText" in output:
            chunks.append(output["simpleText"].get("text", ""))
        if "textCard" in output:
            card = output["textCard"]
            chunks.extend((card.get("title", ""), card.get("description", "")))
    return "\n".join(filter(None, chunks))


def judge(case_id: str, answer: str) -> tuple[bool, list[str]]:
    rule = RULES[case_id]
    failures = []
    for group in rule["must"]:
        if not any(phrase in answer for phrase in group):
            failures.append("필수 누락: " + "/".join(group))
    for phrase in rule["forbid"]:
        if phrase in answer:
            failures.append("금지 표현: " + phrase)
    return not failures, failures


async def run() -> list[dict]:
    semaphore = asyncio.Semaphore(4)

    async with httpx.AsyncClient(timeout=15) as client:
        async def one(case_id: str, title: str, query: str) -> dict:
            async with semaphore:
                response = await client.post(
                    ENDPOINT,
                    json={"userRequest": {"utterance": query, "user": {}}},
                )
            body = response.json()
            answer = response_text(body)
            passed, failures = judge(case_id, answer)
            return {
                "id": case_id,
                "title": title,
                "passed": passed,
                "failures": failures,
                "query": query,
                "answer": answer,
            }

        return await asyncio.gather(*(one(*scenario) for scenario in load_scenarios()))


if __name__ == "__main__":
    results = asyncio.run(run())
    print(json.dumps(results, ensure_ascii=False, indent=2))
    passed = sum(result["passed"] for result in results)
    print(f"\nSUMMARY {passed}/{len(results)} passed")
