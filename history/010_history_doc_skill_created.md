# History-Doc Skill Created

**작성일**: 2026-01-10
**목표**: 히스토리 파일 번호 중복 문제 해결

## 문제점

Claude가 히스토리 파일을 작성할 때 번호를 중복으로 사용하는 문제가 발생했습니다.
- 예: 007번이 두 개 존재

## 해결 방법

`history-doc` 스킬을 생성하여 자동으로 다음 번호를 찾도록 구현했습니다.

### 스킬 구성

```
.claude/skills/history-doc/
├── SKILL.md                        # 스킬 문서
└── scripts/
    └── get_next_number.py          # 다음 번호 찾기 스크립트
```

### 주요 기능

1. **자동 번호 찾기**
   - history/ 폴더의 모든 파일 스캔
   - `XXX_*.md` 패턴 매칭
   - 최대값 + 1 반환

2. **스킬 통합**
   - `/history-doc` 명령어로 스킬 로드
   - 히스토리 파일 작성 시 자동으로 사용

### 사용법

```bash
# 다음 번호 확인
python3 .claude/skills/history-doc/scripts/get_next_number.py

# 파일 생성
# 반환된 번호(예: 010)로 파일 작성
```

## 결과

- ✅ 번호 중복 방지
- ✅ 일관된 파일명 형식
- ✅ 자동화된 워크플로우
- ✅ 재사용 가능한 스킬

## 패키징

스킬은 `.skill` 파일로 패키징되어 배포 가능:
- `history-doc.skill` (루트 디렉토리에 생성됨)
