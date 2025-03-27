from fastapi import APIRouter, Request, Form, HTTPException, Depends, Query
from fastapi.responses import HTMLResponse, JSONResponse
from pathlib import Path
import json
import uuid
import time
import traceback
from typing import List, Dict, Any, Optional, Union
from datetime import datetime, timedelta

from app.utils.product_scraper import ProductScraper
from app.utils.translate import translate_product_info
from app.models.product import ProductInfo
from app.utils.templates import get_templates
from loguru import logger

router = APIRouter(prefix="/product", tags=["product"])
templates = get_templates()

# 세션 데이터를 저장할 메모리 저장소 (실제 프로덕션에서는 Redis 등 사용 권장)
PRODUCT_SESSION = {}
# 세션 만료 시간 (초)
SESSION_EXPIRY = 3600  # 1시간

# 스크레이퍼 인스턴스를 싱글톤으로 생성 (리소스 효율성)
scraper = ProductScraper(use_cache=True, cache_max_age_days=7)

# 주기적으로 만료된 세션 정리
def cleanup_expired_sessions() -> None:
    """만료된 세션을 정리합니다."""
    try:
        current_time = time.time()
        expired_sessions = []
        
        for session_id, session_data in PRODUCT_SESSION.items():
            if current_time - session_data.get("timestamp", 0) > SESSION_EXPIRY:
                expired_sessions.append(session_id)
        
        # 만료된 세션 삭제
        for session_id in expired_sessions:
            del PRODUCT_SESSION[session_id]
            
        if expired_sessions:
            logger.info(f"{len(expired_sessions)}개의 만료된 세션이 정리되었습니다.")
    except Exception as e:
        logger.error(f"세션 정리 중 오류 발생: {str(e)}")

@router.get("/", response_class=HTMLResponse)
async def get_product_form(request: Request):
    """상품 URL 입력 폼을 제공합니다."""
    # 가끔 만료된 세션 정리
    if len(PRODUCT_SESSION) > 100:  # 세션이 100개 이상 쌓이면 정리
        cleanup_expired_sessions()
    return templates.TemplateResponse("product_form.html", {"request": request})

@router.post("/scrape", response_class=HTMLResponse)
async def scrape_product(
    request: Request, 
    product_url: str = Form(...),
    force_refresh: bool = Form(False)
):
    """
    상품 URL에서 정보를 수집하고 결과를 보여줍니다.
    
    Args:
        request: 요청 객체
        product_url: 상품 URL
        force_refresh: 캐시를 무시하고 새로 가져올지 여부
    """
    try:
        # URL 유효성 기본 검사
        if not product_url.startswith(("http://", "https://")):
            product_url = "https://" + product_url
        
        logger.info(f"상품 스크래핑 시작: {product_url}")
            
        # 상품 정보 수집 (캐시 사용 또는 무시 설정)
        try:
            product_info = await scraper.scrape_product(product_url, force_refresh=force_refresh)
        except Exception as e:
            logger.error(f"스크래핑 단계에서 오류 발생: {str(e)}")
            raise Exception(f"상품 정보 수집 실패: {str(e)}")
            
        # 번역 및 정보 처리
        try:
            translated_info = await translate_product_info(product_info)
        except Exception as e:
            logger.error(f"번역 단계에서 오류 발생: {str(e)}")
            # 번역 실패 시에도 원본 정보 사용
            translated_info = product_info
        
        logger.info("ProductInfo 객체를 딕셔너리로 변환 중")
        # ProductInfo 객체를 안전하게 직렬화
        try:
            original_info = convert_product_info_to_dict(product_info)
            translated_info_dict = convert_product_info_to_dict(translated_info)
        except Exception as e:
            logger.error(f"변환 단계에서 오류 발생: {str(e)}")
            raise Exception(f"데이터 변환 오류: {str(e)}")
        
        # 캐시에서 로드되었는지 확인
        from_cache = False
        if (hasattr(product_info, 'raw_data') and product_info.raw_data and 
            isinstance(product_info.raw_data, dict) and product_info.raw_data.get("from_cache", False)):
            from_cache = True
            logger.info("캐시에서 데이터를 불러왔습니다.")
        
        logger.info("세션 ID 생성 및 데이터 저장")
        # 세션 ID 생성 및 데이터 저장
        session_id = str(uuid.uuid4())
        PRODUCT_SESSION[session_id] = {
            "original_info": original_info,
            "translated_info": translated_info_dict,
            "timestamp": time.time()  # 세션 생성 시간 기록
        }
        
        logger.info("템플릿 렌더링 및 응답 반환")
        # 템플릿에 데이터 전달
        return templates.TemplateResponse(
            "product_result.html", 
            {
                "request": request, 
                "original_info": original_info, 
                "translated_info": translated_info_dict,
                "session_id": session_id,
                "from_cache": from_cache
            }
        )
    except Exception as e:
        error_msg = f"상품 스크래핑 중 오류 발생: {str(e)}"
        error_details = {
            "error_type": type(e).__name__,
            "error_msg": str(e),
            "traceback": traceback.format_exc()
        }
        logger.error(error_msg, extra=error_details, exc_info=True)
        logger.debug(f"오류 상세 정보: {error_details}")
        
        return templates.TemplateResponse(
            "error.html",
            {
                "request": request, 
                "error": str(e),
                "error_details": error_details
            }
        )

