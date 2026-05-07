from django.core.exceptions import ValidationError
from django.test import TestCase, Client
from django.contrib.auth import get_user_model
from django.urls import reverse
from .models import CourseCategory, Course, Lesson, CourseEnrollment, LessonProgress, Certificate

User = get_user_model()


class CourseModelTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='testuser', password='pass')
        self.category = CourseCategory.objects.create(name='기술교육', code='TECH', created_by=self.user)

    def test_course_auto_number(self):
        course = Course.objects.create(
            title='Django 기초',
            category=self.category,
            created_by=self.user,
        )
        self.assertTrue(course.course_number.startswith('CRS'))

    def test_enrollment_unique(self):
        course = Course.objects.create(
            title='Python 기초',
            category=self.category,
            created_by=self.user,
        )
        CourseEnrollment.objects.create(course=course, learner=self.user, created_by=self.user)
        with self.assertRaises(Exception):
            CourseEnrollment.objects.create(course=course, learner=self.user, created_by=self.user)

    def test_lesson_ordering(self):
        course = Course.objects.create(
            title='HTML 기초',
            category=self.category,
            created_by=self.user,
        )
        Lesson.objects.create(course=course, title='2강', order=2, created_by=self.user)
        Lesson.objects.create(course=course, title='1강', order=1, created_by=self.user)
        lessons = list(course.lessons.all())
        self.assertEqual(lessons[0].order, 1)
        self.assertEqual(lessons[1].order, 2)


class LmsViewTest(TestCase):
    def setUp(self):
        self.client = Client()
        self.staff_user = User.objects.create_user(
            username='lms_staff', password='pass', role='staff',
        )
        self.manager_user = User.objects.create_user(
            username='lms_manager', password='pass', role='manager',
        )

    def test_course_list_requires_login(self):
        response = self.client.get(reverse('lms:course_list'))
        self.assertIn(response.status_code, [302, 403])

    def test_course_create_requires_manager(self):
        self.client.force_login(self.staff_user)
        response = self.client.get(reverse('lms:course_create'))
        self.assertEqual(response.status_code, 403)

    def test_course_create_unauthenticated_redirects(self):
        response = self.client.get(reverse('lms:course_create'))
        self.assertEqual(response.status_code, 302)

    def test_category_list_requires_manager(self):
        self.client.force_login(self.staff_user)
        response = self.client.get(reverse('lms:category_list'))
        self.assertEqual(response.status_code, 403)

    def test_category_list_unauthenticated_redirects(self):
        response = self.client.get(reverse('lms:category_list'))
        self.assertEqual(response.status_code, 302)


class CourseWorkflowTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='lms_wf', password='pass')
        self.category = CourseCategory.objects.create(name='실습', code='PRAC', created_by=self.user)

    def test_course_lesson_enrollment_workflow(self):
        course = Course.objects.create(
            title='워크플로우 강좌', category=self.category, created_by=self.user,
        )
        lesson1 = Lesson.objects.create(course=course, title='1강', order=1, created_by=self.user)
        Lesson.objects.create(course=course, title='2강', order=2, created_by=self.user)
        enrollment = CourseEnrollment.objects.create(
            course=course, learner=self.user, created_by=self.user,
        )
        self.assertEqual(enrollment.status, CourseEnrollment.Status.ENROLLED)
        self.assertEqual(course.lessons.count(), 2)
        # 강의 진행 기록
        progress = LessonProgress.objects.create(
            enrollment=enrollment, lesson=lesson1,
            is_completed=True, created_by=self.user,
        )
        self.assertTrue(progress.is_completed)

    def test_lesson_progress_drives_enrollment_pct(self):
        course = Course.objects.create(
            title='진도율 강좌', category=self.category, created_by=self.user,
        )
        l1 = Lesson.objects.create(course=course, title='L1', order=1, created_by=self.user)
        l2 = Lesson.objects.create(course=course, title='L2', order=2, created_by=self.user)
        enrollment = CourseEnrollment.objects.create(
            course=course, learner=self.user, created_by=self.user,
        )
        LessonProgress.objects.create(enrollment=enrollment, lesson=l1, is_completed=True, created_by=self.user)
        completed = LessonProgress.objects.filter(enrollment=enrollment, is_completed=True).count()
        total = course.lessons.count()
        pct = int(completed / total * 100)
        enrollment.progress_pct = pct
        enrollment.save()
        enrollment.refresh_from_db()
        self.assertEqual(enrollment.progress_pct, 50)

    def test_course_status_invalid_transition_raises(self):
        course = Course.objects.create(
            title='전이검증 강좌', category=self.category, created_by=self.user,
            status=Course.Status.CLOSED,
        )
        course.status = Course.Status.DRAFT
        with self.assertRaises(ValidationError):
            course.clean()

    def test_certificate_auto_number(self):
        course = Course.objects.create(
            title='수료증 강좌', category=self.category, created_by=self.user,
        )
        enrollment = CourseEnrollment.objects.create(
            course=course, learner=self.user,
            status=CourseEnrollment.Status.COMPLETED,
            created_by=self.user,
        )
        cert = Certificate.objects.create(enrollment=enrollment, created_by=self.user)
        self.assertTrue(cert.certificate_number.startswith('CERT'))

    def test_course_enroll_view_post(self):
        client = Client()
        learner = User.objects.create_user(username='lms_enroll', password='pass', role='staff')
        client.force_login(learner)
        course = Course.objects.create(
            title='수강등록 강좌', category=self.category,
            status=Course.Status.PUBLISHED, created_by=self.user,
        )
        response = client.post(reverse('lms:course_enroll', kwargs={'pk': course.pk}))
        self.assertIn(response.status_code, [200, 302])
        self.assertTrue(
            CourseEnrollment.objects.filter(course=course, learner=learner).exists()
        )
