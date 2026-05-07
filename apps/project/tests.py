import datetime

from django.core.exceptions import ValidationError
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


class ProjectDetailViewAccessTest(TestCase):
    def setUp(self):
        self.client = Client()
        self.admin = User.objects.create_user(username='proj_admin', password='pass', role='admin')
        self.manager = User.objects.create_user(username='proj_mgr2', password='pass', role='manager')
        self.staff = User.objects.create_user(username='proj_stf2', password='pass', role='staff')
        self.project = Project.objects.create(
            name='접근테스트 프로젝트', manager=self.admin, created_by=self.admin,
        )

    def test_admin_can_access_detail(self):
        self.client.force_login(self.admin)
        response = self.client.get(reverse('project:project_detail', kwargs={'pk': self.project.pk}))
        self.assertEqual(response.status_code, 200)

    def test_manager_can_access_detail(self):
        self.client.force_login(self.manager)
        response = self.client.get(reverse('project:project_detail', kwargs={'pk': self.project.pk}))
        self.assertEqual(response.status_code, 200)

    def test_staff_can_access_detail(self):
        self.client.force_login(self.staff)
        response = self.client.get(reverse('project:project_detail', kwargs={'pk': self.project.pk}))
        self.assertEqual(response.status_code, 200)

    def test_unauthenticated_redirects_from_detail(self):
        response = self.client.get(reverse('project:project_detail', kwargs={'pk': self.project.pk}))
        self.assertEqual(response.status_code, 302)


class ProjectStatusWorkflowTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='proj_wf', password='pass')
        self.project = Project.objects.create(
            name='워크플로우 프로젝트', manager=self.user, created_by=self.user,
        )

    def test_project_default_status_is_planning(self):
        self.assertEqual(self.project.status, Project.Status.PLANNING)

    def test_project_status_transition_to_active(self):
        self.project.status = Project.Status.ACTIVE
        self.project.save()
        self.project.refresh_from_db()
        self.assertEqual(self.project.status, Project.Status.ACTIVE)

    def test_project_status_transition_to_completed(self):
        self.project.status = Project.Status.COMPLETED
        self.project.completed_date = datetime.date.today()
        self.project.save()
        self.project.refresh_from_db()
        self.assertEqual(self.project.status, Project.Status.COMPLETED)


class TaskModelValidationTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='task_val', password='pass')
        self.project = Project.objects.create(
            name='태스크검증 프로젝트', manager=self.user, created_by=self.user,
        )

    def test_task_priority_default(self):
        task = Task.objects.create(project=self.project, title='우선순위 테스트', created_by=self.user)
        self.assertEqual(task.priority, Task.Priority.MEDIUM)

    def test_task_due_date_stored_correctly(self):
        due = datetime.date(2026, 12, 31)
        task = Task.objects.create(
            project=self.project, title='마감일 태스크', due_date=due, created_by=self.user,
        )
        self.assertEqual(task.due_date, due)

    def test_task_invalid_status_transition_raises(self):
        task = Task.objects.create(
            project=self.project, title='전이검증', status=Task.Status.DONE, created_by=self.user,
        )
        task.status = Task.Status.IN_PROGRESS
        with self.assertRaises(ValidationError):
            task.clean()


class TaskListViewFilterTest(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(username='task_filter', password='pass', role='staff')
        self.project = Project.objects.create(
            name='필터테스트 프로젝트', manager=self.user, created_by=self.user,
        )
        self.parent = Task.objects.create(
            project=self.project, title='부모태스크', assignee=self.user, created_by=self.user,
        )
        self.child = Task.objects.create(
            project=self.project, title='자식태스크', parent_task=self.parent,
            assignee=self.user, created_by=self.user,
        )
        self.client.force_login(self.user)

    def test_task_list_returns_200(self):
        response = self.client.get(reverse('project:task_list'))
        self.assertEqual(response.status_code, 200)

    def test_parent_task_has_sub_tasks(self):
        self.assertEqual(self.parent.sub_tasks.filter(is_active=True).count(), 1)

    def test_child_task_has_parent_reference(self):
        self.assertEqual(self.child.parent_task, self.parent)
