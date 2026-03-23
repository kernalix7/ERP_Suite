# ERP Suite 개발자 가이드

## 1. 프로젝트 구조

```
ERP_Suite/
├── apps/                    # Django 앱 모음
│   ├── core/                # 공통 기능
│   │   ├── models.py        # BaseModel (추상 모델)
│   │   ├── mixins.py        # RBAC 믹스인 (Staff/Manager/Admin)
│   │   ├── views.py         # 대시보드 뷰
│   │   ├── utils.py         # 공통 유틸리티
│   │   ├── excel.py         # Excel 내보내기 (openpyxl)
│   │   ├── backup.py        # 백업/복원
│   │   ├── notification.py  # 알림 모델
│   │   └── urls.py          # 대시보드, 백업 URL
│   ├── accounts/            # 인증/사용자 관리
│   ├── inventory/           # 재고관리
│   ├── production/          # 생산관리
│   ├── sales/               # 판매관리
│   ├── service/             # AS관리
│   ├── accounting/          # 회계관리
│   ├── investment/          # 투자관리
│   ├── purchase/            # 구매관리
│   ├── marketplace/         # 외부 스토어 연동 (네이버/쿠팡)
│   ├── inquiry/             # 문의관리
│   ├── warranty/            # 정품등록
│   ├── hr/                  # 인사관리
│   ├── attendance/          # 근태관리
│   ├── board/               # 게시판 (공지/자유)
│   ├── calendar_app/        # 일정관리
│   ├── messenger/           # 사내 메신저
│   ├── ad/                  # Active Directory 연동
│   ├── advertising/         # 광고관리
│   ├── approval/            # 결재/품의
│   ├── asset/               # 고정자산관리
│   └── api/                 # REST API
├── config/
│   ├── settings/
│   │   ├── __init__.py      # 환경별 설정 로드
│   │   ├── base.py          # 공통 설정 (비공개)
│   │   ├── development.py   # 개발 환경 설정
│   │   └── production.py    # 운영 환경 설정
│   └── wsgi.py              # WSGI 엔트리포인트
├── templates/               # 전역 템플릿
│   ├── base.html            # 기본 레이아웃 (사이드바, 헤더)
│   ├── 403.html / 404.html / 500.html  # 에러 페이지
│   └── {앱명}/              # 앱별 템플릿 폴더
├── static/                  # 정적 파일
├── locale/                  # i18n 번역 파일
├── requirements/            # 의존성
│   ├── base.txt             # 핵심 의존성
│   ├── dev.txt              # 개발 의존성
│   ├── prod.txt             # 운영 의존성
│   └── test.txt             # 테스트 의존성
├── local/                   # 로컬 설정 (.env 등, Git 미추적)
├── docker-compose.yml
├── Dockerfile
└── manage.py
```

## 2. 새 앱 추가 방법

### 2.1 앱 생성

```bash
cd apps
python ../manage.py startapp myapp
```

### 2.2 앱 설정

`apps/myapp/apps.py`:
```python
from django.apps import AppConfig

class MyappConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.myapp'
    verbose_name = '내앱이름'

    def ready(self):
        import apps.myapp.signals  # noqa: F401  (시그널이 있는 경우)
```

### 2.3 설정에 등록

`config/settings/base.py`의 `INSTALLED_APPS`에 추가:
```python
INSTALLED_APPS = [
    ...
    'apps.myapp',
]
```

### 2.4 URL 등록

`config/urls.py`에 추가:
```python
urlpatterns = [
    ...
    path('myapp/', include('apps.myapp.urls')),
]
```

### 2.5 마이그레이션

```bash
python manage.py makemigrations myapp
python manage.py migrate
```

## 3. 모델 작성 규칙

### 3.1 BaseModel 상속

모든 모델은 `apps.core.models.BaseModel`을 상속합니다.

```python
from apps.core.models import BaseModel
from simple_history.models import HistoricalRecords

class MyModel(BaseModel):
    name = models.CharField('이름', max_length=100)
    history = HistoricalRecords()

    class Meta:
        verbose_name = '내모델'
        verbose_name_plural = '내모델'
        ordering = ['-created_at']

    def __str__(self):
        return self.name
```

**BaseModel이 제공하는 필드:**
| 필드 | 타입 | 설명 |
|------|------|------|
| `created_at` | DateTimeField | 생성일 (자동) |
| `updated_at` | DateTimeField | 수정일 (자동) |
| `created_by` | ForeignKey(User) | 생성자 |
| `is_active` | BooleanField | 활성 여부 (소프트 삭제용) |
| `notes` | TextField | 비고 |

**매니저:**
- `objects`: 활성 레코드만 조회 (`is_active=True`)
- `all_objects`: 전체 레코드 조회

### 3.2 verbose_name 필수

모든 필드에 한글 `verbose_name`을 첫 번째 인자로 지정합니다:
```python
name = models.CharField('제품명', max_length=200)  # O
name = models.CharField(max_length=200)             # X
```

