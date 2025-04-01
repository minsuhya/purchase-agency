from fastapi import APIRouter, Request, Form, HTTPException, Depends, Query, BackgroundTasks
from fastapi.responses import HTMLResponse, JSONResponse
from pathlib import Path
import sys
import json
import uuid
import time
import traceback
from typing import List, Dict, Any, Optional, Union
from datetime import datetime, timedelta

from sqlmodel import Session
from app.scraper.product_scraper import ProductScraper
from app.utils.translate import translate_product_info
from app.utils.ai_detail_generator import generate_product_detail
from app.models.product import Product
from app.models.database import get_db
from app.utils.templates import get_templates
from loguru import logger

router = APIRouter(prefix="/product", tags=["product"])
templates = get_templates()

# 스크레이퍼 인스턴스를 싱글톤으로 생성 (리소스 효율성)
scraper = ProductScraper(use_cache=True, cache_max_age_days=7)

async def process_product_scraping(product_url: str, force_refresh: bool = False, db: Session = None):
    """백그라운드에서 상품 스크래핑을 처리합니다."""
    try:
        # URL 유효성 검사
        if not product_url.startswith(("http://", "https://")):
            product_url = "https://" + product_url
            
        logger.info(f"상품 스크래핑 시작: {product_url} (force_refresh: {force_refresh})")
        
        # 상품 정보 수집 (force_refresh 전달)
        product_info = await scraper.scrape(product_url, force_refresh=force_refresh)
        if not product_info:
            raise ValueError("상품 정보를 가져오지 못했습니다.")

        # 번역 및 정보 처리
        translated_info = await translate_product_info(product_info)
        # logger.info(f"번역된 정보 타입:")
        # for key, value in translated_info.dict().items():
        #     logger.info(f"키: {key} ({type(key).__name__}), 값: {type(value).__name__}")

        # 데이터베이스에 저장
        if db:
            try:
                # force_refresh가 True인 경우 기존 상품 업데이트
                if force_refresh:
                    existing_product = db.query(Product).filter(Product.url == product_url).first()
                    if existing_product:
                        # 기존 상품 정보 업데이트
                        for key, value in translated_info.dict(exclude={'id'}).items():
                            if hasattr(existing_product, key):
                                setattr(existing_product, key, value)
                        existing_product.updated_at = datetime.utcnow()
                        db.commit()
                        db.refresh(existing_product)
                        translated_info = existing_product
                        logger.info(f"기존 상품 업데이트 완료: {existing_product.id}")
                    else:
                        # 새 상품 추가
                        db.add(translated_info)
                        db.commit()
                        db.refresh(translated_info)
                        logger.info(f"새 상품 저장 완료: {translated_info.id}")
                else:
                    # 새 상품 추가
                    db.add(translated_info)
                    db.commit()
                    db.refresh(translated_info)
                    logger.info(f"새 상품 저장 완료: {translated_info.id}")
            
            except Exception as e:
                db.rollback()
                logger.error(f"데이터베이스 저장 중 오류 발생: {str(e)}")
                raise HTTPException(
                    status_code=500,
                    detail="상품 정보를 데이터베이스에 저장하는 중 오류가 발생했습니다."
                )
            
        return translated_info
        
    except Exception as e:
        error_msg = f"상품 스크래핑 처리 중 오류 발생: {str(e)}"
        if hasattr(e, '__traceback__'):
            error_msg += f" (파일: {e.__traceback__.tb_frame.f_code.co_filename}, 줄: {e.__traceback__.tb_lineno})"
        logger.error(error_msg, exc_info=True)
        raise

@router.get("/", response_class=HTMLResponse)
async def get_product_form(request: Request):
    """상품 URL 입력 폼을 제공합니다."""
    return templates.TemplateResponse("product_form.html", {"request": request})

