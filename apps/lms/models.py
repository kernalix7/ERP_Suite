from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from simple_history.models import HistoricalRecords
from apps.core.models import BaseModel


class CourseCategory(BaseModel):
    """강좌 분류"""
    name = models.CharField('분류명', max_length=100)
    code = models.CharField('분류코드', max_length=20, unique=True)
    parent = models.ForeignKey(
        'self', verbose_name='상위분류',
        null=True, blank=True, on_delete=models.SET_NULL,
        related_name='children',
    )
    history = HistoricalRecords()

    class Meta:
        verbose_name = '강좌분류'
        verbose_name_plural = '강좌분류'
        ordering = ['code']

    def __str__(self):
        return f'[{self.code}] {self.name}'


class Course(BaseModel):
    """강좌"""

    class Status(models.TextChoices):
        DRAFT = 'DRAFT', '초안'
        PUBLISHED = 'PUBLISHED', '공개'
        CLOSED = 'CLOSED', '종료'

    class Level(models.TextChoices):
        BEGINNER = 'BEGINNER', '초급'
        INTERMEDIATE = 'INTERMEDIATE', '중급'
        ADVANCED = 'ADVANCED', '고급'

    course_number = models.CharField('강좌번호', max_length=20, unique=True, blank=True)
    title = models.CharField('강좌명', max_length=200)
    category = models.ForeignKey(
        CourseCategory, verbose_name='분류',
        on_delete=models.PROTECT, related_name='courses',
    )
    instructor = models.ForeignKey(
        settings.AUTH_USER_MODEL, verbose_name='강사',
        null=True, blank=True, on_delete=models.SET_NULL,
        related_name='instructed_courses',
    )
    description = models.TextField('설명', blank=True)
    level = models.CharField('난이도', max_length=20, choices=Level.choices, default=Level.BEGINNER)
    status = models.CharField('상태', max_length=20, choices=Status.choices, default=Status.DRAFT)
    thumbnail = models.ImageField('썸네일', upload_to='lms/thumbnails/', blank=True)
    duration_hours = models.DecimalField('총 학습시간(h)', max_digits=6, decimal_places=1, default=0)
    pass_score = models.PositiveIntegerField('수료 최저점수', default=70)
    is_mandatory = models.BooleanField('필수교육 여부', default=False)
    target_departments = models.ManyToManyField(
        'hr.Department', verbose_name='대상부서', blank=True,
    )
    history = HistoricalRecords()

    class Meta:
        verbose_name = '강좌'
        verbose_name_plural = '강좌'
        ordering = ['-created_at']

    def __str__(self):
        return f'[{self.course_number}] {self.title}'

    def clean(self):
        super().clean()
        if self.pk:
            old_status = (
                Course.objects.filter(pk=self.pk).values_list('status', flat=True).first()
            )
            if old_status and old_status != self.status:
                valid_transitions = {
                    Course.Status.DRAFT: [Course.Status.PUBLISHED],
                    Course.Status.PUBLISHED: [Course.Status.CLOSED],
                    Course.Status.CLOSED: [],
                }
                if self.status not in valid_transitions.get(old_status, []):
                    raise ValidationError(
                        f'{self.get_status_display()} 상태에서 {Course.Status(self.status).label}(으)로 전이할 수 없습니다.'
                    )

    def save(self, *args, **kwargs):
        if not self.course_number:
            from apps.core.utils import generate_document_number
            self.course_number = generate_document_number(Course, 'course_number', 'CRS')
        super().save(*args, **kwargs)


class Lesson(BaseModel):
    """강의 (강좌 구성 단위)"""

    class ContentType(models.TextChoices):
        VIDEO = 'VIDEO', '동영상'
        DOCUMENT = 'DOCUMENT', '문서'
        QUIZ = 'QUIZ', '퀴즈'
        EXTERNAL = 'EXTERNAL', '외부링크'

    course = models.ForeignKey(
        Course, verbose_name='강좌',
        on_delete=models.PROTECT, related_name='lessons',
    )
    title = models.CharField('강의명', max_length=200)
    order = models.PositiveIntegerField('순서', default=1)
    content_type = models.CharField('콘텐츠유형', max_length=20, choices=ContentType.choices, default=ContentType.VIDEO)
    content_url = models.URLField('콘텐츠URL', blank=True)
    content_file = models.FileField('첨부파일', upload_to='lms/lessons/', blank=True)
    duration_minutes = models.PositiveIntegerField('소요시간(분)', default=0)
    is_preview = models.BooleanField('미리보기 허용', default=False)
    history = HistoricalRecords()

    class Meta:
        verbose_name = '강의'
        verbose_name_plural = '강의'
        ordering = ['course', 'order']

    def __str__(self):
        return f'{self.course.title} - {self.order}. {self.title}'


class CourseEnrollment(BaseModel):
    """수강 등록"""

    class Status(models.TextChoices):
        ENROLLED = 'ENROLLED', '수강중'
        COMPLETED = 'COMPLETED', '수료'
        DROPPED = 'DROPPED', '중도포기'

    course = models.ForeignKey(
        Course, verbose_name='강좌',
        on_delete=models.PROTECT, related_name='enrollments',
    )
    learner = models.ForeignKey(
        settings.AUTH_USER_MODEL, verbose_name='수강자',
        on_delete=models.PROTECT, related_name='course_enrollments',
    )
    status = models.CharField('상태', max_length=20, choices=Status.choices, default=Status.ENROLLED)
    enrolled_at = models.DateTimeField('등록일시', auto_now_add=True)
    completed_at = models.DateTimeField('수료일시', null=True, blank=True)
    progress_pct = models.PositiveIntegerField('진도율(%)', default=0)
    final_score = models.DecimalField('최종점수', max_digits=5, decimal_places=1, default=0)
    history = HistoricalRecords()

    class Meta:
        verbose_name = '수강등록'
        verbose_name_plural = '수강등록'
        unique_together = ('course', 'learner')
        ordering = ['-enrolled_at']

    def __str__(self):
        return f'{self.learner.get_full_name() or self.learner.username} - {self.course.title}'


