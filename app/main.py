import os
import sys
from pathlib import Path

import uvicorn
from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

# 환경 변수 로드
load_dotenv()

# .env 파일이 있는지 확인하고 경고 메시지 출력
env_file = Path(".env")

# FastAPI 애플리케이션 생성 및 설정
app = FastAPI(
    title="해외 상품 수집 프로토타입",
    description="해외 쇼핑몰의 상품 정보를 수집하고 번역하는 웹 애플리케이션",
    version="0.1.0",
)

# 정적 파일 및 템플릿 설정
app.mount("/static", StaticFiles(directory=Path("app/static")), name="static")

# 템플릿 설정
from app.utils.templates import get_templates, setup_templates
templates = get_templates()
setup_templates(templates)

# 라우터 모듈 import
from app.routers import product_router, home_router

# 라우터 포함
app.include_router(home_router.router)  # 홈 라우터를 먼저 등록
app.include_router(product_router.router)

if __name__ == "__main__":
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
