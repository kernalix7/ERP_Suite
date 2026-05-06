from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import Q, F
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse_lazy, reverse
from django.views.generic import ListView, CreateView, UpdateView, DetailView, TemplateView

from apps.core.mixins import ManagerRequiredMixin
from apps.module_manager.decorators import ModuleRequiredMixin
from .models import WikiSpace, WikiArticle, WikiCategory, ArticleRevision, ArticleComment, ArticleAttachment
from .forms import (
    WikiSpaceForm, WikiArticleForm, WikiCategoryForm,
    ArticleCommentForm, ArticleAttachmentForm, ArticleSearchForm,
)


# ---- WikiSpace ----

class WikiSpaceListView(ModuleRequiredMixin, ListView):
    required_module = 'wiki'
    model = WikiSpace
    template_name = 'wiki/space_list.html'
    context_object_name = 'spaces'
    paginate_by = 20

    def get_queryset(self):
        qs = WikiSpace.objects.filter(is_active=True).select_related('owner')
        if not self.request.user.is_staff:
            qs = qs.filter(is_public=True)
        return qs


class WikiSpaceCreateView(ModuleRequiredMixin, ManagerRequiredMixin, CreateView):
    required_module = 'wiki'
    model = WikiSpace
    form_class = WikiSpaceForm
    template_name = 'wiki/space_form.html'
    success_url = reverse_lazy('wiki:space_list')

    def form_valid(self, form):
        form.instance.created_by = self.request.user
        if not form.instance.owner_id:
            form.instance.owner = self.request.user
        messages.success(self.request, '위키 공간이 생성되었습니다.')
        return super().form_valid(form)


# ---- WikiCategory ----

class WikiCategoryTreeView(ModuleRequiredMixin, DetailView):
    """공간 내 카테고리 트리"""
    required_module = 'wiki'
    model = WikiSpace
    template_name = 'wiki/category_tree.html'
    context_object_name = 'space'
    slug_field = 'code'
    slug_url_kwarg = 'code'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['root_categories'] = self.object.categories.filter(
            is_active=True, parent__isnull=True,
        ).order_by('sort_order', 'name')
        return ctx


class WikiCategoryListView(ModuleRequiredMixin, ManagerRequiredMixin, ListView):
    required_module = 'wiki'
    model = WikiCategory
    template_name = 'wiki/category_list.html'
    context_object_name = 'categories'
    paginate_by = 20

    def get_queryset(self):
        qs = WikiCategory.objects.filter(is_active=True).select_related('space', 'parent').order_by('space', 'sort_order', 'name')
        space = self.request.GET.get('space')
        if space:
            qs = qs.filter(space_id=space)
        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['spaces'] = WikiSpace.objects.filter(is_active=True)
        return ctx


class WikiCategoryCreateView(ModuleRequiredMixin, ManagerRequiredMixin, CreateView):
    required_module = 'wiki'
    model = WikiCategory
    form_class = WikiCategoryForm
    template_name = 'wiki/category_form.html'
    success_url = reverse_lazy('wiki:category_list')

    def form_valid(self, form):
        form.instance.created_by = self.request.user
        messages.success(self.request, '카테고리가 등록되었습니다.')
        return super().form_valid(form)


# ---- WikiArticle ----

class WikiArticleListView(ModuleRequiredMixin, ListView):
    required_module = 'wiki'
    model = WikiArticle
    template_name = 'wiki/article_list.html'
    context_object_name = 'articles'
    paginate_by = 20

    def get_queryset(self):
        qs = WikiArticle.objects.filter(
            is_active=True, status=WikiArticle.Status.PUBLISHED,
        ).select_related('space', 'category', 'author')
        # 비공개 공간 필터
        if not self.request.user.is_staff:
            qs = qs.filter(space__is_public=True)
        space = self.request.GET.get('space')
        if space:
            qs = qs.filter(space_id=space)
        category = self.request.GET.get('category')
        if category:
            qs = qs.filter(category_id=category)
        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['spaces'] = WikiSpace.objects.filter(is_active=True, is_public=True)
        ctx['pinned'] = WikiArticle.objects.filter(
            is_active=True, status=WikiArticle.Status.PUBLISHED, is_pinned=True,
        ).select_related('space')[:5]
        return ctx


class WikiArticleDetailView(ModuleRequiredMixin, DetailView):
    required_module = 'wiki'
    model = WikiArticle
    template_name = 'wiki/article_detail.html'
    context_object_name = 'article'
    slug_field = 'slug'
    slug_url_kwarg = 'slug'

    def get(self, request, *args, **kwargs):
        response = super().get(request, *args, **kwargs)
        WikiArticle.objects.filter(pk=self.object.pk).update(view_count=F('view_count') + 1)
        return response

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['comments'] = self.object.comments.filter(
            is_active=True, parent__isnull=True,
        ).select_related('author').prefetch_related('replies__author')
        ctx['revisions'] = self.object.revisions.order_by('-revision_number')[:5]
        ctx['attachments'] = self.object.attachments.filter(is_active=True)
        ctx['comment_form'] = ArticleCommentForm()
        # 같은 공간/카테고리 관련 문서
        ctx['related_articles'] = WikiArticle.objects.filter(
            space=self.object.space,
            status=WikiArticle.Status.PUBLISHED,
            is_active=True,
        ).exclude(pk=self.object.pk).order_by('-updated_at')[:5]
        return ctx


class WikiArticleCreateView(ModuleRequiredMixin, CreateView):
    required_module = 'wiki'
    model = WikiArticle
    form_class = WikiArticleForm
    template_name = 'wiki/article_form.html'

    def get_initial(self):
        initial = super().get_initial()
        space_id = self.request.GET.get('space')
        if space_id:
            initial['space'] = space_id
        return initial

    def get_success_url(self):
        return reverse('wiki:article_detail', kwargs={'slug': self.object.slug})

    def form_valid(self, form):
        form.instance.author = self.request.user
        form.instance.created_by = self.request.user
        messages.success(self.request, '문서가 등록되었습니다.')
        return super().form_valid(form)


