import re
import json
import asyncio
from datetime import datetime
from urllib.parse import urlparse
from typing import Dict, Any, List, Tuple, Optional, Union, Type

import httpx
from bs4 import BeautifulSoup
from loguru import logger
from pydantic import HttpUrl
import logging
from sqlmodel import SQLModel
from pathlib import Path
import hashlib

from app.models.product import Product, ProductImage, ProductOption
from app.scraper.cache_manager import CacheManager
from app.scraper.amazon_scraper import AmazonScraper
from app.scraper.ebay_scraper import EbayScraper
from app.scraper.generic_scraper import GenericScraper
from app.scraper.vvic_scraper import VvicScraper
from app.scraper.base_scraper import BaseScraper


class ProductScraper(BaseScraper):
    """상품 페이지 스크레이퍼"""
    
    def __init__(self, use_cache: bool = True, cache_max_age_days: int = 7):
        """
        상품 스크레이퍼 초기화
        
        Args:
            use_cache (bool): 캐시 사용 여부, 기본값 True
            cache_max_age_days (int): 캐시 최대 보관 기간(일), 기본값 7일
        """
        super().__init__()
        # 로거 초기화
        self.logger = logging.getLogger(__name__)
        
        # 도메인별 스크레이퍼 매핑
        self._scrapers = {}
        self._domain_patterns = {
            r'amazon\.': AmazonScraper,
            r'ebay\.': EbayScraper,
            r'vvic\.': VvicScraper,
        }
    
    def _get_scraper_for_domain(self, domain: str) -> BaseScraper:
        """도메인에 맞는 스크레이퍼 인스턴스를 반환합니다."""
        if not domain:
            self.logger.warning("도메인이 비어 있어 기본 스크레이퍼를 사용합니다.")
            return self._get_or_create_scraper(GenericScraper)
            
        # 도메인이 문자열이 아닌 경우 안전하게 처리
        domain = str(domain).lower()
        
        # 도메인 패턴 매칭
        for pattern, scraper_class in self._domain_patterns.items():
            if re.search(pattern, domain):
                self.logger.debug(f"도메인 '{domain}'에 대한 스크레이퍼 '{scraper_class.__name__}' 선택")
                return self._get_or_create_scraper(scraper_class)
        
        # 매칭되는 도메인이 없는 경우 기본 스크레이퍼 사용
        self.logger.debug(f"알 수 없는 도메인, 기본 스크레이퍼 사용: {domain}")
        return self._get_or_create_scraper(GenericScraper)
    
    def _get_or_create_scraper(self, scraper_class: Type[BaseScraper]) -> BaseScraper:
        """스크레이퍼 인스턴스를 가져오거나 새로 생성합니다."""
        scraper_key = scraper_class.__name__
        if scraper_key not in self._scrapers:
            self._scrapers[scraper_key] = scraper_class()
            self.logger.debug(f"새로운 스크레이퍼 인스턴스 생성: {scraper_key}")
        return self._scrapers[scraper_key]
    
    async def scrape(self, url: str, force_refresh: bool = False) -> Product:
        """
        상품 정보를 스크래핑합니다.
        
        Args:
            url (str): 스크래핑할 상품 URL
            force_refresh (bool): 캐시를 무시하고 새로 수집할지 여부
            
        Returns:
            Product: 스크래핑된 상품 정보
        """
        try:
            # URL 분석 및 도메인 추출
            parsed_url = urlparse(url)
            domain = parsed_url.netloc.lower()
            
            # 도메인에 맞는 스크레이퍼 선택
            scraper = self._get_scraper_for_domain(domain)
            
            # 스크레이핑 실행 (force_refresh 전달)
            product = await scraper.scrape(url, force_refresh=force_refresh)
            if not product:
                raise ValueError("스크레이퍼가 None 결과를 반환했습니다.")
            
            return product
            
        except Exception as e:
            self.logger.error(f"상품 스크래핑 중 오류 발생: {str(e)} (파일: {__file__}, 줄: {e.__traceback__.tb_lineno})")
            raise
            
    def __del__(self):
        """소멸자: 비동기 클라이언트 연결 종료 시도"""
        logger.warning("ProductScraper 인스턴스가 소멸되었지만, 비동기 스크레이퍼는 정상적으로 닫히지 않았을 수 있습니다.") 