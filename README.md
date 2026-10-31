# 교동마을 고객응대 AX

카카오 챗봇 스킬 요청을 받아 교동마을 산지직송의 주문·배송·환불·프로모션·체험·개인정보 문의에 답하고, 명시적인 접수 요청을 Supabase 업무 건으로 전환하는 FastAPI AX 서버입니다.

## AX 실행 흐름

1. AI가 정책과 근거를 바탕으로 문의를 안내합니다.
2. 사용자가 `배송 확인 접수`, `안전 검토 접수`, `가예약 접수` 등의 버튼을 누릅니다.
3. 서버가 `AX-날짜-코드` 접수번호를 발급하고 담당자·우선순위·승인 필요 여부를 분류합니다.
4. `ax_cases`, `ax_case_events`, `ax_approvals`에 업무와 감사 기록을 저장합니다.
5. 사용자는 `내 문의 상태`에서 최근 접수 상태를 확인합니다.

접수는 처리 완료가 아닙니다. 안전·큰 보상·예외 및 체험 최종 확정은 담당 검토와 조합 승인을 별도로 거칩니다.

## 엔드포인트

- `GET /health`: OpenAI와 Supabase 연결 준비 상태
- `POST /kakao/skill`: 카카오 스킬 v2.0 요청/응답

## 로컬 확인

```powershell
python -m unittest discover -v
uvicorn app:app --reload
```

실제 비밀값은 `.env`와 Vercel 환경 변수에만 둡니다. 정적 정책 답변은 모델 호출 없이 처리하고, 복합 문의는 OpenAI Responses API로 처리합니다.

최초 배포 또는 스키마 변경 시 Supabase SQL Editor에서 `schema.sql`을 실행합니다. Vercel에는 `OPENAI_API_KEY`, `OPENAI_MODEL`, `DATABASE_URL`을 설정합니다.
