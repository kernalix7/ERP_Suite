from apps.core.forms import BaseForm
from .models import ProjectCategory, Project, ProjectMember, Milestone, Task, TaskComment, TimeLog


class ProjectCategoryForm(BaseForm):
    class Meta:
        model = ProjectCategory
        fields = ['name', 'code', 'notes']


class ProjectForm(BaseForm):
    class Meta:
        model = Project
        fields = [
            'name', 'category', 'status', 'priority', 'manager', 'department',
            'description', 'start_date', 'due_date', 'budget', 'notes',
        ]


class ProjectMemberForm(BaseForm):
    class Meta:
        model = ProjectMember
        fields = ['project', 'user', 'role', 'joined_at', 'notes']


class MilestoneForm(BaseForm):
    class Meta:
        model = Milestone
        fields = ['project', 'title', 'description', 'due_date', 'status', 'notes']


class TaskForm(BaseForm):
    class Meta:
        model = Task
        fields = [
            'project', 'milestone', 'parent_task', 'title', 'description',
            'status', 'priority', 'assignee', 'reporter',
            'start_date', 'due_date', 'estimated_hours', 'notes',
        ]


class TaskCommentForm(BaseForm):
    class Meta:
        model = TaskComment
        fields = ['content']


class TimeLogForm(BaseForm):
    class Meta:
        model = TimeLog
        fields = ['task', 'work_date', 'hours', 'description', 'notes']
