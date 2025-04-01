import sys
import re
import json
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime
from urllib.parse import urlparse, parse_qs

from bs4 import BeautifulSoup
from loguru import logger

from app.models.product import Product, ProductImage, ProductOption
from app.scraper.base_scraper import BaseScraper


class VvicScraper(BaseScraper):
    """VVIC 사이트 상품 페이지 스크레이퍼"""
    
    def __init__(self):
        """VVIC 스크레이퍼 초기화"""
        super().__init__()
        # VVIC 특화 헤더 추가
        self.headers["Referer"] = "https://www.vvic.com/"
        self.headers["Accept-Language"] = "ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7"
    
    async def scrape(self, url: str, force_refresh: bool = False) -> Product:
        """
        VVIC 상품 페이지에서 정보를 추출합니다.
        
        Args:
            url (str): 스크래핑할 상품 URL
            force_refresh (bool): 캐시를 무시하고 새로 수집할지 여부
            
        Returns:
            Product: 스크래핑된 상품 정보
        """
        try:
            logger.info(f"VVIC 상품 정보 스크래핑 시작: {url}")
            
            # 상품 ID 추출
            item_id = self._extract_item_id(url)
            if not item_id:
                raise ValueError(f"상품 ID를 URL에서 추출할 수 없습니다: {url}")
            
            # API URL 형식
            api_url = f"https://www.vvic.com/apif/item/{item_id}/detail?lang=ko"
            
            # 캐시 확인 (force_refresh가 True인 경우 캐시 무시)
            json_data = None
            if not force_refresh:
                cached_data = self._get_from_cache(api_url)
                if cached_data:
                    json_data = cached_data
                    logger.info(f"캐시된 데이터 사용: {url}")
            
            # 캐시된 데이터가 없거나 force_refresh가 True인 경우 API 호출
            if not json_data:
                logger.info(f"새로운 데이터 수집: {url}")
                response = await self.client.get(api_url, headers=self.headers)
                if response.status_code != 200:
                    raise Exception(f"VVIC API 접근 실패: HTTP {response.status_code}")
                
                # JSON 응답 파싱
                json_data = response.json()
                if json_data.get('code') != 200 or 'data' not in json_data:
                    raise Exception(f"VVIC API 응답 오류: {json_data.get('msg', '알 수 없는 오류')}")
                
                # 캐시에 저장
                self._save_to_cache(api_url, json_data)
            
            # 상품 데이터 추출
            product_data = json_data['data']
            
            # 기본 정보 추출
            title = product_data.get('title', '')
            price_text = product_data.get('price', '0')
            price_text, price_value = self._extract_price(price_text)

            # 브랜드 추출
            brand = self._extract_brand(product_data)
            
            # 이미지 추출
            images = self._extract_images(product_data)
            
            # 설명 추출
            description = self._extract_description(product_data)
            
            # 스펙 정보 추출
            specs = product_data.get('attrs_json', {})
            
            # 옵션 추출
            options = self._extract_options(product_data)
            
            # 카테고리 추출
            categories = [item['name'] for item in product_data.get('breadCrumbs', [])]
            
            # 배송 정보
            delivery_info = {
                'time': product_data.get('deliveryTime', ''),
                'tips': product_data.get('deliveryTimeTips', '')
            }
            
            # 상품 코드
            product_code = product_data.get('art_no', '')
            
            # 현재 시간
            current_time = datetime.utcnow()
            
            # Product 모델 생성
            product = Product(
                title_original=title,
                title_translated="",  # 번역 별도 처리
                url=url,
                price_original=price_text,
                price_value=price_value,
                price_krw=0.0,  # 환율 변환 별도 처리
                currency="CNY",
                description_original=description,
                description_translated="",  # 번역 별도 처리
                specifications_original=specs,
                specifications_translated={},  # 번역 별도 처리
                options_original=options,
                options_translated=[],  # 번역 별도 처리
                categories_original=categories,
                categories_translated=[],
                images=images,
                created_at=current_time,
                updated_at=current_time,
                raw_data={
                    "item_id": item_id,
                    "product_code": product_code,
                    "delivery_info": delivery_info,
                    "source": "vvic",
                    "scrape_date": current_time.isoformat(),
                    "original_data": product_data
                }
            )
            
            logger.info(f"VVIC 상품 정보 스크래핑 완료: {url}")
            return product
            
        except Exception as e:
            logger.error(f"VVIC 스크래핑 중 오류 발생: {str(e)}", exc_info=True)
            raise
    
    def _extract_item_id(self, url: str) -> Optional[str]:
        """URL에서 상품 ID 추출"""
        # 정규 표현식으로 추출 시도
        match = re.search(r'item/([^/\?#]+)', url)
        if match:
            return match.group(1)
        
        # URL 파싱으로 추출 시도
        parsed_url = urlparse(url)
        path_parts = parsed_url.path.split('/')
        
        for i, part in enumerate(path_parts):
            if part == 'item' and i + 1 < len(path_parts):
                return path_parts[i + 1]
        
        return None
    
    def _extract_images(self, product_data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """상품 이미지 URL 추출"""
        images = []
        
        # 메인 이미지
        if 'imgs' in product_data and product_data['imgs']:
            img_urls = product_data['imgs'].split(',')
            for i, img_url in enumerate(img_urls):
                if img_url:
                    if img_url.startswith('//'):
                        img_url = f"https:{img_url}"
                    images.append({
                        "url": img_url,
                        "alt": f"상품 이미지 {i+1}",
                        "is_main": i == 0
                    })
        
        # 색상별 이미지
        if 'color_pics' in product_data and product_data['color_pics']:
            for i, img_url in enumerate(product_data['color_pics']):
                if img_url and img_url not in [img['url'] for img in images]:
                    if img_url.startswith('//'):
                        img_url = f"https:{img_url}"
                    images.append({
                        "url": img_url,
                        "alt": f"색상 이미지 {i+1}",
                        "is_main": False
                    })
        
        return images
    
    def _extract_price(self, price_text: str) -> Tuple[str, float]:
        """가격 문자열에서 숫자만 추출"""
        try:
            # 숫자와 소수점만 추출
            price_str = re.sub(r'[^\d.]', '', str(price_text))
            if price_str:
                return price_text, float(price_str)
            return '0', 0.0
        except (ValueError, TypeError):
            logger.warning(f"가격 변환 실패: {price_text}")
            return '0', 0.0
    
    def _extract_options(self, product_data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """상품 옵션 추출"""
        options = []
        
        # 색상 옵션
        if 'color' in product_data and product_data['color']:
            colors = product_data['color'].split(',')
            options.append({
                "title": "색상",
                "option_values": colors,
                "is_required": True
            })
        
        # 사이즈 옵션
        if 'size' in product_data and product_data['size']:
            sizes = product_data['size'].split(',')
            options.append({
                "title": "사이즈",
                "option_values": sizes,
                "is_required": True
            })
        
        return options
    
    def _extract_description(self, product_data: Dict[str, Any]) -> str:
        """상품 설명 추출"""
        description_parts = []
        
        # 상품 설명
        if 'item_desc' in product_data:
            item_desc = product_data['item_desc']
            
            # HTML 설명
            if 'desc' in item_desc and item_desc['desc']:
                soup = BeautifulSoup(item_desc['desc'], 'lxml')
                desc_text = soup.get_text(separator='\n', strip=True)
                if desc_text:
                    description_parts.append(desc_text)
            
            # 태그 설명
            if 'tags_desc' in item_desc and item_desc['tags_desc']:
                soup = BeautifulSoup(item_desc['tags_desc'], 'lxml')
                tags_text = soup.get_text(separator='\n', strip=True)
                if tags_text:
                    description_parts.append(tags_text)
        
        # 배송 정보
        if 'deliveryTimeTips' in product_data:
            description_parts.append(f"배송 정보:\n{product_data['deliveryTimeTips']}")
        
        return "\n\n".join(description_parts)
    
    def _extract_brand(self, product_data: Dict[str, Any]) -> Optional[str]:
        """브랜드 정보 추출"""
        # attrs_json에서 브랜드 정보 추출
        if 'attrs_json' in product_data and product_data['attrs_json']:
            attrs = product_data['attrs_json']
            if '品牌' in attrs:
                return attrs['品牌']
        
        # 기본 브랜드 필드 확인
        if 'brand' in product_data and product_data['brand']:
            return product_data['brand']
        
        return None
    
