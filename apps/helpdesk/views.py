from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import Avg, Count, Q
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse_lazy
from django.utils import timezone
from django.views.generic import (
    CreateView,
    DetailView,
    ListView,
    TemplateView,
    UpdateView,
    View,
)

from apps.core.mixins import ManagerRequiredMixin

from .forms import (
    EscalationRuleForm,
    SLAForm,
    TicketAssignForm,
    TicketCategoryForm,
    TicketCommentForm,
    TicketForm,
)
from .models import (
    EscalationRule,
    SLA,
    Ticket,
    TicketCategory,
    TicketComment,
)


# ── Ticket views ──

class TicketListView(LoginRequiredMixin, ListView):
    model = Ticket
    template_name = 'helpdesk/ticket_list.html'
    context_object_name = 'tickets'
    paginate_by = 20

    def get_queryset(self):
        qs = super().get_queryset().filter(is_active=True).select_related(
            'category', 'reporter', 'assigned_to', 'sla',
        )
        status = self.request.GET.get('status')
        if status:
            qs = qs.filter(status=status)
        priority = self.request.GET.get('priority')
        if priority:
            qs = qs.filter(priority=priority)
        q = self.request.GET.get('q')
        if q:
            qs = qs.filter(
                Q(ticket_number__icontains=q)
                | Q(title__icontains=q)
                | Q(reporter__username__icontains=q)
            )
        return qs


class MyTicketListView(LoginRequiredMixin, ListView):
    model = Ticket
    template_name = 'helpdesk/ticket_list.html'
    context_object_name = 'tickets'
    paginate_by = 20

    def get_queryset(self):
        return (
            super().get_queryset()
            .filter(is_active=True, assigned_to=self.request.user)
            .select_related('category', 'reporter', 'assigned_to', 'sla')
        )

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['page_title'] = '내 티켓'
        return ctx


class TicketCreateView(LoginRequiredMixin, CreateView):
    model = Ticket
    form_class = TicketForm
    template_name = 'helpdesk/ticket_form.html'
    success_url = reverse_lazy('helpdesk:ticket_list')

    def form_valid(self, form):
        form.instance.created_by = self.request.user
        form.instance.reporter = self.request.user
        return super().form_valid(form)


class TicketDetailView(LoginRequiredMixin, DetailView):
    model = Ticket
    template_name = 'helpdesk/ticket_detail.html'
    context_object_name = 'ticket'
    slug_field = 'ticket_number'
    slug_url_kwarg = 'ticket_number'

    def get_queryset(self):
        return super().get_queryset().filter(is_active=True).select_related(
            'category', 'reporter', 'assigned_to', 'sla',
            'related_service', 'related_order',
        )

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['comments'] = self.object.comments.filter(is_active=True).select_related('author')
        ctx['attachments'] = self.object.attachments.filter(is_active=True)
        ctx['comment_form'] = TicketCommentForm()
        ctx['assign_form'] = TicketAssignForm(instance=self.object)
        return ctx


class TicketUpdateView(ManagerRequiredMixin, UpdateView):
    model = Ticket
    form_class = TicketForm
    template_name = 'helpdesk/ticket_form.html'
    slug_field = 'ticket_number'
    slug_url_kwarg = 'ticket_number'

    def get_queryset(self):
        return super().get_queryset().filter(is_active=True)

    def get_success_url(self):
        return reverse_lazy('helpdesk:ticket_detail', kwargs={'ticket_number': self.object.ticket_number})


class TicketAssignView(ManagerRequiredMixin, View):
    def post(self, request, ticket_number):
        ticket = get_object_or_404(Ticket, ticket_number=ticket_number, is_active=True)
        form = TicketAssignForm(request.POST, instance=ticket)
        if form.is_valid():
            ticket = form.save(commit=False)
            if ticket.status == Ticket.Status.OPEN:
                ticket.status = Ticket.Status.ASSIGNED
            ticket.save()
        return redirect('helpdesk:ticket_detail', ticket_number=ticket.ticket_number)


