import asyncio
import os
import re
import json
from typing import Dict, Any, List, Tuple, Optional, Union
from abc import ABC, abstractmethod
from datetime import datetime, timedelta
import hashlib
from pathlib import Path

import httpx
from bs4 import BeautifulSoup
from loguru import logger

from app.models.product import Product, ProductImage, ProductOption


class BaseScraper(ABC):
    """스크레이퍼 기본 클래스"""
    
    def __init__(self, use_cache: bool = True, cache_max_age_days: int = 7):
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
        
        # 캐시 관련 설정 추가
        self.use_cache = use_cache
        self.cache_max_age_days = cache_max_age_days
        self.cache_dir = Path("data/cache")
        self.cache_dir.mkdir(parents=True, exist_ok=True)
    
    @abstractmethod
    async def scrape(self, url: str) -> Product:
        """
        URL에서 상품 정보를 추출하는 추상 메서드
        
        Args:
            url: 상품 URL
            
        Returns:
            Product: 추출된 상품 정보
        """
        pass
    
    def _extract_price(self, price_text: str) -> Tuple[str, float]:
        """가격 텍스트에서 가격 정보 추출"""
        try:
            if not price_text or price_text == "N/A":
                return price_text, 0.0
            
            # 문자열이 아닌 경우 처리
            if not isinstance(price_text, str):
                price_text = str(price_text)
            
            # 숫자와 소수점만 추출
            price_match = re.search(r'[\d,]+\.?\d*', price_text)
            if price_match:
                price_str = price_match.group().replace(',', '')
                return price_text, float(price_str)
            return price_text, 0.0
        except Exception as e:
            logger.error(f"가격 추출 오류: {str(e)}, 원본 텍스트: {price_text}")
            return price_text, 0.0
    
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
    
    def _extract_images(self, soup: BeautifulSoup) -> List[Dict[str, str]]:
        """이미지 정보 추출"""
        images = []
        try:
            # 이미지 요소 찾기
            img_elements = soup.select('img[src], img[data-src], img[data-original]')
            for img in img_elements:
                src = img.get('src') or img.get('data-src') or img.get('data-original')
                if src and not src.startswith('data:'):
                    alt = img.get('alt', '')
                    images.append({
                        "url": src,
                        "alt": alt
                    })
        except Exception as e:
            logger.error(f"이미지 추출 중 오류: {str(e)}")
        return images
    
    def _create_product(self, **kwargs) -> Product:
        """Product 모델 생성 헬퍼 메서드"""
        try:
            return Product(**kwargs)
        except Exception as e:
            logger.error(f"Product 모델 생성 중 오류: {str(e)}")
            raise
    
    def _normalize_url(self, url: str) -> str:
        """URL 정규화"""
        if not url.startswith(('http://', 'https://')):
            url = f"https://{url}"
        return url
    
    async def close(self):
        """클라이언트 리소스를 정리합니다."""
        if self.client:
            await self.client.aclose()
    
    def _get_cache_path(self, url: str) -> Path:
        """URL에 대한 캐시 파일 경로를 생성합니다."""
        url_hash = hashlib.md5(url.encode()).hexdigest()
        return self.cache_dir / f"{url_hash}.json"

    def _is_cache_valid(self, cache_path: Path) -> bool:
        """캐시 파일의 유효성을 검사합니다."""
        if not cache_path.exists():
            return False
            
        # 파일 수정 시간 확인
        mtime = datetime.fromtimestamp(cache_path.stat().st_mtime)
        age = datetime.now() - mtime
        return age.days <= self.cache_max_age_days

    def _get_from_cache(self, url: str) -> Optional[Dict[str, Any]]:
        """캐시에서 데이터를 가져옵니다."""
        if not self.use_cache:
            return None
            
        cache_path = self._get_cache_path(url)
        
        try:
            if self._is_cache_valid(cache_path):
                with cache_path.open('r', encoding='utf-8') as f:
                    data = json.load(f)
                    logger.info(f"캐시에서 데이터 로드: {url}")
                    return data
        except Exception as e:
            logger.error(f"캐시 로드 중 오류 발생: {str(e)}")
        return None

    def _save_to_cache(self, url: str, data: Dict[str, Any]) -> None:
        """데이터를 캐시에 저장합니다."""
        if not self.use_cache:
            return
            
        try:
            cache_path = self._get_cache_path(url)
            with cache_path.open('w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            logger.info(f"데이터 캐시 저장 완료: {url}")
        except Exception as e:
            logger.error(f"캐시 저장 중 오류 발생: {str(e)}")

    def __del__(self):
        """소멸자: 비동기 클라이언트 연결 종료 시도"""
        try:
            if hasattr(self, 'client') and self.client:
                logger.warning(f"{self.__class__.__name__} 인스턴스가 소멸되었지만, 비동기 클라이언트는 정상적으로 닫히지 않았을 수 있습니다.")
        except Exception as e:
            logger.error(f"소멸자 오류: {str(e)}")