@router.post("/scrape", response_class=HTMLResponse)
async def scrape_product(
    request: Request, 
    background_tasks: BackgroundTasks,
    product_url: str = Form(...),
    force_refresh: bool = Form(False),
    db: Session = Depends(get_db)
):
    """상품 URL에서 정보를 수집하고 결과를 보여줍니다."""
    try:
        # 백그라운드에서 스크래핑 처리
        product_info = await process_product_scraping(product_url, force_refresh, db)
        
        # 템플릿에 데이터 전달
        return templates.TemplateResponse(
            "product_result.html", 
            {
                "request": request, 
                "product": product_info,
                "from_cache": getattr(product_info, 'from_cache', False)
            }
        )
    except Exception as e:
        error_msg = f"상품 스크래핑 중 오류 발생: {str(e)} (파일: {e.__traceback__.tb_frame.f_code.co_filename}, 줄: {e.__traceback__.tb_lineno})"
        error_details = {
            "error_type": type(e).__name__,
            "error_msg": str(e),
            "file": e.__traceback__.tb_frame.f_code.co_filename,
            "line": e.__traceback__.tb_lineno,
            "traceback": traceback.format_exc()
        }
        logger.error(error_msg, extra=error_details, exc_info=True)
        
        return templates.TemplateResponse(
            "error.html",
            {
                "request": request,
                "error": error_msg,
                "error_details": error_details
            }
        )

@router.get("/list", response_class=HTMLResponse)
async def list_products(
    request: Request,
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    search: Optional[str] = None,
    sort_by: Optional[str] = None,
    sort_order: Optional[str] = "desc",
    db: Session = Depends(get_db)
):
    """상품 목록을 보여줍니다."""
    try:
        # 검색 조건 구성
        query = db.query(Product)
        
        if search:
            search_term = f"%{search}%"
            query = query.filter(
                (Product.title_original.ilike(search_term)) |
                (Product.title_translated.ilike(search_term)) |
                (Product.description_original.ilike(search_term)) |
                (Product.description_translated.ilike(search_term))
            )
        
        # 정렬 조건 적용
        if sort_by:
            sort_column = getattr(Product, sort_by, Product.created_at)
            if sort_order == "desc":
                query = query.order_by(sort_column.desc())
            else:
                query = query.order_by(sort_column.asc())
        else:
            query = query.order_by(Product.created_at.desc())
        
        # 페이지네이션 적용
        total = query.count()
        products = query.offset(skip).limit(limit).all()
        
        return templates.TemplateResponse(
            "product_list.html",
            {
                "request": request,
                "products": products,
                "skip": skip,
                "limit": limit,
                "total": total,
                "search": search,
                "sort_by": sort_by,
                "sort_order": sort_order
            }
        )
    except Exception as e:
        logger.error(f"상품 목록 조회 중 오류 발생: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/{product_id}", response_class=HTMLResponse)
async def get_product_detail(
    request: Request,
    product_id: int,
    db: Session = Depends(get_db)
):
    """상품 상세 정보를 보여줍니다."""
    try:
        product = db.query(Product).filter(Product.id == product_id).first()
        if not product:
            raise HTTPException(status_code=404, detail="상품을 찾을 수 없습니다.")
            
        return templates.TemplateResponse(
            "product_detail.html",
            {
                "request": request,
                "product": product
            }
        )
    except Exception as e:
        logger.error(f"상품 상세 조회 중 오류 발생: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/{product_id}/edit", response_class=HTMLResponse)
async def get_product_edit_form(
    request: Request,
    product_id: int,
    db: Session = Depends(get_db)
):
    """상품 수정 폼을 보여줍니다."""
    try:
        product = db.query(Product).filter(Product.id == product_id).first()
        if not product:
            raise HTTPException(status_code=404, detail="상품을 찾을 수 없습니다.")
            
        return templates.TemplateResponse(
            "product_edit.html",
            {
                "request": request,
                "product": product
            }
        )
    except Exception as e:
        logger.error(f"상품 수정 폼 로드 중 오류 발생: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/{product_id}/edit", response_class=HTMLResponse)
