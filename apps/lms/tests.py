from django.test import TestCase, Client
from django.contrib.auth import get_user_model
from django.urls import reverse
from .models import CourseCategory, Course, Lesson, CourseEnrollment

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
