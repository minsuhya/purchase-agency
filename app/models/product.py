from typing import List, Dict, Optional, Any, Union
from datetime import datetime
from sqlmodel import SQLModel, Field, JSON, Text, String, Float, DateTime, Integer
from pydantic import HttpUrl, validator
import json
import logging

logger = logging.getLogger(__name__)

class ProductImage(SQLModel, table=False):
    """상품 이미지 모델"""
    url: str = Field(sa_type=String(1000))
    alt: Optional[str] = Field(default=None, sa_type=String(200))

class ProductOption(SQLModel, table=False):
    """상품 옵션 모델"""
    title: str = Field(sa_type=String(100))
    values: List[str] = Field(default_factory=list, sa_type=JSON)

class CombinedOption(SQLModel, table=False):
    """상품 조합 옵션 모델"""
    combination: Dict[str, str] = Field(sa_type=JSON)
    price: Optional[float] = Field(default=None, sa_type=Float)
    stock: Optional[int] = Field(default=None)
    sku: Optional[str] = Field(default=None, sa_type=String(100))

class ProductBase(SQLModel):
    """Product 기본 모델"""
    # URL 정보
    url: str = Field(sa_type=String(1000))
    
    # 제목 정보
    title_original: str = Field(sa_type=String(500))
    title_translated: str = Field(sa_type=String(500))
    
    # 가격 정보
    price_original: str = Field(sa_type=String(100))
    price_value: float = Field(sa_type=Float)
    price_krw: float = Field(sa_type=Float)
    currency: str = Field(sa_type=String(10))
    
    # 설명 정보
    description_original: str = Field(sa_type=Text)
    description_translated: str = Field(sa_type=Text)
    
    # 스펙 정보
    specifications_original: Dict[str, Any] = Field(default_factory=dict, sa_type=JSON)
    specifications_translated: Dict[str, Any] = Field(default_factory=dict, sa_type=JSON)
    
    # 옵션 정보
    options_original: List[Dict[str, Any]] = Field(default_factory=list, sa_type=JSON)
    options_translated: List[Dict[str, Any]] = Field(default_factory=list, sa_type=JSON)
    
    # 카테고리 정보
    categories_original: List[str] = Field(default_factory=list, sa_type=JSON)
    categories_translated: List[str] = Field(default_factory=list, sa_type=JSON)
    
    # 이미지 정보
    images: List[Dict[str, Any]] = Field(default_factory=list, sa_type=JSON)

    # AI 생성 상품 상세 HTML
    ai_detail_html: Optional[str] = Field(default=None, sa_type=Text)
    
    # 원본 데이터
    raw_data: Dict[str, Any] = Field(default_factory=dict, sa_type=JSON)
    
    # 메타데이터
    created_at: datetime = Field(default_factory=datetime.utcnow, sa_type=DateTime)
    updated_at: Optional[datetime] = Field(default=None, sa_type=DateTime)

    @validator('specifications_original', 'specifications_translated', 'options_original', 'options_translated', 'categories_original', 'categories_translated', 'images', 'raw_data', pre=True)
    def validate_json_fields(cls, v):
        """JSON 필드들을 검증하고 변환합니다."""
        if isinstance(v, str):
            try:
                # 유니코드 이스케이프 시퀀스를 실제 문자로 변환
                return json.loads(v, strict=False)
            except json.JSONDecodeError:
                logger.warning(f"JSON 파싱 실패: {v[:100]}...")
                return {} if v in ['specifications_original', 'specifications_translated', 'raw_data'] else []
        elif isinstance(v, (dict, list)):
            # 딕셔너리나 리스트의 경우, 내부의 문자열도 처리
            if isinstance(v, dict):
                return {k: cls.validate_json_fields(v) for k, v in v.items()}
            else:
                return [cls.validate_json_fields(item) for item in v]
        else:
            logger.warning(f"지원하지 않는 JSON 필드 타입: {type(v)}")
            return {} if v in ['specifications_original', 'specifications_translated', 'raw_data'] else []

class Product(ProductBase, table=True):
    """상품 모델"""
    id: Optional[int] = Field(default=None, primary_key=True)

    class Config:
        arbitrary_types_allowed = True
        json_encoders = {
            datetime: lambda v: v.isoformat() if v else None
        }
        
    def dict(self, *args, **kwargs):
        """모델을 딕셔너리로 변환합니다."""
        try:
            d = super().dict(*args, **kwargs)
            # datetime 필드 처리
            for key, value in d.items():
                if isinstance(value, datetime):
                    d[key] = value.isoformat()
                elif isinstance(value, dict):
                    # 중첩된 딕셔너리 내의 datetime 처리
                    for k, v in value.items():
                        if isinstance(v, datetime):
                            value[k] = v.isoformat()
            return d
        except Exception as e:
            logger.error(f"모델을 딕셔너리로 변환 중 오류 발생: {str(e)}")
            return {}
        
    def update(self, **kwargs):
        """상품 정보를 업데이트합니다."""
        for key, value in kwargs.items():
            if hasattr(self, key):
                setattr(self, key, value)
        self.updated_at = datetime.utcnow()
        
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Product':
        """딕셔너리로부터 Product 인스턴스를 생성합니다."""
        # datetime 문자열을 datetime 객체로 변환
        if 'created_at' in data and isinstance(data['created_at'], str):
            data['created_at'] = datetime.fromisoformat(data['created_at'])
        if 'updated_at' in data and isinstance(data['updated_at'], str):
            data['updated_at'] = datetime.fromisoformat(data['updated_at'])
            
        return cls(**data)

    def to_json(self) -> str:
        """모델을 JSON 문자열로 변환합니다."""
        try:
            # dict() 메서드를 사용하여 딕셔너리로 변환
            data = self.dict()
            # JSON 문자열로 변환 (ensure_ascii=False로 설정하여 유니코드 문자를 그대로 유지)
            return json.dumps(
                data,
                ensure_ascii=False,  # 한글 등 non-ASCII 문자를 유니코드로 변환하지 않음
                default=str  # datetime 등 기본적으로 직렬화할 수 없는 타입 처리
            )
        except Exception as e:
            logger.error(f"모델을 JSON으로 변환 중 오류 발생: {str(e)}")
            return "{}" 