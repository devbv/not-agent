# Phase 3 확장 계획: Context Compaction (대화 요약)

**작성일**: 2026-01-10
**목표**: 긴 대화에서 토큰 제한을 효과적으로 관리하기 위한 자동 컨텍스트 압축 기능 추가

---

## 배경

### 현재 문제점
- 컨텍스트가 100,000 토큰을 초과하면 경고만 출력
- 사용자가 수동으로 `reset` 명령 실행 필요
- Reset 시 모든 히스토리가 삭제되어 **컨텍스트 완전 손실**
- 긴 작업에서 초반 정보를 참조할 수 없음

### 현재 구현된 기능 (Phase 3)
1. ✅ 토큰 카운팅 (`_count_messages_tokens()`)
2. ✅ 도구 결과 길이 제한 (10,000자)
3. ✅ 컨텍스트 크기 모니터링 (80%/100% 경고)

---

## 목표

### 핵심 목표
**AI에게 대화를 요약시켜서 오래된 메시지를 요약본으로 교체**

### 원하는 동작
1. 컨텍스트가 75% 도달 시 자동으로 압축 트리거
2. **오래된 메시지들을 Claude에게 보내서 요약 생성**
3. 요약본으로 오래된 메시지 교체
4. 최근 메시지는 원본 유지 (정확성 보장)
5. 대화 계속 (중요 정보 손실 없이)

### 성공 기준
- 토큰 사용량 50-70% 감소
- 압축 후에도 작업 컨텍스트 유지
- 파일명, 변수명, 의사결정 등 핵심 정보 보존
- 사용자 개입 없이 자동 동작

---

## 구현 전략

### 1. AI 요약 방식 (채택)

**동작 흐름**:
```
1. 컨텍스트 75% 도달 감지
   ↓
2. 메시지 분리
   - 오래된 메시지 (압축 대상)
   - 최근 4개 메시지 (보존)
   ↓
3. AI 요약 생성
   - 오래된 메시지를 Claude API에 전송
   - 구조화된 요약 프롬프트 사용
   - 요약 결과 받기 (<summary>...</summary>)
   ↓
4. 히스토리 교체
   - messages = [요약 메시지] + [최근 4개]
   ↓
5. 대화 계속
```

**장점**:
- ✅ 핵심 정보 지능적으로 추출
- ✅ 파일명, 변수명, 의사결정 보존
- ✅ Claude Code와 동일한 방식
- ✅ 압축률 높음 (50-70%)

**단점**:
- ❌ 추가 API 호출 필요 (비용)
- ❌ 요약 생성에 시간 소요

### 2. 단순 잘라내기 방식 (기각)

**동작**: 최근 N개만 유지, 나머지 삭제

**장점**:
- ✅ 구현 간단
- ✅ 빠름

**단점**:
- ❌ 오래된 정보 완전 손실
- ❌ 초반 지시사항 잊어버림
- ❌ 압축률 낮음

**결정**: AI 요약 방식 채택 (정보 보존이 더 중요)

---

## 구현 세부사항

### 1. 새로운 파라미터

```python
class AgentLoop:
    def __init__(
        self,
        # ... existing params ...
        max_context_tokens: int = 100_000,
        compaction_threshold: float = 0.75,  # 75% 도달 시 압축
        preserve_recent_messages: int = 4,   # 최근 4개 메시지 보존
        enable_auto_compaction: bool = True, # 자동 압축 ON/OFF
    ):
```

### 2. 새로운 메서드 (4개)

#### `_should_compact() -> bool`
```python
def _should_compact(self) -> bool:
    """압축이 필요한지 확인."""
    if not self.enable_auto_compaction:
        return False

    if len(self.messages) <= self.preserve_recent_messages + 2:
        return False  # 메시지가 너무 적음

    token_count = self._count_messages_tokens()
    threshold = int(self.max_context_tokens * self.compaction_threshold)

    return token_count >= threshold
```

**역할**: 압축 트리거 조건 체크
- 자동 압축 활성화 여부
- 최소 메시지 수 (압축할 게 있는지)
- 75% 임계값 도달 여부

