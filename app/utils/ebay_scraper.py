import re
from typing import Dict, List, Optional
from datetime import datetime

from bs4 import BeautifulSoup
from loguru import logger

from app.models.product import ProductInfo, ProductImage, ProductOption
from app.utils.base_scraper import BaseScraper


class EbayScraper(BaseScraper):
    """eBay 상품 페이지 스크레이퍼"""
    
    def __init__(self):
        """eBay 스크레이퍼 초기화"""
        super().__init__()
        # eBay 특화 헤더 추가
        self.headers["Referer"] = "https://www.ebay.com/"
    
    async def scrape(self, url: str) -> ProductInfo:
        """
        eBay 상품 페이지에서 정보를 추출합니다.
        
        Args:
            url (str): eBay 상품 URL
            
        Returns:
            ProductInfo: 추출된 상품 정보
        """
        try:
            logger.info(f"eBay 상품 정보 스크래핑 시작: {url}")
            response = await self.client.get(url, headers=self.headers)
            
            if response.status_code != 200:
                logger.error(f"eBay 응답 오류: HTTP {response.status_code}")
                raise Exception(f"eBay 페이지 접근 실패: HTTP {response.status_code}")
                
            soup = BeautifulSoup(response.text, "lxml")
            
            # 기본 상품 정보 추출
            title_text = self._extract_title(soup)
            brand = self._extract_brand(soup)
            price_text, price_value = self._extract_price_info(soup)
            
            # 이미지 추출
            main_image, image_gallery = self._extract_images(soup, title_text)
            
            # 상품 설명 추출
            description = await self._extract_description(soup, url)
            
            # 스펙 정보 추출
            specs = self._extract_specs(soup)
            
            # 상품 옵션 추출
            options = self._extract_options(soup)
            
            # 카테고리 추출
            categories = self._extract_categories(soup)
            
            # 상품 상태 추출
            condition = self._extract_condition(soup)
            
            # 배송 정보 추출
            shipping = self._extract_shipping(soup)
            
            # 판매자 정보 추출
            seller = self._extract_seller(soup)
            
            # 재고 상태 추출
            availability = self._extract_availability(soup)
            
            # eBay 아이템 ID 추출
            item_id = self._extract_item_id(url, soup)
            
            # 판매량/인기도 추출
            popularity = self._extract_popularity(soup)
            
            # ProductInfo 객체 생성
            product_info = ProductInfo(
                title={"original": title_text, "translated": ""},
                brand=brand,
                url=url,
                price={
                    "original": price_text,
                    "value": price_value,
                    "krw": None  # 환율 계산은 별도로 처리
                },
                currency=self._extract_currency(price_text),
                main_image=main_image,
                images=image_gallery,
                description={"original": description, "translated": ""},
                specifications={"original": specs, "translated": {}},
                options=options,
                categories=categories,
                condition=condition,
                created_at=datetime.now().isoformat()
            )
            
            # 추가 정보 (raw_data)에 포함
            raw_data = {
                "item_id": item_id,
                "availability": availability,
                "shipping": shipping,
                "seller": seller,
                "popularity": popularity
            }
            
            product_info.raw_data = raw_data
            
            logger.info(f"eBay 상품 정보 스크래핑 완료: {url}")
            return product_info
        
        except Exception as e:
            logger.error(f"eBay 스크래핑 중 오류 발생: {str(e)}", exc_info=True)
            raise Exception(f"eBay 상품 정보 수집 실패: {str(e)}")
    
    def _extract_title(self, soup: BeautifulSoup) -> str:
        """상품명 추출"""
        title_elem = soup.select_one("h1.x-item-title__mainTitle")
        if title_elem:
            return title_elem.text.strip()
        return "Unknown Product"
    
    def _extract_brand(self, soup: BeautifulSoup) -> Optional[str]:
        """브랜드 추출"""
        brand = None
        
        # 방법 1: 상표 정보에서 추출
        brand_elem = soup.select_one("div.x-about-this-item span:contains('Brand:'), div.x-about-this-item span:contains('브랜드:'), div.x-about-this-item span:contains('Marke:')")
        if brand_elem:
            brand_label = brand_elem.parent
            brand_value = brand_label.find_next_sibling("span")
            if brand_value:
                brand = brand_value.text.strip()
        
        # 방법 2: 아이템 속성에서 추출
        if not brand:
            brand_row = soup.select_one("div.ux-layout-section__item span:contains('Brand')")
            if brand_row:
                brand_value = brand_row.parent.find_next_sibling("div")
                if brand_value:
                    brand = brand_value.text.strip()
        
        return brand
    
    def _extract_price_info(self, soup: BeautifulSoup) -> tuple:
        """가격 정보 추출"""
        price_text = "N/A"
        price_value = 0.0
        
        # 가격 추출
        price_elem = soup.select_one(".x-price-primary span")
        if price_elem:
            price_text = price_elem.text.strip()
            # 숫자만 추출
            price_value = self._extract_price(price_text)
        
        return price_text, price_value
    
    def _extract_images(self, soup: BeautifulSoup, title_text: str) -> tuple:
        """이미지 URL 추출"""
        # 메인 이미지
        main_image = None
        img_elem = soup.select_one("#icImg")
        if img_elem and img_elem.get("src"):
            main_image = ProductImage(url=img_elem.get("src"), alt=title_text)
        
        # 추가 이미지
        image_gallery = []
        gallery_images = soup.select("#vi_main_img_fs .img.img300, #mainImgHldr img")
        
        for img in gallery_images:
            if img.get("src") and (not main_image or img.get("src") != main_image.url):
                image_gallery.append(
                    ProductImage(url=img.get("src"), alt=f"{title_text} - {len(image_gallery) + 1}")
                )
        
        return main_image, image_gallery
    
    async def _extract_description(self, soup: BeautifulSoup, url: str) -> str:
        """상품 설명 추출"""
        description = ""
        
        # 방법 1: 설명 프레임에서 추출
        iframe = soup.select_one("#desc_ifr")
        if iframe:
            try:
                iframe_url = iframe.get("src")
                if iframe_url:
                    iframe_resp = await self.client.get(iframe_url, headers=self.headers)
                    iframe_soup = BeautifulSoup(iframe_resp.text, "lxml")
                    description = iframe_soup.text.strip()
            except Exception as e:
                logger.warning(f"eBay 설명 iframe 추출 오류: {str(e)}")
        
        # 방법 2: 직접 설명 섹션에서 추출
        if not description:
            desc_elem = soup.select_one("#viTabs_0_is, .itemDescriptionDiv")
            if desc_elem:
                description = desc_elem.text.strip()
        
        # 방법 3: About this item 섹션에서 추출
        if not description:
            about_elem = soup.select_one(".x-about-this-item")
            if about_elem:
                description = about_elem.text.strip()
        
        return description
    
    def _extract_specs(self, soup: BeautifulSoup) -> Dict[str, str]:
        """상품 스펙 정보 추출"""
        specs = {}
        
        # 아이템 스펙 테이블
        for row in soup.select(".ux-labels-values__labels-content"):
            key_elem = row.select_one(".ux-labels-values__labels")
            val_elem = row.select_one(".ux-labels-values__values")
            if key_elem and val_elem:
                key = key_elem.text.strip()
                value = val_elem.text.strip()
                if key and value:
                    specs[key] = value
        
        # 상세 정보 섹션
        if not specs:
            for item in soup.select(".x-about-this-item .ux-layout-section__row"):
                cols = item.select(".ux-layout-section__item")
                if len(cols) >= 2:
                    key = cols[0].text.strip()
                    value = cols[1].text.strip()
                    if key and value:
                        specs[key] = value
        
        return specs
    
    def _extract_options(self, soup: BeautifulSoup) -> List[ProductOption]:
        """상품 옵션 추출"""
        options = []
        
        # 드롭다운 옵션
        for select in soup.select("select[name^='itemSelect']"):
            option_name = select.get("name", "").replace("itemSelect", "")
            option_values = []
            
            for opt in select.select("option"):
                opt_text = opt.text.strip()
                # "Select" 문구가 포함되지 않고 빈 값이 아닌 경우에만 추가
                if opt_text and "Select" not in opt_text:
                    option_values.append(opt_text)
            
            if option_values:
                options.append(ProductOption(
                    title=option_name or "Option", 
                    option_values=option_values
                ))
        
        # 버튼 형태의 옵션
        for option_group in soup.select(".ux-form-select-dropdown__container"):
            label = option_group.select_one(".ux-form-select-dropdown__label")
            option_title = label.text.strip() if label else "Option"
            
            option_items = option_group.select(".ux-form-select-dropdown__selector-option")
            option_values = []
            
            for item in option_items:
                option_text = item.text.strip()
                if option_text:
                    option_values.append(option_text)
            
            if option_values:
                options.append(ProductOption(
                    title=option_title,
                    option_values=option_values
                ))
        
        return options
    
    def _extract_categories(self, soup: BeautifulSoup) -> List[str]:
        """카테고리 추출"""
        categories = []
        
        # 브레드크럼 내 카테고리
        for crumb in soup.select(".breadcrumbs li a span"):
            category = crumb.text.strip()
            if category:
                categories.append(category)
        
        return categories
    
    def _extract_condition(self, soup: BeautifulSoup) -> Optional[str]:
        """상품 상태 추출"""
        condition = None
        
        # 상품 상태 정보
        condition_elem = soup.select_one("div.x-item-condition-text span, .condText")
        if condition_elem:
            condition = condition_elem.text.strip()
        
        return condition
    
    def _extract_shipping(self, soup: BeautifulSoup) -> Optional[str]:
        """배송 정보 추출"""
        shipping = None
        
        # 배송 정보
        shipping_elem = soup.select_one(".d-shipping-minview, #fshippingCost")
        if shipping_elem:
            shipping = shipping_elem.text.strip()
        
        return shipping
    
    def _extract_seller(self, soup: BeautifulSoup) -> Optional[str]:
        """판매자 정보 추출"""
        seller = None
        
        # 판매자 정보
        seller_elem = soup.select_one("div.d-seller-info span.d-user-name a, span.mbg-nw")
        if seller_elem:
            seller = seller_elem.text.strip()
        
        return seller
    
    def _extract_availability(self, soup: BeautifulSoup) -> Optional[str]:
        """재고 상태 추출"""
        availability = None
        
        # 재고 정보
        avail_elem = soup.select_one("#qtySubTxt, .d-quantity__availability")
        if avail_elem:
            availability = avail_elem.text.strip()
        
        return availability
    
    def _extract_item_id(self, url: str, soup: BeautifulSoup) -> Optional[str]:
        """eBay 아이템 ID 추출"""
        # URL에서 추출 시도
        item_id_match = re.search(r"itm/.*?/(\d+)", url)
        if item_id_match:
            return item_id_match.group(1)
        
        # 페이지 소스에서 추출 시도
        item_id_elem = soup.select_one("div[data-itemid]")
        if item_id_elem and item_id_elem.has_attr("data-itemid"):
            return item_id_elem["data-itemid"]
        
        return None
    
    def _extract_popularity(self, soup: BeautifulSoup) -> Optional[str]:
        """판매량/인기도 정보 추출"""
        popularity = None
        
        # 인기도 정보 (판매량 등)
        pop_elem = soup.select_one(".vi-quantity-wrapper, .d-quantity-sold")
        if pop_elem:
            popularity = pop_elem.text.strip()
        
        return popularity 