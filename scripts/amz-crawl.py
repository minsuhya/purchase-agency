import csv
import json
import os
import random
import re
import time
from urllib.parse import parse_qs, urlparse

import requests
from bs4 import BeautifulSoup


def get_amazon_product_info(url):
    """
    아마존 상품 페이지에서 상세 정보를 추출하는 함수

    Args:
        url (str): 아마존 상품 URL

    Returns:
        dict: 추출된 상품 정보를 담은 딕셔너리
    """
    # 헤더 설정 (아마존 봇 차단 방지)
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
        "Accept-Language": "en-US,en;q=0.9",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
        "Accept-Encoding": "gzip, deflate, br",
        "Referer": "https://www.amazon.com/",
        "Connection": "keep-alive",
        "Cache-Control": "max-age=0",
        "Upgrade-Insecure-Requests": "1",
        "sec-ch-ua": '"Google Chrome";v="123", "Not:A-Brand";v="8", "Chromium";v="123"',
        "sec-ch-ua-mobile": "?0",
        "sec-ch-ua-platform": '"Windows"',
    }

    try:
        # 요청 보내기
        response = requests.get(url, headers=headers)

        # 응답 상태 확인
        if response.status_code != 200:
            print(f"Error: HTTP {response.status_code}")
            return None

        # BeautifulSoup 객체 생성
        soup = BeautifulSoup(response.content, "html.parser")

        # 상품 정보 추출
        product_info = {"url": url}

        # ASIN 추출 (여러 방법 시도)
        asin = extract_asin(url, soup)
        if asin:
            product_info["asin"] = asin

        # 상품명 추출
        title = extract_title(soup)
        if title:
            product_info["title"] = title

        # 가격 추출
        price = extract_price(soup)
        if price:
            product_info["price"] = price

        # 이미지 URL 추출
        images = extract_images(soup)
        if images:
            product_info["main_image"] = images[0]
            if len(images) > 1:
                product_info["additional_images"] = images[1:]

        # 평점 및 리뷰 수 추출
        rating, review_count = extract_rating_reviews(soup)
        if rating:
            product_info["rating"] = rating
        if review_count:
            product_info["review_count"] = review_count

        # 재고 상태 추출
        availability = extract_availability(soup)
        if availability:
            product_info["availability"] = availability

        # 상품 설명 추출
        description = extract_description(soup)
        if description:
            product_info["description"] = description

        # 특징 (Feature bullets) 추출
        features = extract_features(soup)
        if features:
            product_info["features"] = features

        # 기술 세부 정보 추출
        details = extract_technical_details(soup)
        if details:
            product_info["technical_details"] = details

        # 카테고리 경로 추출
        categories = extract_categories(soup)
        if categories:
            product_info["categories"] = categories

        # 판매자 정보 추출
        seller = extract_seller_info(soup)
        if seller:
            product_info["seller"] = seller

        # 배송 정보 추출
        delivery = extract_delivery_info(soup)
        if delivery:
            product_info["delivery"] = delivery

        # 변형 상품 (색상, 사이즈) 추출
        variations = extract_variations(soup)
        if variations:
            product_info.update(variations)

        return product_info

    except Exception as e:
        print(f"Error: {str(e)}")
        return None


def extract_asin(url, soup):
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
    asin_elements = soup.select('*:contains("ASIN"), tr:contains("ASIN")')
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


def extract_title(soup):
    """상품명 추출"""
    # 메인 선택자
    title_element = soup.select_one("#productTitle")
    if title_element:
        return title_element.text.strip()

    # 대체 선택자
    alt_title = soup.select_one("span.product-title-word-break")
    if alt_title:
        return alt_title.text.strip()

    return None


def extract_price(soup):
    """가격 정보 추출"""
    # 현재 가장 많이 사용되는 가격 선택자
    price = soup.select_one("span.a-offscreen")
    if price:
        price_text = price.text.strip()
        # 가격에서 통화 기호 및 쉼표 제거
        return re.sub(r"[^\d.]", "", price_text)

    # 대체 선택자: 가격 전체 부분 + 소수점 부분
    price_whole = soup.select_one("span.a-price-whole")
    price_fraction = soup.select_one("span.a-price-fraction")
    if price_whole and price_fraction:
        price_text = f"{price_whole.text}{price_fraction.text}"
        return re.sub(r"[^\d.]", "", price_text)

    # 다른 가격 형식 시도
    for selector in [
        "#priceblock_dealprice",
        "#dealprice_block",
        "#priceblock_ourprice",
        ".a-price .a-offscreen",
        "#priceblock_saleprice",
    ]:
        price_element = soup.select_one(selector)
        if price_element:
            price_text = price_element.text.strip()
            return re.sub(r"[^\d.]", "", price_text)

    # 데이터 속성에서 가격 추출 시도
    for element in soup.select("[data-asin]"):
        if "data-a-price" in element.attrs:
            return element["data-a-price"]

    return None


