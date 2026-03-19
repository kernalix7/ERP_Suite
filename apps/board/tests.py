from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth import get_user_model

from apps.board.models import Board, Post, Comment

User = get_user_model()


class BoardModelTest(TestCase):
    """게시판 모델 테스트"""

    def setUp(self):
        self.user = User.objects.create_user(
            username='boarduser', password='testpass123',
            role='staff', name='게시판유저',
        )

    def test_board_creation(self):
        """게시판 생성"""
        board = Board.objects.create(
            name='공지사항', slug='notice',
            is_notice=True, created_by=self.user,
        )
        self.assertEqual(board.name, '공지사항')
        self.assertEqual(board.slug, 'notice')
        self.assertTrue(board.is_notice)

    def test_board_str(self):
        """게시판 문자열 표현"""
        board = Board.objects.create(
            name='자유게시판', slug='free', created_by=self.user,
        )
        self.assertEqual(str(board), '자유게시판')

    def test_board_unique_slug(self):
        """게시판 슬러그 중복 불가"""
        Board.objects.create(
            name='게시판1', slug='unique-slug', created_by=self.user,
        )
        from django.db import IntegrityError
        with self.assertRaises(IntegrityError):
            Board.objects.create(
                name='게시판2', slug='unique-slug', created_by=self.user,
            )

    def test_permission_level_choices(self):
        """글쓰기 권한 레벨 선택지"""
        choices = dict(Board.PermissionLevel.choices)
        self.assertIn('anyone', choices)
        self.assertIn('staff', choices)
        self.assertIn('manager', choices)
        self.assertIn('admin', choices)

    def test_default_permission_level(self):
        """기본 글쓰기 권한은 staff"""
        board = Board.objects.create(
            name='기본게시판', slug='default', created_by=self.user,
        )
        self.assertEqual(board.permission_level, Board.PermissionLevel.STAFF)

    def test_board_ordering(self):
        """게시판은 이름순 정렬"""
        Board.objects.create(name='BBB', slug='bbb', created_by=self.user)
        Board.objects.create(name='AAA', slug='aaa', created_by=self.user)
        boards = list(Board.objects.all())
        self.assertEqual(boards[0].name, 'AAA')
        self.assertEqual(boards[1].name, 'BBB')

    def test_board_soft_delete(self):
        """게시판 soft delete"""
        board = Board.objects.create(
            name='삭제테스트', slug='del-test', created_by=self.user,
        )
        board.soft_delete()
        self.assertFalse(Board.objects.filter(pk=board.pk).exists())
        self.assertTrue(Board.all_objects.filter(pk=board.pk).exists())


class PostModelTest(TestCase):
    """게시글 모델 테스트"""

    def setUp(self):
        self.user = User.objects.create_user(
            username='postuser', password='testpass123',
            role='staff', name='게시글유저',
        )
        self.board = Board.objects.create(
            name='테스트게시판', slug='test-board', created_by=self.user,
        )

    def test_post_creation(self):
        """게시글 생성"""
        post = Post.objects.create(
            board=self.board,
            title='테스트 게시글',
            content='게시글 내용입니다.',
            author=self.user,
            created_by=self.user,
        )
        self.assertEqual(post.title, '테스트 게시글')
        self.assertEqual(post.board, self.board)
        self.assertEqual(post.author, self.user)

    def test_post_str(self):
        """게시글 문자열 표현"""
        post = Post.objects.create(
            board=self.board,
            title='문자열 테스트',
            content='내용',
            author=self.user,
            created_by=self.user,
        )
        self.assertEqual(str(post), '문자열 테스트')

    def test_post_default_values(self):
        """게시글 기본값 확인"""
        post = Post.objects.create(
            board=self.board,
            title='기본값 테스트',
            content='내용',
            author=self.user,
            created_by=self.user,
        )
        self.assertFalse(post.is_pinned)
        self.assertEqual(post.view_count, 0)

    def test_post_pinned(self):
        """게시글 상단 고정"""
        post = Post.objects.create(
            board=self.board,
            title='고정 게시글',
            content='내용',
            author=self.user,
            is_pinned=True,
            created_by=self.user,
        )
        self.assertTrue(post.is_pinned)

    def test_post_ordering(self):
        """게시글은 고정 우선, 최신순 정렬"""
        Post.objects.create(
            board=self.board, title='일반글', content='내용',
            author=self.user, created_by=self.user,
        )
        p2 = Post.objects.create(
            board=self.board, title='고정글', content='내용',
            author=self.user, is_pinned=True, created_by=self.user,
        )
        posts = list(Post.objects.all())
        # 고정글이 먼저 (is_pinned descending)
        self.assertEqual(posts[0], p2)

    def test_post_view_count_increment(self):
        """조회수 증가"""
        post = Post.objects.create(
            board=self.board, title='조회수 테스트', content='내용',
            author=self.user, created_by=self.user,
        )
        post.view_count += 1
        post.save()
        post.refresh_from_db()
        self.assertEqual(post.view_count, 1)

    def test_post_soft_delete(self):
        """게시글 soft delete"""
        post = Post.objects.create(
            board=self.board, title='삭제테스트', content='내용',
            author=self.user, created_by=self.user,
        )
        post.soft_delete()
        self.assertFalse(Post.objects.filter(pk=post.pk).exists())
        self.assertTrue(Post.all_objects.filter(pk=post.pk).exists())


