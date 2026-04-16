from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db import transaction
from django.db.models import Q, Count
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse_lazy
from django.utils import timezone
from django.views.generic import ListView, CreateView, UpdateView, DetailView, TemplateView

from apps.core.mixins import ManagerRequiredMixin
from apps.module_manager.decorators import ModuleRequiredMixin
from .models import (
    Course, CourseCategory, CourseEnrollment, Lesson, LessonProgress,
    Quiz, QuizAttempt, Certificate,
)
from .forms import (
    CourseForm, CourseCategoryForm, LessonForm, CourseEnrollmentForm,
    QuizForm, QuizQuestionForm,
)


class CourseListView(ModuleRequiredMixin, ListView):
    required_module = 'lms'
    model = Course
    template_name = 'lms/course_list.html'
    context_object_name = 'courses'
    paginate_by = 20

    def get_queryset(self):
        qs = Course.objects.filter(is_active=True).select_related('category', 'instructor')
        q = self.request.GET.get('q')
        if q:
            qs = qs.filter(Q(title__icontains=q) | Q(description__icontains=q))
        status = self.request.GET.get('status')
        if status:
            qs = qs.filter(status=status)
        level = self.request.GET.get('level')
        if level:
            qs = qs.filter(level=level)
        return qs


class CourseDetailView(ModuleRequiredMixin, DetailView):
    required_module = 'lms'
    model = Course
    template_name = 'lms/course_detail.html'
    context_object_name = 'course'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['lessons'] = self.object.lessons.filter(is_active=True).order_by('order')
        enrollment = CourseEnrollment.objects.filter(
            course=self.object, learner=self.request.user, is_active=True,
        ).first()
        ctx['enrollment'] = enrollment
        return ctx


class CourseCreateView(ModuleRequiredMixin, ManagerRequiredMixin, CreateView):
    required_module = 'lms'
    model = Course
    form_class = CourseForm
    template_name = 'lms/course_form.html'
    success_url = reverse_lazy('lms:course_list')

    def form_valid(self, form):
        form.instance.created_by = self.request.user
        messages.success(self.request, '강좌가 등록되었습니다.')
        return super().form_valid(form)


class CourseUpdateView(ModuleRequiredMixin, ManagerRequiredMixin, UpdateView):
    required_module = 'lms'
    model = Course
    form_class = CourseForm
    template_name = 'lms/course_form.html'

    def get_success_url(self):
        return reverse_lazy('lms:course_detail', kwargs={'pk': self.object.pk})

    def form_valid(self, form):
        messages.success(self.request, '강좌가 수정되었습니다.')
        return super().form_valid(form)


class CourseEnrollView(ModuleRequiredMixin, DetailView):
    """강좌 수강 등록"""
    required_module = 'lms'
    model = Course
    template_name = 'lms/course_detail.html'

    def post(self, request, *args, **kwargs):
        course = self.get_object()
        enrollment, created = CourseEnrollment.objects.get_or_create(
            course=course, learner=request.user,
            defaults={'created_by': request.user},
        )
        if created:
            messages.success(request, f'"{course.title}" 수강 등록이 완료되었습니다.')
        else:
            messages.info(request, '이미 수강 중인 강좌입니다.')
        return redirect('lms:course_detail', pk=course.pk)


class MyLearningView(ModuleRequiredMixin, ListView):
    """내 학습 현황"""
    required_module = 'lms'
    template_name = 'lms/my_learning.html'
    context_object_name = 'enrollments'
    paginate_by = 20

    def get_queryset(self):
        return CourseEnrollment.objects.filter(
            learner=self.request.user, is_active=True,
        ).select_related('course', 'course__category').order_by('-enrolled_at')


