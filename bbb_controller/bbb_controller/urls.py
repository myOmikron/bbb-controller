from django.contrib import admin
from django.urls import path, include

from children.views import MakeCallsView


urlpatterns = [
    path("admin/calls", MakeCallsView.as_view()),
    path("admin/", admin.site.urls),
    path("api/", include("api.urls")),
]
