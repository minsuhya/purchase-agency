import os
from fastapi import Request
from fastapi.templating import Jinja2Templates
from pathlib import Path
import jinja2

# 템플릿 디렉토리 설정
templates_dir = Path(__file__).parent.parent / "templates"

# 템플릿 인스턴스 생성
templates = Jinja2Templates(directory=str(templates_dir))

def get_templates() -> Jinja2Templates:
    """템플릿 인스턴스를 반환합니다."""
    return templates

@jinja2.pass_context
def linebreaks_filter(context, value):
    """줄바꿈을 HTML <br> 태그로 변환합니다."""
    if value:
        return value.replace('\n', '<br>')
    return ''

def setup_templates(templates_instance=None):
    """템플릿 설정 및 커스텀 필터 등록"""
    
    # 템플릿 인스턴스 설정
    target_templates = templates_instance if templates_instance else templates
    
    # 커스텀 필터 등록
    target_templates.env.filters["format_currency"] = format_currency
    target_templates.env.filters["format_date"] = format_date
    target_templates.env.filters["safe_dict_get"] = safe_dict_get
    target_templates.env.filters["linebreaks"] = linebreaks_filter
    
    return target_templates

def format_currency(value, currency="KRW", show_symbol=True):
    """통화 형식으로 포맷팅"""
    if value is None:
        return "N/A"
        
    try:
        # 숫자로 변환 시도
        if isinstance(value, str):
            # 쉼표, 통화 기호 등 제거
            value = value.replace(",", "").strip()
            for symbol in ["$", "€", "£", "¥", "₩", "원", "￦"]:
                value = value.replace(symbol, "")
            value = float(value)
        
        # 통화별 포맷팅
        if currency == "KRW" or currency == "JPY":
            formatted = f"{int(value):,}"
        else:
            formatted = f"{value:,.2f}"
            
        # 통화 기호 추가
        if show_symbol:
            symbols = {
                "USD": "$", 
                "EUR": "€", 
                "GBP": "£", 
                "JPY": "¥", 
                "KRW": "₩", 
                "CNY": "¥"
            }
            symbol = symbols.get(currency, "")
            
            if currency in ["KRW"]:
                formatted = f"{formatted}{symbol}"
            else:
                formatted = f"{symbol}{formatted}"
                
        return formatted
    
    except (ValueError, TypeError):
        # 숫자로 변환할 수 없는 경우 원본 반환
        return value

def format_date(value, format="%Y-%m-%d"):
    """날짜 형식으로 포맷팅"""
    if not value:
        return ""
        
    if hasattr(value, "strftime"):
        return value.strftime(format)
    
    # ISO 형식이나 다른 문자열 날짜는 그대로 반환
    return value

def safe_dict_get(d, key, default=""):
    """딕셔너리에서 키값을 안전하게 가져오기"""
    if not isinstance(d, dict):
        return default
        
    return d.get(key, default) 