class CommentModelTest(TestCase):
    """댓글 모델 테스트"""

    def setUp(self):
        self.user = User.objects.create_user(
            username='commentuser', password='testpass123',
            role='staff', name='댓글유저',
        )
        self.board = Board.objects.create(
            name='댓글게시판', slug='comment-board', created_by=self.user,
        )
        self.post = Post.objects.create(
            board=self.board, title='댓글 테스트 게시글', content='내용',
            author=self.user, created_by=self.user,
        )

    def test_comment_creation(self):
        """댓글 생성"""
        comment = Comment.objects.create(
            post=self.post,
            content='댓글 내용입니다.',
            author=self.user,
            created_by=self.user,
        )
        self.assertEqual(comment.content, '댓글 내용입니다.')
        self.assertEqual(comment.post, self.post)

    def test_comment_str(self):
        """댓글 문자열 표현"""
        comment = Comment.objects.create(
            post=self.post,
            content='긴 댓글 내용 테스트 문자열 표현 확인',
            author=self.user,
            created_by=self.user,
        )
        result = str(comment)
        self.assertIn('댓글유저', result)

    def test_nested_comment(self):
        """대댓글 (중첩 댓글)"""
        parent = Comment.objects.create(
            post=self.post,
            content='부모 댓글',
            author=self.user,
            created_by=self.user,
        )
        reply = Comment.objects.create(
            post=self.post,
            content='자식 댓글',
            author=self.user,
            parent=parent,
            created_by=self.user,
        )
        self.assertEqual(reply.parent, parent)
        self.assertIn(reply, parent.replies.all())

    def test_comment_ordering(self):
        """댓글은 생성일순 정렬"""
        c1 = Comment.objects.create(
            post=self.post, content='첫번째', author=self.user,
            created_by=self.user,
        )
        c2 = Comment.objects.create(
            post=self.post, content='두번째', author=self.user,
            created_by=self.user,
        )
        comments = list(Comment.objects.all())
        self.assertEqual(comments[0], c1)
        self.assertEqual(comments[1], c2)

    def test_comment_cascade_delete_with_post(self):
        """게시글 삭제 시 댓글도 삭제 (CASCADE)"""
        Comment.objects.create(
            post=self.post, content='삭제될 댓글',
            author=self.user, created_by=self.user,
        )
        self.assertEqual(Comment.objects.count(), 1)
        self.post.delete()
        self.assertEqual(Comment.objects.count(), 0)

    def test_nested_comment_cascade(self):
        """부모 댓글 삭제 시 자식 댓글도 삭제"""
        parent = Comment.objects.create(
            post=self.post, content='부모',
            author=self.user, created_by=self.user,
        )
        Comment.objects.create(
            post=self.post, content='자식',
            author=self.user, parent=parent,
            created_by=self.user,
        )
        self.assertEqual(Comment.objects.count(), 2)
        parent.delete()
        self.assertEqual(Comment.objects.count(), 0)


class BoardViewTest(TestCase):
    """게시판 뷰 테스트"""

    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(
            username='boardviewuser', password='testpass123',
            role='staff', name='뷰유저',
        )
        self.board = Board.objects.create(
            name='뷰테스트', slug='view-test', created_by=self.user,
        )

    def test_board_list_requires_login(self):
        """게시판 목록 비로그인 접근 불가"""
        response = self.client.get(reverse('board:board_list'))
        self.assertEqual(response.status_code, 302)

    def test_board_list_accessible(self):
        """게시판 목록 로그인 후 접근"""
        self.client.force_login(User.objects.get(username='boardviewuser'))
        response = self.client.get(reverse('board:board_list'))
        self.assertEqual(response.status_code, 200)

    def test_post_list_accessible(self):
        """게시글 목록 접근"""
        self.client.force_login(User.objects.get(username='boardviewuser'))
        response = self.client.get(
            reverse('board:post_list', kwargs={'slug': self.board.slug}),
        )
        self.assertEqual(response.status_code, 200)

    def test_post_detail_accessible(self):
        """게시글 상세 접근"""
        self.client.force_login(User.objects.get(username='boardviewuser'))
        post = Post.objects.create(
            board=self.board, title='상세보기 테스트', content='내용',
            author=self.user, created_by=self.user,
        )
        response = self.client.get(
            reverse('board:post_detail', kwargs={'pk': post.pk}),
        )
        self.assertEqual(response.status_code, 200)

    def test_post_create_form(self):
        """게시글 작성 폼 접근"""
        self.client.force_login(User.objects.get(username='boardviewuser'))
        response = self.client.get(
            reverse('board:post_create', kwargs={'slug': self.board.slug}),
        )
        self.assertEqual(response.status_code, 200)
