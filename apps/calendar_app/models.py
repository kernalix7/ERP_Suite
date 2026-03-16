from django.conf import settings
from django.db import models
from simple_history.models import HistoricalRecords

from apps.core.models import BaseModel


class Event(BaseModel):
    """일정"""

    class EventType(models.TextChoices):
        PERSONAL = 'personal', '개인'
        TEAM = 'team', '팀'
        COMPANY = 'company', '회사'
        MEETING = 'meeting', '회의'

    title = models.CharField('제목', max_length=200)
    description = models.TextField('설명', blank=True)
    start_datetime = models.DateTimeField('시작일시')
    end_datetime = models.DateTimeField('종료일시')
    all_day = models.BooleanField('종일', default=False)
    event_type = models.CharField(
        '일정 유형',
        max_length=20,
        choices=EventType.choices,
        default=EventType.PERSONAL,
    )
    color = models.CharField('색상', max_length=7, default='#3B82F6')
    location = models.CharField('장소', max_length=200, blank=True)
    creator = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name='생성자',
        on_delete=models.PROTECT,
        related_name='created_events',
    )
    attendees = models.ManyToManyField(
        settings.AUTH_USER_MODEL,
        verbose_name='참석자',
        blank=True,
        related_name='attending_events',
    )
    is_recurring = models.BooleanField('반복 일정', default=False)
    history = HistoricalRecords()

    class Meta:
        verbose_name = '일정'
        verbose_name_plural = '일정'
        ordering = ['start_datetime']

    def __str__(self):
        return self.title
