# 코딩 에이전트 개발 계획

**최종 업데이트**: 2026-01-11

---

## 진행 상황 요약

| Phase | 상태 | 완료일 | 비고 |
|-------|------|--------|------|
| Phase 1 | ✅ 완료 | 2026-01-09 | 기초 인프라 |
| Phase 2 | ✅ 완료 | 2026-01-10 | 핵심 도구 (10개) |
| Phase 3 | ✅ 완료 | 2026-01-10 | 에이전트 루프, 컨텍스트 관리 |
| Phase 4.1 | ✅ 완료 | 2026-01-11 | 구조 리팩토링 |
| Phase 4.2 | 🚧 진행중 | - | 코어 아키텍처 강화 |
| Phase 4.3 | 📋 다음 | - | 코드 생성 및 테스트 |
| Phase 5 | 📋 예정 | - | 고급 기능 |
| Phase 6 | 📋 예정 | - | 사용자 경험 개선 |

---

## Phase 1: 기초 인프라 구축 ✅

### 1.1 프로젝트 셋업
- [x] Python 3.11+ 선택
- [x] 프로젝트 구조 설계
- [x] pyproject.toml 기반 패키지 관리

### 1.2 LLM 통합
- [x] Claude API (anthropic SDK) 연동
- [x] 기본 프롬프트 → 응답 파이프라인
- [x] 환경변수 기반 API 키 관리

### 1.3 기본 CLI 인터페이스
- [x] Click + Rich 기반 CLI
- [x] 대화 세션 관리
- [x] 응답 스트리밍 출력

---

## Phase 2: 핵심 도구(Tools) 구현 ✅

### 2.1 파일 시스템 도구
- [x] `read`: 파일 읽기
- [x] `write`: 파일 쓰기
- [x] `edit`: 파일 수정 (diff 기반)
- [x] `glob`: 패턴으로 파일 찾기
- [x] `grep`: 파일 내용 검색

### 2.2 실행 도구
- [x] `bash`: 쉘 명령어 실행
- [x] 타임아웃 처리 (기본 60초)
- [x] 출력 캡처 및 포맷팅

### 2.3 웹 도구 (추가)
- [x] `web_search`: DuckDuckGo 기반 웹 검색
- [x] `web_fetch`: URL 내용 가져오기

### 2.4 사용자 상호작용 도구
- [x] `ask_user`: 에이전트가 사용자에게 질문
- [x] `todo`: 작업 목록 관리

### 2.5 도구 실행 엔진
- [x] Tool Use 프로토콜 구현
- [x] ToolExecutor 클래스
- [x] 승인 시스템 (ApprovalManager)

---

## Phase 3: 에이전트 루프 개선 ✅

### 3.1 기본 에이전트 루프
- [x] 사용자 입력 → LLM 호출 → 도구 실행 → 결과 피드백 → 반복
- [x] max_turns 제한 (기본 20턴)
- [x] 시스템 프롬프트 구성

### 3.2 대화 컨텍스트 관리
- [x] 메시지 히스토리 유지 (Session)
- [x] 토큰 추정 및 제한 관리
- [x] 자동 컴팩션 (컨텍스트 요약)

### 3.3 사용자 질문 기능
- [x] AskUserQuestion 도구 (선택지 제공)
- [x] 승인 시스템 재설계 (diff 표시)

---

## Phase 4.1: 구조 리팩토링 ✅

### 4.1.1 설정 시스템 (config/)
- [x] `Config` 클래스 (계층적 로더)
- [x] 우선순위: CLI > 환경변수 > 프로젝트 > 글로벌 > 기본값
- [x] `NOT_AGENT_*` 환경변수 지원
- [x] `.not_agent.json` 프로젝트 설정

### 4.1.2 프로바이더 추상화 (provider/)
- [x] `BaseProvider` 인터페이스
- [x] `ClaudeProvider` 구현
- [x] 프로바이더 레지스트리

### 4.1.3 도구 레지스트리 (tools/)
- [x] `@register_tool` 데코레이터
- [x] `ToolRegistry` 싱글톤
- [x] 모든 도구에 데코레이터 적용

### 4.1.4 세션/컨텍스트 분리 (agent/)
- [x] `Session` 클래스 (메시지 관리)
- [x] `ContextManager` 클래스 (토큰 관리)
- [x] `AgentLoop` 간소화

---

## Phase 4.2: 코어 아키텍처 강화 🚧 진행중

> **참고 문서**: [014_core_architecture_review.md](014_core_architecture_review.md)

OpenCode 아키텍처를 참고한 코어 구조 개선

### 4.2.1 메시지 시스템 ✅
> **상세 계획**: [016_plan_message_system.md](016_plan_message_system.md)

- [x] `MessagePart` 추상 기본 클래스
- [x] `TextPart`, `ToolUsePart`, `ToolResultPart` 구현
- [x] 타입 안전한 `Message` 클래스
- [x] Anthropic API 변환 지원
- [x] 직렬화/역직렬화 지원

### 4.2.2 에이전트 루프 상태 관리 ✅
> **상세 계획**: [015_plan_agent_loop_state.md](015_plan_agent_loop_state.md)

- [x] `LoopState` enum (IDLE, CALLING_LLM, EXECUTING_TOOLS 등)
- [x] `TerminationReason` enum
- [x] `LoopContext` 상태 추적 클래스
- [x] 상태 변경 콜백 시스템

### 4.2.3 이벤트 시스템 ✅
> **상세 계획**: [018_plan_event_system.md](018_plan_event_system.md)

