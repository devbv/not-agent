# 기술 스택 결정

## 결정일: 2026-01-09

## 선택: Python

## 선택 이유
- AI/ML 생태계가 가장 풍부함
- 빠른 프로토타이핑 가능
- Anthropic Python SDK 공식 지원
- 학습 곡선이 낮음

## 상세 기술 스택

### 핵심
| 구분 | 선택 | 비고 |
|------|------|------|
| 언어 | Python 3.11+ | match문, 타입힌트 개선 |
| LLM SDK | anthropic | 공식 SDK |
| 패키지 관리 | uv 또는 poetry | 의존성 관리 |

### CLI & UI
| 구분 | 선택 | 비고 |
|------|------|------|
| CLI 프레임워크 | Click | 간단하고 강력함 |
| 터미널 UI | Rich | 색상, 테이블, 진행바 등 |
| 프롬프트 입력 | prompt_toolkit | 멀티라인, 자동완성 |

### 테스트 & 품질
| 구분 | 선택 | 비고 |
|------|------|------|
| 테스트 | pytest | 표준 |
| 타입 체크 | mypy | 정적 타입 검사 |
| 린팅 | ruff | 빠른 린터 |
| 포매팅 | black | 코드 포맷터 |

### 프로젝트 구조
```
not-agent/
├── pyproject.toml      # 프로젝트 설정
├── CLAUDE.md
├── README.md
├── history/
├── src/
│   └── not_agent/      # 메인 패키지
│       ├── __init__.py
│       ├── __main__.py # CLI 진입점
│       ├── agent/      # 에이전트 코어
│       │   ├── __init__.py
│       │   ├── loop.py # 에이전트 루프
│       │   └── context.py # 컨텍스트 관리
│       ├── tools/      # 도구들
│       │   ├── __init__.py
│       │   ├── base.py # 도구 베이스 클래스
│       │   ├── bash.py
│       │   ├── read.py
│       │   ├── write.py
│       │   ├── edit.py
│       │   ├── glob.py
│       │   └── grep.py
│       ├── llm/        # LLM 통합
│       │   ├── __init__.py
│       │   └── claude.py
│       └── cli/        # CLI
│           ├── __init__.py
│           └── main.py
└── tests/
    ├── __init__.py
    ├── test_tools/
    └── test_agent/
```

## 초기 의존성 (pyproject.toml)
```toml
[project]
name = "not-agent"
version = "0.1.0"
requires-python = ">=3.11"

dependencies = [
    "anthropic>=0.40.0",
    "click>=8.0.0",
    "rich>=13.0.0",
    "prompt-toolkit>=3.0.0",
]

[project.optional-dependencies]
dev = [
    "pytest>=8.0.0",
    "mypy>=1.0.0",
    "ruff>=0.5.0",
    "black>=24.0.0",
]

[project.scripts]
not-agent = "not_agent.cli.main:cli"
```

## 다음 단계
1. 프로젝트 초기화 (pyproject.toml 생성)
2. 기본 디렉토리 구조 생성
3. Hello World 에이전트 구현
