# CLAUDE.md - Coding Agent 프로젝트

## 프로젝트 개요
이 프로젝트는 Claude Code와 유사한 코딩 에이전트를 개발하는 것을 목표로 합니다.

## 프로젝트 구조
```
not-agent/
├── CLAUDE.md           # 이 파일 (프로젝트 컨텍스트)
├── history/            # 개발 히스토리 및 의사결정 기록
├── src/not_agent/      # 소스 코드
│   ├── config/         # [신규] 설정 시스템
│   ├── provider/       # [신규] LLM 프로바이더 추상화
│   ├── agent/          # 에이전트 코어 로직
│   ├── tools/          # 도구 구현 (레지스트리 기반)
│   ├── cli/            # CLI 인터페이스
│   └── llm/            # [deprecated] → provider/
├── tests/              # 테스트 코드
└── docs/               # 문서
```

## 핵심 목표
1. 사용자 프롬프트를 받아 코드 생성
2. 생성된 코드 자체 테스트
3. 필요시 사용자에게 질문
4. 반복적 개선 (에이전트 루프)

## 개발 원칙
- **점진적 개발**: 작은 기능부터 시작해서 확장
- **테스트 우선**: 각 기능에 대한 테스트 작성
- **명확한 인터페이스**: 각 모듈간 깔끔한 API
- **문서화**: 주요 의사결정과 설계를 history/에 기록

## 기술 스택
- **언어**: Python 3.11+
- **LLM**: Claude API (anthropic SDK)
- **CLI**: Click + Rich + prompt_toolkit
- **테스트**: pytest
- **타입체크/린팅**: mypy, ruff, black

## 아키텍처 (Phase 4.1)

### 설정 시스템 (config/)
- `Config` 클래스: 계층적 설정 로더
- 우선순위: CLI > 환경변수 > 프로젝트 설정 > 글로벌 설정 > 기본값
- 환경변수: `NOT_AGENT_*` 형식

### 프로바이더 시스템 (provider/)
- `BaseProvider`: LLM 프로바이더 추상 인터페이스
- `ClaudeProvider`: Anthropic Claude API 구현
- `get_provider()`: 이름으로 프로바이더 생성

### 도구 레지스트리 (tools/)
- `@register_tool` 데코레이터로 자동 등록
- `ToolRegistry.get_all()`: 모든 도구 인스턴스 반환

### 세션/컨텍스트 (agent/)
- `Session`: 대화 메시지 관리
- `ContextManager`: 토큰 추정 및 자동 컴팩션

## 현재 상태
- [x] 프로젝트 개요 정의
- [x] 개발 계획 수립
- [x] 기술 스택 결정 (Python)
- [x] Phase 1 완료 (기초 인프라)
- [x] Phase 2 완료 (핵심 도구 구현)
- [x] Phase 3 완료 (에이전트 루프 개선)
- [x] Phase 4.1 완료 (구조 리팩토링)
- [ ] Phase 4.2 (코드 생성 및 테스트)

## 작업 시 참고사항
- `history/` 폴더에 중요한 의사결정과 진행상황 기록
- 중요: 각 Phase 작업 시작시 계획 문서를 history 폴더 아래에 기록
- 중요: 각 Phase 완료 시 마일스톤 문서 작성
- **중요: Phase 작업 완료 시 반드시 커밋할 것** (`/commit` 사용)
- CLAUDE.md 파일과 README.md 파일 업데이트할 것
- 코드 작성 전 설계 먼저 검토

## 명령어
```bash
# 가상환경 활성화
source .venv/bin/activate

# 에이전트 모드 (도구 사용 가능)
not-agent agent

# 에이전트 모드 (모델 지정)
not-agent agent -m claude-haiku-4-5-20251001

# 단순 채팅 (도구 없음)
not-agent chat

# 단일 질문
not-agent ask "질문 내용"

# 단일 태스크 실행 (도구 사용)
not-agent run "태스크 내용"
```

## 설정 파일
```json
// ~/.not_agent/config.json (글로벌)
// .not_agent.json (프로젝트)
{
  "model": "claude-sonnet-4-20250514",
  "max_tokens": 16384,
  "approval_enabled": true,
  "debug": false
}
```

## 히스토리
- 2026-01-09: 프로젝트 시작, 계획 수립
- 2026-01-09: Phase 1 완료 (기초 인프라, LLM 연동, CLI)
- 2026-01-09: Phase 2 완료 (Read, Write, Edit, Glob, Grep, Bash 도구)
- 2026-01-10: Phase 2 확장 (WebSearch, WebFetch 도구 추가)
- 2026-01-10: Phase 3 완료 (컨텍스트 관리, AskUserQuestion 도구)
- 2026-01-11: Phase 4.1 완료 (구조 리팩토링: Config, Provider, ToolRegistry, Session, ContextManager)