async def update_product(
    request: Request,
    product_id: int,
    background_tasks: BackgroundTasks,
    product_url: Optional[str] = Form(None),
    title_original: Optional[str] = Form(None),
    title_translated: Optional[str] = Form(None),
    price_value: Optional[float] = Form(None),
    currency: Optional[str] = Form(None),
    price_krw: Optional[int] = Form(None),
    categories_original: Optional[str] = Form(None),
    categories_translated: Optional[str] = Form(None),
    options_original: Optional[str] = Form(None),
    options_translated: Optional[str] = Form(None),
    description_original: Optional[str] = Form(None),
    description_translated: Optional[str] = Form(None),
    specifications_original: Optional[str] = Form(None),
    specifications_translated: Optional[str] = Form(None),
    db: Session = Depends(get_db)
):
    """상품 정보를 업데이트합니다."""
    try:
        product = db.query(Product).filter(Product.id == product_id).first()
        if not product:
            raise HTTPException(status_code=404, detail="상품을 찾을 수 없습니다.")
        
        # 폼 데이터로 직접 업데이트
        update_data = {
            'url': product_url,
            'title_original': title_original,
            'title_translated': title_translated,
            'price_value': price_value,
            'currency': currency,
            'price_krw': price_krw,
            'description_original': description_original,
            'description_translated': description_translated
        }
        
        # JSON 필드 처리
        try:
            if categories_original:
                update_data['categories_original'] = json.loads(categories_original)
            if categories_translated:
                update_data['categories_translated'] = json.loads(categories_translated)
            if options_original:
                update_data['options_original'] = json.loads(options_original)
            if options_translated:
                update_data['options_translated'] = json.loads(options_translated)
            if specifications_original:
                update_data['specifications_original'] = json.loads(specifications_original)
            if specifications_translated:
                update_data['specifications_translated'] = json.loads(specifications_translated)
        except json.JSONDecodeError as e:
            logger.error(f"JSON 파싱 오류: {str(e)}")
            raise HTTPException(status_code=400, detail="잘못된 JSON 형식입니다.")
        
        # 데이터베이스 업데이트
        for key, value in update_data.items():
            if value is not None and hasattr(product, key):
                setattr(product, key, value)
        
        # 업데이트 시간 갱신
        product.updated_at = datetime.utcnow()
        db.commit()
        db.refresh(product)
        
        return templates.TemplateResponse(
            "product_detail.html",
            {
                "request": request,
                "product": product,
                "message": "상품 정보가 업데이트되었습니다."
            }
        )
    except Exception as e:
        logger.error(f"상품 정보 업데이트 중 오류 발생: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/{product_id}/ai-detail", response_class=HTMLResponse)
async def get_product_ai_detail_form(
    request: Request,
    product_id: int,
    db: Session = Depends(get_db)
):
    """AI 상품 상세 생성 페이지를 보여줍니다."""
    try:
        product = db.query(Product).filter(Product.id == product_id).first()
        if not product:
            raise HTTPException(status_code=404, detail="상품을 찾을 수 없습니다.")
            
        return templates.TemplateResponse(
            "product_ai_detail.html",
            {
                "request": request,
                "product": product
            }
        )
    except Exception as e:
        logger.error(f"AI 상품 상세 페이지 로드 중 오류 발생: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/{product_id}/generate-detail")
def generate_product_detail_page(
    product_id: int,
    db: Session = Depends(get_db)
):
    """AI를 사용하여 상품 상세 페이지를 생성합니다."""
    try:
        product = db.query(Product).filter(Product.id == product_id).first()
        if not product:
            raise HTTPException(status_code=404, detail="상품을 찾을 수 없습니다.")

        # AI 상품 상세 생성 (동기 방식)
        generated_html = generate_product_detail(product)
        
        # 생성된 HTML을 DB에 저장
        product.ai_detail_html = generated_html
        product.updated_at = datetime.utcnow()
        db.commit()
        db.refresh(product)
        
        return JSONResponse({
            "content": generated_html
        })
    except Exception as e:
        logger.error(f"AI 상품 상세 생성 중 오류 발생: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))