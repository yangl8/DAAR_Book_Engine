from django.urls import path
from .views import search_api
from . import views

urlpatterns = [
    path("search", search_api, name="api-search"),
    path("recommendations/query", views.recommendations_query_view),
]
