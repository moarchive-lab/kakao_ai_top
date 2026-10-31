import unittest

from agent import build_messages, fast_reply


class FastReplyTests(unittest.TestCase):
    def test_waybill_is_not_pickup(self):
        reply = fast_reply("송장은 떴는데 왜 배송이 안 와요?")
        self.assertIn("집하", reply)
        self.assertIn("확답", reply)

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