#### `_generate_summary() -> str`
```python
def _generate_summary(self, messages_to_summarize: list[dict[str, Any]]) -> str:
    """AI에게 메시지 요약 요청."""
    summary_prompt = """You have been assisting the user but the conversation is getting long.
Create a concise summary that preserves essential information for continuing the work.

Include in your summary:

1. **Task Overview**
   - User's main request and goals
   - Any constraints or requirements

2. **Work Completed**
   - Files read, created, or modified (with exact paths)
   - Commands executed successfully
   - Key findings or outputs

3. **Important Context**
   - Variable names, function names, class names mentioned
   - Technical decisions made and reasons
   - Errors encountered and how they were resolved
   - User preferences or style requirements

4. **Current State**
   - What needs to be done next
   - Any blockers or open questions

Keep the summary concise (under 1000 words) but preserve ALL critical details.
Focus on facts, not process. Include specific names (files, variables, etc.).
Wrap your entire summary in <summary></summary> tags.
"""

    # Claude API 호출 (요약용)
    response = self.client.messages.create(
        model=self.model,
        max_tokens=2048,
        system="You are a helpful assistant that creates concise summaries.",
        messages=messages_to_summarize + [
            {"role": "user", "content": summary_prompt}
        ],
    )

    # <summary>...</summary> 추출
    text = "".join(block.text for block in response.content if hasattr(block, "text"))

    # Extract summary from tags
    import re
    match = re.search(r"<summary>(.*?)</summary>", text, re.DOTALL)
    if match:
        return match.group(1).strip()
    else:
        return text.strip()
```

**역할**: AI에게 대화 요약 생성 요청
- 구조화된 프롬프트 사용
- 중요 정보 보존 지시 (파일명, 변수명 등)
- `<summary>` 태그로 파싱

#### `_replace_with_summary(summary: str) -> None`
```python
def _replace_with_summary(self, summary: str) -> None:
    """오래된 메시지를 요약으로 교체."""
    # 최근 메시지 추출
    recent_messages = self.messages[-self.preserve_recent_messages:]

    # 요약을 첫 메시지로
    summary_message = {
        "role": "user",
        "content": f"[Previous conversation summary]\n\n{summary}"
    }

    # 히스토리 교체
    self.messages = [summary_message] + recent_messages
```

**역할**: 메시지 히스토리 교체
- 최근 N개 메시지 보존
- 요약을 user 메시지로 추가
- 명확한 표시 (`[Previous conversation summary]`)

#### `_compact_context() -> None`
```python
def _compact_context(self) -> None:
    """컨텍스트 압축 실행 (메인 로직)."""
    print(f"\n{'='*60}")
    print(f"[CONTEXT COMPACTION] Starting...")
    print(f"{'='*60}")

    # 압축 전 상태
    original_count = len(self.messages)
    original_tokens = self._count_messages_tokens()

    print(f"[INFO] Current state: {original_count} messages, {original_tokens:,} tokens")
    print(f"[INFO] Preserving recent {self.preserve_recent_messages} messages")

    # 메시지 분리
    messages_to_summarize = self.messages[:-self.preserve_recent_messages]

    print(f"[INFO] Summarizing {len(messages_to_summarize)} older messages...")

    # AI 요약 생성
    summary = self._generate_summary(messages_to_summarize)

    print(f"[INFO] Summary generated ({len(summary)} characters)")

    # 히스토리 교체
    self._replace_with_summary(summary)

    # 압축 후 상태
    new_count = len(self.messages)
    new_tokens = self._count_messages_tokens()
    reduction = ((original_tokens - new_tokens) / original_tokens) * 100

    print(f"[SUCCESS] Compaction complete!")
    print(f"[SUCCESS] Messages: {original_count} → {new_count}")
    print(f"[SUCCESS] Tokens: {original_tokens:,} → {new_tokens:,} ({reduction:.1f}% reduction)")
    print(f"{'='*60}\n")
```

**역할**: 압축 메인 로직
- 통계 출력 (압축 전/후)
- 요약 생성 호출
- 히스토리 교체
- 사용자에게 알림

### 3. 기존 메서드 수정