class WikiArticleUpdateView(ModuleRequiredMixin, UpdateView):
    required_module = 'wiki'
    model = WikiArticle
    form_class = WikiArticleForm
    template_name = 'wiki/article_form.html'
    slug_field = 'slug'
    slug_url_kwarg = 'slug'

    def get_queryset(self):
        qs = super().get_queryset()
        user = self.request.user
        if getattr(user, 'role', None) in ('admin', 'manager'):
            return qs
        return qs.filter(author=user)

    def get_success_url(self):
        return reverse('wiki:article_detail', kwargs={'slug': self.object.slug})

    def form_valid(self, form):
        # 개정 이력 저장 (수정 전 내용 스냅샷)
        old_content = WikiArticle.objects.get(pk=self.object.pk).content
        response = super().form_valid(form)
        last_rev = ArticleRevision.objects.filter(article=self.object).order_by('-revision_number').first()
        rev_num = (last_rev.revision_number + 1) if last_rev else 1
        ArticleRevision.objects.create(
            article=self.object,
            revision_number=rev_num,
            content=old_content,
            change_summary=self.request.POST.get('change_summary', ''),
            revised_by=self.request.user,
            created_by=self.request.user,
        )
        messages.success(self.request, '문서가 수정되었습니다.')
        return response


# ---- Article Search ----

class WikiArticleSearchView(ModuleRequiredMixin, ListView):
    required_module = 'wiki'
    model = WikiArticle
    template_name = 'wiki/article_search.html'
    context_object_name = 'articles'
    paginate_by = 20

    def get_queryset(self):
        qs = WikiArticle.objects.filter(
            is_active=True, status=WikiArticle.Status.PUBLISHED,
        ).select_related('space', 'category', 'author')
        if not self.request.user.is_staff:
            qs = qs.filter(space__is_public=True)

        q = self.request.GET.get('q', '').strip()
        if q:
            qs = qs.filter(Q(title__icontains=q) | Q(content__icontains=q))

        space = self.request.GET.get('space')
        if space:
            qs = qs.filter(space_id=space)

        tag = self.request.GET.get('tag', '').strip()
        if tag:
            qs = qs.filter(tags__contains=tag)

        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['form'] = ArticleSearchForm(self.request.GET or None)
        ctx['q'] = self.request.GET.get('q', '')
        return ctx


# ---- Revision History ----

class ArticleRevisionListView(ModuleRequiredMixin, DetailView):
    """문서 개정 이력 목록"""
    required_module = 'wiki'
    model = WikiArticle
    template_name = 'wiki/article_history.html'
    context_object_name = 'article'
    slug_field = 'slug'
    slug_url_kwarg = 'slug'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['revisions'] = self.object.revisions.order_by('-revision_number').select_related('revised_by')
        return ctx


class ArticleRevisionDetailView(ModuleRequiredMixin, DetailView):
    """특정 개정 버전 보기 (Diff)"""
    required_module = 'wiki'
    model = ArticleRevision
    template_name = 'wiki/revision_detail.html'
    context_object_name = 'revision'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['article'] = self.object.article
        # 이전 버전 비교
        prev = ArticleRevision.objects.filter(
            article=self.object.article,
            revision_number__lt=self.object.revision_number,
        ).order_by('-revision_number').first()
        ctx['prev_revision'] = prev
        return ctx


# ---- Recent Changes & Popular ----

class RecentChangesView(ModuleRequiredMixin, ListView):
    """최근 변경 문서"""
    required_module = 'wiki'
    model = WikiArticle
    template_name = 'wiki/recent_changes.html'
    context_object_name = 'articles'
    paginate_by = 30

    def get_queryset(self):
        qs = WikiArticle.objects.filter(
            is_active=True, status=WikiArticle.Status.PUBLISHED,
        ).select_related('space', 'author').order_by('-updated_at')
        if not self.request.user.is_staff:
            qs = qs.filter(space__is_public=True)
        return qs


class PopularArticlesView(ModuleRequiredMixin, ListView):
    """인기 문서 (조회수 기준)"""
    required_module = 'wiki'
    model = WikiArticle
    template_name = 'wiki/popular_articles.html'
    context_object_name = 'articles'
    paginate_by = 20

    def get_queryset(self):
        qs = WikiArticle.objects.filter(
            is_active=True, status=WikiArticle.Status.PUBLISHED,
        ).select_related('space', 'author').order_by('-view_count')
        if not self.request.user.is_staff:
            qs = qs.filter(space__is_public=True)
        return qs


class MyArticlesView(ModuleRequiredMixin, ListView):
    """내가 작성한 문서"""
    required_module = 'wiki'
    model = WikiArticle
    template_name = 'wiki/my_articles.html'
    context_object_name = 'articles'
    paginate_by = 20

    def get_queryset(self):
        return WikiArticle.objects.filter(
            author=self.request.user, is_active=True,
        ).select_related('space', 'category').order_by('-updated_at')


# ---- Comments ----

class ArticleCommentCreateView(ModuleRequiredMixin, CreateView):
    required_module = 'wiki'
    model = ArticleComment
    form_class = ArticleCommentForm

    def form_valid(self, form):
        article = get_object_or_404(WikiArticle, pk=self.kwargs['article_pk'])
        form.instance.article = article
        form.instance.author = self.request.user
        form.instance.created_by = self.request.user
        form.save()
        messages.success(self.request, '댓글이 등록되었습니다.')
        return redirect('wiki:article_detail', slug=article.slug)