### 3.3 TextChoices 사용

선택 필드는 `models.TextChoices`를 사용합니다:
```python
class Status(models.TextChoices):
    DRAFT = 'DRAFT', '임시'
    CONFIRMED = 'CONFIRMED', '확정'
    CANCELLED = 'CANCELLED', '취소'

status = models.CharField('상태', max_length=10, choices=Status.choices, default=Status.DRAFT)
```

### 3.4 HistoricalRecords

변경 이력이 필요한 모델에 `simple_history`를 적용합니다:
```python
from simple_history.models import HistoricalRecords

class MyModel(BaseModel):
    ...
    history = HistoricalRecords()
```

## 4. 뷰 작성 규칙

### 4.1 RBAC 믹스인

`apps.core.mixins`에서 적절한 믹스인을 상속합니다:

| 믹스인 | 접근 권한 |
|--------|----------|
| `StaffRequiredMixin` | 모든 로그인 사용자 |
| `ManagerRequiredMixin` | 매니저, 관리자 |
| `AdminRequiredMixin` | 관리자만 |

```python
from apps.core.mixins import StaffRequiredMixin

class MyListView(StaffRequiredMixin, ListView):
    model = MyModel
    template_name = 'myapp/mymodel_list.html'
    context_object_name = 'items'
    paginate_by = 20
```

### 4.2 created_by 자동 설정

CreateView에서 `form_valid`를 오버라이드하여 `created_by`를 설정합니다:

```python
class MyCreateView(StaffRequiredMixin, CreateView):
    model = MyModel
    form_class = MyForm
    template_name = 'myapp/mymodel_form.html'
    success_url = reverse_lazy('myapp:mymodel_list')

    def form_valid(self, form):
        form.instance.created_by = self.request.user
        return super().form_valid(form)
```

### 4.3 성공 메시지

`django.contrib.messages`를 사용하여 사용자에게 피드백을 제공합니다:

```python
from django.contrib import messages

def form_valid(self, form):
    form.instance.created_by = self.request.user
    messages.success(self.request, '등록이 완료되었습니다.')
    return super().form_valid(form)
```

## 5. 폼 작성 규칙

### 5.1 기본 패턴

```python
from django import forms
from .models import MyModel

class MyForm(forms.ModelForm):
    class Meta:
        model = MyModel
        fields = ['name', 'description', 'status']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-input'}),
            'description': forms.Textarea(attrs={'class': 'form-input', 'rows': 3}),
            'status': forms.Select(attrs={'class': 'form-input'}),
        }
```

### 5.2 CSS 클래스

Tailwind CSS 기반 `form-input` 클래스를 사용합니다. `base.html`에 정의되어 있습니다:
```css
.form-input {
    @apply w-full px-3 py-2 border border-gray-300 rounded-lg
           focus:ring-2 focus:ring-blue-500 focus:border-blue-500 text-sm;
}
```

### 5.3 날짜 필드

```python
'date_field': forms.DateInput(attrs={'class': 'form-input', 'type': 'date'}),
```

## 6. 시그널 작성 규칙

### 6.1 F() 표현식 사용

재고 등 수량 변경 시 레이스 컨디션을 방지하기 위해 반드시 `F()` 표현식을 사용합니다:

```python
from django.db.models import F
from django.db import transaction
from django.db.models.signals import post_save
from django.dispatch import receiver

@receiver(post_save, sender=StockMovement)
def update_stock_on_save(sender, instance, created, **kwargs):
    if not created:
        return
    with transaction.atomic():
        Product.objects.filter(pk=instance.product_id).update(
            current_stock=F('current_stock') + instance.quantity
        )
```

### 6.2 transaction.atomic 필수

여러 모델을 동시에 변경하는 시그널은 반드시 `transaction.atomic()`으로 감싸서 데이터 정합성을 보장합니다.

### 6.3 앱 초기화 시 시그널 로드

`apps.py`의 `ready()` 메서드에서 시그널 모듈을 import합니다:
```python
def ready(self):
    import apps.myapp.signals  # noqa: F401
```

## 7. 템플릿 작성 규칙

### 7.1 base.html 상속

모든 템플릿은 `base.html`을 상속합니다:

```html
{% extends "base.html" %}

{% block title %}페이지 제목 - ERP Suite{% endblock %}
{% block page_title %}페이지 제목{% endblock %}

{% block header_actions %}
<!-- 우측 상단 액션 버튼 -->
{% endblock %}

{% block content %}
<!-- 페이지 본문 -->
{% endblock %}
```

### 7.2 사용 가능한 블록

| 블록 | 용도 |
|------|------|
| `title` | HTML `<title>` 태그 |
| `page_title` | 상단 헤더 영역 제목 |
| `header_actions` | 상단 우측 액션 버튼 영역 |
| `content` | 메인 콘텐츠 영역 |
| `public_content` | 비로그인 사용자용 콘텐츠 |

