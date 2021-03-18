import json
import os

import requests
from django.conf import settings
from django.shortcuts import render
from django.views.generic import TemplateView
from django.contrib.auth.mixins import LoginRequiredMixin
from rc_protocol import get_checksum


class MakeCallsView(LoginRequiredMixin, TemplateView):

    template_name = "calls.html"

    def get(self, request, *args, **kwargs):
        method = request.GET.get("method", "post")
        url = request.GET.get("url", None)
        secret = request.GET.get("secret", None)
        parameters = json.loads(request.GET.get("parameters", "null"))

        if url is not None and secret is not None and parameters is not None:
            parameters["checksum"] = get_checksum(parameters, secret, os.path.basename(url))
            response = requests.request(method, url, json=parameters, verify=settings.VERIFY_SSL_CERTS)

            try:
                text = json.dumps(response.json(), indent=4)
            except json.decoder.JSONDecodeError:
                text = response.text

            context = {
                "response": True,
                "status_code": response.status_code,
                "text": text,
            }
        else:
            context = {"response": False}

        return render(request, self.template_name, context=context)
