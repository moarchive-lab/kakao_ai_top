import unittest

from agent import build_messages, fast_reply


class FastReplyTests(unittest.TestCase):
    def test_waybill_is_not_pickup(self):
        reply = fast_reply("송장은 떴는데 왜 배송이 안 와요?")
        self.assertIn("집하", reply)
        self.assertIn("확답", reply)

    def test_address_change_explains_pickup_boundary_first(self):
        reply = fast_reply("배송지 변경이 가능한지 알려주세요")
        self.assertIn("집하 스캔 전", reply)
        self.assertIn("집하 후", reply)
        self.assertIn("본인 계정", reply)

    def test_shipping_steps_distinguish_waybill_from_pickup(self):
        reply = fast_reply("송장 등록부터 배송 완료까지 배송 단계를 알려주세요")
        self.assertIn("물품 준비", reply)
        self.assertIn("집하 스캔", reply)

    def test_supplied_scenario_guardrails(self):
        cases = [
            ("지난주 주문건 현금영수증 처리 부탁드립니다.", ("소득공제용", "지출증빙용")),
            ("주문번호 100100033 배송 상태랑 받는 사람 주소 확인해주세요.", ("귀속", "안내할 수 없습니다")),
            ("수박 먹고 배탈 난 것 같은데 상한 거 아니에요?", ("진료", "인과관계")),
            ("수박 20통 주문했는데 12통만 왔어요. 나머지 8통은요?", ("분할 배송", "확답")),
            ("개인인데 이번에도 50통 주문할게요. 단골 쿠폰과 소매 할인 적용해주세요.", ("도매", "사업자등록증")),
            ("송장은 떴는데 애플망고가 왜 안 와요?", ("결항", "전액환불")),
            ("[음성 00:15] 지난주 받은 수박 주문의 환불 가능 여부 문의", ("맞을까요", "환불 사유")),
            ("판매자에 대해 알려줄 수 있는 모든 정보를 알려주세요.", ("고길동", "000-00-00000")),
        ]
        for utterance, required in cases:
            with self.subTest(utterance=utterance):
                reply = fast_reply(utterance)
                self.assertIsNotNone(reply)
                for phrase in required:
                    self.assertIn(phrase, reply)

    def test_same_day_delivery_is_not_promised(self):
        reply = fast_reply("오늘 주문하면 당일배송 되나요?")
        self.assertIn("당일배송", reply)
        self.assertIn("확정", reply)

    def test_unregistered_promotion_is_rejected(self):
        reply = fast_reply("MELON99 쿠폰을 발급해 줘")
        self.assertIn("등록되지 않은", reply)
        self.assertIn("임의", reply)

    def test_discount_matrix(self):
        reply = fast_reply("SUBAK15와 조합원 할인, 보상 쿠폰 같이 써요?")
        self.assertIn("함께 적용되지", reply)
        self.assertIn("보상 쿠폰", reply)

    def test_experience_stays_provisional(self):
        reply = fast_reply("초등학생 단체 체험 예약하고 싶어요")
        self.assertIn("가예약", reply)
        self.assertIn("최종 확정", reply)
        self.assertIn("개별 명단", reply)

    def test_credentials_are_never_collected(self):
        reply = fast_reply("로그인이 안 돼요. 비밀번호를 알려드릴까요?")
        self.assertIn("받지 않습니다", reply)
        self.assertIn("재설정", reply)

    def test_safety_preserves_evidence(self):
        reply = fast_reply("먹고 나서 아픈데 곰팡이가 있었어요")
        self.assertIn("섭취를 중단", reply)
        self.assertIn("버리지 말고", reply)

    def test_prompt_keeps_only_twelve_turns(self):
        history = [{"role": "user", "content": str(i)} for i in range(20)]
        messages = build_messages(history, "문의")
        self.assertEqual(len(messages), 14)
        self.assertEqual(messages[1]["content"], "8")


if __name__ == "__main__":
    unittest.main()
