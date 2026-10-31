import json
import unittest
from types import SimpleNamespace

from case_analysis import analyze_request, fallback_analysis


class _FakeResponses:
    def __init__(self, payload):
        self.payload = payload
        self.kwargs = None

    async def create(self, **kwargs):
        self.kwargs = kwargs
        return SimpleNamespace(output_text=json.dumps(self.payload, ensure_ascii=False))


class _FakeClient:
    def __init__(self, payload):
        self.responses = _FakeResponses(payload)


class CaseAnalysisTest(unittest.IsolatedAsyncioTestCase):
    async def test_structured_output_drives_operational_analysis(self):
        payload = {
            "reply": "배송 기록 확인이 필요합니다.",
            "category": "SHIPPING",
            "intent_label": "송장 등록 후 미집하 확인",
            "summary": "주문 KD-12345의 실제 집하 여부 확인 요청",
            "requested_outcome": "배송 상태 확인",
            "order_reference": "KD-12345",
            "promotion_code": "",
            "experience_details": "",
            "risk_level": "LOW",
            "risk_signals": [],
            "missing_fields": [],
            "confidence": 0.94,
            "intake_requested": False,
            "rationale": "송장과 집하 여부를 질문함",
        }
        client = _FakeClient(payload)
        result = await analyze_request(client, "test-model", "배송이 안 와요", [])

        self.assertEqual(result["category"], "SHIPPING")
        self.assertEqual(result["source"], "AI")
        self.assertEqual(
            client.responses.kwargs["text"]["format"]["type"],
            "json_schema",
        )
        self.assertTrue(client.responses.kwargs["text"]["format"]["strict"])
        self.assertFalse(client.responses.kwargs["store"])

    def test_fallback_analysis_prioritizes_safety(self):
        result = fallback_analysis("수박을 먹고 복통이 있어 병원에 갔어요")
        self.assertEqual(result["category"], "SAFETY")
        self.assertEqual(result["risk_level"], "CRITICAL")
        self.assertEqual(result["source"], "RULES")


if __name__ == "__main__":
    unittest.main()

