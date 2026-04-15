from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from simple_history.models import HistoricalRecords
from apps.core.models import BaseModel


class ProjectCategory(BaseModel):
    """프로젝트 분류"""
    name = models.CharField('분류명', max_length=100)
    code = models.CharField('코드', max_length=20, unique=True)
    history = HistoricalRecords()

    class Meta:
        verbose_name = '프로젝트분류'
        verbose_name_plural = '프로젝트분류'
        ordering = ['code']

    def __str__(self):
        return f'[{self.code}] {self.name}'


class Project(BaseModel):
    """프로젝트"""

    class Status(models.TextChoices):
        PLANNING = 'PLANNING', '기획'
        ACTIVE = 'ACTIVE', '진행중'
        ON_HOLD = 'ON_HOLD', '보류'
        COMPLETED = 'COMPLETED', '완료'
        CANCELLED = 'CANCELLED', '취소'

    class Priority(models.TextChoices):
        LOW = 'LOW', '낮음'
        MEDIUM = 'MEDIUM', '보통'
        HIGH = 'HIGH', '높음'
        CRITICAL = 'CRITICAL', '긴급'

    project_number = models.CharField('프로젝트번호', max_length=20, unique=True, blank=True)
    name = models.CharField('프로젝트명', max_length=200)
    category = models.ForeignKey(
        ProjectCategory, verbose_name='분류',
        null=True, blank=True, on_delete=models.SET_NULL,
        related_name='projects',
    )
    status = models.CharField('상태', max_length=20, choices=Status.choices, default=Status.PLANNING)
    priority = models.CharField('우선순위', max_length=20, choices=Priority.choices, default=Priority.MEDIUM)
    manager = models.ForeignKey(
        settings.AUTH_USER_MODEL, verbose_name='프로젝트 관리자',
        on_delete=models.PROTECT, related_name='managed_projects',
    )
    department = models.ForeignKey(
        'hr.Department', verbose_name='담당부서',
        null=True, blank=True, on_delete=models.SET_NULL,
        related_name='projects',
    )
    description = models.TextField('설명', blank=True)
    start_date = models.DateField('시작일', null=True, blank=True)
    due_date = models.DateField('목표완료일', null=True, blank=True)
    completed_date = models.DateField('실제완료일', null=True, blank=True)
    budget = models.DecimalField('예산', max_digits=15, decimal_places=0, default=0)
    progress_pct = models.PositiveIntegerField('진행률(%)', default=0)
    history = HistoricalRecords()

    class Meta:
        verbose_name = '프로젝트'
        verbose_name_plural = '프로젝트'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['manager', 'status'], name='idx_project_mgr_status'),
            models.Index(fields=['status', 'due_date'], name='idx_project_status_due'),
        ]

    def __str__(self):
        return f'[{self.project_number}] {self.name}'

    def save(self, *args, **kwargs):
        if not self.project_number:
            from apps.core.utils import generate_document_number
            self.project_number = generate_document_number(Project, 'project_number', 'PRJ')
        super().save(*args, **kwargs)


class ProjectMember(BaseModel):
    """프로젝트 멤버"""

    class Role(models.TextChoices):
        MANAGER = 'MANAGER', '관리자'
        LEAD = 'LEAD', '리드'
        DEVELOPER = 'DEVELOPER', '개발자'
        DESIGNER = 'DESIGNER', '디자이너'
        TESTER = 'TESTER', '테스터'
        STAKEHOLDER = 'STAKEHOLDER', '이해관계자'

    project = models.ForeignKey(
        Project, verbose_name='프로젝트',
        on_delete=models.PROTECT, related_name='members',
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, verbose_name='멤버',
        on_delete=models.PROTECT, related_name='project_memberships',
    )
    role = models.CharField('역할', max_length=20, choices=Role.choices, default=Role.DEVELOPER)
    joined_at = models.DateField('참여일', null=True, blank=True)
    history = HistoricalRecords()

    class Meta:
        verbose_name = '프로젝트멤버'
        verbose_name_plural = '프로젝트멤버'
        unique_together = ('project', 'user')

    def __str__(self):
        return f'{self.project.name} - {self.user.get_full_name() or self.user.username}'


class Milestone(BaseModel):
    """마일스톤"""

    class Status(models.TextChoices):
        PENDING = 'PENDING', '대기'
        IN_PROGRESS = 'IN_PROGRESS', '진행중'
        COMPLETED = 'COMPLETED', '완료'
        MISSED = 'MISSED', '지연'

    project = models.ForeignKey(
        Project, verbose_name='프로젝트',
        on_delete=models.PROTECT, related_name='milestones',
    )
    title = models.CharField('마일스톤명', max_length=200)
    description = models.TextField('설명', blank=True)
    due_date = models.DateField('목표일')
    completed_date = models.DateField('완료일', null=True, blank=True)
    status = models.CharField('상태', max_length=20, choices=Status.choices, default=Status.PENDING)
    history = HistoricalRecords()

    class Meta:
        verbose_name = '마일스톤'
        verbose_name_plural = '마일스톤'
        ordering = ['project', 'due_date']

    def __str__(self):
        return f'{self.project.name} - {self.title}'


