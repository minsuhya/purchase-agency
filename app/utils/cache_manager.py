import os
import json
import hashlib
from pathlib import Path
from typing import Dict, Any, Optional, Union, List, Callable
from datetime import datetime, timedelta
import time

from loguru import logger


class CacheManager:
    """
    상품 데이터 캐싱 관리 유틸리티
    """
    def __init__(self, cache_dir: str = "app/data/cache", max_age_days: int = 7):
        """
        캐시 매니저 초기화
        
        Args:
            cache_dir (str): 캐시 저장 경로
            max_age_days (int): 캐시 기본 만료 기간(일)
        """
        self.cache_dir = Path(cache_dir)
        self.default_max_age_days = max_age_days
        
        # 캐시 디렉토리가 없으면 생성
        self._ensure_cache_dir()
    
    def _ensure_cache_dir(self) -> None:
        """캐시 디렉토리가 존재하는지 확인하고 없으면 생성합니다."""
        try:
            os.makedirs(self.cache_dir, exist_ok=True)
        except Exception as e:
            logger.error(f"캐시 디렉토리 생성 실패: {str(e)}")
            raise
    
    def get_cache_key(self, url: str) -> str:
        """
        URL에서 고유 캐시 키를 생성합니다.
        
        Args:
            url (str): 캐시 키를 생성할 URL
            
        Returns:
            str: MD5 해시로 생성된 캐시 키
        """
        # URL에서 캐시 키 생성 (MD5 해시 이용)
        return hashlib.md5(url.encode()).hexdigest()
    
    def get_cache_path(self, cache_key: str) -> Path:
        """
        캐시 키에 해당하는 파일 경로를 반환합니다.
        
        Args:
            cache_key (str): 캐시 키
            
        Returns:
            Path: 캐시 파일 경로
        """
        return self.cache_dir / f"{cache_key}.json"
    
    def has_cache(self, url: str, max_age_days: Optional[int] = None) -> bool:
        """
        지정된 URL의 캐시가 존재하고 유효한지 확인합니다.
        
        Args:
            url (str): 확인할 URL
            max_age_days (int, optional): 캐시 최대 보관 기간(일). None이면 기본값 사용
            
        Returns:
            bool: 유효한 캐시가 존재하면 True, 그렇지 않으면 False
        """
        if max_age_days is None:
            max_age_days = self.default_max_age_days
            
        try:
            cache_key = self.get_cache_key(url)
            cache_path = self.get_cache_path(cache_key)
            
            if not cache_path.exists():
                return False
            
            # 캐시가 특정 기간보다 오래되었는지 확인
            if max_age_days > 0:
                file_time = datetime.fromtimestamp(cache_path.stat().st_mtime)
                max_age = timedelta(days=max_age_days)
                if datetime.now() - file_time > max_age:
                    logger.info(f"캐시가 만료되었습니다: {url}")
                    return False
            
            return True
        except Exception as e:
            logger.error(f"캐시 확인 중 오류 발생: {str(e)}")
            return False
    
    def get_cache(self, url: str) -> Optional[Dict[str, Any]]:
        """
        URL에 해당하는 캐시된 데이터를 가져옵니다.
        
        Args:
            url (str): 캐시를 조회할 URL
            
        Returns:
            Optional[Dict[str, Any]]: 캐시된 데이터, 없거나 오류 시 None
        """
        try:
            if not self.has_cache(url):
                return None
            
            cache_key = self.get_cache_key(url)
            cache_path = self.get_cache_path(cache_key)
            
            with open(cache_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                logger.info(f"캐시에서 데이터를 로드했습니다: {url}")
                return data
        except Exception as e:
            logger.error(f"캐시 데이터 로드 오류: {str(e)}")
            return None
    
    def save_cache(self, url: str, data: Any) -> bool:
        """URL에 대한 데이터를 캐시로 저장합니다.
        
        Args:
            url (str): 캐시할 데이터의 URL
            data (Any): 저장할 데이터 (JSON으로 직렬화 가능해야 함)
            
        Returns:
            bool: 저장 성공 여부
        """
        try:
            # 캐시 디렉토리 확인 및 생성
            self._ensure_cache_dir()
            
            # URL 기반으로 캐시 키와 파일 경로 생성
            cache_key = self.get_cache_key(url)
            cache_path = self.get_cache_path(cache_key)
            
            # 데이터 준비
            cache_data = {
                "url": str(url),
                "created_at": int(time.time()),
                "data": self.convert_dict(data)  # convert_dict 사용
            }
            
            # JSON으로 저장
            with open(cache_path, 'w', encoding='utf-8') as f:
                json.dump(cache_data, f, ensure_ascii=False, indent=2)
            
            logger.info(f"캐시 저장 완료: {url}")
            return True
            
        except Exception as e:
            logger.error(f"캐시 저장 실패: {str(e)}", exc_info=True)
            return False
    
    def clear_cache(self, url: Optional[str] = None) -> bool:
        """
        캐시를 삭제합니다.
        
        Args:
            url (Optional[str]): 삭제할 URL. None이면 모든 캐시 삭제
            
        Returns:
            bool: 삭제 성공 시 True, 실패 시 False
        """
        try:
            if url:
                cache_key = self.get_cache_key(url)
                cache_path = self.get_cache_path(cache_key)
                if cache_path.exists():
                    os.remove(cache_path)
                    logger.info(f"캐시를 삭제했습니다: {url}")
            else:
                # 모든 캐시 파일 삭제
                deleted_count = 0
                for cache_file in self.cache_dir.glob("*.json"):
                    os.remove(cache_file)
                    deleted_count += 1
                logger.info(f"모든 캐시를 삭제했습니다. (총 {deleted_count}개 파일)")
            return True
        except Exception as e:
            logger.error(f"캐시 삭제 오류: {str(e)}")
            return False
    
    def get_all_cache_entries(self) -> List[Dict[str, Any]]:
        """
        모든 캐시 항목의 기본 정보를 반환합니다.
        
        Returns:
            List[Dict[str, Any]]: 캐시 항목 목록 (파일명, URL, 생성일 등)
        """
        try:
            entries = []
            for cache_file in self.cache_dir.glob("*.json"):
                try:
                    with open(cache_file, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                        created_time = datetime.fromtimestamp(cache_file.stat().st_mtime)
                        
                        entry = {
                            "filename": cache_file.name,
                            "url": data.get("url", "Unknown URL"),
                            "created_at": created_time.isoformat(),
                            "size_kb": round(cache_file.stat().st_size / 1024, 2)
                        }
                        entries.append(entry)
                except Exception as e:
                    logger.error(f"캐시 파일 {cache_file.name} 읽기 오류: {str(e)}")
            
            # 생성일 기준 내림차순 정렬
            entries.sort(key=lambda x: x["created_at"], reverse=True)
            return entries
        except Exception as e:
            logger.error(f"캐시 항목 조회 중 오류 발생: {str(e)}")
            return []

    def convert_dict(self, obj):
        """객체를 딕셔너리로 변환합니다.
        
        obj의 타입에 따라 딕셔너리로 변환하는 방법이 다릅니다.
        - Pydantic 모델: dict() 메서드 사용
        - 기본 타입: 그대로 반환
        - 딕셔너리: 각 값을 재귀적으로 변환
        - 리스트/세트: 각 항목을 재귀적으로 변환
        - HttpUrl: 문자열로 변환
        - 그 외 객체: __dict__ 속성 사용
        """
        if obj is None:
            return None
        
        # 기본 타입은 그대로 반환
        if isinstance(obj, (int, float, bool, str)):
            return obj
        
        # URL 처리
        if hasattr(obj, "__str__") and isinstance(obj.__str__, Callable) and "url" in str(type(obj)).lower():
            return str(obj)
        
        # Pydantic 모델 처리
        if hasattr(obj, "model_dump"):  # Pydantic v2
            try:
                return obj.model_dump()
            except Exception as e:
                logger.debug(f"model_dump 실패: {e}")
        
        if hasattr(obj, "dict") and isinstance(obj.dict, Callable):  # Pydantic v1
            try:
                return obj.dict()
            except Exception as e:
                logger.debug(f"dict() 메서드 실패: {e}")
        
        # 딕셔너리 처리
        if isinstance(obj, dict):
            return {k: self.convert_dict(v) for k, v in obj.items()}
        
        # 리스트 처리
        if isinstance(obj, list):
            return [self.convert_dict(v) for v in obj]
        
        # 세트/튜플 처리
        if isinstance(obj, (set, tuple)):
            return [self.convert_dict(v) for v in obj]
        
        # 특별 처리: 'values' 속성이 callable인 경우 'option_values'를 확인
        result = {}
        if hasattr(obj, "__dict__"):
            for key, value in obj.__dict__.items():
                # values가 callable인 경우 option_values로 대체
                if key == "values" and callable(value):
                    if hasattr(obj, "option_values"):
                        result[key] = self.convert_dict(obj.option_values)
                else:
                    result[key] = self.convert_dict(value)
            return result
        
        # 그 외의 경우, 문자열로 변환
        return str(obj) 