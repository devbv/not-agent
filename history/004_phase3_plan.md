# Phase 3 개발 계획: 에이전트 루프 개선

## 현재 상태 분석

### 이미 구현된 기능
- ✅ 기본 에이전트 루프 (`AgentLoop`)
  - 사용자 입력 → LLM 호출 → 도구 실행 → 결과 피드백 → 반복
  - max_turns (기본 20턴) 제한
  - 메시지 히스토리 유지
  - 첫 턴에 강제 도구 사용 (`tool_choice: any`)
  - 상세한 디버그 로깅

- ✅ 도구 실행 엔진 (`ToolExecutor`)
  - 도구 정의를 Anthropic API 형식으로 변환
  - 도구 호출 실행 및 결과 반환
  - 에러 처리

- ✅ CLI 인터페이스
  - `agent` 모드: 대화형 에이전트 (도구 사용)
  - `chat` 모드: 단순 채팅 (도구 없음)
  - `run` 명령: 단일 태스크 실행
  - `reset` 명령: 대화 히스토리 초기화

### 아직 구현되지 않은 기능
- ❌ 컨텍스트 윈도우 관리 (토큰 제한 대응)
- ❌ 대화 요약/압축 (긴 대화 최적화)
- ❌ 사용자 질문 기능 (`AskUserQuestion` 도구)
- ❌ 선택지 제공 UI
- ❌ 확인 요청 (위험한 작업 전)

---

## Phase 3 목표

Phase 3는 **에이전트가 사용자와 더 지능적으로 상호작용**하도록 개선하는 것이 핵심입니다.

### 3.1 대화 컨텍스트 관리 개선
**목표**: 긴 대화에서도 효율적으로 동작

#### 3.1.1 토큰 카운팅 및 컨텍스트 윈도우 관리
- [x] 메시지 토큰 수 추적 ✅
- [x] 컨텍스트 윈도우 초과 시 경고/자동 처리 ✅
- [x] 도구 결과 출력 길이 제한 (10,000자) ✅

**구현 완료** (2026-01-10):
- `AgentLoop`에 `max_output_length` (기본 10,000자), `max_context_tokens` (기본 100,000 토큰) 파라미터 추가
- `_format_tool_result()` 메서드에서 출력 길이 제한 및 잘림 메시지 추가
- `_estimate_tokens()`: 간단한 토큰 추정 (4자/토큰)
- `_count_messages_tokens()`: 전체 메시지 히스토리의 토큰 수 계산
- `_check_context_size()`: 컨텍스트 크기 체크 및 경고 (80% 이상 시 INFO, 100% 이상 시 WARNING)
- 각 턴 종료 후 자동으로 컨텍스트 크기 체크

**테스트 결과**:
- ✓ 대용량 출력 잘림 확인 (334KB → 10KB)
- ✓ 토큰 카운팅 동작 확인
- ✓ 컨텍스트 경고 메시지 출력 확인

#### 3.1.2 대화 요약 (Optional - 고급 기능)
- [ ] 오래된 메시지 요약하여 컨텍스트 압축
- [ ] 요약 시 중요 정보 유지 (파일명, 변수명 등)

**참고**: 이 기능은 Phase 5로 미루고, 우선은 단순 잘라내기로 대응할 수도 있습니다.

---

### 3.2 사용자 질문 기능 (핵심)
**목표**: 에이전트가 불확실할 때 사용자에게 질문하기

#### 3.2.1 `AskUserQuestion` 도구 구현
- [x] 도구 정의 및 스키마 작성 ✅
- [x] 사용자 입력 받기 (CLI) ✅
- [x] 선택지 제공 (선택형 질문) ✅

**구현 완료** (2026-01-10):
- 자유 응답형 질문: 사용자가 텍스트로 답변 입력
- 선택형 질문: `radiolist_dialog`를 사용한 대화형 선택 UI (2-10개 옵션)
- Rich Panel을 사용한 시각적으로 명확한 질문 표시
- 에러 처리: 빈 답변, 취소, 옵션 개수 검증
- 도구 등록 및 시스템 프롬프트 업데이트 완료

