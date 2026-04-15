from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import Q, Sum
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse_lazy
from django.utils import timezone
from django.views import View
from django.views.generic import DetailView, ListView, TemplateView

from apps.core.mixins import ManagerRequiredMixin

from .forms import PortalLoginForm, PortalUserForm
from .models import PortalDocument, PortalNotification, PortalUser


class PortalAccessMixin(LoginRequiredMixin):
    """포털 사용자 전용 접근 제어 Mixin"""
    login_url = reverse_lazy('portal:login')

    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect('portal:login')
        if not hasattr(request.user, 'portal_profile'):
            return redirect('portal:login')
        if not request.user.portal_profile.is_verified:
            return redirect('portal:login')
        return super().dispatch(request, *args, **kwargs)

    def get_portal_user(self):
        return self.request.user.portal_profile

    def get_partner(self):
        return self.get_portal_user().partner


# ── Portal Auth ──

class PortalLoginView(View):
    template_name = 'portal/login.html'

    def get(self, request):
        if request.user.is_authenticated and hasattr(request.user, 'portal_profile'):
            return redirect('portal:dashboard')
        form = PortalLoginForm()
        return render(request, self.template_name, {'form': form})

    def post(self, request):
        form = PortalLoginForm(request.POST)
        if form.is_valid():
            user = authenticate(
                request,
                username=form.cleaned_data['username'],
                password=form.cleaned_data['password'],
            )
            if user and hasattr(user, 'portal_profile') and user.portal_profile.is_verified:
                login(request, user)
                user.portal_profile.last_portal_login = timezone.now()
                user.portal_profile.save(update_fields=['last_portal_login', 'updated_at'])
                return redirect('portal:dashboard')
            form.add_error(None, '인증 정보가 올바르지 않거나 포털 접근이 허가되지 않았습니다.')
        return render(request, self.template_name, {'form': form})


class PortalLogoutView(View):
    def post(self, request):
        logout(request)
        return redirect('portal:login')


# ── Portal Dashboard ──

class PortalDashboardView(PortalAccessMixin, TemplateView):
    template_name = 'portal/dashboard.html'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        portal_user = self.get_portal_user()
        partner = self.get_partner()

        ctx['portal_user'] = portal_user
        ctx['partner'] = partner
        ctx['unread_notifications'] = portal_user.notifications.filter(
            is_active=True, is_read=False,
        ).count()
        ctx['recent_notifications'] = portal_user.notifications.filter(
            is_active=True,
        ).order_by('-created_at')[:5]

        if portal_user.portal_type == PortalUser.PortalType.CUSTOMER:
            from apps.sales.models import Order
            orders = Order.objects.filter(partner=partner, is_active=True)
            ctx['order_count'] = orders.count()
            ctx['recent_orders'] = orders.order_by('-created_at')[:5]
        else:
            from apps.purchase.models import PurchaseOrder
            pos = PurchaseOrder.objects.filter(partner=partner, is_active=True)
            ctx['po_count'] = pos.count()
            ctx['recent_pos'] = pos.order_by('-created_at')[:5]

        return ctx


# ── Customer views ──

class PortalOrderListView(PortalAccessMixin, ListView):
    template_name = 'portal/order_list.html'
    context_object_name = 'orders'
    paginate_by = 20

    def get_queryset(self):
        from apps.sales.models import Order
        partner = self.get_partner()
        qs = Order.objects.filter(partner=partner, is_active=True).select_related('customer', 'assigned_to').order_by('-created_at')
        status = self.request.GET.get('status')
        if status:
            qs = qs.filter(status=status)
        return qs


class PortalOrderDetailView(PortalAccessMixin, DetailView):
    template_name = 'portal/order_detail.html'
    context_object_name = 'order'
    slug_field = 'order_number'
    slug_url_kwarg = 'order_number'

    def get_queryset(self):
        from apps.sales.models import Order
        partner = self.get_partner()
        return Order.objects.filter(partner=partner, is_active=True)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['items'] = self.object.items.filter(is_active=True).select_related('product')
        return ctx


class PortalInvoiceListView(PortalAccessMixin, ListView):
    template_name = 'portal/invoice_list.html'
    context_object_name = 'documents'
    paginate_by = 20

    def get_queryset(self):
        portal_user = self.get_portal_user()
        return PortalDocument.objects.filter(
            portal_user=portal_user,
            document_type=PortalDocument.DocumentType.INVOICE,
            is_active=True,
        ).order_by('-created_at')


class PortalDeliveryConfirmView(PortalAccessMixin, View):
    def post(self, request, order_number):
        from apps.sales.models import Order
        partner = self.get_partner()
        order = get_object_or_404(
            Order, order_number=order_number, partner=partner, is_active=True,
        )
        # TODO: 배송확인 로직 구현 — 주문 상태 검증 (SHIPPED/DELIVERED) + 고객 수령 확인 처리
        return redirect('portal:order_detail', order_number=order.order_number)


# ── Supplier views ──

class SupplierPOListView(PortalAccessMixin, ListView):
    template_name = 'portal/supplier_po_list.html'
    context_object_name = 'purchase_orders'
    paginate_by = 20

    def get_queryset(self):
        from apps.purchase.models import PurchaseOrder
        partner = self.get_partner()
        qs = PurchaseOrder.objects.filter(partner=partner, is_active=True).order_by('-created_at')
        status = self.request.GET.get('status')
        if status:
            qs = qs.filter(status=status)
        return qs


class SupplierDeliveryScheduleView(PortalAccessMixin, ListView):
    template_name = 'portal/supplier_delivery_schedule.html'
    context_object_name = 'purchase_orders'
    paginate_by = 20

    def get_queryset(self):
        from apps.purchase.models import PurchaseOrder
        partner = self.get_partner()
        return (
            PurchaseOrder.objects.filter(
                partner=partner, is_active=True,
                status__in=['CONFIRMED', 'PARTIAL_RECEIVED'],
            )
            .order_by('expected_date')
        )


# ── Notification views ──

class PortalNotificationListView(PortalAccessMixin, ListView):
    template_name = 'portal/notification_list.html'
    context_object_name = 'notifications'
    paginate_by = 20

    def get_queryset(self):
        portal_user = self.get_portal_user()
        return portal_user.notifications.filter(is_active=True).order_by('-created_at')


# ── Admin views (internal) ──

class PortalUserListView(ManagerRequiredMixin, ListView):
    model = PortalUser
    template_name = 'portal/admin_user_list.html'
    context_object_name = 'portal_users'
    paginate_by = 20

    def get_queryset(self):
        return super().get_queryset().filter(is_active=True).select_related('user', 'partner')


class PortalUserCreateView(ManagerRequiredMixin, View):
    def get(self, request):
        form = PortalUserForm()
        return render(request, 'portal/admin_user_form.html', {'form': form})

    def post(self, request):
        form = PortalUserForm(request.POST)
        if form.is_valid():
            obj = form.save(commit=False)
            obj.created_by = request.user
            obj.save()
            return redirect('portal:admin_user_list')
        return render(request, 'portal/admin_user_form.html', {'form': form})
