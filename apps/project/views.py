from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import Q, Sum
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse_lazy
from django.utils import timezone
from django.views.generic import ListView, CreateView, UpdateView, DetailView

from apps.core.mixins import ManagerRequiredMixin
from apps.module_manager.decorators import ModuleRequiredMixin
from .models import Project, ProjectCategory, ProjectMember, Milestone, Task, TaskComment, TimeLog
from .forms import (
    ProjectForm, ProjectCategoryForm, ProjectMemberForm, MilestoneForm,
    TaskForm, TaskCommentForm, TimeLogForm,
)


class ProjectListView(ModuleRequiredMixin, ListView):
    required_module = 'project'
    model = Project
    template_name = 'project/project_list.html'
    context_object_name = 'projects'
    paginate_by = 20

    def get_queryset(self):
        qs = Project.objects.filter(is_active=True).select_related('category', 'manager', 'department')
        q = self.request.GET.get('q')
        if q:
            qs = qs.filter(Q(name__icontains=q) | Q(description__icontains=q))
        status = self.request.GET.get('status')
        if status:
            qs = qs.filter(status=status)
        priority = self.request.GET.get('priority')
        if priority:
            qs = qs.filter(priority=priority)
        return qs


class ProjectDetailView(ModuleRequiredMixin, DetailView):
    required_module = 'project'
    model = Project
    template_name = 'project/project_detail.html'
    context_object_name = 'project'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['members'] = self.object.members.filter(is_active=True).select_related('user')
        ctx['milestones'] = self.object.milestones.filter(is_active=True).order_by('due_date')
        ctx['tasks'] = self.object.tasks.filter(
            is_active=True, parent_task__isnull=True,
        ).select_related('assignee', 'milestone').order_by('priority', 'due_date')
        ctx['total_logged'] = TimeLog.objects.filter(
            task__project=self.object, is_active=True,
        ).aggregate(total=Sum('hours'))['total'] or 0
        return ctx


class ProjectCreateView(ModuleRequiredMixin, ManagerRequiredMixin, CreateView):
    required_module = 'project'
    model = Project
    form_class = ProjectForm
    template_name = 'project/project_form.html'
    success_url = reverse_lazy('project:project_list')

    def form_valid(self, form):
        form.instance.created_by = self.request.user
        messages.success(self.request, '프로젝트가 등록되었습니다.')
        return super().form_valid(form)


class ProjectUpdateView(ModuleRequiredMixin, ManagerRequiredMixin, UpdateView):
    required_module = 'project'
    model = Project
    form_class = ProjectForm
    template_name = 'project/project_form.html'

    def get_success_url(self):
        return reverse_lazy('project:project_detail', kwargs={'pk': self.object.pk})

    def form_valid(self, form):
        messages.success(self.request, '프로젝트가 수정되었습니다.')
        return super().form_valid(form)


class TaskListView(ModuleRequiredMixin, ListView):
    required_module = 'project'
    model = Task
    template_name = 'project/task_list.html'
    context_object_name = 'tasks'
    paginate_by = 30

    def get_queryset(self):
        qs = Task.objects.filter(is_active=True).select_related(
            'project', 'assignee', 'milestone',
        )
        project_id = self.request.GET.get('project')
        if project_id:
            qs = qs.filter(project_id=project_id)
        assignee = self.request.GET.get('assignee')
        if assignee == 'me':
            qs = qs.filter(assignee=self.request.user)
        status = self.request.GET.get('status')
        if status:
            qs = qs.filter(status=status)
        q = self.request.GET.get('q')
        if q:
            qs = qs.filter(Q(title__icontains=q) | Q(description__icontains=q))
        return qs


class TaskDetailView(ModuleRequiredMixin, DetailView):
    required_module = 'project'
    model = Task
    template_name = 'project/task_detail.html'
    context_object_name = 'task'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['comments'] = self.object.comments.filter(is_active=True).select_related('author')
        ctx['sub_tasks'] = self.object.sub_tasks.filter(is_active=True).select_related('assignee')
        ctx['time_logs'] = self.object.time_logs.filter(is_active=True).select_related('worker')
        ctx['comment_form'] = TaskCommentForm()
        ctx['time_log_form'] = TimeLogForm(initial={'task': self.object})
        return ctx


class TaskCreateView(ModuleRequiredMixin, CreateView):
    required_module = 'project'
    model = Task
    form_class = TaskForm
    template_name = 'project/task_form.html'

    def get_success_url(self):
        return reverse_lazy('project:task_detail', kwargs={'pk': self.object.pk})

    def form_valid(self, form):
        form.instance.created_by = self.request.user
        messages.success(self.request, '태스크가 등록되었습니다.')
        return super().form_valid(form)


class TaskUpdateView(ModuleRequiredMixin, UpdateView):
    required_module = 'project'
    model = Task
    form_class = TaskForm
    template_name = 'project/task_form.html'

    def get_success_url(self):
        return reverse_lazy('project:task_detail', kwargs={'pk': self.object.pk})

    def form_valid(self, form):
        messages.success(self.request, '태스크가 수정되었습니다.')
        return super().form_valid(form)


class TaskCommentCreateView(ModuleRequiredMixin, CreateView):
    required_module = 'project'
    model = TaskComment
    form_class = TaskCommentForm

    def form_valid(self, form):
        task = get_object_or_404(Task, pk=self.kwargs['task_pk'])
        form.instance.task = task
        form.instance.author = self.request.user
        form.instance.created_by = self.request.user
        form.save()
        messages.success(self.request, '댓글이 등록되었습니다.')
        return redirect('project:task_detail', pk=task.pk)


class TimeLogCreateView(ModuleRequiredMixin, CreateView):
    required_module = 'project'
    model = TimeLog
    form_class = TimeLogForm

    def form_valid(self, form):
        form.instance.worker = self.request.user
        form.instance.created_by = self.request.user
        form.save()
        # 실제 시간 합산 갱신
        task = form.instance.task
        from django.db.models import Sum
        total = TimeLog.objects.filter(task=task, is_active=True).aggregate(t=Sum('hours'))['t'] or 0
        Task.objects.filter(pk=task.pk).update(actual_hours=total)
        messages.success(self.request, '작업시간이 기록되었습니다.')
        return redirect('project:task_detail', pk=task.pk)


class MilestoneCreateView(ModuleRequiredMixin, ManagerRequiredMixin, CreateView):
    required_module = 'project'
    model = Milestone
    form_class = MilestoneForm
    template_name = 'project/milestone_form.html'

    def get_success_url(self):
        return reverse_lazy('project:project_detail', kwargs={'pk': self.object.project.pk})

    def form_valid(self, form):
        form.instance.created_by = self.request.user
        messages.success(self.request, '마일스톤이 등록되었습니다.')
        return super().form_valid(form)


class ProjectMemberCreateView(ModuleRequiredMixin, ManagerRequiredMixin, CreateView):
    required_module = 'project'
    model = ProjectMember
    form_class = ProjectMemberForm
    template_name = 'project/member_form.html'

    def get_success_url(self):
        return reverse_lazy('project:project_detail', kwargs={'pk': self.object.project.pk})

    def form_valid(self, form):
        form.instance.created_by = self.request.user
        messages.success(self.request, '멤버가 추가되었습니다.')
        return super().form_valid(form)
