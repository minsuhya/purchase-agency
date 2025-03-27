from fastapi import APIRouter, Request, Depends
from fastapi.responses import HTMLResponse
from pathlib import Path
from typing import List, Dict, Any
from app.utils.templates import get_templates

router = APIRouter()
templates = get_templates()

# 샘플 데이터 및 기능 소개
FEATURES = [
    {
        "title": "간편한 정보 수집",
        "description": "URL 입력만으로 상품 이름, 가격, 이미지, 설명 등 모든 정보를 자동으로 수집합니다.",
        "icon": "list"
    },
    {
        "title": "AI 자동 번역",
        "description": "상품 정보를 한국어로 자동 번역하여 보다 편리한 이해를 돕습니다.",
        "icon": "translate"
    },
    {
        "title": "데이터 내보내기",
        "description": "수집된 정보를 JSON 형식으로 내보내 다른 시스템과 쉽게 연동할 수 있습니다.",
        "icon": "download"
    }
]

# 지원하는 쇼핑몰 정보
SUPPORTED_SHOPS = [
    {"name": "Amazon", "examples": ["https://www.amazon.com/product/..."]},
    {"name": "eBay", "examples": ["https://www.ebay.com/itm/..."]},
    {"name": "기타 쇼핑몰", "examples": ["https://www.example.com/product/..."]}
]


def get_home_context() -> Dict[str, Any]:
    """홈페이지를 위한 컨텍스트 데이터를 제공합니다."""
    return {
        "features": FEATURES,
        "supported_shops": SUPPORTED_SHOPS,
        "stats": {
            "supported_shops": len(SUPPORTED_SHOPS),
            "data_points": "10+",
            "translation_accuracy": "95%"
        }
    }


@router.get("/", response_class=HTMLResponse)
async def home(request: Request, context: Dict[str, Any] = Depends(get_home_context)):
    """메인 홈페이지를 렌더링합니다."""
    return templates.TemplateResponse(
        "home.html", 
        {"request": request, **context}
    ) 