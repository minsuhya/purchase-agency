from typing import List, Dict, Optional, Any
from pydantic import BaseModel, Field, HttpUrl
import json
from datetime import datetime


class ProductImage(BaseModel):
    url: HttpUrl
    alt: Optional[str] = None
    
    class Config:
        json_encoders = {
            HttpUrl: str  # HttpUrl을 문자열로 변환
        }


class ProductOption(BaseModel):
    title: str
    values: List[str] = Field(default_factory=list, alias="option_values")
    
    class Config:
        # JSON 직렬화 시 특별 처리
        json_encoders = {
            list: lambda v: v
        }
        # 별칭 사용 허용
        populate_by_name = True


class CombinedOption(BaseModel):
    combination: Dict[str, str]
    price: Optional[float] = None
    stock: Optional[int] = None
    sku: Optional[str] = None


class ProductInfo(BaseModel):
    # 상품 기본 정보
    title: Dict[str, str] = Field(..., description="상품명 (원문 및 번역/수정된 버전)")
    brand: Optional[str] = None
    sku: Optional[str] = None
    url: HttpUrl = Field(..., description="상품 상세페이지 URL")
    
    price: Dict[str, Any] = Field(
        ..., 
        description="가격 정보: 현지 가격, 원화 환산 가격, 통화 등"
    )
    shipping_fee: Optional[float] = None
    stock: Optional[int] = None
    currency: str
    condition: Optional[str] = Field(None, description="상품 상태 (새상품, 중고, 리퍼 등)")
    
    # 카테고리 정보
    categories: List[str] = Field(default_factory=list, description="원문 사이트의 카테고리")
    
    # 이미지 데이터
    main_image: ProductImage
    images: List[ProductImage] = Field(default_factory=list, description="상품 전체 이미지 세트")
    
    # 상세 설명
    description: Dict[str, str] = Field(
        default_factory=dict, 
        description="상품 설명 (원문 및 번역된 버전)"
    )
    specifications: Optional[Dict[str, Dict[str, str]]] = Field(
        None, 
        description="상품 스펙 정보 (원문 및 번역된 버전)"
    )
    
    # 옵션 정보
    options: List[ProductOption] = Field(default_factory=list)
    combined_options: List[CombinedOption] = Field(
        default_factory=list, 
        description="조합된 옵션 정보"
    )
    
    # 메타데이터
    raw_data: Optional[Dict[str, Any]] = Field(None, description="원본 스크랩 데이터")
    created_at: Optional[str] = Field(default_factory=lambda: datetime.now().isoformat())
    
    class Config:
        # JSON 직렬화 시 Python 객체를 처리하는 방법 설정
        json_encoders = {
            HttpUrl: str  # HttpUrl을 문자열로 변환
        }
    
    def to_json(self) -> str:
        """모델을 JSON 문자열로 직렬화합니다."""
        # 첫 번째 방법: Pydantic v2 스타일
        try:
            return json.dumps(self.model_dump())
        except AttributeError:
            # 두 번째 방법: Pydantic v1 스타일
            try:
                return json.dumps(self.dict())
            except:
                # 세 번째 방법: 수동 변환
                def convert(obj):
                    if hasattr(obj, "__dict__"):
                        return {k: convert(v) for k, v in obj.__dict__.items() 
                                if not k.startswith('_')}
                    elif isinstance(obj, (list, tuple)):
                        return [convert(i) for i in obj]
                    elif isinstance(obj, dict):
                        return {k: convert(v) for k, v in obj.items()}
                    elif hasattr(obj, "__str__"):
                        return str(obj)
                    return obj
                
                return json.dumps(convert(self)) 