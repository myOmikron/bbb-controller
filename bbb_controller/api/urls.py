from django.urls import path

from api.views import *


urlpatterns = [
    path("v1/startStream", StartStream.as_view()),
    path("v1/joinStream", JoinStream.as_view()),
    path("v1/endStream", EndStream.as_view()),
    path("internal/bbbObserver", BBBObserver.as_view())
]
