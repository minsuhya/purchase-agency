import base64
import io
import os
from typing import Dict, List
from PIL import Image, ImageDraw, ImageFont
from google.cloud import vision, translate_v2
from google.oauth2 import service_account
from pathlib import Path

# 프로젝트 루트 디렉토리 경로
BASE_DIR = Path(__file__).resolve().parent.parent.parent

# Google Cloud 인증 파일 경로
CREDENTIALS_PATH = BASE_DIR / "app" / "config" / "ezyops-vision-370bc6081f03.json"

# 한글 폰트 파일 경로
FONT_PATH = BASE_DIR / "app" / "static" / "fonts" / "NotoSansKR-Regular.ttf"

# Google Cloud 인증 설정
credentials = service_account.Credentials.from_service_account_file(
    str(CREDENTIALS_PATH),
    scopes=["https://www.googleapis.com/auth/cloud-platform"],
)

# Vision API 클라이언트 초기화
vision_client = vision.ImageAnnotatorClient(credentials=credentials)

# Translation API 클라이언트 초기화
translate_client = translate_v2.Client(credentials=credentials)

async def process_image(image_content: bytes) -> Dict:
    """
    이미지에서 중국어 텍스트를 감지하고 한국어로 번역하여 새로운 이미지를 생성합니다.
    
    Args:
        image_content (bytes): 이미지 바이트 데이터
        
    Returns:
        Dict: {
            "textBlocks": List[Dict],  # 감지된 텍스트 블록 정보
            "image": str  # base64로 인코딩된 번역된 이미지
        }
    """
    # 이미지 객체 생성
    image = vision.Image(content=image_content)
    
    # Vision API로 텍스트 감지
    response = vision_client.text_detection(image=image)
    texts = response.text_annotations
    
    if not texts:
        return {"textBlocks": [], "image": ""}
    
    # 텍스트 블록 처리
    text_blocks = []
    for text in texts[1:]:
        description = text.description
        # 중국어 문자가 포함된 텍스트 블록만 처리
        if any("\u4e00" <= char <= "\u9fff" for char in description):
            vertices = [(vertex.x, vertex.y) for vertex in text.bounding_poly.vertices]
            
            # 한국어로 번역
            translation = translate_client.translate(
                description, target_language="ko", source_language="zh-CN"
            )
            
            text_blocks.append({
                "original": description,
                "translated": translation["translatedText"],
                "position": vertices
            })
    
    # 원본 이미지 생성
    image = Image.open(io.BytesIO(image_content))
    draw = ImageDraw.Draw(image)
    
    # 각 텍스트 블록 처리
    for block in text_blocks:
        vertices = block["position"]
        x = min(v[0] for v in vertices)
        y = min(v[1] for v in vertices)
        width = max(v[0] for v in vertices) - x
        height = max(v[1] for v in vertices) - y
        
        # 원본 텍스트 영역을 지우기
        draw.rectangle([x, y, x + width, y + height], fill="white")
        
        # 새 텍스트 그리기
        try:
            font = ImageFont.truetype(str(FONT_PATH), 20)
            draw.text((x, y), block["translated"], fill="black", font=font)
        except IOError:
            draw.text((x, y), block["translated"], fill="black")
    
    # 처리된 이미지를 base64로 인코딩
    output = io.BytesIO()
    image.save(output, format="PNG")
    output.seek(0)
    result_data = base64.b64encode(output.getvalue()).decode("utf-8")
    
    return {
        "textBlocks": text_blocks,
        "image": f"data:image/png;base64,{result_data}"
    }

async def save_translated_image(image_data: bytes, product_id: int, image_index: int) -> str:
    """
    번역된 이미지를 저장하고 URL을 반환합니다.
    
    Args:
        image_data (bytes): 번역된 이미지 데이터
        product_id (int): 상품 ID
        image_index (int): 이미지 인덱스
        
    Returns:
        str: 저장된 이미지의 URL
    """
    # 이미지 저장 디렉토리 생성
    save_dir = BASE_DIR / "app" / "static" / "uploads" / "translated" / str(product_id)
    save_dir.mkdir(parents=True, exist_ok=True)
    
    # 이미지 파일명 생성
    filename = f"translated_{image_index}.png"
    filepath = save_dir / filename
    
    # 이미지 저장
    with open(filepath, "wb") as f:
        f.write(image_data)
    
    # URL 생성 (실제 운영 환경에서는 CDN이나 스토리지 서비스 URL로 대체)
    return f"/static/uploads/translated/{product_id}/{filename}" 