#### `_check_context_size()` 수정
```python
def _check_context_size(self) -> None:
    """Check and warn if context is getting large."""
    token_count = self._count_messages_tokens()

    # 압축 필요 시 자동 실행
    if self._should_compact():
        self._compact_context()
        return  # 압축 후 종료

    # 기존 경고 로직
    if token_count > self.max_context_tokens:
        print(f"\n[WARNING] Context size ({token_count:,} tokens) exceeds limit ({self.max_context_tokens:,} tokens)")
        print(f"[WARNING] Consider using 'reset' command to clear history")
    elif token_count > self.max_context_tokens * 0.8:
        print(f"\n[INFO] Context size: {token_count:,} / {self.max_context_tokens:,} tokens (80%+)")
```

**변경점**: 압축 체크 추가
- `_should_compact()` 호출
- True면 즉시 `_compact_context()` 실행
- 압축 후에는 경고 생략

---

## 요약 프롬프트 설계

### 핵심 원칙
1. **구조화**: 섹션별로 명확히 구분
2. **구체성**: "파일을 읽었다" (X) → "README.md를 읽었다" (O)
3. **간결성**: 1000 단어 이내
4. **사실 중심**: 과정보다 결과 (what, not how)

### 프롬프트 구조
```
1. Task Overview
   - 사용자의 원래 요청
   - 제약사항/요구사항

2. Work Completed
   - 읽은 파일: /path/to/file.py
   - 수정한 파일: /path/to/another.py
   - 실행한 명령: pytest tests/
   - 주요 결과

3. Important Context
   - 변수명: user_id, get_user_profile()
   - 기술 결정: "pytest 사용하기로 결정 (unittest보다 간결)"
   - 에러 해결: "ImportError → __init__.py 추가로 해결"

4. Current State
   - 다음 작업: "테스트 코드 작성 필요"
   - 열린 질문: "API 키를 환경변수에 저장할지?"
```

### 예시 요약

**압축 전 대화** (10개 메시지, 약 30,000 토큰):
```
User: "Python 계산기를 만들어줘"
Assistant: [도구 사용: write calculator.py]
User: [도구 결과: 파일 생성됨]
Assistant: "계산기를 만들었습니다..."
User: "테스트도 작성해줘"
Assistant: [도구 사용: write test_calculator.py]
...
```

**압축 후 요약** (약 500 토큰):
```
[Previous conversation summary]

**Task Overview**
User requested creation of a Python calculator with tests.

**Work Completed**
- Created calculator.py with Calculator class
  - Methods: add(), subtract(), multiply(), divide()
  - Added zero division error handling
- Created test_calculator.py using pytest
  - 8 test cases covering all operations
  - Edge cases: zero division, negative numbers

**Important Context**
- File paths: /Users/user/project/calculator.py, test_calculator.py
- User prefers pytest over unittest
- Division by zero raises ValueError with message "Cannot divide by zero"

**Current State**
- All tests passing (8/8)
- User may request README or additional features next
```

---

## 메시지 보존 전략

### 보존할 메시지 (최근 4개)
**이유**: 현재 작업 컨텍스트 유지

**예시**:
```
[-4] user: "테스트를 실행해줘"
[-3] assistant: [ToolUse: bash pytest]
[-2] user: [ToolResult: 8 passed]
[-1] assistant: "모든 테스트 통과했습니다"
```

### 압축할 메시지 (나머지 모두)
**이유**: AI가 핵심만 추출

**포함 대상**:
- 초반 사용자 요청
- 중간 작업들 (파일 읽기/쓰기)
- 에러 및 해결 과정
- 의사결정 내역

---

## 구현 파일

### 수정 대상
**`src/not_agent/agent/loop.py`**

**변경 내용**:
1. `__init__`: 파라미터 3개 추가
   - `compaction_threshold`
   - `preserve_recent_messages`
   - `enable_auto_compaction`

2. 새 메서드 4개 추가:
   - `_should_compact()`
   - `_generate_summary()`
   - `_replace_with_summary()`
   - `_compact_context()`

3. `_check_context_size()` 수정:
   - 압축 트리거 추가

### 문서 업데이트
1. `history/004_phase3_plan.md` - 섹션 추가
2. `history/005_phase3_milestone.md` - 구현 내용 추가

---

## 테스트 계획

### 수동 테스트 시나리오

