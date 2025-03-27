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

from app.models.product import ProductInfo, ProductImage, ProductOption
from app.utils.cache_manager import CacheManager
from app.utils.amazon_scraper import AmazonScraper
from app.utils.ebay_scraper import EbayScraper
from app.utils.generic_scraper import GenericScraper
from app.utils.vvic_scraper import VvicScraper
from app.utils.base_scraper import BaseScraper


class ProductScraper:
    """
    상품 스크레이퍼 - 여러 사이트를 지원하는 팩토리 클래스
    특정 도메인에 맞는 스크레이퍼를 반환하고 캐싱 기능을 제공합니다.
    """
    
    def __init__(self, use_cache: bool = True, cache_max_age_days: int = 7):
        """
        상품 스크레이퍼 초기화
        
        Args:
            use_cache (bool): 캐시 사용 여부, 기본값 True
            cache_max_age_days (int): 캐시 최대 보관 기간(일), 기본값 7일
        """
        # 캐시 관련 속성 설정
        self.use_cache = use_cache
        self.cache_max_age_days = cache_max_age_days
        self.cache_manager = CacheManager()
        
        # 도메인별 스크레이퍼 초기화
        self._scrapers = {}
    
    async def scrape_product(self, url: str, force_refresh: bool = False) -> ProductInfo:
        """
        주어진 URL에서 상품 정보를 추출합니다.
        
        Args:
            url (str): 상품 URL
            force_refresh (bool): 캐시가 있더라도 강제로 새로 가져올지 여부, 기본값 False
            
        Returns:
            ProductInfo: 추출된 상품 정보
        """
        if not url:
            logger.error("URL이 비어 있습니다.")
            raise ValueError("URL이 비어 있습니다.")
        
        try:
            # URL을 문자열로 변환 및 공백 제거
            url = str(url).strip()
            
            # 캐시 확인 (use_cache가 True이고 force_refresh가 False인 경우)
            if self.use_cache and not force_refresh and self.cache_manager.has_cache(url, self.cache_max_age_days):
                cached_data = self.cache_manager.get_cache(url)
                if cached_data:
                    logger.info(f"캐시에서 상품 정보 로드: {url}")
                    return self._create_product_info_from_cache(cached_data)
            
            # URL 분석 및 도메인 추출
            parsed_url = urlparse(url)
            domain = parsed_url.netloc.lower()
            
            if not domain:
                logger.error(f"유효하지 않은 URL 형식: {url}")
                raise ValueError("유효하지 않은 URL 형식입니다.")
            
            # 도메인에 따라 적절한 스크레이퍼 선택
            scraper = self._get_scraper_for_domain(domain)
            logger.info(f"도메인 '{domain}'에 대한 스크레이퍼 '{scraper.__class__.__name__}' 선택")
            
            # 스크레이핑 실행
            product_info = await scraper.scrape(url)
            
            # 결과 검증
            if not product_info:
                logger.error("스크레이퍼가 None 결과를 반환했습니다.")
                raise ValueError("상품 정보를 가져오지 못했습니다.")
            
            # 캐시 저장 (use_cache가 True인 경우)
            if self.use_cache and product_info:
                self._save_to_cache(url, product_info)
            
            return product_info
        
        except Exception as e:
            logger.error(f"상품 스크래핑 중 오류 발생: {str(e)}", exc_info=True)
            raise Exception(f"상품 정보 수집 실패: {str(e)}")
    
    def _get_scraper_for_domain(self, domain: str) -> BaseScraper:
        """도메인에 맞는 스크레이퍼 인스턴스를 반환합니다."""
        if not domain:
            logger.warning("도메인이 비어 있어 기본 스크레이퍼를 사용합니다.")
            return self._get_or_create_scraper(GenericScraper)
            
        # 도메인이 문자열이 아닌 경우 안전하게 처리
        domain = str(domain).lower()
        
        # 도메인별 스크레이퍼 매핑
        if "amazon" in domain:
            logger.debug(f"Amazon 도메인 감지: {domain}")
            return self._get_or_create_scraper(AmazonScraper)
        elif "ebay" in domain:
            logger.debug(f"eBay 도메인 감지: {domain}")
            return self._get_or_create_scraper(EbayScraper)
        elif "vvic" in domain:
            logger.debug(f"VVIC 도메인 감지: {domain}")
            return self._get_or_create_scraper(VvicScraper)
        else:
            logger.debug(f"알 수 없는 도메인, 기본 스크레이퍼 사용: {domain}")
            return self._get_or_create_scraper(GenericScraper)
    
    def _get_or_create_scraper(self, scraper_class: Type[BaseScraper]) -> BaseScraper:
        """스크레이퍼 인스턴스를 가져오거나 새로 생성합니다."""
        scraper_key = scraper_class.__name__
        if scraper_key not in self._scrapers:
            self._scrapers[scraper_key] = scraper_class()
        return self._scrapers[scraper_key]
    
    def _save_to_cache(self, url: str, product_info: ProductInfo) -> bool:
        """제품 정보를 캐시에 저장"""
        if not self.use_cache or not self.cache_manager:
            return False
            
        try:
            product_dict = self._product_info_to_dict(product_info)
            return self.cache_manager.save_cache(url, product_dict)
        except Exception as e:
            logger.error(f"캐시 저장 중 오류 발생: {str(e)}", exc_info=True)
            return False
    
    def _product_info_to_dict(self, product_info: ProductInfo) -> Dict[str, Any]:
        """ProductInfo 객체를 안전하게 dictionary로 변환합니다."""
        try:
            # Pydantic v2
            result = product_info.model_dump()
        except AttributeError:
            try:
                # Pydantic v1
                result = product_info.dict()
            except AttributeError:
                # 최후의 방법: 직접 변환
                result = self._manual_convert_to_dict(product_info)
                return result
        
        # HttpUrl 객체를 문자열로 변환
        self._convert_httpurls_to_str(result)
        return result
    
    def _convert_httpurls_to_str(self, data: Dict[str, Any]) -> None:
        """딕셔너리 내의 HttpUrl 객체를 문자열로 변환합니다. (in-place)"""
        if not data or not isinstance(data, dict):
            return
            
        # URL 문자열 변환
        if 'url' in data:
            data['url'] = str(data['url'])
            
        # 메인 이미지 URL 변환
        if 'main_image' in data and data['main_image'] and 'url' in data['main_image']:
            data['main_image']['url'] = str(data['main_image']['url'])
            
        # 이미지 배열 내 URL 변환
        if 'images' in data and data['images']:
            for img in data['images']:
                if 'url' in img:
                    img['url'] = str(img['url'])
    
    def _manual_convert_to_dict(self, obj: Any) -> Union[Dict[str, Any], List, Any]:
        """객체를 딕셔너리로 직접 변환합니다."""
        if isinstance(obj, HttpUrl):
            return str(obj)
            
        if hasattr(obj, "__dict__") and not isinstance(obj, (str, int, float, bool, type(None))):
            result = {}
            for key, value in obj.__dict__.items():
                if not key.startswith("_"):
                    if isinstance(value, list):
                        result[key] = [self._manual_convert_to_dict(item) for item in value]
                    elif hasattr(value, "__dict__") and not isinstance(value, (str, int, float, bool, type(None))):
                        result[key] = self._manual_convert_to_dict(value)
                    else:
                        result[key] = value
            return result
        elif isinstance(obj, list):
            return [self._manual_convert_to_dict(item) for item in obj]
        elif hasattr(obj, "__str__"):
            return str(obj)
        else:
            return obj
    
    def _create_product_info_from_cache(self, cached_data: Dict[str, Any]) -> ProductInfo:
        """캐시 데이터로부터 ProductInfo 객체 생성"""
        try:
            # 캐시된 데이터가 API 응답 형식인 경우 ('data' 키가 있는 경우)
            if 'data' in cached_data:
                product_data = cached_data['data']
            else:
                product_data = cached_data

            # 이미지 객체 생성
            main_image = None
            if "main_image" in product_data and product_data["main_image"]:
                main_image_data = product_data["main_image"]
                main_image = ProductImage(
                    url=main_image_data.get("url", ""),
                    alt=main_image_data.get("alt", "")
                )
            else:
                # main_image가 없는 경우 기본 이미지 생성
                main_image = ProductImage(
                    url="https://via.placeholder.com/400x400?text=No+Image",
                    alt="No Image Available"
                )
            
            # 이미지 목록 생성
            images = []
            if "images" in product_data and product_data["images"]:
                for img_data in product_data["images"]:
                    if isinstance(img_data, dict):
                        images.append(ProductImage(
                            url=img_data.get("url", ""),
                            alt=img_data.get("alt", "")
                        ))
                    elif isinstance(img_data, str):
                        images.append(ProductImage(
                            url=img_data,
                            alt=f"Product Image"
                        ))
            
            # 옵션 목록 생성
            options = []
            if "options" in product_data and product_data["options"]:
                for opt_data in product_data["options"]:
                    if isinstance(opt_data, dict):
                        title = opt_data.get("title", "")
                        values = opt_data.get("values", [])
                        if title and values and isinstance(values, list):
                            options.append(ProductOption(
                                title=title,
                                option_values=values
                            ))
            
            # raw_data 준비 및 캐시 표시
            raw_data = product_data.get("raw_data", {}) or {}
            if not isinstance(raw_data, dict):
                raw_data = {}
            
            # 캐시에서 로드했음을 표시
            raw_data["from_cache"] = True
            
            # created_at 처리
            created_at = product_data.get("created_at")
            if isinstance(created_at, int):
                # Unix timestamp를 ISO 형식 문자열로 변환
                created_at = datetime.fromtimestamp(created_at).isoformat()
            elif not created_at:
                created_at = datetime.now().isoformat()
            
            # ProductInfo 객체 생성 및 반환
            return ProductInfo(
                title=product_data.get("title", {"original": "", "translated": ""}),
                brand=product_data.get("brand"),
                url=product_data.get("url", ""),
                price=product_data.get("price", {"original": "", "value": 0, "krw": None}),
                currency=product_data.get("currency", "CNY"),
                main_image=main_image,
                images=images,
                description=product_data.get("description", {"original": "", "translated": ""}),
                specifications=product_data.get("specifications", {"original": {}, "translated": {}}),
                options=options,
                categories=product_data.get("categories", []),
                created_at=created_at,
                raw_data=raw_data
            )
            
        except Exception as e:
            logger.error(f"캐시 데이터로부터 ProductInfo 생성 중 오류 발생: {str(e)}", exc_info=True)
            raise
    
    async def close(self):
        """모든 스크레이퍼 리소스를 정리합니다."""
        for scraper_name, scraper in self._scrapers.items():
            try:
                await scraper.close()
                logger.debug(f"{scraper_name} 정리 완료")
            except Exception as e:
                logger.error(f"{scraper_name} 정리 중 오류 발생: {str(e)}")
    
    # 캐시 관리 메서드
    def clear_cache(self, url: Optional[str] = None) -> bool:
        """
        캐시를 삭제합니다.
        url이 None이면 모든 캐시를 삭제하고, 그렇지 않으면 지정된 URL의 캐시만 삭제합니다.
        """
        return self.cache_manager.clear_cache(url)
    
    def get_cache_list(self) -> List[str]:
        """
        캐싱된 모든 URL 목록을 반환합니다.
        """
        urls = []
        try:
            # 캐시 디렉토리가 존재하는지 확인
            if not self.cache_manager.cache_dir.exists():
                return []
                
            # 캐시 파일 목록 가져오기
            cache_files = list(self.cache_manager.cache_dir.glob("*.json"))
            
            # 각 캐시 파일에서 URL 추출
            for cache_file in cache_files:
                try:
                    with open(cache_file, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                        if isinstance(data, dict) and 'url' in data:
                            urls.append(str(data['url']))
                except Exception as e:
                    logger.error(f"캐시 파일 {cache_file.name} 읽기 오류: {str(e)}")
                    continue
            
            return urls
        except Exception as e:
            logger.error(f"캐시 목록 조회 중 오류 발생: {str(e)}")
            return []
            
    def __del__(self):
        """소멸자: 비동기 클라이언트 연결 종료 시도"""
        logger.warning("ProductScraper 인스턴스가 소멸되었지만, 비동기 스크레이퍼는 정상적으로 닫히지 않았을 수 있습니다.") 