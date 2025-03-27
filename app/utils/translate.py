import os
import json
from typing import Dict, Any, List, Optional
from dotenv import load_dotenv

from openai import AsyncOpenAI
from loguru import logger

from app.models.product import ProductInfo

load_dotenv()  # .env 파일에서 환경 변수 로드

# OpenAI 클라이언트 초기화
client = AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))


async def translate_product_info(product_info: ProductInfo) -> ProductInfo:
    """상품 정보를 번역하고 처리합니다."""
    # 번역할 데이터 준비
    try:
        # 상품명 번역
        if product_info.title.get("original"):
            product_info.title["translated"] = await translate_text(
                product_info.title["original"], "상품명"
            )
        
        # 상품 설명 번역
        if product_info.description.get("original"):
            product_info.description["translated"] = await translate_text(
                product_info.description["original"], "상품 설명"
            )
        
        # 상품 스펙 번역
        if product_info.specifications and product_info.specifications.get("original"):
            translated_specs = {}
            for key, value in product_info.specifications["original"].items():
                translated_key = await translate_text(key, "스펙 키")
                translated_value = await translate_text(value, "스펙 값")
                translated_specs[translated_key] = translated_value
            
            product_info.specifications["translated"] = translated_specs
        
        # 원화 가격 계산
        if product_info.price and product_info.price.get("value"):
            product_info.price["krw"] = await convert_to_krw(
                product_info.price["value"], product_info.currency
            )
        
        return product_info
    
    except Exception as e:
        logger.error(f"상품 정보 번역 오류: {str(e)}")
        # 오류가 발생해도 원본 데이터 반환
        return product_info


async def translate_text(text: str, context: str = "") -> str:
    """AI를 사용하여 텍스트를 번역합니다."""
    if not text:
        return ""
    
    try:
        # OpenAI API를 사용한 번역 (v1.0 형식)
        response = await client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": "당신은 전문 번역가입니다. 한국어로 자연스럽게 번역해주세요."},
                {"role": "user", "content": f"다음 {context}을 한국어로 번역해주세요: {text}"}
            ],
            temperature=0.3,
            max_tokens=1000
        )
        
        translated_text = response.choices[0].message.content
        return translated_text.strip()
    
    except Exception as e:
        logger.error(f"번역 오류: {str(e)}")
        return text  # 오류 시 원본 텍스트 반환


async def convert_to_krw(price: float, currency: str) -> float:
    """외화를 원화로 변환합니다."""
    # 실제 프로덕션에서는 환율 API를 사용할 것
    # 프로토타입에서는 간단한 하드코딩된 환율 사용
    exchange_rates = {
        "USD": 1375.0,
        "EUR": 1500.0,
        "JPY": 9.0,
        "GBP": 1750.0,
        "AUD": 900.0,
        "CAD": 1000.0,
        "CNY": 190.0,
        "HKD": 175.0,
        "KRW": 1.0,
    }
    
    rate = exchange_rates.get(currency, 1.0)
    return round(price * rate, 2) 