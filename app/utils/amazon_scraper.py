import re
import json
from typing import Dict, Any, List, Tuple, Optional
from urllib.parse import urlparse, parse_qs
from datetime import datetime

from bs4 import BeautifulSoup
from loguru import logger

from app.models.product import ProductInfo, ProductImage, ProductOption
from app.utils.base_scraper import BaseScraper


class AmazonScraper(BaseScraper):
    """Amazon 상품 페이지 스크레이퍼"""
    
    def __init__(self):
        """Amazon 스크레이퍼 초기화"""
        super().__init__()
        # Amazon 특화 헤더 추가
        self.headers["Referer"] = "https://www.amazon.com/"
    
    async def scrape(self, url: str) -> ProductInfo:
        """
        Amazon 상품 페이지에서 정보를 추출합니다.
        
        Args:
            url (str): Amazon 상품 URL
            
        Returns:
            ProductInfo: 추출된 상품 정보
        """
        try:
            logger.info(f"Amazon 상품 정보 스크래핑 시작: {url}")
            response = await self.client.get(url, headers=self.headers)
            
            if response.status_code != 200:
                logger.error(f"Amazon 응답 오류: HTTP {response.status_code}")
                raise Exception(f"Amazon 페이지 접근 실패: HTTP {response.status_code}")
                
            soup = BeautifulSoup(response.text, "lxml")
            
            # ASIN 추출
            asin = self._extract_asin(url, soup)
            
            # 상품명 추출 - 복수의 선택자 시도
            title_text = self._extract_title(soup)
            
            # 브랜드 추출
            brand = self._extract_brand(soup)
            
            # 가격 추출
            price_text, price_value = self._extract_amazon_price(soup)
            
            # 이미지 URL 추출
            images = self._extract_amazon_images(soup)
            main_image = None
            image_gallery = []
            
            if images and len(images) > 0:
                main_image = ProductImage(url=images[0], alt=title_text)
                for i in range(1, len(images)):
                    image_gallery.append(ProductImage(url=images[i], alt=f"{title_text} - {i}"))
            
            # 상품 설명 추출
            description = self._extract_amazon_description(soup)
            
            # 스펙 정보 추출
            specs = self._extract_amazon_specs(soup)
            
            # 상품 옵션 추출 (색상, 사이즈)
            options = []
            colors = []
            sizes = []
            try:
                options_result = self._extract_amazon_options(soup)
                if options_result and isinstance(options_result, tuple) and len(options_result) == 3:
                    options, colors, sizes = options_result
                else:
                    logger.warning("옵션 추출 결과가 예상 형식과 다릅니다.")
            except Exception as e:
                logger.error(f"옵션 추출 중 오류 발생: {str(e)}")
            
            # 카테고리 추출
            categories = self._extract_categories(soup)
            
            # 재고 상태 추출
            availability = self._extract_availability(soup)
            
            # 평점 및 리뷰 수 추출 - 안전한 방식으로 처리
            try:
                # 평점 추출 메서드 호출 - 항상 (str, str) 튜플을 반환
                rating, review_count = self._extract_amazon_rating(soup)
                logger.debug(f"상품 평점 추출 성공: {rating}, 리뷰 수: {review_count}")
            except Exception as e:
                logger.error(f"평점 추출 중 예외 발생: {str(e)}", exc_info=True)
                rating, review_count = "0", "0"  # 기본값 설정
            
            # 판매자 정보 추출
            seller = self._extract_seller(soup)
            
            # 배송 정보 추출
            delivery = self._extract_delivery(soup)
            
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
                created_at=datetime.now().isoformat()
            )
            
            # 추가 정보 (raw_data)에 포함
            raw_data = {
                "asin": asin,
                "availability": availability,
                "rating": rating,
                "review_count": review_count,
                "seller": seller,
                "delivery": delivery
            }
            
            if colors:
                raw_data["colors"] = colors
            if sizes:
                raw_data["sizes"] = sizes
                
            product_info.raw_data = raw_data
            
            logger.info(f"Amazon 상품 정보 스크래핑 완료: {url}")
            return product_info
        
        except Exception as e:
            logger.error(f"Amazon 스크래핑 중 오류 발생: {str(e)}", exc_info=True)
            raise Exception(f"Amazon 상품 정보 수집 실패: {str(e)}")
    
    def _extract_asin(self, url: str, soup: BeautifulSoup) -> Optional[str]:
        """ASIN 추출"""
        # 방법 1: URL에서 추출
        asin_pattern = r"/dp/([A-Z0-9]{10})/"
        asin_match = re.search(asin_pattern, url)
        if asin_match:
            return asin_match.group(1)

        # 방법 2: URL 파라미터에서 추출
        parsed_url = urlparse(url)
        query_params = parse_qs(parsed_url.query)
        if "ASIN" in query_params:
            return query_params["ASIN"][0]

        # 방법 3: 상세 정보에서 추출
        asin_elements = soup.select('tr:contains("ASIN"), li:contains("ASIN")')
        for element in asin_elements:
            text = element.text
            asin_match = re.search(r"ASIN[:\s]*([A-Z0-9]{10})", text)
            if asin_match:
                return asin_match.group(1)

        # 방법 4: 숨겨진 입력 필드에서 추출
        asin_input = soup.select_one('input[name="ASIN"]')
        if asin_input and "value" in asin_input.attrs:
            return asin_input["value"]

        return None
    
    def _extract_title(self, soup: BeautifulSoup) -> str:
        """상품명 추출"""
        # 메인 선택자
        for selector in ["#productTitle", "span.product-title-word-break", "h1.a-size-large"]:
            title_element = soup.select_one(selector)
            if title_element:
                return title_element.text.strip()
        
        # 타이틀이 없는 경우 기본값
        return "Unknown Product"
    
    def _extract_brand(self, soup: BeautifulSoup) -> Optional[str]:
        """브랜드 추출"""
        brand = None
        brand_elem = soup.select_one("#bylineInfo, .a-row.a-spacing-base a#bylineInfo")
        if brand_elem:
            brand = brand_elem.text.strip()
            # "Brand: XXX" 형식에서 브랜드명만 추출
            brand_match = re.search(r"Brand:?\s*([^:]+)$", brand)
            if brand_match:
                brand = brand_match.group(1).strip()
        return brand
    
    def _extract_amazon_price(self, soup: BeautifulSoup) -> Tuple[str, float]:
        """Amazon 페이지에서 가격 정보 추출"""
        price_text = "N/A"
        price_value = 0.0
        
        # 현재 가장 많이 사용되는 가격 선택자들
        selectors = [
            "span.a-offscreen", 
            ".a-price .a-offscreen",
            "#priceblock_dealprice",
            "#dealprice_block",
            "#priceblock_ourprice",
            "#priceblock_saleprice",
            ".a-price"
        ]
        
        for selector in selectors:
            price_element = soup.select_one(selector)
            if price_element:
                price_text = price_element.text.strip()
                break
        
        # 가격 분할 형식 (전체 + 소수 부분)
        if price_text == "N/A":
            price_whole = soup.select_one("span.a-price-whole")
            price_fraction = soup.select_one("span.a-price-fraction")
            if price_whole and price_fraction:
                price_text = f"{price_whole.text}{price_fraction.text}"
        
        # 숫자만 추출
        price_value = self._extract_price(price_text)
        
        return price_text, price_value
    
    def _extract_amazon_images(self, soup: BeautifulSoup) -> List[str]:
        """Amazon 페이지에서 이미지 URL 추출"""
        images = []
        
        # 메인 이미지 추출
        for selector in ["#landingImage", "#imgBlkFront", "#main-image"]:
            image = soup.select_one(selector)
            if image:
                if "src" in image.attrs:
                    images.append(image["src"])
                    break
                elif "data-old-hires" in image.attrs:
                    images.append(image["data-old-hires"])
                    break
                elif "data-a-dynamic-image" in image.attrs:
                    try:
                        image_json = json.loads(image["data-a-dynamic-image"])
                        image_urls = list(image_json.keys())
                        if image_urls:
                            images.append(image_urls[0])  # 첫 번째 이미지 URL 사용
                            break
                    except:
                        pass
        
        # 이미지 갤러리 (추가 이미지)
        gallery_selectors = [
            "#altImages li.item img",
            "#imageBlock_feature_div li.item img",
            ".a-dynamic-image"
        ]
        
        for selector in gallery_selectors:
            gallery_images = soup.select(selector)
            for img in gallery_images:
                if "src" in img.attrs:
                    # 썸네일 이미지 URL을 고해상도 이미지 URL로 변환
                    hi_res_url = img["src"].replace("._SS40_", "._SL1500_")
                    if hi_res_url not in images:  # 중복 방지
                        images.append(hi_res_url)
        
        return images
    
    def _extract_amazon_description(self, soup: BeautifulSoup) -> str:
        """Amazon 페이지에서 상품 설명 추출"""
        description = ""
        
        # 상품 설명
        for selector in [
            "#productDescription", 
            "#dpx-product-description_feature_div",
            "#aplus", 
            "#aplus3p_feature_div"
        ]:
            desc_elem = soup.select_one(selector)
            if desc_elem:
                description = desc_elem.text.strip()
                break
        
        # 상품 설명이 없는 경우 특징(features) 사용
        if not description:
            features = self._extract_amazon_features(soup)
            if features:
                description = "\n".join(features)
        
        return description
    
    def _extract_amazon_features(self, soup: BeautifulSoup) -> List[str]:
        """Amazon 상품 특징(bullet points) 추출"""
        features = []
        feature_items = soup.select(
            "#feature-bullets li span.a-list-item, #feature-bullets ul li"
        )
        for item in feature_items:
            feature_text = item.text.strip()
            if feature_text:
                features.append(feature_text)
        return features
    
    def _extract_amazon_specs(self, soup: BeautifulSoup) -> Dict[str, str]:
        """Amazon 페이지에서 기술 세부 정보 추출"""
        specs = {}
        
        # 방법 1: 기술 명세 테이블
        detail_selectors = [
            "#productDetails_techSpec_section_1 tr",
            "#productDetails_detailBullets_sections1 tr",
            "#technicalSpecifications_section_1 tr"
        ]
        
        for selector in detail_selectors:
            detail_rows = soup.select(selector)
            for row in detail_rows:
                key_element = row.select_one("th")
                value_element = row.select_one("td")

                if key_element and value_element:
                    key = key_element.text.strip().rstrip(":")
                    value = value_element.text.strip()
                    specs[key] = value
        
        # 방법 2: 상세 정보 글머리 기호
        if not specs:
            detail_bullets = soup.select(
                "#detailBullets_feature_div li, #detailBulletsWrapper_feature_div li"
            )
            for bullet in detail_bullets:
                text = bullet.text.strip()
                parts = text.split(":", 1)
                if len(parts) == 2:
                    key = parts[0].strip()
                    value = parts[1].strip()
                    specs[key] = value
        
        return specs
    
    def _extract_amazon_options(self, soup: BeautifulSoup) -> Tuple[List[ProductOption], List[str], List[str]]:
        """Amazon 페이지에서 옵션 정보 추출"""
        options = []
        colors = []
        sizes = []
        
        try:
            # 색상 옵션
            color_elements = soup.select("#variation_color_name li, #variation_style_name li")
            color_values = []
            if color_elements:  # 비어있지 않은 경우에만 처리
                for element in color_elements:
                    if element.has_attr("title"):
                        color = element["title"].strip()
                        if color and color != "":
                            color_values.append(color)
                            colors.append(color)
            
            if color_values:
                options.append(ProductOption(
                    title="Color", 
                    option_values=color_values  # 별칭 사용
                ))
            
            # 사이즈 옵션
            size_elements = soup.select("#variation_size_name li, #variation-size-name li")
            size_values = []
            if size_elements:  # 비어있지 않은 경우에만 처리
                for element in size_elements:
                    if element.has_attr("title"):
                        size = element["title"].strip()
                        if size and size != "":
                            size_values.append(size)
                            sizes.append(size)
            
            if size_values:
                options.append(ProductOption(
                    title="Size", 
                    option_values=size_values  # 별칭 사용
                ))
            
            # 다른 타입의 옵션
            option_containers = soup.select(".a-dropdown-container")
            if option_containers:  # 비어있지 않은 경우에만 처리
                for option_elem in option_containers:
                    label_elem = option_elem.select_one("label")
                    select_elem = option_elem.select_one("select")
                    
                    if label_elem and select_elem:
                        option_title = label_elem.text.strip().rstrip(":")
                        option_values = []
                        
                        option_elements = select_elem.select("option")
                        if option_elements:  # 비어있지 않은 경우에만 처리
                            for opt in option_elements:
                                # 속성 존재 확인
                                opt_value = ""
                                if opt.has_attr("value"):
                                    opt_value = opt["value"]
                                
                                if opt_value != "-1" and opt.text.strip():  # 사용가능한 옵션만 추가
                                    option_values.append(opt.text.strip())
                        
                        if option_values:
                            options.append(ProductOption(
                                title=option_title, 
                                option_values=option_values  # 별칭 사용
                            ))
                        
        except Exception as e:
            logger.error(f"Amazon 옵션 추출 중 오류: {str(e)}", exc_info=True)
            # 오류 발생 시 빈 결과 반환
        
        # 타입 검증
        if not isinstance(options, list):
            logger.error("options가 리스트가 아닙니다. 빈 리스트로 초기화합니다.")
            options = []
        if not isinstance(colors, list):
            logger.error("colors가 리스트가 아닙니다. 빈 리스트로 초기화합니다.")
            colors = []
        if not isinstance(sizes, list):
            logger.error("sizes가 리스트가 아닙니다. 빈 리스트로 초기화합니다.")
            sizes = []
            
        return options, colors, sizes
    
    def _extract_amazon_rating(self, soup: BeautifulSoup) -> Tuple[str, str]:
        """
        Amazon 페이지에서 평점 및 리뷰 수 추출
        
        Args:
            soup: BeautifulSoup 객체
            
        Returns:
            Tuple[str, str]: (평점, 리뷰 수) 튜플, 문자열 형식
        """
        rating_str = "0"  # 기본값
        review_count_str = "0"  # 기본값
        
        try:
            # 평점 추출
            rating_element = soup.select_one(
                '#acrPopover, span[data-hook="rating-out-of-text"], i.a-icon-star, .a-star-4-5'
            )
            if rating_element:
                rating_text = ""
                if rating_element.has_attr("title"):
                    rating_text = rating_element["title"]
                else:
                    rating_text = rating_element.text.strip()

                # "4.5 out of 5 stars" 같은 텍스트에서 숫자만 추출
                rating_match = re.search(r"(\d+\.?\d*)", rating_text)
                if rating_match:
                    rating_str = rating_match.group(1)
            
            # 리뷰 수 추출
            review_element = soup.select_one(
                '#acrCustomerReviewText, span[data-hook="total-review-count"]'
            )
            if review_element:
                review_text = review_element.text.strip()
                # "1,234 ratings" 같은 텍스트에서 숫자만 추출
                count_match = re.search(r"([\d,]+)", review_text)
                if count_match:
                    review_count_str = count_match.group(1).replace(",", "")
        except Exception as e:
            logger.warning(f"평점 및 리뷰 추출 중 오류: {str(e)}", exc_info=True)
        
        # 결과 확인 및 안전 반환 (문자열 형식으로 반환)
        if not rating_str or not isinstance(rating_str, str):
            rating_str = "0"
        if not review_count_str or not isinstance(review_count_str, str):
            review_count_str = "0"
            
        return (rating_str, review_count_str)
    
    def _extract_categories(self, soup: BeautifulSoup) -> List[str]:
        """카테고리 추출"""
        categories = []
        breadcrumb = soup.select("#wayfinding-breadcrumbs_feature_div li, .a-breadcrumb li")
        for crumb in breadcrumb:
            a_tag = crumb.select_one("a")
            if a_tag and a_tag.text.strip():
                categories.append(a_tag.text.strip())
        return categories
    
    def _extract_availability(self, soup: BeautifulSoup) -> Optional[str]:
        """재고 상태 추출"""
        availability = None
        avail_elem = soup.select_one("#availability span, #availability, #outOfStock")
        if avail_elem:
            availability = avail_elem.text.strip()
        return availability
    
    def _extract_seller(self, soup: BeautifulSoup) -> Optional[str]:
        """판매자 정보 추출"""
        seller = None
        seller_elem = soup.select_one("#merchant-info, #bylineInfo, #sellerProfileTriggerId")
        if seller_elem:
            seller = seller_elem.text.strip()
        return seller
    
    def _extract_delivery(self, soup: BeautifulSoup) -> Optional[str]:
        """배송 정보 추출"""
        delivery = None
        delivery_elem = soup.select_one("#delivery-message, #mir-layout-DELIVERY_BLOCK")
        if delivery_elem:
            delivery = delivery_elem.text.strip()
        return delivery 