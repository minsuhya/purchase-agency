import re
import json
from typing import Dict, Any, List, Tuple, Optional
from datetime import datetime

from bs4 import BeautifulSoup
from loguru import logger

from app.models.product import Product, ProductImage, ProductOption
from app.scraper.base_scraper import BaseScraper


class EbayScraper(BaseScraper):
    """eBay 상품 페이지 스크레이퍼"""
    
    def __init__(self):
        """eBay 스크레이퍼 초기화"""
        super().__init__()
        # eBay 특화 헤더 추가
        self.headers["Referer"] = "https://www.ebay.com/"
    
    async def scrape(self, url: str) -> Product:
        """
        eBay 상품 페이지에서 정보를 추출합니다.
        
        Args:
            url (str): eBay 상품 URL
            
        Returns:
            Product: 추출된 상품 정보
        """
        try:
            self.logger.info(f"eBay 상품 정보 스크래핑 시작: {url}")
            status_code, html = await self._fetch_page(url)
            
            if status_code != 200:
                self.logger.error(f"eBay 응답 오류: HTTP {status_code}")
                raise Exception(f"eBay 페이지 접근 실패: HTTP {status_code}")
                
            soup = BeautifulSoup(html, "lxml")
            
            # 상품명 추출
            title_text = self._extract_title(soup)
            
            # 브랜드 추출
            brand = self._extract_brand(soup)
            
            # 가격 추출
            price_text, price_value = self._extract_ebay_price(soup)
            
            # 이미지 URL 추출
            images = self._extract_ebay_images(soup)
            image_list = []
            
            if images:
                for i, img_url in enumerate(images):
                    image_list.append({
                        "url": img_url,
                        "alt": f"{title_text} - {i}" if i > 0 else title_text,
                        "is_main": i == 0
                    })
            
            # 상품 설명 추출
            description = self._extract_ebay_description(soup)
            
            # 스펙 정보 추출
            specs = self._extract_ebay_specs(soup)
            
            # 상품 옵션 추출
            options = self._extract_ebay_options(soup)
            
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
            
            # 추가 정보 (raw_data)에 포함
            raw_data = {
                "availability": availability,
                "seller": seller,
                "delivery": delivery
            }
            
            product.raw_data = raw_data
            
            self.logger.info(f"eBay 상품 정보 스크래핑 완료: {url}")
            return product
        
        except Exception as e:
            self.logger.error(f"eBay 스크래핑 중 오류 발생: {str(e)}", exc_info=True)
            raise Exception(f"eBay 상품 정보 수집 실패: {str(e)}")
    
    def _extract_title(self, soup: BeautifulSoup) -> str:
        """상품명 추출"""
        title_elem = soup.select_one("h1.x-item-title")
        if title_elem:
            return self._clean_text(title_elem.text)
        return "Unknown Product"
    
    def _extract_brand(self, soup: BeautifulSoup) -> Optional[str]:
        """브랜드 추출"""
        brand_elem = soup.select_one(".x-item-details--secondary .ux-textspans")
        if brand_elem:
            return self._clean_text(brand_elem.text)
        return None
    
    def _extract_ebay_price(self, soup: BeautifulSoup) -> Tuple[str, float]:
        """eBay 페이지에서 가격 정보 추출"""
        price_text = "N/A"
        price_value = 0.0
        
        price_elem = soup.select_one(".x-price-primary span")
        if price_elem:
            price_text = self._clean_text(price_elem.text)
            price_text, price_value = self._extract_price(price_text)
        
        return price_text, price_value
    
    def _extract_ebay_images(self, soup: BeautifulSoup) -> List[str]:
        """eBay 페이지에서 이미지 URL 추출"""
        images = []
        
        # 메인 이미지
        main_image = soup.select_one(".ux-image-carousel-item.active img")
        if main_image and "src" in main_image.attrs:
            images.append(main_image["src"])
        
        # 이미지 갤러리
        gallery_images = soup.select(".ux-image-carousel-item img")
        for img in gallery_images:
            if "src" in img.attrs and img["src"] not in images:
                images.append(img["src"])
        
        return images
    
    def _extract_ebay_description(self, soup: BeautifulSoup) -> str:
        """eBay 페이지에서 상품 설명 추출"""
        description = ""
        
        desc_elem = soup.select_one(".x-item-description")
        if desc_elem:
            description = self._clean_text(desc_elem.text)
        
        return description
    
    def _extract_ebay_specs(self, soup: BeautifulSoup) -> Dict[str, str]:
        """eBay 페이지에서 기술 세부 정보 추출"""
        specs = {}
        
        spec_rows = soup.select(".ux-layout-section-evo__row")
        for row in spec_rows:
            key_elem = row.select_one(".ux-labels-values__values")
            value_elem = row.select_one(".ux-labels-values__values")
            
            if key_elem and value_elem:
                key = self._clean_text(key_elem.text)
                value = self._clean_text(value_elem.text)
                if key and value:
                    specs[key] = value
        
        return specs
    
    def _extract_ebay_options(self, soup: BeautifulSoup) -> List[ProductOption]:
        """eBay 페이지에서 옵션 정보 추출"""
        options = []
        
        try:
            # 색상 옵션
            color_elem = soup.select_one(".ux-labels-values__values--color")
            if color_elem:
                colors = [self._clean_text(color.text) for color in color_elem.select("span")]
                if colors:
                    options.append(ProductOption(
                        title="Color",
                        option_values=colors,
                        is_required=True
                    ))
            
            # 사이즈 옵션
            size_elem = soup.select_one(".ux-labels-values__values--size")
            if size_elem:
                sizes = [self._clean_text(size.text) for size in size_elem.select("span")]
                if sizes:
                    options.append(ProductOption(
                        title="Size",
                        option_values=sizes,
                        is_required=True
                    ))
            
            # 기타 옵션
            other_options = soup.select(".ux-labels-values__values--other")
            for option_elem in other_options:
                title_elem = option_elem.select_one(".ux-labels-values__labels")
                values_elem = option_elem.select_one(".ux-labels-values__values")
                
                if title_elem and values_elem:
                    title = self._clean_text(title_elem.text)
                    values = [self._clean_text(value.text) for value in values_elem.select("span")]
                    
                    if title and values:
                        options.append(ProductOption(
                            title=title,
                            option_values=values,
                            is_required=True
                        ))
        
        except Exception as e:
            self.logger.error(f"eBay 옵션 추출 중 오류: {str(e)}", exc_info=True)
        
        return options
    
    def _extract_categories(self, soup: BeautifulSoup) -> List[str]:
        """카테고리 추출"""
        categories = []
        breadcrumb = soup.select(".ux-breadcrumb__item")
        for crumb in breadcrumb:
            if crumb.text.strip():
                categories.append(self._clean_text(crumb.text))
        return categories
    
    def _extract_availability(self, soup: BeautifulSoup) -> Optional[str]:
        """재고 상태 추출"""
        avail_elem = soup.select_one(".x-item-quantity")
        if avail_elem:
            return self._clean_text(avail_elem.text)
        return None
    
    def _extract_seller(self, soup: BeautifulSoup) -> Optional[str]:
        """판매자 정보 추출"""
        seller_elem = soup.select_one(".x-seller-persona__member-name")
        if seller_elem:
            return self._clean_text(seller_elem.text)
        return None
    
    def _extract_delivery(self, soup: BeautifulSoup) -> Optional[str]:
        """배송 정보 추출"""
        delivery_elem = soup.select_one(".ux-labels-values__values--delivery")
        if delivery_elem:
            return self._clean_text(delivery_elem.text)
        return None 