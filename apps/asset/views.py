from django.contrib import messages
from django.db import transaction
from django.db.models import Sum, F
from django.urls import reverse_lazy
from django.views.generic import ListView, CreateView, UpdateView, DetailView, TemplateView, FormView

from apps.core.mixins import ManagerRequiredMixin
from .models import AssetCategory, FixedAsset, DepreciationRecord
from .forms import AssetCategoryForm, FixedAssetForm, AssetDisposalForm, DepreciationRunForm


# === 고정자산 ===

class AssetListView(ManagerRequiredMixin, ListView):
    model = FixedAsset
    template_name = 'asset/asset_list.html'
    context_object_name = 'assets'
    paginate_by = 20

    def get_queryset(self):
        qs = super().get_queryset().filter(
            is_active=True,
        ).select_related('category', 'department', 'responsible_person')

        q = self.request.GET.get('q')
        if q:
            qs = qs.filter(name__icontains=q)

        category = self.request.GET.get('category')
        if category:
            qs = qs.filter(category_id=category)

        status = self.request.GET.get('status')
        if status:
            qs = qs.filter(status=status)

        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['categories'] = AssetCategory.objects.filter(is_active=True)
        ctx['status_choices'] = FixedAsset.Status.choices
        return ctx


class AssetCreateView(ManagerRequiredMixin, CreateView):
    model = FixedAsset
    form_class = FixedAssetForm
    template_name = 'asset/asset_form.html'
    success_url = reverse_lazy('asset:asset_list')

    def form_valid(self, form):
        form.instance.created_by = self.request.user
        messages.success(self.request, '고정자산이 등록되었습니다.')
        return super().form_valid(form)


class AssetDetailView(ManagerRequiredMixin, DetailView):
    model = FixedAsset
    template_name = 'asset/asset_detail.html'
    context_object_name = 'asset'
    slug_field = 'asset_number'
    slug_url_kwarg = 'slug'

    def get_queryset(self):
        return super().get_queryset().select_related(
            'category', 'department', 'responsible_person',
        )

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['depreciation_records'] = self.object.depreciation_records.all()[:24]
        return ctx


class AssetUpdateView(ManagerRequiredMixin, UpdateView):
    model = FixedAsset
    form_class = FixedAssetForm
    template_name = 'asset/asset_form.html'
    slug_field = 'asset_number'
    slug_url_kwarg = 'slug'
    success_url = reverse_lazy('asset:asset_list')

    def form_valid(self, form):
        messages.success(self.request, '고정자산이 수정되었습니다.')
        return super().form_valid(form)


class AssetDisposalView(ManagerRequiredMixin, UpdateView):
    model = FixedAsset
    form_class = AssetDisposalForm
    template_name = 'asset/asset_form.html'
    slug_field = 'asset_number'
    slug_url_kwarg = 'slug'
    success_url = reverse_lazy('asset:asset_list')

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['form_title'] = '자산 처분'
        return ctx

    def form_valid(self, form):
        messages.success(self.request, '자산 처분이 처리되었습니다.')
        return super().form_valid(form)


class AssetDepreciationRunView(ManagerRequiredMixin, FormView):
    form_class = DepreciationRunForm
    template_name = 'asset/depreciation_run.html'
    success_url = reverse_lazy('asset:asset_list')

    def form_valid(self, form):
        year = form.cleaned_data['year']
        month = form.cleaned_data['month']

        assets = FixedAsset.objects.filter(
            is_active=True,
            status=FixedAsset.Status.ACTIVE,
        )

        created_count = 0
        skipped_count = 0

        with transaction.atomic():
            for asset in assets:
                # 이미 해당 기간 감가상각 내역이 있으면 건너뜀
                if DepreciationRecord.objects.filter(asset=asset, year=year, month=month).exists():
                    skipped_count += 1
                    continue

                # 완전 상각된 자산은 건너뜀
                if asset.is_fully_depreciated:
                    skipped_count += 1
                    continue

                dep_amount = asset.monthly_depreciation
                if dep_amount <= 0:
                    skipped_count += 1
                    continue

                # 잔존가치 이하로 내려가지 않도록 조정
                max_depreciable = asset.book_value - asset.residual_value
                if dep_amount > max_depreciable:
                    dep_amount = int(max_depreciable)

                if dep_amount <= 0:
                    skipped_count += 1
                    continue

                new_accumulated = asset.accumulated_depreciation + dep_amount
                new_book_value = asset.acquisition_cost - new_accumulated

                DepreciationRecord.objects.create(
                    asset=asset,
                    year=year,
                    month=month,
                    depreciation_amount=dep_amount,
                    accumulated_amount=new_accumulated,
                    book_value_after=new_book_value,
                    created_by=self.request.user,
                )

                # F() 표현식으로 원자적 업데이트
                FixedAsset.all_objects.filter(pk=asset.pk).update(
                    accumulated_depreciation=F('accumulated_depreciation') + dep_amount,
                    book_value=F('book_value') - dep_amount,
                )

                created_count += 1

        messages.success(
            self.request,
            f'{year}년 {month}월 감가상각 완료: {created_count}건 처리, {skipped_count}건 건너뜀',
        )
        return super().form_valid(form)


# === 자산 분류 ===

class AssetCategoryListView(ManagerRequiredMixin, ListView):
    model = AssetCategory
    template_name = 'asset/category_list.html'
    context_object_name = 'categories'
    paginate_by = 20

    def get_queryset(self):
        return super().get_queryset().filter(is_active=True)


class AssetCategoryCreateView(ManagerRequiredMixin, CreateView):
    model = AssetCategory
    form_class = AssetCategoryForm
    template_name = 'asset/category_form.html'
    success_url = reverse_lazy('asset:category_list')

    def form_valid(self, form):
        form.instance.created_by = self.request.user
        messages.success(self.request, '자산 분류가 등록되었습니다.')
        return super().form_valid(form)


# === 자산 현황 요약 ===

class AssetSummaryView(ManagerRequiredMixin, TemplateView):
    template_name = 'asset/summary.html'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)

        # 분류별 현황
        category_summary = AssetCategory.objects.filter(
            is_active=True,
        ).prefetch_related('assets').all()

        summary_data = []
        total_acquisition = 0
        total_accumulated = 0
        total_book_value = 0

        for cat in category_summary:
            active_assets = cat.assets.filter(is_active=True, status=FixedAsset.Status.ACTIVE)
            agg = active_assets.aggregate(
                acq=Sum('acquisition_cost'),
                acc=Sum('accumulated_depreciation'),
                bv=Sum('book_value'),
            )
            acq = agg['acq'] or 0
            acc = agg['acc'] or 0
            bv = agg['bv'] or 0
            count = active_assets.count()

            if count > 0:
                summary_data.append({
                    'category': cat,
                    'count': count,
                    'acquisition_cost': acq,
                    'accumulated_depreciation': acc,
                    'book_value': bv,
                })
                total_acquisition += acq
                total_accumulated += acc
                total_book_value += bv

        ctx['summary_data'] = summary_data
        ctx['total_acquisition'] = total_acquisition
        ctx['total_accumulated'] = total_accumulated
        ctx['total_book_value'] = total_book_value

        # 상태별 자산 수
        ctx['active_count'] = FixedAsset.objects.filter(is_active=True, status=FixedAsset.Status.ACTIVE).count()
        ctx['disposed_count'] = FixedAsset.objects.filter(is_active=True, status=FixedAsset.Status.DISPOSED).count()
        ctx['scrapped_count'] = FixedAsset.objects.filter(is_active=True, status=FixedAsset.Status.SCRAPPED).count()

        return ctx
