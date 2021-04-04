import os
import logging
from json import JSONDecodeError

from django.conf import settings
from django.db import models
from django.utils.functional import cached_property
from bigbluebutton_api_python import BigBlueButton
from django.utils.http import urlencode
from rc_protocol import get_checksum
import requests
from requests import RequestException

request_logger = logging.getLogger("children.requests")


def _post(base_url, secret, endpoint, params):
    url = os.path.join(base_url, endpoint)
    params["checksum"] = get_checksum(params, secret, endpoint)

    try:
        response = requests.post(
            url,
            json=params,
            headers={"user-agent": "bbb-controller"},
            verify=settings.VERIFY_SSL_CERTS
        )
    except RequestException as err:
        request_logger.exception(f"Couldn't request '{url}'")
        return {"success": False, "message": f"The request failed with an '{repr(err)}'. "
                                             "See the log for full traceback."}

    try:
        return response.json()
    except JSONDecodeError:
        return {"success": False, "message": f"The response from {url} wasn't json. "
                                             f"Got '{response.status_code}: {response.reason}' instead."}


class _Child(models.Model):
    url: str
    secret: str

    def __str__(self):
        return self.url

    def get_absolute_url(self):
        return "/admin/calls?" + urlencode({
            "url": self.api_url,
            "secret": self.secret
        })

    @property
    def api_url(self):
        return self.url

    class Meta:
        abstract = True


class BBB(_Child):
    url = models.CharField(default="", max_length=255)
    secret = models.CharField(default="", max_length=255)

    @cached_property
    def api(self):
        return BigBlueButton(self.url, self.secret)


class BBBChat(_Child):
    bbb = models.OneToOneField(BBB, on_delete=models.CASCADE)
    secret = models.CharField(default="", max_length=255)

    @cached_property
    def url(self):
        url = self.bbb.url.rstrip("/")
        if url.endswith("bigbluebutton"):
            url = os.path.dirname(url)
        return url + "/api/chat"

    def start_chat(self, meeting_id, chat_user, frontend_uri="", frontend_secret=""):
        return _post(self.url, self.secret, "startChat", {
            "chat_id": meeting_id,
            "chat_user": chat_user,
            "callback_uri": frontend_uri,
            "callback_secret": frontend_secret,
            "callback_id": meeting_id,
        })

    def end_chat(self, meeting_id):
        return _post(self.url, self.secret, "endChat", {"chat_id": meeting_id})


class BBBLive(_Child):
    url = models.CharField(default="", max_length=255)
    secret = models.CharField(default="", max_length=255)

    def start_stream(self, rtmp_uri, meeting_id, meeting_password):
        return _post(self.url, self.secret, "startStream", {
            "rtmp_uri": rtmp_uri,
            "meeting_id": meeting_id,
            "meeting_password": meeting_password,
        })

    def stop_stream(self, meeting_id):
        return _post(self.url, self.secret, "stopStream", {
            "meeting_id": meeting_id,
        })


class StreamFrontend(_Child):
    url = models.CharField(default="", max_length=255)
    secret = models.CharField(default="", max_length=255)

    @property
    def api_url(self):
        return os.path.join(self.url, "api", "v1")

    def start_chat(self, meeting_id, bbb_uri="", bbb_secret=""):
        return _post(self.api_url, self.secret, "startChat", {
            "chat_id": meeting_id,
            "callback_uri": bbb_uri,
            "callback_secret": bbb_secret,
            "callback_id": meeting_id,
        })

    def end_chat(self, meeting_id):
        return _post(self.api_url, self.secret, "endChat", {
            "chat_id": meeting_id
        })

    def open_channel(self, meeting_id, welcome_msg=None, redirect_url=None, **kwargs):
        params = {"meeting_id": meeting_id}
        if welcome_msg:
            params["welcome_msg"] = welcome_msg
        if redirect_url:
            params["redirect_url"] = redirect_url

        return _post(self.api_url, self.secret, "openChannel", params)

    def close_channel(self, meeting_id):
        return _post(self.api_url, self.secret, "closeChannel", {
            "meeting_id": meeting_id,
        })
