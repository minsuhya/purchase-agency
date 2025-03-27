import re
import json
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime
from urllib.parse import urlparse, parse_qs

from bs4 import BeautifulSoup
from loguru import logger

from app.models.product import ProductInfo, ProductImage, ProductOption
from app.utils.base_scraper import BaseScraper


class VvicScraper(BaseScraper):
    """VVIC 사이트 상품 페이지 스크레이퍼"""
    
    def __init__(self):
        """VVIC 스크레이퍼 초기화"""
        super().__init__()
        # VVIC 특화 헤더 추가
        self.headers["Referer"] = "https://www.vvic.com/"
        self.headers["Accept-Language"] = "ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7"
    
    async def scrape(self, url: str) -> ProductInfo:
        """
        VVIC 상품 페이지에서 정보를 추출합니다.
        
        Args:
            url (str): VVIC 상품 URL
            
        Returns:
            ProductInfo: 추출된 상품 정보
        """
        try:
            logger.info(f"VVIC 상품 정보 스크래핑 시작: {url}")
            
            # 상품 ID 추출
            item_id = self._extract_item_id(url)
            if not item_id:
                raise ValueError(f"상품 ID를 URL에서 추출할 수 없습니다: {url}")
            
            # API URL 형식
            api_url = f"https://www.vvic.com/apif/item/{item_id}/detail?lang=ko"
            logger.debug(f"API URL: {api_url}")
            
            # API 호출
            response = await self.client.get(api_url, headers=self.headers)
            
            if response.status_code != 200:
                logger.error(f"VVIC API 응답 오류: HTTP {response.status_code}")
                raise Exception(f"VVIC API 접근 실패: HTTP {response.status_code}")
            
            # JSON 응답 파싱
            json_data = response.json()
            
            if json_data.get('code') != 200 or 'data' not in json_data:
                logger.error(f"VVIC API 응답 오류: {json_data.get('msg', '알 수 없는 오류')}")
                raise Exception(f"VVIC API 응답 오류: {json_data.get('msg', '알 수 없는 오류')}")
            
            # 상품 데이터 추출
            product_data = json_data['data']
            
            # 기본 정보 추출
            title = product_data.get('title', 'Unknown Product')
            
            # 가격 정보 추출
            price_text = product_data.get('price', 'N/A')
            price_value = self._extract_price(price_text)
            
            # 이미지 추출
            images = self._extract_images(product_data)
            main_image = None
            image_gallery = []
            
            if images and len(images) > 0:
                main_image = ProductImage(url=images[0], alt=title)
                for i in range(1, len(images)):
                    image_gallery.append(ProductImage(url=images[i], alt=f"{title} - {i}"))
            
            # 상품 설명 추출
            description = self._extract_description(product_data)
            
            # 스펙 정보 추출
            specs = self._extract_specs(product_data)
            
            # 옵션 추출
            options = self._extract_options(product_data)
            
            # 카테고리 추출
            categories = self._extract_categories(product_data)
            
            # ProductInfo 객체 생성
            product_info = ProductInfo(
                title={"original": title, "translated": ""},
                brand=product_data.get('brand'),
                url=url,
                price={
                    "original": price_text,
                    "value": price_value,
                    "krw": None  # 환율 계산은 별도로 처리
                },
                currency="CNY",  # VVIC는 기본적으로 중국 위안화(CNY)
                main_image=main_image,
                images=image_gallery,
                description={"original": description, "translated": ""},
                specifications={"original": specs, "translated": {}},
                options=options,
                categories=categories,
                created_at=datetime.now().isoformat()
            )
            
            # 추가 정보 (raw_data)에 포함
            raw_data = {
                "item_id": item_id,
                "product_code": product_data.get('art_no'),
                "vvic_data": product_data,  # VVIC 원본 데이터 전체 저장
                "source": "vvic",
                "scrape_date": datetime.now().isoformat()
            }
            
            product_info.raw_data = raw_data
            
            logger.info(f"VVIC 상품 정보 스크래핑 완료: {url}")
            return product_info
        
        except Exception as e:
            logger.error(f"VVIC 스크래핑 중 오류 발생: {str(e)}", exc_info=True)
            raise Exception(f"VVIC 상품 정보 수집 실패: {str(e)}")
    
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
    
    def _extract_images(self, product_data: Dict[str, Any]) -> List[str]:
        """상품 이미지 URL 추출"""
        images = []
        
        # 메인 이미지 추출
        if 'imgs' in product_data and product_data['imgs']:
            img_urls = product_data['imgs'].split(',')
            for img_url in img_urls:
                if img_url:
                    # URL 형식 확인 및 수정
                    if img_url.startswith('//'):
                        img_url = f"https:{img_url}"
                    images.append(img_url)
        
        # 색상별 이미지 추출
        if 'color_pics' in product_data and product_data['color_pics']:
            for img_url in product_data['color_pics']:
                if img_url and img_url not in images:
                    # URL 형식 확인 및 수정
                    if img_url.startswith('//'):
                        img_url = f"https:{img_url}"
                    images.append(img_url)
        
        return images
    
    def _extract_price(self, price_text: str) -> float:
        """가격 문자열에서 숫자만 추출"""
        try:
            # 숫자와 소수점만 추출
            price_str = re.sub(r'[^\d.]', '', str(price_text))
            if price_str:
                return float(price_str)
            return 0.0
        except (ValueError, TypeError):
            logger.warning(f"가격 변환 실패: {price_text}")
            return 0.0
    
    def _extract_description(self, product_data: Dict[str, Any]) -> str:
        """상품 설명 추출"""
        description_parts = []
        
        # 기본 설명 추출
        if product_data.get('desc'):
            description_parts.append(str(product_data['desc']))
        
        # 상세 설명 추출
        if 'item_desc' in product_data and product_data['item_desc']:
            item_desc = product_data['item_desc']
            
            # HTML 설명 추출
            if 'desc' in item_desc and item_desc['desc']:
                # HTML 태그 제거
                soup = BeautifulSoup(item_desc['desc'], 'lxml')
                desc_text = soup.get_text(separator='\n', strip=True)
                if desc_text:
                    description_parts.append(desc_text)
            
            # 태그 설명 추출
            if 'tags_desc' in item_desc and item_desc['tags_desc']:
                soup = BeautifulSoup(item_desc['tags_desc'], 'lxml')
                tags_text = soup.get_text(separator='\n', strip=True)
                if tags_text:
                    description_parts.append("상품 태그:\n" + tags_text)
        
        # 속성 정보를 설명에 추가
        if 'attrs_json' in product_data and product_data['attrs_json']:
            attrs = product_data['attrs_json']
            if isinstance(attrs, dict):
                attrs_text = "\n".join([f"{k}: {v}" for k, v in attrs.items()])
                if attrs_text:
                    description_parts.append("\n상품 속성:\n" + attrs_text)
        
        return "\n\n".join(description_parts)
    
    def _extract_specs(self, product_data: Dict[str, Any]) -> Dict[str, str]:
        """상품 스펙 정보 추출"""
        specs = {}
        
        # 속성 정보 추출
        if 'attrs_json' in product_data and product_data['attrs_json']:
            specs.update(product_data['attrs_json'])
        
        # 추가 정보
        additional_fields = ['art_no', 'deliveryTime']
        for field in additional_fields:
            if field in product_data and product_data[field]:
                field_name = {
                    'art_no': '상품코드',
                    'deliveryTime': '배송시간'
                }.get(field, field)
                specs[field_name] = product_data[field]
        
        return specs
    
    def _extract_options(self, product_data: Dict[str, Any]) -> List[ProductOption]:
        """상품 옵션 추출"""
        options = []
        
        # options 필드에서 옵션 정보 추출
        if 'options' in product_data and isinstance(product_data['options'], list):
            for option in product_data['options']:
                if isinstance(option, dict):
                    title = option.get('title', '')
                    values = option.get('values', [])
                    
                    if title and values and isinstance(values, list):
                        options.append(ProductOption(
                            title=title,
                            option_values=values
                        ))
        
        # 디버그 로깅
        logger.debug(f"추출된 옵션: {options}")
        
        return options
    
    def _extract_categories(self, product_data: Dict[str, Any]) -> List[str]:
        """카테고리 정보 추출"""
        categories = []
        
        # 카테고리 정보가 있는 경우
        if 'category' in product_data and product_data['category']:
            # 카테고리가 문자열인 경우 (콤마로 구분된)
            if isinstance(product_data['category'], str):
                categories = [cat.strip() for cat in product_data['category'].split(',') if cat.strip()]
            # 카테고리가 리스트인 경우
            elif isinstance(product_data['category'], list):
                categories = [str(cat).strip() for cat in product_data['category'] if str(cat).strip()]
            # 카테고리가 딕셔너리인 경우
            elif isinstance(product_data['category'], dict):
                for cat_name in product_data['category'].values():
                    if cat_name and isinstance(cat_name, str):
                        categories.append(cat_name.strip())
        
        return categories 