class Task(BaseModel):
    """태스크 (작업 항목)"""

    class Status(models.TextChoices):
        TODO = 'TODO', '할일'
        IN_PROGRESS = 'IN_PROGRESS', '진행중'
        IN_REVIEW = 'IN_REVIEW', '검토중'
        DONE = 'DONE', '완료'
        CANCELLED = 'CANCELLED', '취소'

    class Priority(models.TextChoices):
        LOW = 'LOW', '낮음'
        MEDIUM = 'MEDIUM', '보통'
        HIGH = 'HIGH', '높음'
        CRITICAL = 'CRITICAL', '긴급'

    project = models.ForeignKey(
        Project, verbose_name='프로젝트',
        on_delete=models.PROTECT, related_name='tasks',
    )
    milestone = models.ForeignKey(
        Milestone, verbose_name='마일스톤',
        null=True, blank=True, on_delete=models.SET_NULL,
        related_name='tasks',
    )
    parent_task = models.ForeignKey(
        'self', verbose_name='상위태스크',
        null=True, blank=True, on_delete=models.SET_NULL,
        related_name='sub_tasks',
    )
    title = models.CharField('태스크명', max_length=300)
    description = models.TextField('설명', blank=True)
    status = models.CharField('상태', max_length=20, choices=Status.choices, default=Status.TODO)
    priority = models.CharField('우선순위', max_length=20, choices=Priority.choices, default=Priority.MEDIUM)
    assignee = models.ForeignKey(
        settings.AUTH_USER_MODEL, verbose_name='담당자',
        null=True, blank=True, on_delete=models.SET_NULL,
        related_name='assigned_tasks',
    )
    reporter = models.ForeignKey(
        settings.AUTH_USER_MODEL, verbose_name='보고자',
        null=True, blank=True, on_delete=models.SET_NULL,
        related_name='reported_tasks',
    )
    start_date = models.DateField('시작일', null=True, blank=True)
    due_date = models.DateField('마감일', null=True, blank=True)
    completed_date = models.DateField('완료일', null=True, blank=True)
    estimated_hours = models.DecimalField('예상시간(h)', max_digits=6, decimal_places=1, default=0)
    actual_hours = models.DecimalField('실제시간(h)', max_digits=6, decimal_places=1, default=0)
    history = HistoricalRecords()

    class Meta:
        verbose_name = '태스크'
        verbose_name_plural = '태스크'
        ordering = ['project', 'priority', 'due_date']
        indexes = [
            models.Index(fields=['project', 'status'], name='idx_task_project_status'),
            models.Index(fields=['assignee', 'due_date'], name='idx_task_assignee_due'),
        ]

    def __str__(self):
        return f'{self.project.name} - {self.title}'

    def clean(self):
        super().clean()
        if self.pk:
            old_status = (
                Task.objects.filter(pk=self.pk).values_list('status', flat=True).first()
            )
            if old_status and old_status != self.status:
                valid_transitions = {
                    Task.Status.TODO: [Task.Status.IN_PROGRESS, Task.Status.CANCELLED],
                    Task.Status.IN_PROGRESS: [Task.Status.IN_REVIEW, Task.Status.DONE, Task.Status.CANCELLED],
                    Task.Status.IN_REVIEW: [Task.Status.IN_PROGRESS, Task.Status.DONE, Task.Status.CANCELLED],
                    Task.Status.DONE: [],
                    Task.Status.CANCELLED: [],
                }
                if self.status not in valid_transitions.get(old_status, []):
                    raise ValidationError(
                        f'{self.get_status_display()} 상태에서 {Task.Status(self.status).label}(으)로 전이할 수 없습니다.'
                    )


class TaskComment(BaseModel):
    """태스크 댓글"""
    task = models.ForeignKey(
        Task, verbose_name='태스크',
        on_delete=models.PROTECT, related_name='comments',
    )
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL, verbose_name='작성자',
        on_delete=models.PROTECT, related_name='task_comments',
    )
    content = models.TextField('내용')
    history = HistoricalRecords()

    class Meta:
        verbose_name = '태스크댓글'
        verbose_name_plural = '태스크댓글'
        ordering = ['created_at']

    def __str__(self):
        return f'{self.task.title} - 댓글 by {self.author.username}'


class TaskAttachment(BaseModel):
    """태스크 첨부파일"""
    task = models.ForeignKey(
        Task, verbose_name='태스크',
        on_delete=models.PROTECT, related_name='attachments',
    )
    file = models.FileField('파일', upload_to='project/attachments/')
    file_name = models.CharField('파일명', max_length=300)
    uploader = models.ForeignKey(
        settings.AUTH_USER_MODEL, verbose_name='업로더',
        on_delete=models.SET_NULL, null=True,
        related_name='task_attachments',
    )
    history = HistoricalRecords()

    class Meta:
        verbose_name = '태스크첨부파일'
        verbose_name_plural = '태스크첨부파일'
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.task.title} - {self.file_name}'


class TimeLog(BaseModel):
    """작업 시간 기록"""
    task = models.ForeignKey(
        Task, verbose_name='태스크',
        on_delete=models.PROTECT, related_name='time_logs',
    )
    worker = models.ForeignKey(
        settings.AUTH_USER_MODEL, verbose_name='작업자',
        on_delete=models.PROTECT, related_name='time_logs',
    )
    work_date = models.DateField('작업일')
    hours = models.DecimalField('작업시간(h)', max_digits=5, decimal_places=1)
    description = models.TextField('작업내용', blank=True)
    history = HistoricalRecords()

    class Meta:
        verbose_name = '작업시간기록'
        verbose_name_plural = '작업시간기록'
        ordering = ['-work_date']

    def __str__(self):
        return f'{self.task.title} - {self.worker.username} {self.work_date} {self.hours}h'
