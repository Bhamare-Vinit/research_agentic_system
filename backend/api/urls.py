from django.urls import path

from . import views

urlpatterns = [
    path("health/", views.health),
    path("research/", views.research),
    path("dossier/", views.dossier),
]
