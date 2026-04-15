from django.urls import path
from . import views
from apps.core.excel_views import ProjectExcelView, TaskExcelView

app_name = 'project'

urlpatterns = [
    path('export/projects/', ProjectExcelView.as_view(), name='project_excel'),
    path('export/tasks/', TaskExcelView.as_view(), name='task_excel'),
    path('', views.ProjectListView.as_view(), name='project_list'),
    path('create/', views.ProjectCreateView.as_view(), name='project_create'),
    path('tasks/', views.TaskListView.as_view(), name='task_list'),
    path('tasks/create/', views.TaskCreateView.as_view(), name='task_create'),
    path('tasks/<int:pk>/', views.TaskDetailView.as_view(), name='task_detail'),
    path('tasks/<int:pk>/edit/', views.TaskUpdateView.as_view(), name='task_update'),
    path('tasks/<int:task_pk>/comments/', views.TaskCommentCreateView.as_view(), name='task_comment_create'),
    path('tasks/<int:task_pk>/timelogs/', views.TimeLogCreateView.as_view(), name='timelog_create'),
    path('milestones/create/', views.MilestoneCreateView.as_view(), name='milestone_create'),
    path('members/create/', views.ProjectMemberCreateView.as_view(), name='member_create'),
    path('<int:pk>/', views.ProjectDetailView.as_view(), name='project_detail'),
    path('<int:pk>/edit/', views.ProjectUpdateView.as_view(), name='project_update'),
]