class LessonDetailView(ModuleRequiredMixin, DetailView):
    """강의 학습"""
    required_module = 'lms'
    model = Lesson
    template_name = 'lms/lesson_detail.html'
    context_object_name = 'lesson'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        enrollment = get_object_or_404(
            CourseEnrollment,
            course=self.object.course,
            learner=self.request.user,
            is_active=True,
        )
        ctx['enrollment'] = enrollment
        progress, _ = LessonProgress.objects.get_or_create(
            enrollment=enrollment, lesson=self.object,
            defaults={'created_by': self.request.user},
        )
        ctx['progress'] = progress
        return ctx

    def post(self, request, *args, **kwargs):
        lesson = self.get_object()
        enrollment = get_object_or_404(
            CourseEnrollment,
            course=lesson.course,
            learner=request.user,
            is_active=True,
        )
        progress, _ = LessonProgress.objects.get_or_create(
            enrollment=enrollment, lesson=lesson,
            defaults={'created_by': request.user},
        )
        if not progress.is_completed:
            progress.is_completed = True
            progress.completed_at = timezone.now()
            progress.save()
            # 진도율 갱신
            total = lesson.course.lessons.filter(is_active=True).count()
            completed = LessonProgress.objects.filter(
                enrollment=enrollment, is_completed=True, is_active=True,
            ).count()
            enrollment.progress_pct = int(completed / total * 100) if total else 0
            if enrollment.progress_pct >= 100:
                enrollment.status = CourseEnrollment.Status.COMPLETED
                enrollment.completed_at = timezone.now()
            enrollment.save()
            messages.success(request, '강의를 완료하였습니다.')
        return redirect('lms:lesson_detail', pk=lesson.pk)


class LessonCreateView(ModuleRequiredMixin, ManagerRequiredMixin, CreateView):
    required_module = 'lms'
    model = Lesson
    form_class = LessonForm
    template_name = 'lms/lesson_form.html'

    def get_success_url(self):
        return reverse_lazy('lms:course_detail', kwargs={'pk': self.object.course.pk})

    def form_valid(self, form):
        form.instance.created_by = self.request.user
        messages.success(self.request, '강의가 등록되었습니다.')
        return super().form_valid(form)


class QuizListView(ModuleRequiredMixin, ListView):
    required_module = 'lms'
    model = Quiz
    template_name = 'lms/quiz_list.html'
    context_object_name = 'quizzes'
    paginate_by = 20

    def get_queryset(self):
        return Quiz.objects.filter(is_active=True).select_related('course')


class QuizCreateView(ModuleRequiredMixin, ManagerRequiredMixin, CreateView):
    required_module = 'lms'
    model = Quiz
    form_class = QuizForm
    template_name = 'lms/quiz_form.html'
    success_url = reverse_lazy('lms:quiz_list')

    def form_valid(self, form):
        form.instance.created_by = self.request.user
        messages.success(self.request, '퀴즈가 등록되었습니다.')
        return super().form_valid(form)


class EnrollmentListView(ModuleRequiredMixin, ManagerRequiredMixin, ListView):
    required_module = 'lms'
    model = CourseEnrollment
    template_name = 'lms/enrollment_list.html'
    context_object_name = 'enrollments'
    paginate_by = 30

    def get_queryset(self):
        return CourseEnrollment.objects.filter(
            is_active=True,
        ).select_related('course', 'learner').order_by('-enrolled_at')


class CertificateListView(ModuleRequiredMixin, ListView):
    required_module = 'lms'
    model = Certificate
    template_name = 'lms/certificate_list.html'
    context_object_name = 'certificates'
    paginate_by = 20

    def get_queryset(self):
        return Certificate.objects.filter(
            enrollment__learner=self.request.user,
            is_active=True,
        ).select_related('enrollment__course').order_by('-issued_at')


class CourseCategoryListView(ModuleRequiredMixin, ManagerRequiredMixin, ListView):
    required_module = 'lms'
    model = CourseCategory
    template_name = 'lms/category_list.html'
    context_object_name = 'categories'
    paginate_by = 20

    def get_queryset(self):
        return CourseCategory.objects.filter(is_active=True).order_by('code')


class CourseCategoryCreateView(ModuleRequiredMixin, ManagerRequiredMixin, CreateView):
    required_module = 'lms'
    model = CourseCategory
    form_class = CourseCategoryForm
    template_name = 'lms/category_form.html'
    success_url = reverse_lazy('lms:category_list')

    def form_valid(self, form):
        form.instance.created_by = self.request.user
        messages.success(self.request, '분류가 등록되었습니다.')
        return super().form_valid(form)
