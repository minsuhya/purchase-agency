#!/usr/bin/env python3
import asyncio
import sys
import os
from pathlib import Path
import json

# 상위 디렉토리 경로 추가하여 app 패키지 임포트 가능하게 함
current_dir = Path(__file__).resolve().parent
parent_dir = current_dir.parent.parent
sys.path.append(str(parent_dir))

from loguru import logger
from app.utils.amazon_scraper import AmazonScraper
from app.utils.ebay_scraper import EbayScraper
from app.utils.generic_scraper import GenericScraper
from app.utils.vvic_scraper import VvicScraper
from app.utils.product_scraper import ProductScraper

# 로그 설정
logger.remove()
logger.add(sys.stdout, level="INFO")

async def test_amazon_scraper():
    """Amazon 스크레이퍼 테스트"""
    try:
        logger.info("Amazon 스크레이퍼 테스트 시작...")
        scraper = AmazonScraper()
        url = "https://www.amazon.com/dp/B07ZPKN6YR"  # 테스트용 Amazon 상품 URL
        product_info = await scraper.scrape(url)
        
        if product_info:
            logger.info(f"Amazon 스크레이핑 성공: {product_info.title}")
            logger.info(f"가격: {product_info.price_currency} {product_info.price}")
            logger.info(f"이미지 수: {len(product_info.images)}")
            logger.info(f"옵션 수: {len(product_info.options)}")
            return True
        else:
            logger.error("Amazon 스크레이핑 실패: 제품 정보가 없습니다.")
            return False
    except Exception as e:
        logger.error(f"Amazon 스크레이퍼 테스트 중 오류 발생: {str(e)}")
        return False

async def test_ebay_scraper():
    """eBay 스크레이퍼 테스트"""
    try:
        logger.info("eBay 스크레이퍼 테스트 시작...")
        scraper = EbayScraper()
        url = "https://www.ebay.com/itm/234195262343"  # 테스트용 eBay 상품 URL
        product_info = await scraper.scrape(url)
        
        if product_info:
            logger.info(f"eBay 스크레이핑 성공: {product_info.title}")
            logger.info(f"가격: {product_info.price_currency} {product_info.price}")
            logger.info(f"이미지 수: {len(product_info.images)}")
            logger.info(f"옵션 수: {len(product_info.options)}")
            return True
        else:
            logger.error("eBay 스크레이핑 실패: 제품 정보가 없습니다.")
            return False
    except Exception as e:
        logger.error(f"eBay 스크레이퍼 테스트 중 오류 발생: {str(e)}")
        return False

async def test_generic_scraper():
    """일반 스크레이퍼 테스트"""
    try:
        logger.info("일반 스크레이퍼 테스트 시작...")
        scraper = GenericScraper()
        url = "https://www.target.com/p/dyson-v8-origin-vacuum/-/A-85778990"  # 테스트용 일반 상품 URL
        product_info = await scraper.scrape(url)
        
        if product_info:
            logger.info(f"일반 스크레이핑 성공: {product_info.title}")
            logger.info(f"가격: {product_info.price_currency} {product_info.price}")
            logger.info(f"이미지 수: {len(product_info.images)}")
            return True
        else:
            logger.error("일반 스크레이핑 실패: 제품 정보가 없습니다.")
            return False
    except Exception as e:
        logger.error(f"일반 스크레이퍼 테스트 중 오류 발생: {str(e)}")
        return False

async def test_vvic_scraper():
    """VVIC 스크레이퍼 테스트"""
    try:
        logger.info("VVIC 스크레이퍼 테스트 시작...")
        scraper = VvicScraper()
        url = "https://www.vvic.com/item/652d12b9b9e4b1db53fda9db"  # 테스트용 VVIC 상품 URL
        product_info = await scraper.scrape(url)
        
        if product_info:
            logger.info(f"VVIC 스크레이핑 성공: {product_info.title}")
            logger.info(f"가격: {product_info.price_currency} {product_info.price}")
            logger.info(f"이미지 수: {len(product_info.images)}")
            logger.info(f"옵션 수: {len(product_info.options)}")
            
            # 원시 데이터 확인 (JSON 형식)
            if product_info.raw_data:
                logger.info("원시 데이터 확인 성공")
                
                # 원시 데이터를 파일에 저장 (테스트 목적)
                save_path = current_dir / "vvic_sample_data.json"
                with open(save_path, "w", encoding="utf-8") as f:
                    json.dump(product_info.raw_data, f, ensure_ascii=False, indent=2)
                logger.info(f"원시 데이터를 파일에 저장: {save_path}")
            
            return True
        else:
            logger.error("VVIC 스크레이핑 실패: 제품 정보가 없습니다.")
            return False
    except Exception as e:
        logger.error(f"VVIC 스크레이퍼 테스트 중 오류 발생: {str(e)}")
        return False

async def test_product_scraper():
    """제품 스크레이퍼 팩토리 테스트"""
    try:
        logger.info("제품 스크레이퍼 팩토리 테스트 시작...")
        scraper = ProductScraper(use_cache=True)
        
        # 다양한 도메인 테스트
        test_urls = [
            "https://www.amazon.com/dp/B07ZPKN6YR",
            "https://www.ebay.com/itm/234195262343",
            "https://www.vvic.com/item/652d12b9b9e4b1db53fda9db",
            "https://www.target.com/p/dyson-v8-origin-vacuum/-/A-85778990"
        ]
        
        for url in test_urls:
            try:
                logger.info(f"URL 테스트 중: {url}")
                product_info = await scraper.scrape_product(url)
                
                if product_info:
                    logger.info(f"스크레이핑 성공: {product_info.title}")
                    logger.info(f"가격: {product_info.price_currency} {product_info.price}")
                    logger.info(f"이미지 수: {len(product_info.images)}")
                else:
                    logger.error(f"스크레이핑 실패: {url}")
            except Exception as e:
                logger.error(f"URL {url} 테스트 중 오류 발생: {str(e)}")
        
        return True
    except Exception as e:
        logger.error(f"제품 스크레이퍼 팩토리 테스트 중 오류 발생: {str(e)}")
        return False

async def main():
    """메인 테스트 실행"""
    logger.info("스크레이퍼 테스트 시작...")
    
    tests = [
        # ("Amazon 스크레이퍼", test_amazon_scraper),
        # ("eBay 스크레이퍼", test_ebay_scraper),
        # ("일반 스크레이퍼", test_generic_scraper),
        ("VVIC 스크레이퍼", test_vvic_scraper),
        # ("제품 스크레이퍼 팩토리", test_product_scraper)
    ]
    
    results = []
    for name, test_func in tests:
        try:
            logger.info(f"{name} 테스트 실행 중...")
            result = await test_func()
            results.append((name, result))
            logger.info(f"{name} 테스트 완료: {'성공' if result else '실패'}")
        except Exception as e:
            logger.error(f"{name} 테스트 중 예외 발생: {str(e)}")
            results.append((name, False))
    
    # 결과 요약
    logger.info("\n테스트 결과 요약:")
    for name, result in results:
        logger.info(f"{name}: {'성공' if result else '실패'}")
    
    success_count = sum(1 for _, result in results if result)
    logger.info(f"총 {len(results)}개 테스트 중 {success_count}개 성공, {len(results) - success_count}개 실패")
    
    logger.info("스크레이퍼 테스트 종료.")

if __name__ == "__main__":
    asyncio.run(main()) 