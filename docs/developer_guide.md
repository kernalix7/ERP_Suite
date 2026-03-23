# ERP Suite Developer Guide

## 1. Project Structure

```
ERP_Suite/
├── apps/                    # Django app collection
│   ├── core/                # Common functionality
│   │   ├── models.py        # BaseModel (abstract model)
│   │   ├── mixins.py        # RBAC mixins (Staff/Manager/Admin)
│   │   ├── views.py         # Dashboard view
│   │   ├── utils.py         # Common utilities
│   │   ├── excel.py         # Excel export (openpyxl)
│   │   ├── backup.py        # Backup/restore
│   │   ├── notification.py  # Notification model
│   │   └── urls.py          # Dashboard, backup URLs
│   ├── accounts/            # Authentication/user management
│   ├── inventory/           # Inventory management
│   ├── production/          # Production management
│   ├── sales/               # Sales management
│   ├── service/             # After-sales service management
│   ├── accounting/          # Accounting management
│   ├── investment/          # Investment management
│   ├── purchase/            # Purchase management
│   ├── marketplace/         # External store integration (Naver/Coupang)
│   ├── inquiry/             # Inquiry management
│   ├── warranty/            # Product registration
│   ├── hr/                  # HR management
│   ├── attendance/          # Attendance management
│   ├── board/               # Board (notice/general)
│   ├── calendar_app/        # Calendar management
│   ├── messenger/           # Internal messenger
│   ├── ad/                  # Active Directory integration
│   ├── advertising/         # Ad management
│   ├── approval/            # Approval/request workflow
│   ├── asset/               # Fixed asset management
│   └── api/                 # REST API
├── config/
│   ├── settings/
│   │   ├── __init__.py      # Environment-specific settings loader
│   │   ├── base.py          # Common settings (private)
│   │   ├── development.py   # Development environment settings
│   │   └── production.py    # Production environment settings
│   └── wsgi.py              # WSGI entry point
├── templates/               # Global templates
│   ├── base.html            # Base layout (sidebar, header)
│   ├── 403.html / 404.html / 500.html  # Error pages
│   └── {app_name}/          # Per-app template folders
├── static/                  # Static files
├── locale/                  # i18n translation files
├── requirements/            # Dependencies
│   ├── base.txt             # Core dependencies
│   ├── dev.txt              # Development dependencies
│   ├── prod.txt             # Production dependencies
│   └── test.txt             # Test dependencies
├── local/                   # Local settings (.env, etc., not tracked by Git)
├── docker-compose.yml
├── Dockerfile
└── manage.py
```

## 2. How to Add a New App

### 2.1 Create the App

```bash
cd apps
python ../manage.py startapp myapp
```

### 2.2 App Configuration

`apps/myapp/apps.py`:
```python
from django.apps import AppConfig

class MyappConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.myapp'
    verbose_name = '내앱이름'

    def ready(self):
        import apps.myapp.signals  # noqa: F401  (if signals exist)
```

### 2.3 Register in Settings

Add to `INSTALLED_APPS` in `config/settings/base.py`:
```python
INSTALLED_APPS = [
    ...
    'apps.myapp',
]
```

### 2.4 Register URLs

Add to `config/urls.py`:
```python
urlpatterns = [
    ...
    path('myapp/', include('apps.myapp.urls')),
]
```

### 2.5 Migrations

```bash
python manage.py makemigrations myapp
python manage.py migrate
```

## 3. Model Writing Rules

### 3.1 Inherit from BaseModel

All models must inherit from `apps.core.models.BaseModel`.

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

**Fields provided by BaseModel:**
| Field | Type | Description |
|-------|------|-------------|
| `created_at` | DateTimeField | Creation date (auto) |
| `updated_at` | DateTimeField | Modification date (auto) |
| `created_by` | ForeignKey(User) | Creator |
| `is_active` | BooleanField | Active status (for soft delete) |
| `notes` | TextField | Remarks |

