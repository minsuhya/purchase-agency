import json
import hashlib
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, Any, Optional
from loguru import logger

class CacheManager:
    """캐시 관리 클래스"""
    
    def __init__(self, cache_dir: str = "data/cache", max_age_days: int = 7):
        """
        캐시 매니저 초기화
        
        Args:
            cache_dir (str): 캐시 디렉토리 경로
            max_age_days (int): 캐시 최대 보관 기간(일)
        """
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.max_age_days = max_age_days
        
    def _get_cache_key(self, url: str) -> str:
        """URL을 캐시 키로 변환합니다."""
        return hashlib.md5(url.encode()).hexdigest()
    
    def _get_cache_path(self, url: str) -> Path:
        """캐시 파일 경로를 반환합니다."""
        cache_key = self._get_cache_key(url)
        return self.cache_dir / f"{cache_key}.json"
    
    def _is_cache_valid(self, cache_path: Path) -> bool:
        """캐시가 유효한지 확인합니다."""
        if not cache_path.exists():
            return False
            
        # 파일 수정 시간 확인
        mtime = datetime.fromtimestamp(cache_path.stat().st_mtime)
        age = datetime.now() - mtime
        
        return age < timedelta(days=self.max_age_days)
    
    def get(self, url: str) -> Optional[Dict[str, Any]]:
        """캐시된 데이터를 가져옵니다."""
        try:
            cache_path = self._get_cache_path(url)
            
            if not self._is_cache_valid(cache_path):
                logger.debug(f"캐시 만료 또는 없음: {url}")
                return None
                
            with open(cache_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                logger.debug(f"캐시에서 데이터 로드: {url}")
                return data
                
        except Exception as e:
            logger.error(f"캐시 로드 중 오류 발생: {str(e)}")
            return None
    
    def set(self, url: str, data: Dict[str, Any]) -> bool:
        """데이터를 캐시에 저장합니다."""
        try:
            cache_path = self._get_cache_path(url)
            
            with open(cache_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
                logger.debug(f"데이터를 캐시에 저장: {url}")
                return True
                
        except Exception as e:
            logger.error(f"캐시 저장 중 오류 발생: {str(e)}")
            return False
    
    def delete(self, url: str) -> bool:
        """캐시를 삭제합니다."""
        try:
            cache_path = self._get_cache_path(url)
            
            if cache_path.exists():
                cache_path.unlink()
                logger.debug(f"캐시 삭제: {url}")
                return True
                
            return False
            
        except Exception as e:
            logger.error(f"캐시 삭제 중 오류 발생: {str(e)}")
            return False
    
    def clear(self) -> bool:
        """모든 캐시를 삭제합니다."""
        try:
            for cache_file in self.cache_dir.glob("*.json"):
                cache_file.unlink()
            logger.debug("모든 캐시 삭제")
            return True
            
        except Exception as e:
            logger.error(f"캐시 전체 삭제 중 오류 발생: {str(e)}")
            return False 