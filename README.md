# 교동마을 고객응대 AX

카카오 챗봇 스킬 요청을 받아 교동마을 산지직송의 주문·배송·환불·프로모션·체험·개인정보 문의에 답하고, 명시적인 접수 요청을 Supabase 업무 건으로 전환하는 FastAPI AX 서버입니다.

## AX 실행 흐름

1. AI가 자유 대화에서 의도·업무유형·요청 결과·식별값·위험도·누락정보를 JSON Schema로 구조화합니다.
2. 정책 답변과 함께 분석 결과에 맞는 다음 행동 버튼을 제시합니다.
3. 사용자가 접수 버튼을 누르거나 “이 내용으로 접수해 주세요”라고 명시적으로 요청합니다.
4. 서버가 AI 분석을 업무 규칙으로 검증한 뒤 `AX-날짜-코드` 접수번호와 상태를 생성합니다.
5. `ax_cases`, `ax_case_events`, `ax_approvals`에 분석·신뢰도·라우팅 근거·감사 기록을 저장합니다.
6. 사용자는 `내 문의 상태`에서 최근 접수 상태를 확인합니다.

접수는 처리 완료가 아닙니다. 안전·큰 보상·예외 및 체험 최종 확정은 담당 검토와 조합 승인을 별도로 거칩니다.

## 엔드포인트

- `GET /health`: OpenAI와 Supabase 연결 준비 상태
- `POST /kakao/skill`: 카카오 스킬 v2.0 요청/응답

## 로컬 확인

```powershell
python -m unittest discover -v
uvicorn app:app --reload
```

실제 비밀값은 `.env`와 Vercel 환경 변수에만 둡니다. 고위험·정본 정책 답변은 결정적 규칙으로 보호하고, 복합 문의는 OpenAI Responses API Structured Outputs로 답변과 업무 분석을 한 번에 생성합니다.

최초 배포 또는 스키마 변경 시 Supabase SQL Editor에서 `schema.sql`을 실행합니다. Vercel에는 `OPENAI_API_KEY`, `OPENAI_MODEL`, `DATABASE_URL`을 설정합니다. 구조화 분석 모델은 선택적으로 `OPENAI_ANALYSIS_MODEL`로 바꿀 수 있으며 기본값은 지연이 짧은 `gpt-4o-mini`입니다.