- [x] `Event` 기본 클래스
- [x] `EventBus` 구현 (publish/subscribe)
- [x] 주요 이벤트 타입 정의
  - [x] LoopStartedEvent, LoopCompletedEvent
  - [x] TurnStartedEvent, TurnCompletedEvent
  - [x] ToolExecutionStartedEvent, ToolExecutionCompletedEvent
  - [x] LLMRequestEvent, LLMResponseEvent
- [x] `EventLogger` 디버그 로거
- [x] AgentLoop 이벤트 통합

### 4.2.4 권한 시스템 확장 📋
> **상세 계획**: [017_plan_permission_system.md](017_plan_permission_system.md)

- [ ] `Permission` enum (ALLOW, DENY, ASK)
- [ ] `PermissionRule` 규칙 클래스
- [ ] `PermissionManager` 클래스
- [ ] 설정 파일에서 규칙 로드
- [ ] 기존 ApprovalManager 호환 래퍼

---

## Phase 4.3: 코드 생성 및 테스트 📋

> **의존성**: Phase 4.2.4 (권한 시스템) 완료 후 진행

### 4.3.1 코드 생성 개선
- [ ] 언어별 코드 스타일 감지
- [ ] import/의존성 자동 관리
- [ ] 기존 코드 패턴 학습 및 적용

### 4.3.2 테스트 자동화
- [ ] 테스트 프레임워크 감지 (pytest, jest, go test 등)
- [ ] 테스트 코드 생성
- [ ] 테스트 실행 및 결과 파싱
- [ ] 실패 시 자동 수정 시도

### 4.3.3 코드 검증
- [ ] 문법 오류 검사
- [ ] 타입 체크 연동 (mypy, tsc 등)
- [ ] 린팅 연동 (ruff, eslint 등)

---

## Phase 5: 고급 기능 📋

### 5.1 멀티 에이전트
- [ ] 서브 에이전트 생성 (`Task` 도구)
- [ ] 에이전트 간 컨텍스트 공유
- [ ] 병렬 작업 처리

### 5.2 계획 모드
- [ ] 복잡한 작업 분해
- [ ] 단계별 계획 수립
- [ ] 사용자 승인 후 실행

### 5.3 세션 지속성
- [ ] 세션 저장/복원 기능
- [ ] JSON 파일 기반 스토리지

---

## Phase 6: 사용자 경험 개선 📋

### 6.1 진행 상황 표시
- [ ] 실시간 스트리밍 출력
- [ ] Todo 리스트 시각화
- [ ] 스피너/진행률 개선

### 6.2 안전장치
- [ ] 위험 명령어 확인 강화
- [ ] 샌드박스 실행 옵션
- [ ] 롤백 기능

### 6.3 추가 설정
- [ ] CLAUDE.md 유사 프로젝트 설정 파일 지원
- [ ] 플러그인/확장 시스템

---

## 현재 아키텍처

```
not_agent/
├── config/              # 설정 시스템
│   ├── config.py        # Config 클래스
│   └── defaults.py      # 기본값 정의
├── provider/            # LLM 프로바이더 추상화
│   ├── base.py          # BaseProvider 인터페이스
│   ├── claude.py        # Claude 프로바이더
│   └── registry.py      # 프로바이더 레지스트리
├── core/                # 핵심 시스템
│   ├── events.py        # Event, EventBus
│   └── event_logger.py  # EventLogger
├── agent/               # 에이전트 코어
│   ├── loop.py          # AgentLoop (이벤트 통합)
│   ├── session.py       # Session (메시지 관리)
│   ├── context.py       # ContextManager (토큰 관리)
│   ├── message.py       # MessagePart 타입들
│   ├── states.py        # LoopState, TerminationReason
│   ├── executor.py      # ToolExecutor
│   └── approval.py      # ApprovalManager
├── tools/               # 도구 구현
│   ├── registry.py      # ToolRegistry
│   ├── base.py          # BaseTool
│   ├── read.py          # read
│   ├── write.py         # write
│   ├── edit.py          # edit
│   ├── bash.py          # bash
│   ├── glob_tool.py     # glob
│   ├── grep.py          # grep
│   ├── web_search.py    # web_search
│   ├── web_fetch.py     # web_fetch
│   ├── ask_user.py      # ask_user
│   └── todo.py          # todo
└── cli/                 # CLI 인터페이스
    └── main.py          # Click 기반 CLI
```

---

## 기술 스택 (확정)

- **언어**: Python 3.11+
- **LLM**: Claude API (anthropic SDK)
- **CLI**: Click + Rich + prompt_toolkit
- **테스트**: pytest
- **타입체크/린팅**: mypy, ruff, black

---

## 다음 작업 (우선순위)

1. **권한 시스템 확장** (Phase 4.2.4) ← 현재
   - 규칙 기반 자동 승인/거부
   - 설정 파일 연동
   - 코드 생성/테스트의 반복 승인 문제 해결

2. **코드 생성 및 테스트** (Phase 4.3)
   - 테스트 프레임워크 감지 및 실행
   - 테스트 실패 시 자동 수정
   - 코드 검증 (타입체크, 린팅)

3. **멀티 에이전트** (Phase 5.1)
   - Task 도구 구현
   - 서브 에이전트 생성

4. **세션 지속성** (Phase 5.3)
   - 대화 저장/복원

---

## 참고 자료

- [Claude API Documentation](https://docs.anthropic.com)
- [Anthropic Cookbook](https://github.com/anthropics/anthropic-cookbook)
- [Tool Use Guide](https://docs.anthropic.com/claude/docs/tool-use)
- [OpenCode Project](https://github.com/devbv/opencode) - 아키텍처 참고
