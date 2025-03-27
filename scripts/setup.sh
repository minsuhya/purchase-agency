#!/bin/bash

# 스크립트가 있는 디렉토리의 부모 디렉토리로 이동 (프로젝트 루트)
cd "$(dirname "$0")/.." || exit

# 색상 정의
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${GREEN}해외 상품 수집 프로토타입 설정 스크립트${NC}"
echo "---------------------------------------------"

# uv가 설치되어 있는지 확인
if ! command -v uv &> /dev/null; then
    echo -e "${RED}ERROR: uv가 설치되어 있지 않습니다.${NC}"
    echo -e "설치 방법: ${YELLOW}curl --proto '=https' --tlsv1.2 -sSf https://sh.uv.dev | sh${NC}"
    exit 1
fi

echo -e "${GREEN}uv 버전:${NC} $(uv --version)"

# 가상환경 생성
echo -e "\n${GREEN}가상환경 생성 중...${NC}"
uv venv

# 가상환경 활성화
echo -e "\n${GREEN}가상환경 활성화 중...${NC}"
source .venv/bin/activate

# 의존성 설치
echo -e "\n${GREEN}의존성 설치 중...${NC}"
uv pip install -r requirements.txt

# .env 파일 생성
if [ ! -f .env ]; then
    echo -e "\n${GREEN}.env 파일 생성 중...${NC}"
    cp .env.example .env
    echo -e "${YELLOW}주의: .env 파일을 수정하여 필요한 API 키를 설정하세요.${NC}"
else
    echo -e "\n${GREEN}.env 파일이 이미 존재합니다.${NC}"
fi

echo -e "\n${GREEN}설정 완료!${NC}"
echo "실행 방법: python run.py" 