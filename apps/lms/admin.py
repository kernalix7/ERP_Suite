from django.contrib import admin
from .models import (
    CourseCategory, Course, Lesson, CourseEnrollment, LessonProgress,
    Quiz, QuizQuestion, QuizChoice, QuizAttempt, Certificate,
)

admin.site.register(CourseCategory)
admin.site.register(Course)
admin.site.register(Lesson)
admin.site.register(CourseEnrollment)
admin.site.register(LessonProgress)
admin.site.register(Quiz)
admin.site.register(QuizQuestion)
admin.site.register(QuizChoice)
admin.site.register(QuizAttempt)
admin.site.register(Certificate)