def convert_product_info_to_dict(product_info: ProductInfo) -> Dict[str, Any]:
    """ProductInfo 객체를 안전하게 딕셔너리로 변환합니다."""
    if product_info is None:
        logger.warning("변환할 ProductInfo 객체가 None입니다.")
        return {}
        
    # 결과 사전
    result = {}
    
    try:
        # 방법 1: Pydantic v2
        try:
            result = product_info.model_dump()
            logger.debug("Pydantic v2 model_dump 메서드로 변환 성공")
        except AttributeError:
            # 방법 2: Pydantic v1
            try:
                result = product_info.dict()
                logger.debug("Pydantic v1 dict 메서드로 변환 성공")
            except AttributeError:
                # 방법 3: __dict__ 직접 접근
                logger.debug("직접 변환 방식으로 변환 시도")
                if hasattr(product_info, '__dict__'):
                    for key, val in vars(product_info).items():
                        if not key.startswith('_'):
                            result[key] = _convert_obj_to_dict(val)
                else:
                    logger.error("ProductInfo 객체를 직렬화할 수 없습니다.")
                    return {}
    except Exception as e:
        logger.error(f"ProductInfo 직렬화 중 오류: {str(e)}", exc_info=True)
        # 최소한의 정보라도 반환하기 위해 빈 객체 생성
        result = {"error": "직렬화 오류", "message": str(e)}
        
        # 기본 필드 추가
        if hasattr(product_info, 'title'):
            try:
                result["title"] = _convert_obj_to_dict(product_info.title)
            except:
                result["title"] = {"original": "Unknown", "translated": ""}
                
        if hasattr(product_info, 'url'):
            try:
                result["url"] = str(product_info.url)
            except:
                result["url"] = ""
                
        return result
    
    # URL 처리
    try:
        if 'url' in result:
            result['url'] = str(result['url'])
        
        # 이미지 URL 처리 (main_image)
        if 'main_image' in result and result['main_image']:
            if isinstance(result['main_image'], dict) and 'url' in result['main_image']:
                result['main_image']['url'] = str(result['main_image']['url'])
            elif hasattr(result['main_image'], 'url'):
                # 객체인 경우
                result['main_image'] = {
                    'url': str(result['main_image'].url),
                    'alt': getattr(result['main_image'], 'alt', '')
                }
        
        # 이미지 URL 처리 (images 배열)
        if 'images' in result and result['images']:
            if isinstance(result['images'], (list, tuple)):
                processed_images = []
                for img in result['images']:
                    if isinstance(img, dict) and 'url' in img:
                        img_copy = img.copy()
                        img_copy['url'] = str(img['url'])
                        processed_images.append(img_copy)
                    elif hasattr(img, 'url'):
                        # 객체인 경우
                        processed_images.append({
                            'url': str(img.url),
                            'alt': getattr(img, 'alt', '')
                        })
                result['images'] = processed_images
                
        # options 처리 - option.values가 내장 함수 "values()"가 아닌 리스트임을 보장
        if 'options' in result and isinstance(result['options'], list):
            processed_options = []
            for option in result['options']:
                if isinstance(option, dict):
                    option_copy = option.copy()
                    
                    # values가 내장 함수처럼 보이는 경우를 처리
                    if 'values' in option and callable(option['values']):
                        # 대체 필드 사용 또는 빈 리스트로 대체
                        option_copy['values'] = option.get('option_values', [])
                    elif 'values' not in option or not isinstance(option['values'], (list, tuple)):
                        option_copy['values'] = []
                        
                    processed_options.append(option_copy)
                else:
                    # 객체인 경우 직접 접근
                    option_dict = {}
                    option_dict['title'] = getattr(option, 'title', '')
                    
                    # 객체의 values 속성에 접근
                    values_attr = getattr(option, 'values', None)
                    if values_attr is not None and not callable(values_attr):
                        option_dict['values'] = list(values_attr)
                    else:
                        # 대체 속성 시도
                        option_dict['values'] = getattr(option, 'option_values', [])
                        
                    processed_options.append(option_dict)
            
            result['options'] = processed_options
    except Exception as e:
        logger.error(f"URL 및 옵션 변환 중 오류 발생: {str(e)}", exc_info=True)
    
    return result

