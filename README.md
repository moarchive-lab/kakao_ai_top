# 교동마을 고객응대 AX

카카오 챗봇 스킬 요청을 받아 교동마을 산지직송의 주문·배송·환불·프로모션·체험·개인정보 문의에 답하는 FastAPI 서버입니다.

## 엔드포인트

- `GET /health`: OpenAI와 Supabase 연결 준비 상태
- `POST /kakao/skill`: 카카오 스킬 v2.0 요청/응답

## 로컬 확인

```powershell
python -m unittest -v
uvicorn app:app --reload
```

실제 비밀값은 `.env`와 Vercel 환경 변수에만 둡니다. 정적 정책 답변은 모델 호출 없이 처리하고, 복합 문의는 OpenAI Responses API로 처리합니다.
