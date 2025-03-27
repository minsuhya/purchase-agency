import re
from typing import Dict, Optional, List
from datetime import datetime

from bs4 import BeautifulSoup
from loguru import logger

from app.models.product import ProductInfo, ProductImage, ProductOption
from app.utils.base_scraper import BaseScraper


class GenericScraper(BaseScraper):
    """일반 웹사이트를 위한 범용 스크레이퍼"""
    
    def __init__(self):
        """제네릭 스크레이퍼 초기화"""
        super().__init__()
    
    async def scrape(self, url: str) -> ProductInfo:
        """
        일반 상품 페이지에서 정보를 추출합니다.
        일반적인 HTML 구조와 Open Graph 태그를 활용합니다.
        
        Args:
            url (str): 상품 URL
            
        Returns:
            ProductInfo: 추출된 상품 정보
        """
        try:
            logger.info(f"일반 상품 정보 스크래핑 시작: {url}")
            response = await self.client.get(url, headers=self.headers)
            
            if response.status_code != 200:
                logger.error(f"응답 오류: HTTP {response.status_code}")
                raise Exception(f"페이지 접근 실패: HTTP {response.status_code}")
                
            soup = BeautifulSoup(response.text, "lxml")
            
            # Open Graph 태그에서 기본 정보 추출
            title_text = self._extract_title(soup, url)
            description = self._extract_description(soup)
            images = self._extract_images(soup, url)
            price_text, price_value = self._extract_price(soup)
            
            # 이미지 객체 생성
            main_image = None
            image_gallery = []
            
            if images and len(images) > 0:
                main_image = ProductImage(url=images[0], alt=title_text)
                for i in range(1, len(images)):
                    image_gallery.append(ProductImage(url=images[i], alt=f"{title_text} - {i}"))
            
            # 추가 정보 추출
            brand = self._extract_brand(soup)
            specs = self._extract_specs(soup)
            categories = self._extract_categories(soup)
            
            # ProductInfo 객체 생성
            product_info = ProductInfo(
                title={"original": title_text, "translated": ""},
                brand=brand,
                url=url,
                price={
                    "original": price_text,
                    "value": price_value,
                    "krw": None
                },
                currency=self._extract_currency(price_text),
                main_image=main_image,
                images=image_gallery,
                description={"original": description, "translated": ""},
                specifications={"original": specs, "translated": {}},
                categories=categories,
                created_at=datetime.now().isoformat()
            )
            
            # 추가 메타데이터
            product_info.raw_data = {
                "source": "generic",
                "scrape_date": datetime.now().isoformat()
            }
            
            logger.info(f"일반 상품 정보 스크래핑 완료: {url}")
            return product_info
            
        except Exception as e:
            logger.error(f"일반 스크래핑 중 오류 발생: {str(e)}", exc_info=True)
            raise Exception(f"상품 정보 수집 실패: {str(e)}")
    
    def _extract_title(self, soup: BeautifulSoup, url: str) -> str:
        """
        상품 제목을 추출합니다.
        다양한 방법으로 제목을 찾아보고, 찾지 못하면 기본값을 반환합니다.
        """
        # 1. Open Graph 태그에서 추출
        og_title = soup.select_one("meta[property='og:title']")
        if og_title and og_title.get("content"):
            return og_title.get("content").strip()
        
        # 2. 타이틀 태그에서 추출
        title_tag = soup.select_one("title")
        if title_tag and title_tag.text:
            return title_tag.text.strip()
        
        # 3. h1 태그에서 추출
        h1_tag = soup.select_one("h1")
        if h1_tag and h1_tag.text:
            return h1_tag.text.strip()
        
        # 4. product-title, item-title 등의 클래스를 가진 요소에서 추출
        product_title = soup.select_one(".product-title, .item-title, .product-name, .productTitle")
        if product_title and product_title.text:
            return product_title.text.strip()
        
        # 찾지 못한 경우 URL에서 추출 시도
        try:
            from urllib.parse import urlparse
            path = urlparse(url).path
            if path and path != "/":
                # 경로의 마지막 부분을 사용
                title_from_path = path.strip('/').split('/')[-1]
                # 하이픈을 공백으로 변환하고 첫 글자를 대문자로
                title_from_path = title_from_path.replace('-', ' ').replace('_', ' ')
                return title_from_path.title()
        except:
            pass
        
        # 모든 방법이 실패하면 기본값 반환
        return "Unknown Product"
    
    def _extract_description(self, soup: BeautifulSoup) -> str:
        """
        상품 설명을 추출합니다.
        다양한 방법으로 설명을 찾아보고, 찾지 못하면 빈 문자열을 반환합니다.
        """
        # 1. Open Graph 설명 태그에서 추출
        og_desc = soup.select_one("meta[property='og:description'], meta[name='description']")
        if og_desc and og_desc.get("content"):
            return og_desc.get("content").strip()
        
        # 2. 상품 설명 관련 클래스를 가진 요소에서 추출
        desc_selectors = [
            ".product-description", 
            "#product-description",
            ".description",
            "#description",
            ".product-details",
            "#product-details",
            ".details",
            "[itemprop='description']"
        ]
        
        for selector in desc_selectors:
            desc_elem = soup.select_one(selector)
            if desc_elem and desc_elem.text.strip():
                return desc_elem.text.strip()
        
        # 찾지 못한 경우 빈 문자열 반환
        return ""
    
    def _extract_images(self, soup: BeautifulSoup, url: str) -> List[str]:
        """
        상품 이미지를 추출합니다.
        다양한 방법으로 이미지를 찾아보고, 결과를 리스트로 반환합니다.
        """
        images = []
        
        # 1. Open Graph 이미지 태그에서 추출
        og_image = soup.select_one("meta[property='og:image']")
        if og_image and og_image.get("content"):
            images.append(og_image.get("content"))
        
        # 2. 상품 이미지 관련 클래스를 가진 이미지 요소 추출
        image_selectors = [
            ".product-image img", 
            "#product-image img",
            ".gallery img",
            "#gallery img",
            ".carousel img",
            "[itemprop='image']",
            ".product img",
            ".product-gallery img",
            "img.product",
            ".main-image img"
        ]
        
        for selector in image_selectors:
            img_elems = soup.select(selector)
            for img in img_elems:
                if img.get("src") and img.get("src") not in images:
                    # 상대 경로를 절대 경로로 변환
                    src = img.get("src")
                    if src.startswith("//"):
                        src = "https:" + src
                    elif src.startswith("/"):
                        from urllib.parse import urlparse
                        parsed_url = urlparse(url)
                        base_url = f"{parsed_url.scheme}://{parsed_url.netloc}"
                        src = base_url + src
                    
                    images.append(src)
        
        # 3. 상품 갤러리 이미지 요소 추출
        data_image_elems = soup.select("[data-image-url], [data-src], [data-lazy-src]")
        for elem in data_image_elems:
            for attr in ["data-image-url", "data-src", "data-lazy-src"]:
                if elem.get(attr) and elem.get(attr) not in images:
                    images.append(elem.get(attr))
        
        return images
    
    def _extract_price(self, soup: BeautifulSoup) -> tuple:
        """
        상품 가격을 추출합니다.
        다양한 방법으로 가격을 찾아보고, 결과를 (텍스트, 숫자값) 형태로 반환합니다.
        """
        price_text = "N/A"
        
        # 가격 관련 클래스를 가진 요소 탐색
        price_selectors = [
            ".price", 
            "#price",
            ".product-price",
            "#product-price",
            ".current-price",
            ".sale-price",
            "[itemprop='price']",
            ".price-box",
            "span.amount",
            ".price-container"
        ]
        
        for selector in price_selectors:
            price_elem = soup.select_one(selector)
            if price_elem and price_elem.text.strip():
                price_text = price_elem.text.strip()
                break
        
        # 가격에서 숫자만 추출
        price_value = self._extract_price(price_text)
        
        return price_text, price_value
    
    def _extract_brand(self, soup: BeautifulSoup) -> Optional[str]:
        """
        상품 브랜드를 추출합니다.
        다양한 방법으로 브랜드를 찾아보고, 결과를 반환합니다.
        """
        # 브랜드 관련 메타 태그 확인
        brand_meta = soup.select_one("meta[property='product:brand'], meta[name='brand'], meta[itemprop='brand']")
        if brand_meta and brand_meta.get("content"):
            return brand_meta.get("content").strip()
        
        # 브랜드 관련 요소 확인
        brand_selectors = [
            ".brand", 
            "#brand",
            "[itemprop='brand']",
            ".manufacturer",
            ".product-brand",
            "span.brand"
        ]
        
        for selector in brand_selectors:
            brand_elem = soup.select_one(selector)
            if brand_elem and brand_elem.text.strip():
                return brand_elem.text.strip()
        
        # 브랜드: 값 형태의 텍스트 찾기
        brand_labels = soup.select("th:contains('Brand'), td:contains('Brand'), dt:contains('Brand'), strong:contains('Brand')")
        for label in brand_labels:
            next_elem = label.find_next_sibling()
            if next_elem and next_elem.text.strip():
                return next_elem.text.strip()
            
            # 특정 텍스트 패턴 확인 (Brand: XXX)
            text = label.text.strip()
            brand_match = re.search(r"Brand:?\s*([^:]+)$", text)
            if brand_match:
                return brand_match.group(1).strip()
        
        return None
    
    def _extract_specs(self, soup: BeautifulSoup) -> Dict[str, str]:
        """
        상품 스펙 정보를 추출합니다.
        다양한 방법으로 스펙 정보를 찾아보고, 결과를 딕셔너리로 반환합니다.
        """
        specs = {}
        
        # 스펙 테이블 확인
        spec_tables = soup.select("table.specifications, table.product-specs, table.tech-specs, table.details")
        for table in spec_tables:
            rows = table.select("tr")
            for row in rows:
                cells = row.select("th, td")
                if len(cells) >= 2:
                    key = cells[0].text.strip()
                    value = cells[1].text.strip()
                    if key and value:
                        specs[key] = value
        
        # 정의 목록 확인
        spec_lists = soup.select("dl.specifications, dl.product-specs, dl.tech-specs, dl.details")
        for dl in spec_lists:
            dt_elements = dl.select("dt")
            for dt in dt_elements:
                dd = dt.find_next_sibling("dd")
                if dd:
                    key = dt.text.strip()
                    value = dd.text.strip()
                    if key and value:
                        specs[key] = value
        
        # 명세 목록 확인
        spec_items = soup.select(".specification-item, .spec-item, .product-spec")
        for item in spec_items:
            key_elem = item.select_one(".spec-name, .spec-key, .spec-title")
            val_elem = item.select_one(".spec-value, .spec-val, .spec-text")
            if key_elem and val_elem:
                key = key_elem.text.strip()
                value = val_elem.text.strip()
                if key and value:
                    specs[key] = value
        
        return specs
    
    def _extract_categories(self, soup: BeautifulSoup) -> List[str]:
        """
        상품 카테고리를 추출합니다.
        다양한 방법으로 카테고리를 찾아보고, 결과를 리스트로 반환합니다.
        """
        categories = []
        
        # 브레드크럼 확인
        breadcrumb_selectors = [
            ".breadcrumbs", 
            "#breadcrumbs",
            ".breadcrumb",
            "#breadcrumb",
            "[itemtype*='BreadcrumbList']",
            ".navigation-path"
        ]
        
        for selector in breadcrumb_selectors:
            breadcrumb = soup.select_one(selector)
            if breadcrumb:
                # 링크 또는 항목 추출
                items = breadcrumb.select("a, li, span.item")
                for item in items:
                    text = item.text.strip()
                    if text and text not in ["Home", "Home Page", "홈", "메인", ">"]:
                        categories.append(text)
                        
                if categories:
                    break  # 카테고리를 찾았으면 중지
        
        # 카테고리 메타 태그 확인
        if not categories:
            category_meta = soup.select_one("meta[property='product:category'], meta[name='category']")
            if category_meta and category_meta.get("content"):
                cat_text = category_meta.get("content").strip()
                # 콤마나 슬래시로 구분된 카테고리 처리
                if "," in cat_text:
                    categories = [c.strip() for c in cat_text.split(",") if c.strip()]
                elif "/" in cat_text:
                    categories = [c.strip() for c in cat_text.split("/") if c.strip()]
                else:
                    categories = [cat_text]
        
        return categories 