def _convert_obj_to_dict(obj: Any) -> Any:
    """
    중첩된 객체를 딕셔너리로 안전하게 변환합니다.
    반복 가능한 객체가 예상되는 곳에서 안전하게 처리합니다.
    
    Args:
        obj: 변환할 객체
        
    Returns:
        변환된 객체
    """
    # None 처리
    if obj is None:
        return None
    
    # 기본 타입은 그대로 반환
    if isinstance(obj, (str, int, float, bool)):
        return obj
        
    # 딕셔너리 처리
    if isinstance(obj, dict):
        result = {}
        for k, v in obj.items():
            result[str(k)] = _convert_obj_to_dict(v)
        return result
    
    # 리스트, 튜플, 세트 같은 반복 가능 객체 처리
    if isinstance(obj, (list, tuple, set)):
        return [_convert_obj_to_dict(item) for item in obj]
    
    # 사전형 객체로 변환 시도 (__dict__ 속성 이용)
    if hasattr(obj, '__dict__'):
        result = {}
        for key, val in vars(obj).items():
            if not key.startswith('_'):  # 비공개 속성 제외
                try:
                    # 특별한 속성 이름 처리 - 내장 함수 이름과 충돌할 수 있는 경우
                    if key == 'values' and callable(val):
                        # values가 메서드인 경우 대체 속성 찾기
                        if hasattr(obj, 'option_values'):
                            alternate_val = getattr(obj, 'option_values')
                            result[key] = _convert_obj_to_dict(alternate_val)
                        else:
                            # 기본값으로 빈 리스트 사용
                            result[key] = []
                    else:
                        result[key] = _convert_obj_to_dict(val)
                except Exception as e:
                    # 변환할 수 없는 경우 문자열로
                    logger.error(f"객체 속성 변환 오류 (key={key}): {str(e)}")
                    try:
                        result[key] = str(val)
                    except:
                        result[key] = f"<변환 불가능 {type(val).__name__}>"
        return result
    
    # 나머지 모든 케이스: 안전하게 문자열로 변환
    try:
        return str(obj)
    except Exception as e:
        logger.error(f"객체 문자열 변환 오류: {str(e)}")
        return f"<객체 {type(obj).__name__}>"

@router.get("/data/{session_id}", response_class=JSONResponse)
async def get_product_data(session_id: str):
    """세션 ID에 해당하는 상품 데이터를 JSON으로 반환합니다."""
    if session_id not in PRODUCT_SESSION:
        raise HTTPException(status_code=404, detail="세션 데이터를 찾을 수 없습니다.")
    
    # 세션 접근 시 타임스탬프 갱신
    PRODUCT_SESSION[session_id]["timestamp"] = time.time()
    
    return PRODUCT_SESSION[session_id]["translated_info"]

@router.post("/export", response_class=JSONResponse)
async def export_product_data(product_data: dict):
    """처리된 상품 데이터를 JSON 형태로 반환합니다."""
    try:
        # 이미 dict 형태로 받으므로 바로 반환
        return product_data
    except Exception as e:
        logger.error(f"상품 데이터 내보내기 중 오류 발생: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

# 캐시 관리 엔드포인트
@router.get("/cache/list", response_class=JSONResponse)
async def list_cache():
    """캐시된 모든 URL 목록을 반환합니다."""
    try:
        urls = scraper.get_cache_list()
        return {"count": len(urls), "urls": urls}
    except Exception as e:
        logger.error(f"캐시 목록 조회 중 오류 발생: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/cache", response_class=JSONResponse)
async def clear_cache(url: Optional[str] = None):
    """
    캐시를 삭제합니다.
    url 파라미터가 제공되면 해당 URL의 캐시만 삭제하고, 
    제공되지 않으면 모든 캐시를 삭제합니다.
    """
    try:
        result = scraper.clear_cache(url)
        message = f"{'특정 URL의' if url else '모든'} 캐시가 삭제되었습니다."
        return {"success": result, "message": message}
    except Exception as e:
        logger.error(f"캐시 삭제 중 오류 발생: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/debug", response_class=HTMLResponse)
async def debug_page(request: Request):
    """디버깅 도구 페이지를 제공합니다."""
    try:
        cache_urls = scraper.get_cache_list()
        session_count = len(PRODUCT_SESSION)
        
        return templates.TemplateResponse(
            "debug.html", 
            {
                "request": request,
                "cache_count": len(cache_urls),
                "cache_urls": cache_urls,
                "session_count": session_count
            }
        )
    except Exception as e:
        logger.error(f"디버깅 페이지 로드 중 오류 발생: {str(e)}")
        return templates.TemplateResponse(
            "error.html", 
            {"request": request, "error": str(e)}
        ) 