from django.contrib import admin

from .models import Answer, Attempt, Classroom, Course, Question, Quiz


class QuestionInline(admin.TabularInline):
    model = Question
    extra = 0
    fields = ["index", "prompt", "options", "correct_index"]


@admin.register(Quiz)
class QuizAdmin(admin.ModelAdmin):
    list_display = ["title", "user", "score", "created_at"]
    list_filter = ["user", "created_at"]
    search_fields = ["title", "source_text"]
    inlines = [QuestionInline]


@admin.register(Question)
class QuestionAdmin(admin.ModelAdmin):
    list_display = ["quiz", "index", "qtype", "prompt"]
    list_filter = ["quiz", "qtype"]
    search_fields = ["prompt"]


@admin.register(Classroom)
class ClassroomAdmin(admin.ModelAdmin):
    list_display = ["name", "code", "teacher", "created_at"]
    search_fields = ["name", "code"]


@admin.register(Course)
class CourseAdmin(admin.ModelAdmin):
    list_display = ["title", "owner", "source_type", "created_at"]
    list_filter = ["source_type"]
    search_fields = ["title"]


@admin.register(Attempt)
class AttemptAdmin(admin.ModelAdmin):
    list_display = ["quiz", "student", "number", "score", "created_at"]
    list_filter = ["quiz"]


@admin.register(Answer)
class AnswerAdmin(admin.ModelAdmin):
    list_display = ["attempt", "question", "is_correct"]
    list_filter = ["is_correct"]