#### 시나리오 1: 대용량 파일 연속 읽기
```bash
not-agent agent
> "README.md를 읽어줘"
> "src/not_agent/agent/loop.py를 읽어줘"
> "src/not_agent/agent/executor.py를 읽어줘"
> "src/not_agent/tools/read.py를 읽어줘"
> ... (10개 이상 파일)

[예상 결과]
- 75% 도달 시 압축 트리거
- 요약 생성 메시지 출력
- 토큰 50%+ 감소
- 압축 후에도 대화 가능

> "지금까지 읽은 파일들을 요약해줘"
[예상 결과]
- 요약된 정보로도 답변 가능
- 파일명 정확히 기억
```

#### 시나리오 2: 긴 작업 흐름
```bash
not-agent agent
> "Python 계산기 프로젝트를 만들어줘"
> "테스트도 작성해줘"
> "README.md도 작성해줘"
> "setup.py도 추가해줘"
> "타입 힌트를 추가해줘"
> ... (계속 요청)

[예상 결과]
- 자동 압축 여러 번 발생
- 초반 요청 내용 기억
- 프로젝트 구조 파악 유지
```

### 검증 항목
- [ ] 75% 도달 시 자동 압축 트리거
- [ ] AI 요약 생성 성공
- [ ] 최근 4개 메시지 보존
- [ ] 압축 후 대화 정상 진행
- [ ] 파일명, 변수명 등 핵심 정보 손실 없음
- [ ] 토큰 50%+ 감소
- [ ] 압축 통계 정확히 출력
- [ ] 여러 번 압축 가능 (75% 도달 시마다)

---

## 완료 기준

Phase 3 확장 완료:

- [ ] Context compaction 기능 구현 완료
- [ ] 자동 트리거 (75% 임계값) 동작
- [ ] AI 요약 생성 정상 동작
- [ ] 최근 메시지 보존 로직 정상
- [ ] 사용자 알림 메시지 출력
- [ ] 수동 테스트 2개 이상 성공
- [ ] 마일스톤 문서 업데이트

---

## 예상 효과

### 정량적 효과
- **토큰 사용량**: 50-70% 감소 (Claude Cookbook 사례 기준)
- **대화 지속성**: 무한정 긴 대화 가능
- **API 비용**: 약간 증가 (요약 생성 비용) but 전체 토큰 감소로 상쇄

### 정성적 효과
- **UX 개선**: 수동 reset 불필요
- **정보 보존**: 핵심 컨텍스트 유지
- **Claude Code 패리티**: 동일한 사용자 경험

---

## 향후 개선 (Phase 5 이후)

### 추가 기능 아이디어
1. **수동 압축 명령어**: `compact` 명령으로 강제 압축
2. **압축 전략 선택**: 요약 vs 슬라이딩 윈도우 선택 가능
3. **도메인별 요약**: 코드 생성/디버깅/리서치별 커스텀 프롬프트
4. **압축 히스토리**: 압축 내역 저장 및 복원

---

## 의사결정 기록

### Q1: AI 요약 vs 단순 잘라내기?
**결정**: AI 요약 채택

**이유**:
- 정보 보존이 더 중요
- Claude Code와 동일한 방식
- 압축률이 더 높음
- 비용은 감수할 만함 (전체 토큰 감소로 상쇄)

### Q2: 최근 메시지 몇 개 보존?
**결정**: 4개 (기본값)

**이유**:
- 최근 2턴 정도 (user → assistant → tool_result → assistant)
- 너무 적으면 현재 작업 컨텍스트 손실
- 너무 많으면 압축 효과 감소
- 사용자가 파라미터로 조정 가능

### Q3: 임계값 75% vs 80%?
**결정**: 75%

**이유**:
- Claude Code 방식
- 요약 생성에 토큰 필요 (~20%)
- 여유 있게 트리거하는 게 안전

### Q4: 요약 모델은?
**결정**: 동일 모델 사용 (`self.model`)

**이유**:
- 일관성
- 사용자가 선택한 모델 존중
- Haiku도 요약 잘함

---

## 참고 자료

- [Anthropic Cookbook: Context Compaction](https://platform.claude.com/cookbook/tool-use-automatic-context-compaction)
- [Claude Code 구현 분석](https://gist.github.com/badlogic/cd2ef65b0697c4dbe2d13fbecb0a0a5f)
- [How Claude Code Got Better by Protecting More Context](https://hyperdev.matsuoka.com/p/how-claude-code-got-better-by-protecting)