**Managers:**
- `objects`: Queries only active records (`is_active=True`)
- `all_objects`: Queries all records

### 3.2 verbose_name Required

All fields must have a Korean `verbose_name` as the first argument:
```python
name = models.CharField('제품명', max_length=200)  # O
name = models.CharField(max_length=200)             # X
```

### 3.3 Use TextChoices

Choice fields should use `models.TextChoices`:
```python
class Status(models.TextChoices):
    DRAFT = 'DRAFT', '임시'
    CONFIRMED = 'CONFIRMED', '확정'
    CANCELLED = 'CANCELLED', '취소'

status = models.CharField('상태', max_length=10, choices=Status.choices, default=Status.DRAFT)
```

### 3.4 HistoricalRecords

Apply `simple_history` to models that require change history tracking:
```python
from simple_history.models import HistoricalRecords

class MyModel(BaseModel):
    ...
    history = HistoricalRecords()
```

## 4. View Writing Rules

### 4.1 RBAC Mixins

Inherit the appropriate mixin from `apps.core.mixins`:

| Mixin | Access Permission |
|-------|-------------------|
| `StaffRequiredMixin` | All logged-in users |
| `ManagerRequiredMixin` | Managers and administrators |
| `AdminRequiredMixin` | Administrators only |

```python
from apps.core.mixins import StaffRequiredMixin

class MyListView(StaffRequiredMixin, ListView):
    model = MyModel
    template_name = 'myapp/mymodel_list.html'
    context_object_name = 'items'
    paginate_by = 20
```

### 4.2 Auto-setting created_by

Override `form_valid` in CreateView to set `created_by`:

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

### 4.3 Success Messages

Use `django.contrib.messages` to provide user feedback:

```python
from django.contrib import messages

def form_valid(self, form):
    form.instance.created_by = self.request.user
    messages.success(self.request, '등록이 완료되었습니다.')
    return super().form_valid(form)
```

## 5. Form Writing Rules

### 5.1 Basic Pattern

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

### 5.2 CSS Classes

Use the Tailwind CSS-based `form-input` class. It is defined in `base.html`:
```css
.form-input {
    @apply w-full px-3 py-2 border border-gray-300 rounded-lg
           focus:ring-2 focus:ring-blue-500 focus:border-blue-500 text-sm;
}
```

### 5.3 Date Fields

```python
'date_field': forms.DateInput(attrs={'class': 'form-input', 'type': 'date'}),
```

## 6. Signal Writing Rules

### 6.1 Use F() Expressions

When modifying quantities such as inventory, always use `F()` expressions to prevent race conditions:

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

### 6.2 transaction.atomic Required

Signals that modify multiple models simultaneously must be wrapped in `transaction.atomic()` to ensure data consistency.

### 6.3 Load Signals During App Initialization

Import the signals module in the `ready()` method of `apps.py`:
```python
def ready(self):
    import apps.myapp.signals  # noqa: F401
```

## 7. Template Writing Rules

### 7.1 Inherit from base.html

All templates inherit from `base.html`:

```html
{% extends "base.html" %}

{% block title %}Page Title - ERP Suite{% endblock %}
{% block page_title %}Page Title{% endblock %}

{% block header_actions %}
<!-- Top-right action buttons -->
{% endblock %}

{% block content %}
<!-- Page body -->
{% endblock %}
```

### 7.2 Available Blocks

| Block | Purpose |
|-------|---------|
| `title` | HTML `<title>` tag |
| `page_title` | Top header area title |
| `header_actions` | Top-right action button area |
| `content` | Main content area |
| `public_content` | Content for non-logged-in users |

### 7.3 Standard List Page Structure