### 7.3 목록 페이지 표준 구조

```html
{% block content %}
<div class="bg-white rounded-xl shadow-sm border border-gray-200">
    <!-- 필터 영역 -->
    <div class="p-4 border-b border-gray-200">
        <form method="get" class="flex flex-col sm:flex-row gap-3">
            ...
        </form>
    </div>

    <!-- 테이블 -->
    <div class="overflow-x-auto">
        <table class="w-full text-sm text-left">
            <thead class="bg-gray-50 text-gray-600 uppercase text-xs tracking-wider">
                ...
            </thead>
            <tbody class="divide-y divide-gray-100">
                {% for item in items %}
                <tr class="hover:bg-gray-50 transition-colors">...</tr>
                {% empty %}
                <tr><td colspan="N" class="px-6 py-12 text-center text-gray-400">...</td></tr>
                {% endfor %}
            </tbody>
        </table>
    </div>

    <!-- 페이지네이션 -->
    {% if is_paginated %}
    <div class="px-6 py-4 border-t border-gray-200 flex items-center justify-between">
        ...
    </div>
    {% endif %}
</div>
{% endblock %}
```

### 7.4 폼 페이지 표준 구조

```html
{% block content %}
<div class="max-w-2xl mx-auto">
    <div class="bg-white rounded-xl shadow-sm border border-gray-200 p-6">
        <form method="post" novalidate>
            {% csrf_token %}
            <!-- 비필드 에러 -->
            {% if form.non_field_errors %}...{% endif %}

            <!-- 필드 반복 -->
            <div class="space-y-5">
                {% for field in form %}
                <div>
                    <label>{{ field.label }}</label>
                    {{ field }}
                    {% if field.errors %}...{% endif %}
                </div>
                {% endfor %}
            </div>

            <!-- 버튼 -->
            <div class="mt-8 flex items-center justify-end gap-3 pt-6 border-t border-gray-200">
                <a href="..." class="btn btn-secondary">취소</a>
                <button type="submit" class="btn btn-primary">등록</button>
            </div>
        </form>
    </div>
</div>
{% endblock %}
```

### 7.5 버튼 클래스

| 클래스 | 용도 | 색상 |
|--------|------|------|
| `btn btn-primary` | 주요 액션 | 파란색 |
| `btn btn-secondary` | 보조 액션 | 회색 |
| `btn btn-danger` | 삭제/위험 액션 | 빨간색 |
| `btn btn-success` | 성공/완료 액션 | 초록색 |

## 8. 사이드바 메뉴 추가 방법

### 8.1 단일 메뉴 항목

`templates/base.html`의 사이드바 `<nav>` 영역에 추가합니다:

```html
<li>
    <a href="{% url 'myapp:list' %}"
       class="flex items-center px-3 py-2.5 rounded-lg hover:bg-slate-700 transition-colors
              {% if request.resolver_match.app_name == 'myapp' %}bg-slate-700{% endif %}">
        <svg class="w-5 h-5 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <!-- SVG 아이콘 path -->
        </svg>
        <span class="ml-3" x-show="sidebarOpen">내앱</span>
    </a>
</li>
```

### 8.2 하위 메뉴가 있는 항목

```html
<li x-data="{ open: {% if request.resolver_match.app_name == 'myapp' %}true{% else %}false{% endif %} }">
    <button @click="open = !open"
            class="flex items-center w-full px-3 py-2.5 rounded-lg hover:bg-slate-700 transition-colors
                   {% if request.resolver_match.app_name == 'myapp' %}bg-slate-700{% endif %}">
        <svg class="w-5 h-5 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <!-- 아이콘 -->
        </svg>
        <span class="ml-3 flex-1 text-left" x-show="sidebarOpen">내앱</span>
        <svg x-show="sidebarOpen" class="w-4 h-4 transition-transform" :class="{ 'rotate-90': open }"
             fill="currentColor" viewBox="0 0 20 20">
            <path fill-rule="evenodd" d="M7.293 14.707a1 1 0 010-1.414L10.586 10 7.293 6.707a1 1 0 011.414-1.414l4 4a1 1 0 010 1.414l-4 4a1 1 0 01-1.414 0z"/>
        </svg>
    </button>
    <ul x-show="open && sidebarOpen" x-cloak class="mt-1 ml-4 space-y-1">
        <li><a href="{% url 'myapp:list1' %}" class="block px-3 py-2 text-sm rounded-lg hover:bg-slate-700 text-slate-300 hover:text-white">하위메뉴1</a></li>
        <li><a href="{% url 'myapp:list2' %}" class="block px-3 py-2 text-sm rounded-lg hover:bg-slate-700 text-slate-300 hover:text-white">하위메뉴2</a></li>
    </ul>
</li>
```

> **참고:** Alpine.js의 `x-data`로 메뉴 토글 상태를 관리하며, 현재 앱인 경우 자동으로 펼쳐집니다.
