from django.urls import path
from . import views
from apps.core.excel_views import CourseExcelView, EnrollmentExcelView

app_name = 'lms'

urlpatterns = [
    path('export/courses/', CourseExcelView.as_view(), name='course_excel'),
    path('export/enrollments/', EnrollmentExcelView.as_view(), name='enrollment_excel'),
    path('', views.CourseListView.as_view(), name='course_list'),
    path('create/', views.CourseCreateView.as_view(), name='course_create'),
    path('my/', views.MyLearningView.as_view(), name='my_learning'),
    path('enrollments/', views.EnrollmentListView.as_view(), name='enrollment_list'),
    path('certificates/', views.CertificateListView.as_view(), name='certificate_list'),
    path('categories/', views.CourseCategoryListView.as_view(), name='category_list'),
    path('categories/create/', views.CourseCategoryCreateView.as_view(), name='category_create'),
    path('quizzes/', views.QuizListView.as_view(), name='quiz_list'),
    path('quizzes/create/', views.QuizCreateView.as_view(), name='quiz_create'),
    path('lessons/create/', views.LessonCreateView.as_view(), name='lesson_create'),
    path('lessons/<int:pk>/', views.LessonDetailView.as_view(), name='lesson_detail'),
    path('<int:pk>/', views.CourseDetailView.as_view(), name='course_detail'),
    path('<int:pk>/edit/', views.CourseUpdateView.as_view(), name='course_update'),
    path('<int:pk>/enroll/', views.CourseEnrollView.as_view(), name='course_enroll'),
]