def extract_images(soup):
    """상품 이미지 URL 추출"""
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
    gallery_images = soup.select(
        "#altImages li.item img, #imageBlock_feature_div li.item img"
    )
    for img in gallery_images:
        if "src" in img.attrs:
            # 썸네일 이미지 URL을 고해상도 이미지 URL로 변환
            hi_res_url = img["src"].replace("._SS40_", "._SL1500_")
            if hi_res_url not in images:  # 중복 방지
                images.append(hi_res_url)

    return images


def extract_rating_reviews(soup):
    """평점 및 리뷰 수 추출"""
    rating = None
    review_count = None

    # 평점 추출
    rating_element = soup.select_one(
        '#acrPopover, span[data-hook="rating-out-of-text"], i.a-icon-star'
    )
    if rating_element:
        if "title" in rating_element.attrs:
            rating_text = rating_element["title"]
        else:
            rating_text = rating_element.text.strip()

        # "4.5 out of 5 stars" 같은 텍스트에서 숫자만 추출
        rating_match = re.search(r"(\d+\.?\d*)", rating_text)
        if rating_match:
            rating = rating_match.group(1)

    # 리뷰 수 추출
    review_element = soup.select_one(
        '#acrCustomerReviewText, span[data-hook="total-review-count"]'
    )
    if review_element:
        review_text = review_element.text.strip()
        # "1,234 ratings" 같은 텍스트에서 숫자만 추출
        count_match = re.search(r"([\d,]+)", review_text)
        if count_match:
            review_count = count_match.group(1).replace(",", "")

    return rating, review_count


def extract_availability(soup):
    """재고 상태 추출"""
    availability_element = soup.select_one(
        "#availability span, #availability, #outOfStock"
    )
    if availability_element:
        return availability_element.text.strip()
    return None


def extract_description(soup):
    """상품 설명 추출"""
    # 상품 설명
    for selector in ["#productDescription", "#dpx-product-description_feature_div"]:
        description = soup.select_one(selector)
        if description:
            return description.text.strip()

    # 상품 설명이 없는 경우 대체 위치 확인
    for selector in ["#feature-bullets", "#aplus", "#aplus3p_feature_div"]:
        description = soup.select_one(selector)
        if description:
            return description.text.strip()

    return None


def extract_features(soup):
    """상품 특징 추출"""
    features = []
    feature_items = soup.select(
        "#feature-bullets li span.a-list-item, #feature-bullets ul li"
    )
    for item in feature_items:
        feature_text = item.text.strip()
        if feature_text:
            features.append(feature_text)
    return features


def extract_technical_details(soup):
    """기술 세부 정보 추출"""
    tech_details = {}

    # 방법 1: 기술 명세 테이블
    detail_rows = soup.select(
        "#productDetails_techSpec_section_1 tr, #productDetails_detailBullets_sections1 tr"
    )
    for row in detail_rows:
        key_element = row.select_one("th")
        value_element = row.select_one("td")

        if key_element and value_element:
            key = key_element.text.strip().rstrip(":")
            value = value_element.text.strip()
            tech_details[key] = value

    # 방법 2: 상세 정보 글머리 기호
    if not tech_details:
        detail_bullets = soup.select(
            "#detailBullets_feature_div li, #detailBulletsWrapper_feature_div li"
        )
        for bullet in detail_bullets:
            text = bullet.text.strip()
            parts = text.split(":", 1)
            if len(parts) == 2:
                key = parts[0].strip()
                value = parts[1].strip()
                tech_details[key] = value

    return tech_details


def extract_categories(soup):
    """카테고리 경로 추출"""
    categories = []
    breadcrumbs = soup.select(
        "#wayfinding-breadcrumbs_feature_div li, .a-breadcrumb li"
    )
    for crumb in breadcrumbs:
        link = crumb.select_one("a")
        if link:
            category_text = link.text.strip()
            if category_text:
                categories.append(category_text)
    return categories


