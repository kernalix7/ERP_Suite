from django.db.models.signals import post_save
from django.dispatch import receiver

from .models import WikiArticle


@receiver(post_save, sender=WikiArticle)
def notify_article_published(sender, instance, created, **kwargs):
    """WikiArticle이 PUBLISHED 상태로 저장되면 같은 공간의 구독자(staff)에게 알림."""
    if instance.status != WikiArticle.Status.PUBLISHED:
        return
    # created=True 이거나 갱신된 경우 모두 처리 (새 글 게시 및 초안→게시 전환)
    try:
        from django.contrib.auth import get_user_model
        from apps.core.notification import create_notification

        User = get_user_model()
        # 공간 소유자 + 전체 활성 staff에게 알림 (간단한 구독 구현)
        recipients = list(
            User.objects.filter(is_active=True, is_staff=True).exclude(pk=instance.author_id)
        )
        if instance.space.owner and instance.space.owner != instance.author:
            if instance.space.owner not in recipients:
                recipients.append(instance.space.owner)

        if recipients:
            create_notification(
                users=recipients,
                title=f'새 위키 문서: {instance.title}',
                message=f'[{instance.space.name}] {instance.author.get_full_name() or instance.author.username}님이 문서를 게시했습니다: {instance.title}',
                noti_type='SYSTEM',
                link=f'/wiki/article/{instance.slug}/',
            )
    except Exception:
        pass
