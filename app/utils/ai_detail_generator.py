import os
from openai import OpenAI
from loguru import logger

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

def generate_product_detail(product):
    """상품 정보를 기반으로 AI 상품 상세 페이지를 생성합니다."""
    try:
        # 상품 정보 구성
        product_info = {
            "title": product.title_translated,
            "description": product.description_translated,
            "specifications": product.specifications_translated,
        }

        # 이미지 URL 목록 생성
        image_urls = "\n".join([f"이미지 {i+1}: {img['url']}" for i, img in enumerate(product.images)])

        # 프롬프트 구성
        prompt = f"""패션 상품 상세 페이지를 위한 세련되고 고급스러운 HTML을 생성해주세요.

상품 정보:
- 상품명: {product_info['title']}
- 상품 설명: {product_info['description']} 
- 상품 사양: {product_info['specifications']}

상품 이미지 정보: 
{image_urls}

디자인 요구사항:
1. 럭셔리/하이엔드 패션 브랜드 감성의 미니멀하고 세련된 디자인
2. 상품 이미지를 돋보이게 하는 여백과 레이아웃
3. 타이포그래피는 고급스러운 serif체와 modern한 sans-serif체 조합 
4. 상품 주요 이미지는 풀스크린 히어로 섹션으로 구성
5. 스크롤시 자연스러운 이미지 전환 효과 적용
6. 상품 설명은 읽기 편한 단락과 여백으로 구성
7. 상품 사양은 심플하고 세련된 테이블로 표현
8. 모바일 환경 최적화를 위한 반응형 디자인
9. 독립적인 CSS로 구성하여 다양한 환경 지원
10. 브랜드 아이덴티티를 살리는 컬러와 디자인 요소 활용
11. 상품 이미지 정보의 이미지들은 모두 화면에 표시해주세요.

추가 고려사항:
- 상품의 가치와 품격이 느껴지는 고급스러운 분위기 연출
- 사용자 경험을 고려한 직관적인 정보 구조화
- 세련된 hover/transition 효과로 인터랙션 강화
- 이미지 로딩 최적화를 위한 lazy loading 적용
- 크로스 브라우징 호환성 확보

HTML 코드만 깔끔하게 반환해주세요."""

        # OpenAI API 호출 (동기 방식)
        response = client.chat.completions.create(
            model="gpt-4-turbo-preview",
            messages=[
                {"role": "system", "content": "당신은 전문적인 상품 상세 페이지 디자이너입니다."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.7,
            max_tokens=2000
        )

        # 생성된 HTML 반환
        return response.choices[0].message.content

    except Exception as e:
        logger.error(f"AI 상품 상세 생성 중 오류 발생: {str(e)}")
        raise 