from django.contrib import admin
from .models import VisitorPurpose, Visitor, VisitRequest, VisitLog, VisitorNDA

admin.site.register(VisitorPurpose)
admin.site.register(Visitor)
admin.site.register(VisitRequest)
admin.site.register(VisitLog)
admin.site.register(VisitorNDA)
