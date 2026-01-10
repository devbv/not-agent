# 웹 도구 추가: WebSearch & WebFetch

## 완료일: 2026-01-10

## 개요
Phase 2에 웹 검색 및 웹 페이지 가져오기 기능을 추가하여 에이전트가 인터넷에서 정보를 검색하고 웹 페이지 내용을 분석할 수 있도록 개선했습니다.

## 추가된 도구

### 1. WebSearch (`tools/web_search.py`)
- **기능**: Claude API의 웹 검색 기능을 활용하여 인터넷 검색
- **파라미터**:
  - `query` (required): 검색할 쿼리 문자열
- **동작 방식**:
  1. Claude API에 `web_search` 도구를 활성화하여 요청
  2. 검색 결과를 자연어로 처리하여 반환
  3. 출처(Sources) 섹션 포함
- **사용 사례**:
  - 최신 기술 정보 검색
  - 라이브러리 문서 찾기
  - 에러 메시지 해결책 검색

### 2. WebFetch (`tools/web_fetch.py`)
- **기능**: URL에서 웹 페이지 내용을 가져와 LLM으로 분석
- **파라미터**:
  - `url` (required): 가져올 웹 페이지 URL
  - `prompt` (required): 페이지 내용에 대해 실행할 프롬프트
- **동작 방식**:
  1. requests로 웹 페이지 HTML 가져오기
  2. BeautifulSoup으로 HTML을 텍스트로 변환
  3. Claude Haiku로 텍스트 분석 및 프롬프트 처리
  4. 결과 반환
- **사용 사례**:
  - API 문서 읽기
  - 블로그 포스트 요약
  - 특정 정보 추출

## 추가된 의존성
```toml
dependencies = [
    # ... 기존 의존성
    "requests>=2.31.0",
    "beautifulsoup4>=4.12.0",
]
```

## 설계 결정사항

### WebSearch vs WebFetch
- **WebSearch**: 복잡한 검색, 최신 정보, 여러 출처 비교 시 사용
- **WebFetch**: 특정 URL의 내용을 분석할 때 사용

### 모델 선택
- **WebSearch**: `claude-sonnet-4-5` - 검색 결과 종합 능력 필요
- **WebFetch**: `claude-haiku-4-5` - 빠르고 비용 효율적, 텍스트 분석에 충분

### 에러 처리
- 의존성 누락 시 친절한 에러 메시지 (`pip install ...`)
- URL 검증 및 자동 HTTPS 업그레이드
- 타임아웃 설정 (30초)
- 큰 페이지 자동 잘림 (50,000자)

## 테스트
```bash
# 의존성 설치
source .venv/bin/activate
pip install -e .

# 도구 테스트 (format 확인)
python test_web_tools.py
```

## 파일 변경사항
- `src/not_agent/tools/web_search.py` (신규)
- `src/not_agent/tools/web_fetch.py` (신규)
- `src/not_agent/tools/__init__.py` (업데이트: 도구 등록)
- `pyproject.toml` (업데이트: 의존성 추가)
- `history/005_phase2_complete.md` (업데이트)
- `CLAUDE.md` (업데이트)

## 사용 예시

### WebSearch 사용 예시
```python
# 에이전트 모드에서
> "Python 3.13의 새로운 기능을 검색해줘"

# WebSearch 도구가 호출되어 최신 Python 3.13 정보 검색
```

### WebFetch 사용 예시
```python
# 에이전트 모드에서
> "https://docs.python.org/3/whatsnew/3.13.html 에서 주요 변경사항을 요약해줘"

# WebFetch 도구가 URL 내용을 가져와서 요약 제공
```

## 다음 단계
- [ ] 실제 에이전트 모드에서 웹 도구 테스트
- [ ] 캐시 기능 추가 (동일 URL 반복 요청 시 성능 개선)
- [ ] 리다이렉트 처리 개선
- [ ] PDF 파일 다운로드 및 분석 지원
