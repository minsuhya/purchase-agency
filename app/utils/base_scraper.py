import asyncio
import re
import json
from typing import Dict, Any, List, Tuple, Optional, Union
from abc import ABC, abstractmethod
from datetime import datetime

import httpx
from bs4 import BeautifulSoup
from loguru import logger

from app.models.product import ProductInfo, ProductImage, ProductOption


class BaseScraper(ABC):
    """스크레이퍼 기본 클래스"""
    
    def __init__(self):
        """스크레이퍼 초기화"""
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
            "Accept-Language": "en-US,en;q=0.9",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
            "Accept-Encoding": "gzip, deflate, br",
            "Connection": "keep-alive",
            "Cache-Control": "max-age=0",
            "Upgrade-Insecure-Requests": "1",
            "sec-ch-ua": '"Google Chrome";v="123", "Not:A-Brand";v="8", "Chromium";v="123"',
            "sec-ch-ua-mobile": "?0",
            "sec-ch-ua-platform": '"Windows"',
        }
        self.client = httpx.AsyncClient(timeout=30.0, follow_redirects=True)
    
    @abstractmethod
    async def scrape(self, url: str) -> ProductInfo:
        """
        URL에서 상품 정보를 추출하는 추상 메서드
        
        Args:
            url: 상품 URL
            
        Returns:
            ProductInfo: 추출된 상품 정보
        """
        pass
    
    def _extract_price(self, price_text: str) -> float:
        """가격 문자열에서 숫자만 추출합니다."""
        try:
            if not price_text or price_text == "N/A":
                return 0.0
            
            # 문자열이 아닌 경우 처리
            if not isinstance(price_text, str):
                price_text = str(price_text)
            
            # 통화 기호 및 쉼표 제거
            price_str = re.sub(r'[^\d.]', '', price_text)
            if price_str:
                return float(price_str)
            return 0.0
        except Exception as e:
            logger.error(f"가격 추출 오류: {str(e)}, 원본 텍스트: {price_text}")
            return 0.0
    
    def _extract_currency(self, price_text: str) -> str:
        """가격 문자열에서 통화 정보를 추출합니다."""
        currency_map = {
            "$": "USD",
            "£": "GBP",
            "€": "EUR",
            "¥": "JPY",
            "₩": "KRW",
            "₹": "INR",
            "₽": "RUB",
            "฿": "THB",
            "A$": "AUD",
            "C$": "CAD",
        }
        
        for symbol, code in currency_map.items():
            if symbol in price_text:
                return code
        
        # 기본값은 USD
        return "USD"
    
    async def close(self):
        """클라이언트 리소스를 정리합니다."""
        if self.client:
            await self.client.aclose()
    
    def __del__(self):
        """소멸자: 비동기 클라이언트 연결 종료 시도"""
        try:
            if hasattr(self, 'client') and self.client:
                # close는 코루틴이므로 직접 호출할 수 없음, 경고만 출력
                logger.warning(f"{self.__class__.__name__} 인스턴스가 소멸되었지만, 비동기 클라이언트는 정상적으로 닫히지 않았을 수 있습니다.")
        except Exception as e:
            logger.error(f"소멸자 오류: {str(e)}") 