class LessonProgress(BaseModel):
    """강의 진행 이력"""
    enrollment = models.ForeignKey(
        CourseEnrollment, verbose_name='수강등록',
        on_delete=models.PROTECT, related_name='lesson_progresses',
    )
    lesson = models.ForeignKey(
        Lesson, verbose_name='강의',
        on_delete=models.PROTECT, related_name='progresses',
    )
    is_completed = models.BooleanField('완료여부', default=False)
    completed_at = models.DateTimeField('완료일시', null=True, blank=True)
    watch_seconds = models.PositiveIntegerField('시청시간(초)', default=0)
    history = HistoricalRecords()

    class Meta:
        verbose_name = '강의진행'
        verbose_name_plural = '강의진행'
        unique_together = ('enrollment', 'lesson')

    def __str__(self):
        return f'{self.enrollment} - {self.lesson.title}'


class Quiz(BaseModel):
    """퀴즈"""
    course = models.ForeignKey(
        Course, verbose_name='강좌',
        on_delete=models.PROTECT, related_name='quizzes',
    )
    lesson = models.ForeignKey(
        Lesson, verbose_name='연결강의',
        null=True, blank=True, on_delete=models.SET_NULL,
        related_name='quizzes',
    )
    title = models.CharField('퀴즈명', max_length=200)
    time_limit_minutes = models.PositiveIntegerField('제한시간(분)', default=30)
    pass_score = models.PositiveIntegerField('합격점수', default=70)
    history = HistoricalRecords()

    class Meta:
        verbose_name = '퀴즈'
        verbose_name_plural = '퀴즈'
        ordering = ['course', 'title']

    def __str__(self):
        return f'{self.course.title} - {self.title}'


class QuizQuestion(BaseModel):
    """퀴즈 문제"""

    class QuestionType(models.TextChoices):
        SINGLE = 'SINGLE', '단일선택'
        MULTIPLE = 'MULTIPLE', '복수선택'
        SHORT = 'SHORT', '단답형'

    quiz = models.ForeignKey(
        Quiz, verbose_name='퀴즈',
        on_delete=models.PROTECT, related_name='questions',
    )
    question_text = models.TextField('문제')
    question_type = models.CharField('문제유형', max_length=20, choices=QuestionType.choices, default=QuestionType.SINGLE)
    order = models.PositiveIntegerField('순서', default=1)
    score = models.PositiveIntegerField('배점', default=10)
    explanation = models.TextField('해설', blank=True)
    history = HistoricalRecords()

    class Meta:
        verbose_name = '퀴즈문제'
        verbose_name_plural = '퀴즈문제'
        ordering = ['quiz', 'order']

    def __str__(self):
        return f'{self.quiz.title} - Q{self.order}'


class QuizChoice(BaseModel):
    """퀴즈 선택지"""
    question = models.ForeignKey(
        QuizQuestion, verbose_name='문제',
        on_delete=models.PROTECT, related_name='choices',
    )
    choice_text = models.CharField('선택지', max_length=500)
    is_correct = models.BooleanField('정답여부', default=False)
    order = models.PositiveIntegerField('순서', default=1)
    history = HistoricalRecords()

    class Meta:
        verbose_name = '선택지'
        verbose_name_plural = '선택지'
        ordering = ['question', 'order']

    def __str__(self):
        return f'{self.question} - {self.choice_text[:30]}'


class QuizAttempt(BaseModel):
    """퀴즈 응시 기록"""
    enrollment = models.ForeignKey(
        CourseEnrollment, verbose_name='수강등록',
        on_delete=models.PROTECT, related_name='quiz_attempts',
    )
    quiz = models.ForeignKey(
        Quiz, verbose_name='퀴즈',
        on_delete=models.PROTECT, related_name='attempts',
    )
    score = models.DecimalField('점수', max_digits=5, decimal_places=1, default=0)
    is_passed = models.BooleanField('합격여부', default=False)
    started_at = models.DateTimeField('시작일시', auto_now_add=True)
    submitted_at = models.DateTimeField('제출일시', null=True, blank=True)
    history = HistoricalRecords()

    class Meta:
        verbose_name = '퀴즈응시'
        verbose_name_plural = '퀴즈응시'
        ordering = ['-started_at']

    def __str__(self):
        return f'{self.enrollment} - {self.quiz.title} ({self.score}점)'


class Certificate(BaseModel):
    """수료증"""
    enrollment = models.OneToOneField(
        CourseEnrollment, verbose_name='수강등록',
        on_delete=models.PROTECT, related_name='certificate',
    )
    certificate_number = models.CharField('수료증번호', max_length=30, unique=True, blank=True)
    issued_at = models.DateTimeField('발급일시', auto_now_add=True)
    history = HistoricalRecords()

    class Meta:
        verbose_name = '수료증'
        verbose_name_plural = '수료증'
        ordering = ['-issued_at']

    def __str__(self):
        return f'{self.certificate_number} - {self.enrollment}'

    def save(self, *args, **kwargs):
        if not self.certificate_number:
            from apps.core.utils import generate_document_number
            self.certificate_number = generate_document_number(Certificate, 'certificate_number', 'CERT')
        super().save(*args, **kwargs)