**테스트 결과**:
- ✓ 자유 응답형 질문 동작 확인
- ✓ 선택형 질문 (radiolist) 동작 확인
- ✓ 빈 답변 거부 확인
- ✓ 사용자 취소 처리 확인
- ✓ 옵션 개수 검증 (2-10개) 확인

**도구 스키마 예시**:
```python
{
    "name": "AskUserQuestion",
    "description": "Ask the user a question when you need clarification or confirmation.",
    "input_schema": {
        "type": "object",
        "properties": {
            "question": {
                "type": "string",
                "description": "The question to ask the user"
            },
            "options": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Optional list of choices for the user to select from"
            }
        },
        "required": ["question"]
    }
}
```

**CLI 인터페이스**:
```python
from prompt_toolkit import prompt
from prompt_toolkit.shortcuts import radiolist_dialog

def ask_user_question(question: str, options: list[str] | None = None) -> str:
    """사용자에게 질문하고 답변 받기."""
    if options:
        # 선택형 질문
        result = radiolist_dialog(
            title="Agent Question",
            text=question,
            values=[(opt, opt) for opt in options]
        ).run()
        return result or options[0]
    else:
        # 자유 응답형 질문
        return prompt(f"\n[Agent Question] {question}\nYour answer: ")
```

#### 3.2.2 확인 요청 기능
- [ ] 위험한 명령어 탐지 (예: `rm -rf`, `DROP TABLE` 등)
- [ ] 자동으로 확인 요청
- [ ] 사용자가 거부하면 작업 중단

**예시**:
```python
DANGEROUS_PATTERNS = [
    r"rm\s+-rf",
    r"DROP\s+TABLE",
    r"DELETE\s+FROM.*WHERE\s+1=1",
    # ...
]

def is_dangerous_command(command: str) -> bool:
    """Check if command is potentially dangerous."""
    import re
    return any(re.search(pattern, command, re.IGNORECASE)
               for pattern in DANGEROUS_PATTERNS)
```

**통합**:
- `Bash` 도구에서 위험한 명령어 실행 전 자동으로 `AskUserQuestion` 호출
- 또는 시스템 프롬프트에 "위험한 작업 전에는 AskUserQuestion으로 확인받으세요" 추가

---

### 3.3 시스템 프롬프트 개선
**목표**: 에이전트가 질문 도구를 적절히 사용하도록 유도

#### 업데이트할 내용
- [ ] `AskUserQuestion` 도구 사용 가이드라인 추가
- [ ] 불확실할 때 질문하도록 지시
- [ ] 위험한 작업 전 확인하도록 지시

**예시**:
```
GUIDELINES:
1. If you're unsure about something, ASK using AskUserQuestion
2. Before executing dangerous commands (e.g., rm -rf), ASK for confirmation
3. When multiple approaches are possible, ASK which one the user prefers
4. After asking, wait for the user's response and follow their instruction
```

---

### 3.4 에러 처리 개선
**목표**: 에이전트가 에러를 스스로 복구하도록

#### 3.4.1 자동 재시도 로직
- [ ] 도구 실행 실패 시 에러 메시지를 LLM에 피드백
- [ ] LLM이 수정된 입력으로 재시도 가능
- [ ] 최대 재시도 횟수 제한 (예: 3회)

**현재 구현**:
- 도구 실행 실패 시 `ToolResult(success=False, error=...)` 반환
- 이미 LLM에 피드백되어 있음 ✅
- 추가 개선 여부는 테스트 후 결정

#### 3.4.2 더 나은 에러 메시지
- [ ] 도구별 맞춤 에러 메시지
- [ ] 에러 해결 힌트 제공

---

## 개발 우선순위

### ✅ Completed
1. **컨텍스트 윈도우 관리** ✅
   - 토큰 카운팅
   - 도구 결과 길이 제한
   - 컨텍스트 크기 모니터링

2. **사용자 질문 기능** (`AskUserQuestion` 도구) ✅
   - 자유 응답형 및 선택형 질문
   - Rich UI 통합
   - 시스템 프롬프트 업데이트

### High Priority (필수)
3. **위험 명령어 확인** 👈 다음 작업 (Optional)
   - 안전성 확보
   - 시스템 프롬프트에 가이드라인 추가됨
   - 추가 구현 필요 여부는 실사용 후 결정

