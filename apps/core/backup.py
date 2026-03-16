import io
from datetime import datetime

from django.http import HttpResponse
from django.views import View
from django.views.generic import TemplateView

from apps.core.mixins import AdminRequiredMixin


class BackupView(AdminRequiredMixin, TemplateView):
    template_name = 'core/backup.html'


class BackupDownloadView(AdminRequiredMixin, View):
    def get(self, request):
        from django.core.management import call_command
        output = io.StringIO()
        call_command(
            'dumpdata',
            '--exclude=contenttypes',
            '--exclude=auth.permission',
            '--indent=2',
            stdout=output,
        )
        response = HttpResponse(output.getvalue(), content_type='application/json')
        response['Content-Disposition'] = (
            f'attachment; filename="erp_backup_{datetime.now().strftime("%Y%m%d_%H%M%S")}.json"'
        )
        return response
