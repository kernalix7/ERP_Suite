"""증빙/증적 첨부파일 뷰"""
from django.apps import apps
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.contenttypes.models import ContentType
from django.http import HttpResponseRedirect, Http404
from django.urls import reverse
from django.views import View
from django.views.generic import ListView, TemplateView

from apps.core.mixins import ManagerRequiredMixin
from .attachment import Attachment, ALLOWED_EXTENSIONS, MAX_FILE_SIZE


class AttachmentListView(ManagerRequiredMixin, ListView):
    """전체 증빙 목록"""
    model = Attachment
    template_name = 'core/attachment_list.html'
    context_object_name = 'attachments'
    paginate_by = 20

    def get_queryset(self):
        qs = super().get_queryset()
        doc_type = self.request.GET.get('type')
        if doc_type:
            qs = qs.filter(doc_type=doc_type)
        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['doc_types'] = Attachment.DocType.choices
        return ctx


class AttachmentUploadView(LoginRequiredMixin, View):
    """증빙 파일 업로드 (POST)"""
    def post(self, request, app_label, model_name, pk):
        try:
            model = apps.get_model(app_label, model_name)
        except LookupError:
            raise Http404

        try:
            obj = model.objects.get(pk=pk)
        except model.DoesNotExist:
            raise Http404

        uploaded_file = request.FILES.get('file')
        if not uploaded_file:
            return HttpResponseRedirect(request.META.get('HTTP_REFERER', '/'))

        if uploaded_file.size > MAX_FILE_SIZE:
            return HttpResponseRedirect(request.META.get('HTTP_REFERER', '/'))

        ct = ContentType.objects.get_for_model(obj)
        Attachment.objects.create(
            content_type=ct,
            object_id=obj.pk,
            file=uploaded_file,
            original_filename=uploaded_file.name,
            file_size=uploaded_file.size,
            doc_type=request.POST.get('doc_type', 'OTHER'),
            description=request.POST.get('description', ''),
            uploaded_by=request.user,
        )

        return HttpResponseRedirect(request.META.get('HTTP_REFERER', '/'))


class AttachmentDeleteView(ManagerRequiredMixin, View):
    """증빙 삭제"""
    def post(self, request, pk):
        try:
            attachment = Attachment.objects.get(pk=pk)
        except Attachment.DoesNotExist:
            raise Http404

        attachment.file.delete()
        attachment.delete()

        return HttpResponseRedirect(request.META.get('HTTP_REFERER', '/'))