### Medium Priority (중요)
5. **에러 처리 개선**
   - 더 나은 에러 메시지
   - 자동 재시도 로직 검증

### Low Priority (나중에)
6. **대화 요약 기능**
   - Phase 5로 미룰 수 있음
   - 우선은 단순 잘라내기로 대응

---

## 구현 계획

### Step 1: `AskUserQuestion` 도구 구현
**파일**: `src/not_agent/tools/ask_user.py`

```python
"""AskUserQuestion tool - Ask the user for input."""

from typing import Any
from prompt_toolkit import prompt
from prompt_toolkit.shortcuts import radiolist_dialog

from .base import BaseTool, ToolResult


class AskUserQuestionTool(BaseTool):
    """Tool for asking the user questions."""

    name = "AskUserQuestion"
    description = "Ask the user a question when you need clarification or confirmation."

    def get_parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "question": {
                    "type": "string",
                    "description": "The question to ask the user",
                },
                "options": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Optional list of choices for the user (max 10)",
                },
            },
            "required": ["question"],
        }

    def execute(
        self, question: str, options: list[str] | None = None
    ) -> ToolResult:
        """Ask the user a question."""
        try:
            if options:
                # 선택형 질문
                if len(options) > 10:
                    return ToolResult(
                        success=False,
                        error="Too many options (max 10)",
                    )

                result = radiolist_dialog(
                    title="Agent Question",
                    text=question,
                    values=[(opt, opt) for opt in options],
                ).run()

                if result is None:
                    return ToolResult(success=False, error="User cancelled")

                return ToolResult(
                    success=True,
                    output=f"User selected: {result}",
                )
            else:
                # 자유 응답형 질문
                answer = prompt(f"\n[Agent Question] {question}\nYour answer: ").strip()

                if not answer:
                    return ToolResult(success=False, error="User provided no answer")

                return ToolResult(
                    success=True,
                    output=f"User answered: {answer}",
                )

        except Exception as e:
            return ToolResult(success=False, error=str(e))
```

### Step 2: 도구 등록
**파일**: `src/not_agent/tools/__init__.py`

```python
from .ask_user import AskUserQuestionTool

def get_all_tools() -> list[BaseTool]:
    return [
        # ... existing tools ...
        AskUserQuestionTool(),
    ]
```

### Step 3: 시스템 프롬프트 업데이트
**파일**: `src/not_agent/agent/loop.py`

`_get_system_prompt()` 메서드에 다음 내용 추가:
```python
- AskUserQuestion: Ask the user for clarification or confirmation

GUIDELINES:
1. If you're unsure about requirements or approach, ASK the user
2. Before executing dangerous commands (rm -rf, DROP TABLE, etc.), ASK for confirmation
3. When multiple valid approaches exist, ASK which one the user prefers
4. Use AskUserQuestion with options when possible (easier for user)
```

### Step 4: 위험 명령어 확인 (Optional)
**파일**: `src/not_agent/tools/bash.py`

`execute()` 메서드에 확인 로직 추가:
```python
def execute(self, command: str, timeout: int = 30) -> ToolResult:
    # Check for dangerous commands
    if self._is_dangerous(command):
        return ToolResult(
            success=False,
            error="This command looks dangerous. Please use AskUserQuestion to get user confirmation first.",
            output=f"Dangerous command detected: {command}"
        )

    # ... existing code ...

def _is_dangerous(self, command: str) -> bool:
    import re
    patterns = [
        r"rm\s+-rf",
        r"DROP\s+TABLE",
        r"DELETE\s+FROM.*WHERE\s+1\s*=\s*1",
        # Add more patterns...
    ]
    return any(re.search(p, command, re.IGNORECASE) for p in patterns)
```

**주의**: 이 접근은 LLM이 직접 확인하도록 유도하는 방식입니다. 더 나은 방법은 시스템 프롬프트에 명시하는 것입니다.

### Step 5: 컨텍스트 관리 (간단 버전)
**파일**: `src/not_agent/agent/loop.py`

