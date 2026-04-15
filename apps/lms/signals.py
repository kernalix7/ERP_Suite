from django.db.models.signals import post_save
from django.dispatch import receiver

from .models import CourseEnrollment, Certificate


@receiver(post_save, sender=CourseEnrollment)
def auto_issue_certificate(sender, instance, **kwargs):
    """수강 등록이 COMPLETED 상태가 되면 수료증 자동 발급 가능 여부 확인 후 생성."""
    if instance.status != CourseEnrollment.Status.COMPLETED:
        return
    # 이미 수료증이 있으면 스킵
    if hasattr(instance, 'certificate'):
        return
    # pass_score 이상 점수를 받은 경우에만 발급
    course = instance.course
    if instance.final_score >= course.pass_score:
        try:
            Certificate.objects.get_or_create(
                enrollment=instance,
                defaults={'created_by': instance.created_by},
            )
        except Exception:
            pass
