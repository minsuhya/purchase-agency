import os
import json
from typing import Dict, Any, List, Optional
from dotenv import load_dotenv

from openai import AsyncOpenAI
from loguru import logger

from app.models.product import Product

load_dotenv()  # .env 파일에서 환경 변수 로드

# OpenAI 클라이언트 초기화
client = AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))


async def translate_product_info(product: Product) -> Product:
    """상품 정보를 번역하고 처리합니다."""
    try:
        # 상품명 번역
        if product.title_original:
            product.title_translated = await translate_text(
                product.title_original, "상품명"
            )

        # 상품 설명 번역
        if product.description_original:
            product.description_translated = await translate_text(
                product.description_original, "상품 설명"
            )

        # 상품 스펙 번역
        if product.specifications_original:
            specs = product.specifications_original
            # 문자열인 경우 JSON으로 파싱
            if isinstance(specs, str):
                try:
                    specs = json.loads(specs)
                except json.JSONDecodeError:
                    logger.warning(f"스펙 JSON 파싱 실패: {specs}")
                    specs = {}
            
            # 전체 스펙을 JSON 문자열로 변환
            specs_str = json.dumps(specs, ensure_ascii=False)
            
            # 문자열 전체를 한 번에 번역
            translated_specs_str = await translate_text(specs_str, "상품 스펙")
            
            # 번역된 문자열을 다시 딕셔너리로 변환
            try:
                translated_specs = json.loads(translated_specs_str)
                # 유니코드 이스케이프 시퀀스를 실제 문자로 변환
                product.specifications_translated = json.loads(
                    json.dumps(translated_specs, ensure_ascii=False)
                )
            except json.JSONDecodeError:
                logger.error("스펙 JSON 파싱 실패")
                product.specifications_translated = specs

        # 상품 옵션 번역
        if product.options_original:
            # 옵션 리스트를 JSON 문자열로 변환
            options_str = json.dumps(product.options_original, ensure_ascii=False)
            
            # 문자열 번역
            translated_options_str = await translate_text(options_str, "상품 옵션")
            
            # 번역된 문자열을 다시 원래 타입(리스트)으로 변환
            try:
                translated_options = json.loads(translated_options_str)
                # 유니코드 이스케이프 시퀀스를 실제 문자로 변환
                product.options_translated = json.loads(
                    json.dumps(translated_options, ensure_ascii=False)
                )
            except json.JSONDecodeError:
                logger.error("옵션 JSON 파싱 실패")
                product.options_translated = product.options_original

        # 카테고리 번역
        if product.categories_original:
            # 카테고리 리스트를 JSON 문자열로 변환
            categories_str = json.dumps(product.categories_original, ensure_ascii=False)
            
            # 문자열 번역
            translated_categories_str = await translate_text(categories_str, "카테고리")
            
            # 번역된 문자열을 다시 원래 타입(리스트)으로 변환
            try:
                translated_categories = json.loads(translated_categories_str)
                # 유니코드 이스케이프 시퀀스를 실제 문자로 변환
                product.categories_translated = json.loads(
                    json.dumps(translated_categories, ensure_ascii=False)
                )   
            except json.JSONDecodeError:
                logger.error("카테고리 JSON 파싱 실패")
                product.categories_translated = product.categories_original

        # 원화 가격 계산
        if product.price_value:
            product.price_krw = await convert_to_krw(
                product.price_value, product.currency
            )

        return product
    
    except Exception as e:
        logger.error(f"상품 정보 번역 오류: {str(e)}")
        # 오류가 발생해도 원본 데이터 반환
        return product


async def translate_text(text: str, context: str = "") -> str:
    """AI를 사용하여 텍스트를 번역합니다."""
    if not text:
        return ""
    
    try:
        # OpenAI API를 사용한 번역 (v1.0 형식)
        response = await client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": "당신은 전문 번역가입니다. 한국어 그대로 번역해주세요."},
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