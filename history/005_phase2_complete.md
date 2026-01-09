# Phase 2 완료: 핵심 도구 구현

## 완료일: 2026-01-09

## 구현된 도구들

### 1. 기본 인프라
- **BaseTool** (`tools/base.py`): 모든 도구의 추상 베이스 클래스
- **ToolResult**: 도구 실행 결과를 담는 데이터 클래스
- **ToolExecutor** (`agent/executor.py`): 도구 실행 관리자

### 2. 파일 시스템 도구
| 도구 | 파일 | 기능 |
|------|------|------|
| Read | `tools/read.py` | 파일 읽기 (라인 번호 포함) |
| Write | `tools/write.py` | 파일 쓰기 (생성/덮어쓰기) |
| Edit | `tools/edit.py` | 문자열 치환으로 파일 수정 |
| Glob | `tools/glob_tool.py` | 패턴으로 파일 검색 |
| Grep | `tools/grep.py` | 정규식으로 내용 검색 |

### 3. 실행 도구
| 도구 | 파일 | 기능 |
|------|------|------|
| Bash | `tools/bash.py` | 쉘 명령어 실행 |

### 4. 에이전트 루프
- **AgentLoop** (`agent/loop.py`): LLM과 도구를 연결하는 메인 루프
  - 사용자 메시지 → LLM 호출 → 도구 실행 → 결과 피드백 → 반복

## 새로운 CLI 명령어

```bash
not-agent chat   # 단순 채팅 (도구 없음)
not-agent agent  # 에이전트 모드 (도구 사용)
not-agent ask    # 단일 질문
not-agent run    # 단일 태스크 실행 (도구 사용)
```

## 파일 구조
```
src/not_agent/
├── agent/
│   ├── __init__.py
│   ├── executor.py    # 도구 실행기
│   └── loop.py        # 에이전트 루프
├── tools/
│   ├── __init__.py    # 도구 등록
│   ├── base.py        # 베이스 클래스
│   ├── bash.py
│   ├── edit.py
│   ├── glob_tool.py
│   ├── grep.py
│   ├── read.py
│   └── write.py
├── llm/
│   └── claude.py
└── cli/
    └── main.py        # CLI (업데이트됨)
```

## 다음 단계 (Phase 3)
- [ ] 도구 실행 상태 표시 (어떤 도구를 사용 중인지)
- [ ] 스트리밍 출력
- [ ] 대화 컨텍스트 개선
- [ ] 사용자 확인 기능 (위험한 작업 전)
