from django.test import TestCase, Client
from django.contrib.auth import get_user_model
from django.urls import reverse
from .models import ProjectCategory, Project, Task

User = get_user_model()


class ProjectModelTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='pm', password='pass')
        self.category = ProjectCategory.objects.create(name='IT개발', code='IT', created_by=self.user)

    def test_project_auto_number(self):
        project = Project.objects.create(
            name='ERP 구축',
            manager=self.user,
            created_by=self.user,
        )
        self.assertTrue(project.project_number.startswith('PRJ'))

    def test_task_default_status(self):
        project = Project.objects.create(
            name='웹사이트 개발',
            manager=self.user,
            created_by=self.user,
        )
        task = Task.objects.create(
            project=project,
            title='디자인 작업',
            created_by=self.user,
        )
        self.assertEqual(task.status, Task.Status.TODO)

    def test_project_str(self):
        project = Project.objects.create(
            name='모바일 앱',
            manager=self.user,
            created_by=self.user,
        )
        self.assertIn('PRJ', str(project))


class ProjectViewTest(TestCase):
    def setUp(self):
        self.client = Client()
        self.staff_user = User.objects.create_user(
            username='proj_staff', password='pass', role='staff',
        )
        self.manager_user = User.objects.create_user(
            username='proj_manager', password='pass', role='manager',
        )

    def test_project_list_requires_login(self):
        response = self.client.get(reverse('project:project_list'))
        self.assertIn(response.status_code, [302, 403])

    def test_project_create_requires_manager(self):
        self.client.force_login(self.staff_user)
        response = self.client.get(reverse('project:project_create'))
        self.assertEqual(response.status_code, 403)

    def test_project_create_unauthenticated_redirects(self):
        response = self.client.get(reverse('project:project_create'))
        self.assertEqual(response.status_code, 302)

    def test_task_list_requires_login(self):
        response = self.client.get(reverse('project:task_list'))
        self.assertIn(response.status_code, [302, 403])

    def test_milestone_create_requires_manager(self):
        self.client.force_login(self.staff_user)
        response = self.client.get(reverse('project:milestone_create'))
        self.assertEqual(response.status_code, 403)
