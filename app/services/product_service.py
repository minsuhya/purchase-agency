from typing import List, Optional, Dict, Any
from sqlmodel import Session, select
from app.models.product import Product, ProductCreate, ProductRead
from datetime import datetime
import json
import logging
from pathlib import Path
import hashlib

logger = logging.getLogger(__name__)

class ProductService:
    CACHE_DIR = Path("data/cache")
    CACHE_DIR.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def _get_cache_path(url: str) -> Path:
        """URL에 대한 캐시 파일 경로를 생성합니다."""
        url_hash = hashlib.md5(url.encode()).hexdigest()
        return ProductService.CACHE_DIR / f"{url_hash}.json"

    @staticmethod
    def _save_to_cache(url: str, data: Dict[str, Any]) -> None:
        """데이터를 캐시에 저장합니다."""
        cache_path = ProductService._get_cache_path(url)
        with open(cache_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    @staticmethod
    def _load_from_cache(url: str) -> Optional[Dict[str, Any]]:
        """캐시에서 데이터를 로드합니다."""
        cache_path = ProductService._get_cache_path(url)
        if cache_path.exists():
            with open(cache_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        return None

    @staticmethod
    def _get_dict_value(data: Dict[str, Any], key: str, default: Any = None) -> Any:
        """딕셔너리에서 안전하게 값을 가져옵니다."""
        if isinstance(data, dict):
            return data.get(key, default)
        return default

    @staticmethod
    def _safe_float(value: Any, default: float = 0.0) -> float:
        """값을 안전하게 float로 변환합니다."""
        if value is None:
            return default
        try:
            return float(value)
        except (ValueError, TypeError):
            return default

    @staticmethod
    def _safe_str(value: Any, default: str = "") -> str:
        """값을 안전하게 문자열로 변환합니다."""
        if value is None:
            return default
        try:
            return str(value)
        except (ValueError, TypeError):
            return default

    @staticmethod
    def _decode_json(data: Any) -> Any:
        """JSON 데이터를 디코딩합니다."""
        if isinstance(data, str):
            try:
                return json.loads(data)
            except json.JSONDecodeError:
                return data
        elif isinstance(data, dict):
            return {k: ProductService._decode_json(v) for k, v in data.items()}
        elif isinstance(data, list):
            return [ProductService._decode_json(item) for item in data]
        return data

    @staticmethod
    def create_product(db: Session, product_info: Dict[str, Any]) -> Product:
        """상품 정보를 데이터베이스에 저장합니다."""
        try:
            # 캐시에 저장
            ProductService._save_to_cache(product_info["url"], product_info)
            
            # Product 모델 생성
            product = Product(**product_info)
            
            # 데이터베이스에 저장
            db.add(product)
            db.commit()
            db.refresh(product)
            
            logger.info(f"상품 저장 완료: {product.id}")
            return product
            
        except Exception as e:
            db.rollback()
            logger.error(f"상품 저장 중 오류 발생: {str(e)}")
            raise

    @staticmethod
    def get_products(
        db: Session,
        skip: int = 0,
        limit: int = 100,
        search: Optional[str] = None
    ) -> List[Product]:
        """상품 목록을 조회합니다."""
        try:
            query = select(Product)
            
            if search:
                query = query.where(
                    (Product.title_original.ilike(f"%{search}%")) |
                    (Product.title_translated.ilike(f"%{search}%"))
                )
            
            query = query.offset(skip).limit(limit)
            return db.exec(query).all()
            
        except Exception as e:
            logger.error(f"상품 목록 조회 중 오류 발생: {str(e)}")
            raise

    @staticmethod
    def get_product(db: Session, product_id: int) -> Optional[Product]:
        """ID로 상품 정보를 조회합니다."""
        try:
            statement = select(Product).where(Product.id == product_id)
            return db.exec(statement).first()
        except Exception as e:
            logger.error(f"상품 조회 중 오류 발생: {str(e)}")
            raise

    @staticmethod
    def update_product(
        db: Session,
        product_id: int,
        product_update: ProductUpdate
    ) -> Optional[Product]:
        """상품 정보를 업데이트합니다."""
        try:
            product = ProductService.get_product(db, product_id)
            if not product:
                return None
                
            # 업데이트할 필드만 업데이트
            update_data = product_update.dict(exclude_unset=True)
            for key, value in update_data.items():
                setattr(product, key, value)
            
            # updated_at 자동 업데이트
            product.updated_at = datetime.utcnow()
            
            db.commit()
            db.refresh(product)
            
            logger.info(f"상품 업데이트 완료: {product_id}")
            return product
            
        except Exception as e:
            db.rollback()
            logger.error(f"상품 업데이트 중 오류 발생: {str(e)}")
            raise

    @staticmethod
    def delete_product(db: Session, product_id: int) -> bool:
        """상품을 삭제합니다."""
        try:
            product = ProductService.get_product(db, product_id)
            if not product:
                return False
                
            # 캐시 파일도 삭제
            cache_path = ProductService._get_cache_path(product.url)
            if cache_path.exists():
                cache_path.unlink()
            
            db.delete(product)
            db.commit()
            
            logger.info(f"상품 삭제 완료: {product_id}")
            return True
            
        except Exception as e:
            db.rollback()
            logger.error(f"상품 삭제 중 오류 발생: {str(e)}")
            raise 