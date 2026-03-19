from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import PermissionDenied
from django.db.models import F, Q
from django.shortcuts import get_object_or_404
from django.urls import reverse, reverse_lazy
from django.views.generic import (
    ListView, CreateView, UpdateView, DeleteView, DetailView,
)

from .models import Board, Post, Comment
from .forms import PostForm, CommentForm


class BoardListView(LoginRequiredMixin, ListView):
    model = Board
    template_name = 'board/board_list.html'
    context_object_name = 'boards'

    def get_queryset(self):
        return Board.objects.filter(is_active=True)


class PostListView(LoginRequiredMixin, ListView):
    model = Post
    template_name = 'board/post_list.html'
    context_object_name = 'posts'
    paginate_by = 20

    def get_queryset(self):
        self.board = get_object_or_404(Board, slug=self.kwargs['slug'])
        qs = Post.objects.filter(board=self.board, is_active=True).select_related('author')
        q = self.request.GET.get('q')
        if q:
            qs = qs.filter(Q(title__icontains=q) | Q(content__icontains=q))
        return qs.order_by('-is_pinned', '-created_at')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['board'] = self.board
        return context


class PostDetailView(LoginRequiredMixin, DetailView):
    model = Post
    template_name = 'board/post_detail.html'
    context_object_name = 'post'

    def get_queryset(self):
        return Post.objects.select_related('board', 'author')

    def get_object(self, queryset=None):
        obj = super().get_object(queryset)
        # 조회수 증가
        Post.objects.filter(pk=obj.pk).update(view_count=F('view_count') + 1)
        obj.view_count += 1
        return obj

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['comments'] = (
            self.object.comments.filter(parent__isnull=True)
            .select_related('author')
            .prefetch_related('replies__author')
        )
        context['comment_form'] = CommentForm()
        return context


def _check_board_permission(board, user):
    """게시판 글쓰기 권한 확인"""
    level = board.permission_level
    if level == Board.PermissionLevel.ADMIN and user.role != 'admin':
        raise PermissionDenied('관리자만 글을 작성할 수 있습니다.')
    if level == Board.PermissionLevel.MANAGER and user.role not in ('admin', 'manager'):
        raise PermissionDenied('매니저 이상만 글을 작성할 수 있습니다.')


class PostCreateView(LoginRequiredMixin, CreateView):
    model = Post
    form_class = PostForm
    template_name = 'board/post_form.html'

    def dispatch(self, request, *args, **kwargs):
        self.board = get_object_or_404(Board, slug=kwargs['slug'])
        if request.user.is_authenticated:
            _check_board_permission(self.board, request.user)
        return super().dispatch(request, *args, **kwargs)

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['user'] = self.request.user
        return kwargs

    def get_initial(self):
        return {'board': self.board}

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['board'] = self.board
        return context

    def form_valid(self, form):
        form.instance.author = self.request.user
        form.instance.board = self.board
        form.instance.created_by = self.request.user
        return super().form_valid(form)

    def get_success_url(self):
        return reverse('board:post_detail', kwargs={'pk': self.object.pk})


class PostUpdateView(LoginRequiredMixin, UpdateView):
    model = Post
    form_class = PostForm
    template_name = 'board/post_form.html'

    def get_queryset(self):
        return Post.objects.select_related('board')

    def dispatch(self, request, *args, **kwargs):
        obj = self.get_object()
        if obj.author != request.user and request.user.role not in ('admin', 'manager'):
            raise PermissionDenied('본인 글만 수정할 수 있습니다.')
        return super().dispatch(request, *args, **kwargs)

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['user'] = self.request.user
        return kwargs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['board'] = self.object.board
        return context

    def get_success_url(self):
        return reverse('board:post_detail', kwargs={'pk': self.object.pk})


class PostDeleteView(LoginRequiredMixin, DeleteView):
    model = Post
    template_name = 'board/post_confirm_delete.html'

    def dispatch(self, request, *args, **kwargs):
        obj = self.get_object()
        if obj.author != request.user and request.user.role not in ('admin', 'manager'):
            raise PermissionDenied('본인 글만 삭제할 수 있습니다.')
        return super().dispatch(request, *args, **kwargs)

    def get_success_url(self):
        return reverse('board:post_list', kwargs={'slug': self.object.board.slug})

    def form_valid(self, form):
        self.object = self.get_object()
        self.object.soft_delete()
        return self.render_to_response(self.get_context_data())

    def delete(self, request, *args, **kwargs):
        """Soft delete instead of hard delete."""
        self.object = self.get_object()
        success_url = self.get_success_url()
        self.object.soft_delete()
        from django.http import HttpResponseRedirect
        return HttpResponseRedirect(success_url)


class CommentCreateView(LoginRequiredMixin, CreateView):
    model = Comment
    form_class = CommentForm
    http_method_names = ['post']

    def form_valid(self, form):
        post = get_object_or_404(Post, pk=self.kwargs['pk'])
        form.instance.post = post
        form.instance.author = self.request.user
        form.instance.created_by = self.request.user
        return super().form_valid(form)

    def get_success_url(self):
        return reverse('board:post_detail', kwargs={'pk': self.kwargs['pk']})

    def form_invalid(self, form):
        from django.http import HttpResponseRedirect
        return HttpResponseRedirect(
            reverse('board:post_detail', kwargs={'pk': self.kwargs['pk']})
        )
