import unittest

from workflow import build_case_draft, explicit_intake_intent, intake_category, status_label


class WorkflowTest(unittest.TestCase):
    def test_intake_requires_explicit_action(self):
        self.assertEqual(intake_category("배송 확인 접수"), "SHIPPING")
        self.assertIsNone(intake_category("배송 상태가 궁금해요"))

    def test_shipping_routes_to_delivery_owner(self):
        draft = build_case_draft(
            "SHIPPING",
            [{"role": "user", "content": "주문번호 KD-12345 배송이 멈췄어요"}],
            "배송 확인 접수",
        )
        self.assertEqual(draft["assignee_role"], "구방만")
        self.assertEqual(draft["missing_fields"], [])
        self.assertFalse(draft["requires_approval"])

    def test_safety_is_urgent_and_requires_approval(self):
        draft = build_case_draft(
            "SAFETY",
            [{"role": "user", "content": "주문번호 KD-9999 수박을 먹고 복통이 있어 병원에 갔어요"}],
            "안전 검토 접수",
        )
        self.assertEqual(draft["priority"], "URGENT")
        self.assertTrue(draft["requires_approval"])
        self.assertEqual(draft["approver_role"], "고길동")
        self.assertEqual(draft["missing_fields"], [])

    def test_experience_detects_missing_intake_fields(self):
        draft = build_case_draft(
            "EXPERIENCE",
            [{"role": "user", "content": "초등학생 12명 체험하고 싶어요"}],
            "가예약 접수",
        )
        self.assertIn("책임자 성명", draft["missing_fields"])
        self.assertIn("연락처", draft["missing_fields"])
        self.assertIn("희망일 1·2지망", draft["missing_fields"])
        self.assertNotIn("인솔자 포함 총인원", draft["missing_fields"])

    def test_credentials_are_not_persisted(self):
        draft = build_case_draft(
            "GENERAL",
            [{"role": "user", "content": "비밀번호: hunter2 주문을 확인해 주세요"}],
            "일반 문의 접수",
        )
        self.assertNotIn("hunter2", draft["summary"])
        self.assertIn("저장하지 않음", draft["summary"])

    def test_status_has_customer_label(self):
        self.assertEqual(status_label("AWAITING_APPROVAL"), "승인 대기")

    def test_ai_analysis_is_validated_by_routing_rules(self):
        analysis = {
            "category": "SAFETY",
            "intent_label": "섭취 후 복통 신고",
            "summary": "주문번호 KD-7777 상품 섭취 후 복통",
            "risk_level": "CRITICAL",
            "missing_fields": [],
            "confidence": 0.96,
            "source": "AI",
        }
        draft = build_case_draft("GENERAL", [], "이 내용 접수해줘", analysis)
        self.assertEqual(draft["category"], "SAFETY")
        self.assertEqual(draft["priority"], "URGENT")
        self.assertEqual(draft["decision_source"], "AI_VALIDATED")
        self.assertEqual(draft["status"], "RECEIVED")

    def test_missing_required_data_enters_needs_info(self):
        draft = build_case_draft(
            "SHIPPING",
            [{"role": "user", "content": "배송이 멈춘 것 같아요"}],
            "배송 확인 접수",
        )
        self.assertEqual(draft["status"], "NEEDS_INFO")
        self.assertIn("주문번호", draft["missing_fields"])

    def test_natural_intake_requires_affirmative_language(self):
        self.assertTrue(explicit_intake_intent("이 내용으로 접수해 주세요"))
        self.assertFalse(explicit_intake_intent("접수할 수 있나요?"))


if __name__ == "__main__":
    unittest.main()

