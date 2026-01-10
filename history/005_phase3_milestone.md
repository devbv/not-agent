# Phase 3 완료 마일스톤: 에이전트 루프 개선

**완료일**: 2026-01-10
**목표**: 에이전트가 사용자와 더 지능적으로 상호작용하도록 개선

---

## 구현된 기능

### 1. 컨텍스트 윈도우 관리 ✅

#### 구현 내용
- **출력 길이 제한** ([loop.py:179-198](../src/not_agent/agent/loop.py#L179-L198))
  - 도구 결과가 10,000자 초과 시 자동 잘림
  - 잘린 문자 수를 명확히 표시 (예: "output truncated, 324,400 characters omitted")
  - 성공/에러 출력 모두 동일하게 적용

- **토큰 카운팅** ([loop.py:196-227](../src/not_agent/agent/loop.py#L196-L227))
  - 간단한 토큰 추정 알고리즘 (4자/토큰)
  - 메시지 히스토리 전체 토큰 수 계산
  - 시스템 프롬프트 토큰도 포함

- **컨텍스트 크기 모니터링** ([loop.py:229-237](../src/not_agent/agent/loop.py#L229-L237))
  - 80% 이상: INFO 메시지 출력
  - 100% 초과: WARNING 메시지 + `reset` 명령 권장
  - 각 턴 종료 후 자동 체크

#### 설정 파라미터
```python
AgentLoop(
    max_output_length=10_000,    # 도구 출력 최대 길이
    max_context_tokens=100_000,  # 컨텍스트 최대 토큰 수
)
```

#### 테스트 결과
- ✅ 334KB 파일 읽기 → 10KB로 자동 잘림
- ✅ 토큰 카운팅 정확도 검증
- ✅ 경고 메시지 적절히 출력

---

### 2. 사용자 질문 기능 (`AskUserQuestion`) ✅

#### 구현 내용
새로운 도구 추가: [ask_user.py](../src/not_agent/tools/ask_user.py)

**주요 기능**:
1. **자유 응답형 질문**
   - 사용자가 텍스트로 직접 답변
   - `prompt_toolkit.prompt()` 사용
   - 빈 답변 자동 거부

2. **선택형 질문**
   - 2-10개 옵션 중 선택
   - `prompt_toolkit.shortcuts.radiolist_dialog()` 사용
   - 대화형 UI로 사용자 경험 개선

3. **UI 개선**
   - Rich Panel로 질문을 시각적으로 강조
   - 선택 결과 즉시 피드백
   - 취소 처리 지원

#### 도구 스키마
```python
{
    "name": "AskUserQuestion",
    "description": "Ask the user a question when you need clarification or confirmation.",
    "parameters": {
        "question": "The question to ask (required)",
        "options": "Optional list of 2-10 choices for selection"
    }
}
```

#### 사용 예시

**자유 응답형**:
```python
tool.execute(
    question="What operations should the calculator support?"
)
# Output: "User answered: +, -, *, /"
```

**선택형**:
```python
tool.execute(
    question="Which test framework do you want to use?",
    options=["unittest", "pytest", "nose"]
)
# Output: "User selected: pytest"
```

#### 테스트 결과
- ✅ 자유 응답형 질문 동작 확인
- ✅ 선택형 질문 (radiolist) 동작 확인
- ✅ 빈 답변 거부 확인
- ✅ 사용자 취소 처리 확인
- ✅ 옵션 개수 검증 (2-10개) 확인

---

### 3. 시스템 프롬프트 개선 ✅

#### 추가된 가이드라인
에이전트 시스템 프롬프트에 다음 섹션 추가:

```
ASKING QUESTIONS:
- If you're UNSURE about requirements or approach → USE AskUserQuestion
- Before DANGEROUS operations (rm -rf, DROP TABLE, etc.) → USE AskUserQuestion to confirm
- When MULTIPLE VALID approaches exist → USE AskUserQuestion to let user choose
- Provide options array when possible (easier for user to select)
- Be specific and clear in your questions

SAFETY:
- Always read files before editing them
- Be careful with destructive bash commands
- Ask before deleting files or making irreversible changes
```

#### 효과
- LLM이 불확실할 때 스스로 질문하도록 유도
- 위험한 작업 전 확인 요청 권장
- 선택형 질문 사용 장려

---

## 완료 기준 충족 확인

- [x] `AskUserQuestion` 도구 구현 및 동작 확인
- [x] 시스템 프롬프트에 질문 가이드라인 추가
- [x] 선택형 질문 UI 동작 (radiolist_dialog)
- [x] 자유 응답형 질문 UI 동작 (prompt)
- [x] 도구 결과 길이 제한 (10,000자)
- [x] 컨텍스트 크기 모니터링 및 경고
- [x] 유닛 테스트 작성 및 통과

---

## 파일 변경 사항

### 새로 추가된 파일
1. `src/not_agent/tools/ask_user.py` - AskUserQuestion 도구 구현

### 수정된 파일
1. `src/not_agent/agent/loop.py`
   - 컨텍스트 관리 기능 추가
   - 시스템 프롬프트 업데이트

2. `src/not_agent/tools/__init__.py`
   - AskUserQuestion 도구 등록

### 문서
1. `history/004_phase3_plan.md` - Phase 3 계획 및 진행 상황
2. `history/005_phase3_milestone.md` - 이 마일스톤 문서

---

## 성과 및 개선사항

### 주요 성과
1. **컨텍스트 오버플로우 방지**
   - 대용량 파일 처리 시 메모리 효율 개선
   - 토큰 제한 초과 사전 경고

2. **사용자 상호작용 강화**
   - 에이전트가 불확실할 때 질문 가능
   - 사용자 선택을 존중하는 협력적 작업 흐름

3. **안전성 향상**
   - 위험한 작업 전 확인 요청 권장
   - 시스템 프롬프트에 안전 가이드라인 명시

### 기술적 개선
- Rich 라이브러리를 활용한 UX 개선
- prompt_toolkit의 대화형 UI 활용
- 에러 처리 강화 (빈 답변, 취소, 검증)

---

## 남은 작업 (Optional)

### 위험 명령어 자동 탐지
현재는 시스템 프롬프트로만 가이드라인 제공. 필요하면 추가 구현:
- `Bash` 도구에서 위험 패턴 탐지
- 자동으로 `AskUserQuestion` 호출

**결정**: 실사용 후 필요성 판단. 현재는 LLM의 판단에 맡김.

### 대화 요약 기능
긴 대화 시 오래된 메시지 요약하여 컨텍스트 압축.

**결정**: Phase 5로 연기. 현재는 단순 잘라내기로 충분.

---

## 다음 단계: Phase 4

Phase 3 완료 후 다음 목표:

### Phase 4: 코드 생성 및 테스트
1. **코드 생성 최적화**
   - 기존 코드 스타일 파악 및 적용
   - Import/의존성 자동 관리

2. **자동 테스트**
   - 테스트 코드 생성
   - 테스트 실행 및 결과 파싱
   - 실패 시 자동 수정 시도

3. **코드 검증**
   - 문법 오류 검사
   - 타입 체크 (Python: mypy)
   - 린팅 (ruff, black)

---

## 의사결정 기록

### 왜 컨텍스트 관리를 먼저 구현?
- **이유**: 기반 기능이며, 이후 테스트 시에도 필요
- **결과**: 올바른 선택. 대용량 출력 처리 문제 사전 해결

### AskUserQuestion의 옵션 개수 제한 (2-10개)
- **이유**:
  - 너무 적으면(1개) 선택의 의미 없음
  - 너무 많으면(10개+) UI가 복잡해짐
- **대안**: 많은 옵션이 필요하면 자유 응답형 사용

### 위험 명령어 확인 방법
- **선택**: 시스템 프롬프트에 가이드라인 명시
- **이유**:
  - LLM이 컨텍스트를 고려하여 판단 가능
  - 도구 레벨 차단보다 유연함
  - 필요하면 나중에 추가 구현 가능

---

## 결론

Phase 3의 핵심 목표를 모두 달성했습니다:
- ✅ 컨텍스트 윈도우 관리로 안정성 확보
- ✅ 사용자 질문 기능으로 상호작용 개선
- ✅ 시스템 프롬프트로 안전 가이드라인 제공

에이전트가 이제 사용자와 더 지능적으로 협력하며, 긴 대화에서도 안정적으로 동작합니다.

Phase 4에서는 코드 생성 품질과 자동 테스트에 집중하여 실용성을 더욱 높일 예정입니다.
