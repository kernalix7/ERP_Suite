from django.db import models, transaction
from django.db.models.signals import post_save
from django.dispatch import receiver

from .models import Task, Project


@receiver(post_save, sender=Task)
def update_project_progress(sender, instance, **kwargs):
    """Task 상태 변경 시 Project 진행률 자동 업데이트. 완료 시 manager에게 알림."""
    project = instance.project
    with transaction.atomic():
        total = Task.objects.filter(project=project, is_active=True).count()
        if total == 0:
            return
        done = Task.objects.filter(
            project=project, is_active=True, status=Task.Status.DONE,
        ).count()
        new_pct = int(done / total * 100)
        Project.objects.filter(pk=project.pk).update(progress_pct=new_pct)

        # 모든 태스크가 완료되면 프로젝트 manager에게 알림
        if new_pct >= 100 and project.manager_id:
            try:
                from apps.core.notification import create_notification
                create_notification(
                    users=[project.manager],
                    title=f'프로젝트 완료: {project.name}',
                    message=f'프로젝트 [{project.project_number}] {project.name}의 모든 태스크가 완료되었습니다.',
                    noti_type='SYSTEM',
                    link=f'/project/{project.pk}/',
                )
            except Exception:
                pass