```html
{% block content %}
<div class="bg-white rounded-xl shadow-sm border border-gray-200">
    <!-- Filter area -->
    <div class="p-4 border-b border-gray-200">
        <form method="get" class="flex flex-col sm:flex-row gap-3">
            ...
        </form>
    </div>

    <!-- Table -->
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

    <!-- Pagination -->
    {% if is_paginated %}
    <div class="px-6 py-4 border-t border-gray-200 flex items-center justify-between">
        ...
    </div>
    {% endif %}
</div>
{% endblock %}
```

### 7.4 Standard Form Page Structure

```html
{% block content %}
<div class="max-w-2xl mx-auto">
    <div class="bg-white rounded-xl shadow-sm border border-gray-200 p-6">
        <form method="post" novalidate>
            {% csrf_token %}
            <!-- Non-field errors -->
            {% if form.non_field_errors %}...{% endif %}

            <!-- Field iteration -->
            <div class="space-y-5">
                {% for field in form %}
                <div>
                    <label>{{ field.label }}</label>
                    {{ field }}
                    {% if field.errors %}...{% endif %}
                </div>
                {% endfor %}
            </div>

            <!-- Buttons -->
            <div class="mt-8 flex items-center justify-end gap-3 pt-6 border-t border-gray-200">
                <a href="..." class="btn btn-secondary">Cancel</a>
                <button type="submit" class="btn btn-primary">Submit</button>
            </div>
        </form>
    </div>
</div>
{% endblock %}
```

### 7.5 Button Classes

| Class | Purpose | Color |
|-------|---------|-------|
| `btn btn-primary` | Primary action | Blue |
| `btn btn-secondary` | Secondary action | Gray |
| `btn btn-danger` | Delete/dangerous action | Red |
| `btn btn-success` | Success/completion action | Green |

## 8. How to Add Sidebar Menu Items

### 8.1 Single Menu Item

Add to the sidebar `<nav>` area in `templates/base.html`:

```html
<li>
    <a href="{% url 'myapp:list' %}"
       class="flex items-center px-3 py-2.5 rounded-lg hover:bg-slate-700 transition-colors
              {% if request.resolver_match.app_name == 'myapp' %}bg-slate-700{% endif %}">
        <svg class="w-5 h-5 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <!-- SVG icon path -->
        </svg>
        <span class="ml-3" x-show="sidebarOpen">My App</span>
    </a>
</li>
```

### 8.2 Item with Submenu

```html
<li x-data="{ open: {% if request.resolver_match.app_name == 'myapp' %}true{% else %}false{% endif %} }">
    <button @click="open = !open"
            class="flex items-center w-full px-3 py-2.5 rounded-lg hover:bg-slate-700 transition-colors
                   {% if request.resolver_match.app_name == 'myapp' %}bg-slate-700{% endif %}">
        <svg class="w-5 h-5 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <!-- Icon -->
        </svg>
        <span class="ml-3 flex-1 text-left" x-show="sidebarOpen">My App</span>
        <svg x-show="sidebarOpen" class="w-4 h-4 transition-transform" :class="{ 'rotate-90': open }"
             fill="currentColor" viewBox="0 0 20 20">
            <path fill-rule="evenodd" d="M7.293 14.707a1 1 0 010-1.414L10.586 10 7.293 6.707a1 1 0 011.414-1.414l4 4a1 1 0 010 1.414l-4 4a1 1 0 01-1.414 0z"/>
        </svg>
    </button>
    <ul x-show="open && sidebarOpen" x-cloak class="mt-1 ml-4 space-y-1">
        <li><a href="{% url 'myapp:list1' %}" class="block px-3 py-2 text-sm rounded-lg hover:bg-slate-700 text-slate-300 hover:text-white">Submenu 1</a></li>
        <li><a href="{% url 'myapp:list2' %}" class="block px-3 py-2 text-sm rounded-lg hover:bg-slate-700 text-slate-300 hover:text-white">Submenu 2</a></li>
    </ul>
</li>
```

> **Note:** Menu toggle state is managed with Alpine.js `x-data`, and the menu automatically expands when the current app matches.
