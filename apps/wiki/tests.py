from django.test import TestCase, Client
from django.contrib.auth import get_user_model
from django.urls import reverse
from .models import WikiSpace, WikiCategory, WikiArticle, ArticleRevision, ArticleComment

User = get_user_model()


class WikiSpaceTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='wikiuser', password='pass')

    def test_space_creation(self):
        space = WikiSpace.objects.create(
            name='개발팀 위키', code='DEV', owner=self.user, created_by=self.user,
        )
        self.assertEqual(str(space), '[DEV] 개발팀 위키')

    def test_space_default_public(self):
        space = WikiSpace.objects.create(name='공개위키', code='PUB', created_by=self.user)
        self.assertTrue(space.is_public)


class WikiCategoryTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='catuser', password='pass')
        self.space = WikiSpace.objects.create(name='테스트 공간', code='TST', created_by=self.user)

    def test_category_creation(self):
        cat = WikiCategory.objects.create(
            space=self.space, name='기술문서', slug='tech', created_by=self.user,
        )
        self.assertEqual(str(cat), 'TST / 기술문서')

    def test_category_hierarchy(self):
        parent = WikiCategory.objects.create(
            space=self.space, name='부모', slug='parent', created_by=self.user,
        )
        child = WikiCategory.objects.create(
            space=self.space, name='자식', slug='child',
            parent=parent, created_by=self.user,
        )
        self.assertEqual(child.parent, parent)


class WikiArticleTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='articleuser', password='pass')
        self.space = WikiSpace.objects.create(name='테스트 공간', code='ART', created_by=self.user)

    def test_article_auto_number(self):
        article = WikiArticle.objects.create(
            space=self.space, title='Django 소개', slug='django-intro',
            author=self.user, content='본문입니다.', created_by=self.user,
        )
        self.assertTrue(article.article_number.startswith('WIKI'))

    def test_article_default_status(self):
        article = WikiArticle.objects.create(
            space=self.space, title='초안 문서', slug='draft-doc',
            author=self.user, content='내용', created_by=self.user,
        )
        self.assertEqual(article.status, WikiArticle.Status.DRAFT)

    def test_article_tags_json(self):
        article = WikiArticle.objects.create(
            space=self.space, title='태그 문서', slug='tag-doc',
            author=self.user, content='내용', tags=['python', 'django'],
            created_by=self.user,
        )
        self.assertIn('python', article.tags)

    def test_article_str(self):
        article = WikiArticle.objects.create(
            space=self.space, title='STR 테스트', slug='str-test',
            author=self.user, content='내용', created_by=self.user,
        )
        self.assertIn('WIKI', str(article))
        self.assertIn('STR 테스트', str(article))


class ArticleRevisionTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='revuser', password='pass')
        self.space = WikiSpace.objects.create(name='개정 공간', code='REV', created_by=self.user)
        self.article = WikiArticle.objects.create(
            space=self.space, title='개정 문서', slug='rev-doc',
            author=self.user, content='원본 내용', created_by=self.user,
        )

    def test_revision_creation(self):
        rev = ArticleRevision.objects.create(
            article=self.article, revision_number=1,
            content='원본 내용', change_summary='초기 등록',
            revised_by=self.user, created_by=self.user,
        )
        self.assertEqual(str(rev), '개정 문서 v1')

    def test_revision_unique_per_article(self):
        ArticleRevision.objects.create(
            article=self.article, revision_number=1,
            content='v1', revised_by=self.user, created_by=self.user,
        )
        with self.assertRaises(Exception):
            ArticleRevision.objects.create(
                article=self.article, revision_number=1,
                content='중복', revised_by=self.user, created_by=self.user,
            )


class WikiViewTest(TestCase):
    def setUp(self):
        self.client = Client()
        self.staff_user = User.objects.create_user(
            username='wiki_staff', password='pass', role='staff',
        )
        self.manager_user = User.objects.create_user(
            username='wiki_manager', password='pass', role='manager',
        )

    def test_space_list_requires_login(self):
        response = self.client.get(reverse('wiki:space_list'))
        self.assertIn(response.status_code, [302, 403])

    def test_space_create_requires_manager(self):
        self.client.force_login(self.staff_user)
        response = self.client.get(reverse('wiki:space_create'))
        self.assertEqual(response.status_code, 403)

    def test_space_create_unauthenticated_redirects(self):
        response = self.client.get(reverse('wiki:space_create'))
        self.assertEqual(response.status_code, 302)

    def test_article_list_requires_login(self):
        response = self.client.get(reverse('wiki:article_list'))
        self.assertIn(response.status_code, [302, 403])

    def test_category_create_requires_manager(self):
        self.client.force_login(self.staff_user)
        response = self.client.get(reverse('wiki:category_create'))
        self.assertEqual(response.status_code, 403)