도구 결과 길이 제한:
```python
def _format_tool_result(self, result: ToolResult) -> str:
    """Format a tool result for the LLM."""
    MAX_OUTPUT_LENGTH = 10_000

    if result.success:
        output = result.output
        if len(output) > MAX_OUTPUT_LENGTH:
            output = (
                output[:MAX_OUTPUT_LENGTH]
                + f"\n\n... (truncated {len(output) - MAX_OUTPUT_LENGTH} characters)"
            )
        return output
    else:
        return f"Error: {result.error}\n{result.output}".strip()
```

---

## 테스트 계획

### 수동 테스트 시나리오

1. **사용자 질문 - 자유 응답**
   ```
   사용자: "Python으로 간단한 계산기를 만들어줘"
   에이전트: (불확실하면) "어떤 연산을 지원해야 하나요?"
   사용자: "+, -, *, /"
   에이전트: (코드 생성)
   ```

2. **사용자 질문 - 선택형**
   ```
   사용자: "테스트 프레임워크를 설정해줘"
   에이전트: "어떤 프레임워크를 사용할까요? 1) pytest 2) unittest 3) nose"
   사용자: "1"
   에이전트: (pytest 설정)
   ```

3. **위험 명령어 확인**
   ```
   사용자: "node_modules 폴더를 지워줘"
   에이전트: "rm -rf node_modules를 실행하려고 하는데, 계속할까요?"
   사용자: "yes"
   에이전트: (실행)
   ```

4. **긴 출력 잘라내기**
   ```
   사용자: "큰 로그 파일을 읽어줘"
   에이전트: (읽고) "파일 내용 (처음 10,000자)... (truncated)"
   ```

### 자동 테스트 (pytest)
- [ ] `AskUserQuestionTool` 유닛 테스트 (mock 사용)
- [ ] 컨텍스트 관리 테스트
- [ ] 위험 명령어 탐지 테스트

---

## 완료 기준

Phase 3는 다음 조건을 만족하면 완료:

- [ ] `AskUserQuestion` 도구 구현 및 동작 확인
- [ ] 시스템 프롬프트에 질문 가이드라인 추가
- [ ] 선택형 질문 UI 동작 (radiolist_dialog)
- [ ] 자유 응답형 질문 UI 동작 (prompt)
- [ ] 도구 결과 길이 제한 (10,000자)
- [ ] 위험 명령어 확인 (시스템 프롬프트 또는 도구 레벨)
- [ ] 수동 테스트 시나리오 3개 이상 성공
- [ ] 마일스톤 문서 작성 (`005_phase3_milestone.md`)

---

## 다음 단계 (Phase 4)

Phase 3 완료 후:
- Phase 4: 코드 생성 및 테스트
  - 언어별 코드 생성 최적화
  - 자동 테스트 생성 및 실행
  - 코드 검증 (린트, 타입체크)

---

## 의사결정 기록

### 왜 `AskUserQuestion`을 도구로 구현?
- **대안 1**: 시스템 프롬프트에 "불확실하면 응답에 질문을 포함하세요" 추가
  - 단점: LLM이 질문과 답변을 구분하기 어려움
  - 단점: 파싱 로직 필요

- **대안 2**: 도구로 구현 ✅
  - 장점: 명확한 프로토콜
  - 장점: 선택형 질문 지원 가능
  - 장점: 확장성 (나중에 UI 개선 가능)

### 위험 명령어 확인 방법?
- **대안 1**: `Bash` 도구에서 차단하고 에러 반환
  - 장점: 간단
  - 단점: LLM이 우회 방법 시도 가능

- **대안 2**: 시스템 프롬프트에 명시 ✅
  - 장점: LLM이 스스로 판단
  - 장점: 더 유연함
  - 선택: 우선 이 방법 사용, 나중에 필요하면 도구 레벨 추가

### 컨텍스트 윈도우 관리 전략?
- **대안 1**: 오래된 메시지 삭제
  - 단점: 중요 정보 손실 가능

- **대안 2**: 오래된 메시지 요약
  - 장점: 정보 보존
  - 단점: 복잡도 증가, 추가 LLM 호출 필요

- **대안 3**: 우선 간단하게 도구 결과만 잘라내기 ✅
  - 장점: 즉시 구현 가능
  - 나중에 필요하면 요약 기능 추가 (Phase 5)
