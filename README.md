# 해외 상품 수집 프로토타입

해외 쇼핑몰의 상품 정보를 수집하고 번역하는 웹 애플리케이션 프로토타입입니다.

## 주요 기능

- 해외 쇼핑몰 상품 URL을 입력하면 상품 정보를 자동으로 수집
- 원문과 번역된 정보를 함께 제공
- 수집된 데이터를 JSON 형식으로 내보내기
- AI를 활용한 자동 번역

## 수집 가능한 상품 정보

1. 상품 기본 정보:
   - 상품명 (원문 및 번역/수정된 버전)
   - 브랜드
   - SKU (상품 고유번호)
   - 상품 상세페이지 URL
   - 가격 (현지 가격 및 원화 환산 가격)
   - 배송비
   - 재고량
   - 통화 정보
   - 상품 상태 (새상품, 중고, 리퍼 등)

2. 카테고리 정보:
   - 원문 사이트의 카테고리

3. 이미지 데이터:
   - 상품 대표 이미지
   - 상품 전체 이미지 세트

4. 상세 설명:
   - 상품 설명 (원문 및 번역된 버전)
   - 상품 스펙 정보 (원문 및 번역된 버전)

5. 옵션 정보:
   - 옵션 타이틀
   - 옵션 리스트
   - 조합된 옵션 정보

## 기술 스택

- **백엔드**: Python, FastAPI
- **프론트엔드**: HTML, CSS, JavaScript, Tailwindcss
- **템플릿 엔진**: Jinja2
- **데이터 처리**: BeautifulSoup4, httpx
- **AI 번역**: OpenAI API
- **패키지 관리**: uv

## 설치 및 실행 방법

### 사전 요구사항

- Python 3.8 이상
- [uv](https://github.com/astral-sh/uv) 패키지 관리자

uv 설치 방법:
```bash
# Linux/macOS
curl --proto '=https' --tlsv1.2 -sSf https://sh.uv.dev | sh

# Windows PowerShell
powershell -c "irm https://windows.uv.dev | iex"
```

### 설치 및 실행

1. 저장소 클론
   ```bash
   git clone https://github.com/yourusername/purchase-agency-prototype.git
   cd purchase-agency-prototype
   ```

2. 가상환경 생성 및 의존성 설치
   ```bash
   # 가상환경 생성
   uv venv

   # 가상환경 활성화
   source .venv/bin/activate  # Linux/macOS
   # 또는
   .venv\Scripts\activate  # Windows
   
   # 의존성 설치
   uv pip install -r requirements.txt
   ```

3. 환경 변수 설정
   ```bash
   cp .env.example .env
   # .env 파일을 편집하여 API 키 등 필요한 값 설정
   ```

4. 애플리케이션 실행
   ```bash
   # FastAPI CLI를 사용하여 애플리케이션 실행
   uv run fastapi dev
   ```

5. 웹 브라우저에서 http://localhost:8000 접속

### 추가 실행 방법

FastAPI CLI 외에도 다음과 같은 방법으로 애플리케이션을 실행할 수 있습니다:

```bash
# 방법 1: 모듈로 직접 실행
uv run -m app.main

# 방법 2: start 함수 직접 호출
uv run app.main:start

# 방법 3: Uvicorn으로 직접 실행
uv run uvicorn app.main:app --reload
```

## 개발 환경 관리

새 패키지 추가:
```bash
uv pip install 패키지명
```

requirements.txt 업데이트:
```bash
uv pip freeze > requirements.txt
```

패키지 일괄 업데이트:
```bash
uv pip sync requirements.txt
```

## 지원하는 쇼핑몰

현재 아래 쇼핑몰에서 상품 정보 수집을 지원합니다:
- Amazon
- eBay
- 기타 일반적인 쇼핑몰(제한된 정보만 수집 가능)

## 라이센스

MIT 