class TicketResolveView(ManagerRequiredMixin, View):
    def post(self, request, ticket_number):
        ticket = get_object_or_404(Ticket, ticket_number=ticket_number, is_active=True)
        ticket.status = Ticket.Status.RESOLVED
        ticket.save(update_fields=['status', 'updated_at'])
        return redirect('helpdesk:ticket_detail', ticket_number=ticket.ticket_number)


class TicketCloseView(ManagerRequiredMixin, View):
    def post(self, request, ticket_number):
        ticket = get_object_or_404(Ticket, ticket_number=ticket_number, is_active=True)
        ticket.status = Ticket.Status.CLOSED
        ticket.save(update_fields=['status', 'updated_at'])
        return redirect('helpdesk:ticket_detail', ticket_number=ticket.ticket_number)


class TicketCommentCreateView(LoginRequiredMixin, View):
    def post(self, request, ticket_number):
        ticket = get_object_or_404(Ticket, ticket_number=ticket_number, is_active=True)
        form = TicketCommentForm(request.POST)
        if form.is_valid():
            comment = form.save(commit=False)
            comment.ticket = ticket
            comment.author = request.user
            comment.created_by = request.user
            comment.save()
        return redirect('helpdesk:ticket_detail', ticket_number=ticket.ticket_number)


# ── Category views ──

class CategoryListView(ManagerRequiredMixin, ListView):
    model = TicketCategory
    template_name = 'helpdesk/category_list.html'
    context_object_name = 'categories'
    paginate_by = 20

    def get_queryset(self):
        return super().get_queryset().filter(is_active=True).select_related('parent', 'default_sla')


class CategoryCreateView(ManagerRequiredMixin, CreateView):
    model = TicketCategory
    form_class = TicketCategoryForm
    template_name = 'helpdesk/category_form.html'
    success_url = reverse_lazy('helpdesk:category_list')

    def form_valid(self, form):
        form.instance.created_by = self.request.user
        return super().form_valid(form)


class CategoryUpdateView(ManagerRequiredMixin, UpdateView):
    model = TicketCategory
    form_class = TicketCategoryForm
    template_name = 'helpdesk/category_form.html'
    success_url = reverse_lazy('helpdesk:category_list')


# ── SLA views ──

class SLAListView(ManagerRequiredMixin, ListView):
    model = SLA
    template_name = 'helpdesk/sla_list.html'
    context_object_name = 'slas'
    paginate_by = 20

    def get_queryset(self):
        return super().get_queryset().filter(is_active=True)


class SLACreateView(ManagerRequiredMixin, CreateView):
    model = SLA
    form_class = SLAForm
    template_name = 'helpdesk/sla_form.html'
    success_url = reverse_lazy('helpdesk:sla_list')

    def form_valid(self, form):
        form.instance.created_by = self.request.user
        return super().form_valid(form)


class SLAUpdateView(ManagerRequiredMixin, UpdateView):
    model = SLA
    form_class = SLAForm
    template_name = 'helpdesk/sla_form.html'
    success_url = reverse_lazy('helpdesk:sla_list')


# ── Dashboard ──

class HelpdeskDashboardView(LoginRequiredMixin, TemplateView):
    template_name = 'helpdesk/dashboard.html'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        tickets = Ticket.objects.filter(is_active=True)
        ctx['open_count'] = tickets.filter(
            status__in=[Ticket.Status.OPEN, Ticket.Status.ASSIGNED, Ticket.Status.IN_PROGRESS, Ticket.Status.WAITING],
        ).count()
        ctx['breached_count'] = tickets.filter(sla_breached=True).exclude(
            status__in=[Ticket.Status.RESOLVED, Ticket.Status.CLOSED],
        ).count()
        ctx['resolved_count'] = tickets.filter(status=Ticket.Status.RESOLVED).count()
        ctx['closed_count'] = tickets.filter(status=Ticket.Status.CLOSED).count()
        ctx['by_priority'] = (
            tickets.exclude(status__in=[Ticket.Status.RESOLVED, Ticket.Status.CLOSED])
            .values('priority').annotate(count=Count('id')).order_by('priority')
        )
        ctx['recent_tickets'] = (
            tickets.select_related('category', 'reporter', 'assigned_to')
            .order_by('-created_at')[:10]
        )
        return ctx
