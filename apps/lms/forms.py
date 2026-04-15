from django import forms
from apps.core.forms import BaseForm
from .models import Course, CourseCategory, Lesson, CourseEnrollment, Quiz, QuizQuestion, QuizChoice


class CourseCategoryForm(BaseForm):
    class Meta:
        model = CourseCategory
        fields = ['name', 'code', 'parent', 'notes']


class CourseForm(BaseForm):
    class Meta:
        model = Course
        fields = [
            'title', 'category', 'instructor', 'description', 'level',
            'status', 'thumbnail', 'duration_hours', 'pass_score',
            'is_mandatory', 'target_departments', 'notes',
        ]


class LessonForm(BaseForm):
    class Meta:
        model = Lesson
        fields = [
            'course', 'title', 'order', 'content_type',
            'content_url', 'content_file', 'duration_minutes', 'is_preview', 'notes',
        ]


class CourseEnrollmentForm(BaseForm):
    class Meta:
        model = CourseEnrollment
        fields = ['course', 'learner', 'status', 'notes']


class QuizForm(BaseForm):
    class Meta:
        model = Quiz
        fields = ['course', 'lesson', 'title', 'time_limit_minutes', 'pass_score', 'notes']


class QuizQuestionForm(BaseForm):
    class Meta:
        model = QuizQuestion
        fields = ['quiz', 'question_text', 'question_type', 'order', 'score', 'explanation', 'notes']


class QuizChoiceForm(BaseForm):
    class Meta:
        model = QuizChoice
        fields = ['question', 'choice_text', 'is_correct', 'order']
