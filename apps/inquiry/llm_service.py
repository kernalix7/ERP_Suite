import logging

from django.conf import settings

logger = logging.getLogger(__name__)


def generate_inquiry_reply(inquiry, templates=None):
    """
    Claude API를 사용하여 고객 문의에 대한 답변 초안을 생성합니다.

    Args:
        inquiry: Inquiry model instance
        templates: Optional list of ReplyTemplate instances for context

    Returns:
        str: Generated reply text, or None if generation fails
    """
    # SystemConfig 우선, 없으면 settings fallback
    try:
        from apps.core.system_config import SystemConfig
        api_key = SystemConfig.get_value('AI', 'anthropic_api_key')
    except Exception:
        api_key = ''
    if not api_key:
        api_key = getattr(settings, 'ANTHROPIC_API_KEY', '')
    if not api_key:
        logger.warning("Anthropic API 키가 설정되지 않았습니다. 시스템설정 > AI/자동화에서 설정하세요.")
        return None

    try:
        import anthropic
    except ImportError:
        logger.warning("anthropic 패키지가 설치되지 않았습니다. pip install anthropic>=0.40")
        return None

    system_prompt = (
        "당신은 한국 기업의 고객 응대 담당자입니다. "
        "고객의 문의에 대해 정중하고 전문적으로 답변해주세요. "
        "답변은 한국어로 작성하며, 존댓말을 사용합니다."
    )

    user_message = f"고객 문의에 대한 답변을 작성해주세요.\n\n## 고객 문의\n제목: {inquiry.subject}\n내용: {inquiry.content}"

    if templates:
        template_lines = "\n".join(
            f"- [{t.category}] {t.title}: {t.content}" for t in templates
        )
        user_message += f"\n\n## 참고 답변 템플릿\n{template_lines}"

    try:
        client = anthropic.Anthropic(api_key=api_key)
        response = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=1024,
            temperature=0.7,
            system=system_prompt,
            messages=[{"role": "user", "content": user_message}],
        )
        return response.content[0].text
    except (anthropic.APIError, anthropic.APIConnectionError, TimeoutError, ValueError) as e:
        logger.error("Claude API 호출 중 오류 발생: %s", e)
        return None
