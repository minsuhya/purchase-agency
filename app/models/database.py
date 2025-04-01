from typing import Optional, List, Dict, Any
from datetime import datetime
from sqlmodel import SQLModel, Field, create_engine, Session, select
from pathlib import Path
import os
import logging

logger = logging.getLogger(__name__)

# 데이터베이스 파일 경로 설정
DB_PATH = Path("data/database.sqlite")
DB_PATH.parent.mkdir(parents=True, exist_ok=True)

# SQLite 데이터베이스 URL 설정
DATABASE_URL = f"sqlite:///{DB_PATH}"

# 엔진 설정
engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False},  # SQLite 전용 설정
    echo=False  # SQL 쿼리 로깅 비활성화
)

def init_db():
    """데이터베이스 초기화 및 테이블 생성"""
    try:
        logger.info("데이터베이스 초기화 시작...")
        SQLModel.metadata.create_all(engine)
        logger.info("데이터베이스 테이블 생성 완료")
    except Exception as e:
        logger.error(f"데이터베이스 초기화 중 오류 발생: {str(e)}")
        raise

# 데이터베이스 세션 의존성
def get_db():
    """데이터베이스 세션 생성"""
    with Session(engine) as session:
        yield session

# CRUD 작업을 위한 유틸리티 함수들
def create_product(db: Session, product_data: Dict[str, Any]) -> "Product":
    """상품 생성"""
    from app.models.product import Product
    product = Product(**product_data)
    db.add(product)
    db.commit()
    db.refresh(product)
    return product

def get_products(
    db: Session, 
    skip: int = 0, 
    limit: int = 100,
    search_term: Optional[str] = None
) -> list["Product"]:
    """상품 목록 조회"""
    from app.models.product import Product
    query = select(Product)
    
    if search_term:
        query = query.where(
            (Product.title_original.ilike(f"%{search_term}%")) |
            (Product.title_translated.ilike(f"%{search_term}%"))
        )
    
    return db.exec(query.offset(skip).limit(limit)).all()

def get_product(db: Session, product_id: int) -> Optional["Product"]:
    """상품 상세 조회"""
    from app.models.product import Product
    return db.get(Product, product_id)

def update_product(db: Session, product_id: int, product_data: Dict[str, Any]) -> Optional["Product"]:
    """상품 정보 업데이트"""
    from app.models.product import Product
    product = get_product(db, product_id)
    if not product:
        return None

    # 업데이트할 필드만 업데이트
    for key, value in product_data.items():
        if hasattr(product, key):
            setattr(product, key, value)
    
    product.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(product)
    return product

def delete_product(db: Session, product_id: int) -> bool:
    """상품 삭제"""
    from app.models.product import Product
    product = get_product(db, product_id)
    if not product:
        return False

    db.delete(product)
    db.commit()
    return True

def search_products(
    db: Session,
    search_term: str,
    skip: int = 0,
    limit: int = 100
) -> list["Product"]:
    """상품 검색"""
    from app.models.product import Product
    query = select(Product).where(
        (Product.title_original.ilike(f"%{search_term}%")) |
        (Product.title_translated.ilike(f"%{search_term}%")) |
        (Product.description_original.ilike(f"%{search_term}%")) |
        (Product.description_translated.ilike(f"%{search_term}%"))
    )
    return db.exec(query.offset(skip).limit(limit)).all() 