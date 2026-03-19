import pytest
from django.contrib.auth import get_user_model
from playwright.sync_api import Page, expect

from apps.board.models import Board, Post, Comment


@pytest.mark.django_db
class TestBoardWorkflow:
    """게시판 워크플로우 E2E 테스트"""

    def test_board_list_loads(self, logged_in_page: Page, live_url):
        """게시판 목록 페이지가 정상적으로 로드되는지 확인"""
        page = logged_in_page
        page.goto(f'{live_url}/board/')
        page.wait_for_load_state('networkidle')

        page_content = page.content()
        assert '게시판' in page_content

    def test_create_post(self, logged_in_page: Page, live_url):
        """게시글 작성 워크플로우 테스트"""
        page = logged_in_page

        # 사전 데이터: 게시판 생성
        board = Board.objects.create(
            name='공지사항',
            slug='notice-e2e',
            is_notice=True,
        )

        # 글 작성 페이지로 이동
        page.goto(f'{live_url}/board/{board.slug}/create/')
        page.wait_for_load_state('networkidle')

        # 폼 필드 채우기
        page.fill('input[name="title"]', 'E2E 테스트 공지')
        page.fill('textarea[name="content"]', 'E2E 테스트 내용입니다.')

        # 저장 버튼 클릭
        page.click('button[type="submit"]')
        page.wait_for_load_state('networkidle')

        # DB에서 게시글 확인
        post = Post.objects.get(title='E2E 테스트 공지')
        assert post.board == board
        assert post.content == 'E2E 테스트 내용입니다.'

    def test_view_post_detail(self, logged_in_page: Page, live_url, admin_user):
        """게시글 상세 페이지 확인"""
        page = logged_in_page

        # 사전 데이터 생성
        board = Board.objects.create(
            name='자유게시판',
            slug='free-e2e',
        )
        post = Post.objects.create(
            board=board,
            title='상세보기 테스트',
            content='상세보기 테스트 내용',
            author=admin_user,
        )

        # 게시글 상세 페이지로 이동
        page.goto(f'{live_url}/board/{board.slug}/{post.pk}/')
        page.wait_for_load_state('networkidle')

        # 제목과 내용 확인
        page_content = page.content()
        assert '상세보기 테스트' in page_content
        assert '상세보기 테스트 내용' in page_content

    def test_create_comment(self, logged_in_page: Page, live_url, admin_user):
        """댓글 작성 워크플로우 테스트"""
        page = logged_in_page

        # 사전 데이터 생성
        board = Board.objects.create(
            name='댓글테스트 게시판',
            slug='comment-e2e',
        )
        post = Post.objects.create(
            board=board,
            title='댓글 테스트 게시글',
            content='댓글 테스트용 게시글입니다.',
            author=admin_user,
        )

        # 게시글 상세 페이지로 이동
        page.goto(f'{live_url}/board/{board.slug}/{post.pk}/')
        page.wait_for_load_state('networkidle')

        # 댓글 작성
        page.fill('textarea[name="content"]', 'E2E 테스트 댓글')
        page.click('button[type="submit"]')
        page.wait_for_load_state('networkidle')

        # 댓글이 페이지에 표시되는지 확인
        page_content = page.content()
        assert 'E2E 테스트 댓글' in page_content

        # DB에서 댓글 확인
        comment = Comment.objects.get(post=post)
        assert comment.content == 'E2E 테스트 댓글'