def extract_seller_info(soup):
    """판매자 정보 추출"""
    seller_element = soup.select_one(
        "#merchant-info, #bylineInfo, #sellerProfileTriggerId"
    )
    if seller_element:
        return seller_element.text.strip()
    return None


def extract_delivery_info(soup):
    """배송 정보 추출"""
    delivery_element = soup.select_one("#delivery-message, #mir-layout-DELIVERY_BLOCK")
    if delivery_element:
        return delivery_element.text.strip()
    return None


def extract_variations(soup):
    """변형 상품 (색상, 사이즈) 추출"""
    variations = {}

    # 색상 옵션
    colors = []
    color_elements = soup.select("#variation_color_name li, #variation_style_name li")
    for element in color_elements:
        if "title" in element.attrs:
            color = element["title"].strip()
            if color and color != "":
                colors.append(color)

    if colors:
        variations["colors"] = colors

    # 사이즈 옵션
    sizes = []
    size_elements = soup.select("#variation_size_name li, #variation-size-name li")
    for element in size_elements:
        if "title" in element.attrs:
            size = element["title"].strip()
            if size and size != "":
                sizes.append(size)

    if sizes:
        variations["sizes"] = sizes

    return variations


def save_to_csv(product_info, filename="amazon_products.csv"):
    """상품 정보를 CSV 파일로 저장"""
    try:
        # 첫 상품인 경우 헤더 작성
        file_exists = os.path.isfile(filename)

        # 리스트 및 딕셔너리 데이터 직렬화
        serialized_info = product_info.copy()
        for key, value in serialized_info.items():
            if isinstance(value, (list, dict)):
                serialized_info[key] = json.dumps(value, ensure_ascii=False)

        with open(filename, "a", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=serialized_info.keys())

            if not file_exists:
                writer.writeheader()

            writer.writerow(serialized_info)

        print(f"상품 정보가 {filename}에 저장되었습니다.")
        return True
    except Exception as e:
        print(f"CSV 저장 중 오류 발생: {str(e)}")
        return False


# 여러 상품을 크롤링하는 함수
def crawl_multiple_products(urls, delay_range=(2, 5)):
    """
    여러 아마존 상품 URL을 크롤링

    Args:
        urls (list): 크롤링할 아마존 상품 URL 리스트
        delay_range (tuple): 요청 간 딜레이 범위(초)
    """
    results = []

    for i, url in enumerate(urls):
        print(f"\n크롤링 중... ({i+1}/{len(urls)}): {url}")

        product_info = get_amazon_product_info(url)

        if product_info:
            results.append(product_info)
            save_to_csv(product_info)

        # 아마존 차단 방지를 위한 랜덤 딜레이
        if i < len(urls) - 1:
            delay = random.uniform(delay_range[0], delay_range[1])
            print(f"{delay:.2f}초 대기 중...")
            time.sleep(delay)

    return results


# 예제 사용
if __name__ == "__main__":
    url = "https://www.amazon.com/Redragon-S101-Keyboard-Ergonomic-Programmable/dp/B00NLZUM36/ref=sr_1_1?_encoding=UTF8&content-id=amzn1.sym.12129333-2117-4490-9c17-6d31baf0582a&dib=eyJ2IjoiMSJ9.GoHw03VyLhlV5P1QkaN6Db4TKoOJxQGgBCl7sb9n2w1_OhgfhzTvvor7hYb8UD6INjAYWlhYnbzpUbZQj3Tfe1_y_5OP6dNPnQ3rCCDK2OFllnNwl-RQO3l1tsy3Xq-Wa9PJ4df2EIe2POQvHibpa0feqMTyPxgC4pSUflfQsW-0tL2V7g68grRnlXgS6wmXuw4fA-4hIk_Yn1ZpqvWP-4Towd67P8Ak-RpgASxD-Lk.23ML92Bu-2bsXPfBER2l_oMnVrzXOFojf-Q3mIP8-9M&dib_tag=se&keywords=gaming%2Bkeyboard&pd_rd_r=3c33972b-071d-4709-a4ec-8a8f4d9a616c&pd_rd_w=KWKlr&pd_rd_wg=njj4D&qid=1743049338&sr=8-1&th=1"

    product_info = get_amazon_product_info(url)

    if product_info:
        print("추출된 상품 정보:")
        for key, value in product_info.items():
            print(f"{key}: {value}")

        # CSV 파일로 저장
        save_to_csv(product_info)
    else:
        print("상품 정보를 가져오는데 실패했습니다.")
