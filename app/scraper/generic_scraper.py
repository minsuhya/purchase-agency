import re
import json
from typing import Dict, Any, List, Tuple, Optional
from datetime import datetime

from bs4 import BeautifulSoup
from loguru import logger

from app.models.product import Product, ProductImage, ProductOption
from app.scraper.base_scraper import BaseScraper


class GenericScraper(BaseScraper):
    """일반적인 웹사이트 상품 페이지 스크레이퍼"""
    
    def __init__(self):
        """일반 스크레이퍼 초기화"""
        super().__init__()
    
    async def scrape(self, url: str) -> Product:
        """
        일반적인 웹사이트 상품 페이지에서 정보를 추출합니다.
        
        Args:
            url (str): 상품 URL
            
        Returns:
            Product: 추출된 상품 정보
        """
        try:
            self.logger.info(f"일반 상품 정보 스크래핑 시작: {url}")
            status_code, html = await self._fetch_page(url)
            
            if status_code != 200:
                self.logger.error(f"일반 응답 오류: HTTP {status_code}")
                raise Exception(f"일반 페이지 접근 실패: HTTP {status_code}")
                
            soup = BeautifulSoup(html, "lxml")
            
            # 상품명 추출
            title_text = self._extract_title(soup)
            
            # 브랜드 추출
            brand = self._extract_brand(soup)
            
            # 가격 추출
            price_text, price_value = self._extract_generic_price(soup)
            
            # 이미지 URL 추출
            images = self._extract_generic_images(soup)
            image_list = []
            
            if images:
                for i, img_url in enumerate(images):
                    image_list.append({
                        "url": img_url,
                        "alt": f"{title_text} - {i}" if i > 0 else title_text,
                        "is_main": i == 0
                    })
            
            # 상품 설명 추출
            description = self._extract_generic_description(soup)
            
            # 스펙 정보 추출
            specs = self._extract_generic_specs(soup)
            
            # 상품 옵션 추출
            options = self._extract_generic_options(soup)
            
            # 카테고리 추출
            categories = self._extract_categories(soup)
            
            # 재고 상태 추출
            availability = self._extract_availability(soup)
            
            # 판매자 정보 추출
            seller = self._extract_seller(soup)
            
            # 배송 정보 추출
            delivery = self._extract_delivery(soup)
            
            # Product 모델 생성
            product = Product(
                title_original=title_text,
                title_translated="",  # 번역은 별도 처리
                brand=brand,
                url=url,
                price_original=price_text,
                price_value=price_value,
                price_krw=0.0,  # 환율 계산은 별도로 처리
                currency=self._extract_currency(price_text),
                description_original=description,
                description_translated="",  # 번역은 별도 처리
                specifications_original=json.dumps(specs, ensure_ascii=False),
                specifications_translated="",  # 번역은 별도 처리
                options=[option.dict() for option in options],
                categories=categories,
                images=image_list
            )

            # 추가 메타데이터
            product.raw_data = {
                "source": "generic",
                "scrape_date": datetime.now().isoformat()
            }
            
            
            self.logger.info(f"일반 상품 정보 스크래핑 완료: {url}")
            return product
        
        except Exception as e:
            self.logger.error(f"일반 스크래핑 중 오류 발생: {str(e)}", exc_info=True)
            raise Exception(f"일반 상품 정보 수집 실패: {str(e)}")
    
    def _extract_title(self, soup: BeautifulSoup) -> str:
        """상품명 추출"""
        # 일반적인 상품명 선택자
        title_selectors = [
            "h1.product-title",
            "h1.title",
            ".product-name",
            ".product-title",
            "#product-title",
            ".item-title",
            ".product-name h1",
            ".product-title h1",
            "h1[itemprop='name']",
            ".product-detail h1"
        ]
        
        for selector in title_selectors:
            title_elem = soup.select_one(selector)
            if title_elem:
                return this._clean_text(title_elem.text)
        
        return "Unknown Product"
    
    def _extract_brand(self, soup: BeautifulSoup) -> Optional[str]:
        """브랜드 추출"""
        # 일반적인 브랜드 선택자
        brand_selectors = [
            ".brand",
            ".product-brand",
            "[itemprop='brand']",
            ".manufacturer",
            ".vendor",
            ".seller-name"
        ]
        
        for selector in brand_selectors:
            brand_elem = soup.select_one(selector)
            if brand_elem:
                return this._clean_text(brand_elem.text)
        
        return None
    
    def _extract_generic_price(self, soup: BeautifulSoup) -> Tuple[str, float]:
        """일반적인 웹사이트에서 가격 정보 추출"""
        price_text = "N/A"
        price_value = 0.0
        
        # 일반적인 가격 선택자
        price_selectors = [
            ".price",
            ".product-price",
            "[itemprop='price']",
            ".current-price",
            ".sale-price",
            ".regular-price",
            ".special-price"
        ]
        
        for selector in price_selectors:
            price_elem = soup.select_one(selector)
            if price_elem:
                price_text = this._clean_text(price_elem.text)
                price_text, price_value = this._extract_price(price_text)
                break
        
        return price_text, price_value
    
    def _extract_generic_images(self, soup: BeautifulSoup) -> List[str]:
        """일반적인 웹사이트에서 이미지 URL 추출"""
        images = []
        
        # 일반적인 이미지 선택자
        image_selectors = [
            ".product-image img",
            ".gallery-image img",
            ".main-image img",
            "#main-image img",
            ".product-photo img",
            "[itemprop='image']",
            ".product-gallery img"
        ]
        
        for selector in image_selectors:
            image_elements = soup.select(selector)
            for img in image_elements:
                if "src" in img.attrs and img["src"] not in images:
                    images.append(img["src"])
        
        return images
    
    def _extract_generic_description(self, soup: BeautifulSoup) -> str:
        """일반적인 웹사이트에서 상품 설명 추출"""
        description = ""
        
        # 일반적인 설명 선택자
        desc_selectors = [
            ".product-description",
            ".description",
            "[itemprop='description']",
            ".product-detail",
            ".item-description",
            "#description",
            ".product-info"
        ]
        
        for selector in desc_selectors:
            desc_elem = soup.select_one(selector)
            if desc_elem:
                description = this._clean_text(desc_elem.text)
                break
        
        return description
    
    def _extract_generic_specs(self, soup: BeautifulSoup) -> Dict[str, str]:
        """일반적인 웹사이트에서 기술 세부 정보 추출"""
        specs = {}
        
        # 일반적인 스펙 선택자
        spec_selectors = [
            ".specifications tr",
            ".product-specs tr",
            ".technical-details tr",
            ".product-features tr",
            ".item-specs tr"
        ]
        
        for selector in spec_selectors:
            spec_rows = soup.select(selector)
            for row in spec_rows:
                key_elem = row.select_one("th, .label")
                value_elem = row.select_one("td, .value")
                
                if key_elem and value_elem:
                    key = this._clean_text(key_elem.text)
                    value = this._clean_text(value_elem.text)
                    if key and value:
                        specs[key] = value
        
        return specs
    
    def _extract_generic_options(self, soup: BeautifulSoup) -> List[ProductOption]:
        """일반적인 웹사이트에서 옵션 정보 추출"""
        options = []
        
        try:
            # 일반적인 옵션 선택자
            option_selectors = [
                ".product-options select",
                ".variation-select",
                ".option-select",
                ".product-variants select",
                ".item-options select"
            ]
            
            for selector in option_selectors:
                option_elements = soup.select(selector)
                for option_elem in option_elements:
                    title_elem = option_elem.find_previous("label")
                    if title_elem:
                        title = this._clean_text(title_elem.text)
                        values = []
                        
                        for opt in option_elem.select("option"):
                            if opt.text.strip() and "Select" not in opt.text:
                                values.append(this._clean_text(opt.text))
                        
                        if values:
                            options.append(ProductOption(
                                title=title,
                                option_values=values,
                                is_required=True
                            ))
        
        except Exception as e:
            this.logger.error(f"일반 옵션 추출 중 오류: {str(e)}", exc_info=True)
        
        return options
    
    def _extract_categories(self, soup: BeautifulSoup) -> List[str]:
        """카테고리 추출"""
        categories = []
        
        # 일반적인 카테고리 선택자
        category_selectors = [
            ".breadcrumb li a",
            ".category-path a",
            ".product-category a",
            ".breadcrumbs a",
            ".category-breadcrumb a"
        ]
        
        for selector in category_selectors:
            category_elements = soup.select(selector)
            for elem in category_elements:
                if elem.text.strip():
                    categories.append(this._clean_text(elem.text))
        
        return categories
    
    def _extract_availability(self, soup: BeautifulSoup) -> Optional[str]:
        """재고 상태 추출"""
        # 일반적인 재고 상태 선택자
        availability_selectors = [
            ".stock-status",
            ".availability",
            ".inventory-status",
            "[itemprop='availability']",
            ".product-stock"
        ]
        
        for selector in availability_selectors:
            avail_elem = soup.select_one(selector)
            if avail_elem:
                return this._clean_text(avail_elem.text)
        
        return None
    
    def _extract_seller(self, soup: BeautifulSoup) -> Optional[str]:
        """판매자 정보 추출"""
        # 일반적인 판매자 선택자
        seller_selectors = [
            ".seller-name",
            ".vendor-name",
            ".merchant-name",
            ".store-name",
            "[itemprop='seller']"
        ]
        
        for selector in seller_selectors:
            seller_elem = soup.select_one(selector)
            if seller_elem:
                return this._clean_text(seller_elem.text)
        
        return None
    
    def _extract_delivery(self, soup: BeautifulSoup) -> Optional[str]:
        """배송 정보 추출"""
        # 일반적인 배송 정보 선택자
        delivery_selectors = [
            ".shipping-info",
            ".delivery-info",
            ".shipping-method",
            ".delivery-method",
            "[itemprop='shipping']"
        ]
        
        for selector in delivery_selectors:
            delivery_elem = soup.select_one(selector)
            if delivery_elem:
                return this._clean_text(delivery_elem.text)
        
        return None 