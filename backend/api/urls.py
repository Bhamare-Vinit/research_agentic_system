from django.urls import path

from . import views

urlpatterns = [
    path("health/", views.health),
    path("research/", views.research),
    path("dossier/", views.dossier),
    path("threads/<str:thread_id>/", views.thread),
    path("tokens/", views.token_usage),
]
