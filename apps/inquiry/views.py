import json

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import Count
from django.http import HttpResponseRedirect, JsonResponse
from django.shortcuts import get_object_or_404
from django.urls import reverse_lazy, reverse
from django.views import View
from django.views.generic import (
    ListView, CreateView, UpdateView, DetailView, TemplateView,
)

from apps.core.mixins import ManagerRequiredMixin
from .models import InquiryChannel, Inquiry, InquiryReply, ReplyTemplate
from .forms import InquiryChannelForm, InquiryForm, InquiryReplyForm, ReplyTemplateForm
from .llm_service import generate_inquiry_reply


class InquiryDashboardView(LoginRequiredMixin, TemplateView):
    template_name = 'inquiry/dashboard.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['status_counts'] = (
            Inquiry.objects.filter(is_active=True).values('status')
            .annotate(count=Count('id'))
            .order_by('status')
        )
        context['recent_inquiries'] = Inquiry.objects.filter(is_active=True)[:10]
        context['total_inquiries'] = Inquiry.objects.filter(is_active=True).count()
        return context


class InquiryListView(LoginRequiredMixin, ListView):
    model = Inquiry
    template_name = 'inquiry/inquiry_list.html'
    context_object_name = 'inquiries'
    paginate_by = 20

    def get_queryset(self):
        qs = super().get_queryset().filter(is_active=True).select_related('channel')
        status = self.request.GET.get('status')
        channel = self.request.GET.get('channel')
        if status:
            qs = qs.filter(status=status)
        if channel:
            qs = qs.filter(channel_id=channel)
        return qs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['channels'] = InquiryChannel.objects.filter(is_active=True)
        return context


class InquiryCreateView(ManagerRequiredMixin, CreateView):
    model = Inquiry
    form_class = InquiryForm
    template_name = 'inquiry/inquiry_form.html'
    success_url = reverse_lazy('inquiry:inquiry_list')

    def form_valid(self, form):
        form.instance.created_by = self.request.user
        return super().form_valid(form)


class InquiryDetailView(LoginRequiredMixin, DetailView):
    model = Inquiry
    template_name = 'inquiry/inquiry_detail.html'
    context_object_name = 'inquiry'
    slug_field = 'inquiry_number'
    slug_url_kwarg = 'slug'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['replies'] = self.object.replies.all()
        context['reply_form'] = InquiryReplyForm()
        return context


class InquiryUpdateView(ManagerRequiredMixin, UpdateView):
    model = Inquiry
    form_class = InquiryForm
    template_name = 'inquiry/inquiry_form.html'
    slug_field = 'inquiry_number'
    slug_url_kwarg = 'slug'

    def get_success_url(self):
        return reverse('inquiry:inquiry_detail', kwargs={'slug': self.object.inquiry_number})


class InquiryReplyCreateView(LoginRequiredMixin, CreateView):
    model = InquiryReply
    form_class = InquiryReplyForm
    template_name = 'inquiry/inquiry_detail.html'

    def form_valid(self, form):
        inquiry = get_object_or_404(Inquiry, inquiry_number=self.kwargs['slug'])
        form.instance.inquiry = inquiry
        form.instance.replied_by = self.request.user
        form.instance.created_by = self.request.user
        response = super().form_valid(form)
        # Update inquiry status to replied
        if inquiry.status in (Inquiry.Status.RECEIVED, Inquiry.Status.WAITING):
            inquiry.status = Inquiry.Status.REPLIED
            inquiry.save(update_fields=['status', 'updated_at'])
        return response

    def get_success_url(self):
        return reverse('inquiry:inquiry_detail', kwargs={'slug': self.kwargs['slug']})


class ReplyTemplateListView(LoginRequiredMixin, ListView):
    model = ReplyTemplate
    template_name = 'inquiry/template_list.html'
    context_object_name = 'templates'
    paginate_by = 20

    def get_queryset(self):
        return super().get_queryset().filter(is_active=True)


class ReplyTemplateCreateView(ManagerRequiredMixin, CreateView):
    model = ReplyTemplate
    form_class = ReplyTemplateForm
    template_name = 'inquiry/template_form.html'
    success_url = reverse_lazy('inquiry:template_list')

    def form_valid(self, form):
        form.instance.created_by = self.request.user
        return super().form_valid(form)


class ReplyTemplateUpdateView(ManagerRequiredMixin, UpdateView):
    model = ReplyTemplate
    form_class = ReplyTemplateForm
    template_name = 'inquiry/template_form.html'
    success_url = reverse_lazy('inquiry:template_list')


class LLMGenerateView(LoginRequiredMixin, View):
    """AJAX 기반 AI 답변 초안 생성 (텍스트영역에 삽입용)."""

    def post(self, request, slug):
        inquiry = get_object_or_404(Inquiry, inquiry_number=slug)
        templates = list(ReplyTemplate.objects.filter(is_active=True)[:10])

        reply_text = generate_inquiry_reply(inquiry, templates=templates)
        if reply_text:
            return JsonResponse({'success': True, 'content': reply_text})
        return JsonResponse(
            {'success': False, 'error': 'AI 답변 생성에 실패했습니다.'},
        )


class GenerateReplyView(LoginRequiredMixin, View):
    """AI 답변을 InquiryReply로 저장하고 리다이렉트."""

    http_method_names = ['post']

    def post(self, request, slug):
        inquiry = get_object_or_404(Inquiry, inquiry_number=slug)
        templates = list(ReplyTemplate.objects.filter(is_active=True)[:10])

        reply_text = generate_inquiry_reply(inquiry, templates=templates)

        if reply_text:
            InquiryReply.objects.create(
                inquiry=inquiry,
                content=reply_text,
                is_llm_generated=True,
                replied_by=request.user,
                created_by=request.user,
            )
            if inquiry.status in (Inquiry.Status.RECEIVED, Inquiry.Status.WAITING):
                inquiry.status = Inquiry.Status.REPLIED
                inquiry.save(update_fields=['status', 'updated_at'])
            messages.success(request, 'AI 답변이 성공적으로 생성되었습니다.')
        else:
            messages.error(request, 'AI 답변 생성에 실패했습니다. API 키 설정을 확인해주세요.')

        return HttpResponseRedirect(
            reverse('inquiry:inquiry_detail', kwargs={'slug': slug})
        )


class InquiryChannelListView(ManagerRequiredMixin, ListView):
    model = InquiryChannel
    template_name = 'inquiry/channel_list.html'
    context_object_name = 'channels'
    paginate_by = 20

    def get_queryset(self):
        return super().get_queryset().filter(is_active=True)


class InquiryChannelCreateView(ManagerRequiredMixin, CreateView):
    model = InquiryChannel
    form_class = InquiryChannelForm
    template_name = 'inquiry/channel_form.html'
    success_url = reverse_lazy('inquiry:channel_list')

    def form_valid(self, form):
        form.instance.created_by = self.request.user
        return super().form_valid(form)


class InquiryChannelUpdateView(ManagerRequiredMixin, UpdateView):
    model = InquiryChannel
    form_class = InquiryChannelForm
    template_name = 'inquiry/channel_form.html'
    success_url = reverse_lazy('inquiry:channel_list')
