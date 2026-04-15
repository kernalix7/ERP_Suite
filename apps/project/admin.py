from django.contrib import admin
from .models import (
    ProjectCategory, Project, ProjectMember, Milestone,
    Task, TaskComment, TaskAttachment, TimeLog,
)

admin.site.register(ProjectCategory)
admin.site.register(Project)
admin.site.register(ProjectMember)
admin.site.register(Milestone)
admin.site.register(Task)
admin.site.register(TaskComment)
admin.site.register(TaskAttachment)
admin.site.register(TimeLog)
