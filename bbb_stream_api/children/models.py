import os

from django.db import models
from django.utils.functional import cached_property
from bigbluebutton_api_python import BigBlueButton
from rc_protocol import get_checksum
import requests


class BBB(models.Model):

    url = models.CharField(default="", max_length=255)
    secret = models.CharField(default="", max_length=255)

    @cached_property
    def api(self):
        return BigBlueButton(self.url, self.secret)


class _AbstractChatBridge(models.Model):

    url: str
    secret: str

    class Meta:
        abstract = True

    def _post(self, endpoint, params):
        params["checksum"] = get_checksum(params, self.secret, endpoint)
        return requests.post(
            os.path.join(self.url, endpoint),
            json=params,
            headers={"user-agent": "bbb-controller"}
        )

    def start_chat(self, chat_id, callback_uri, callback_secret, callback_id):
        return self._post("startChat", {
            "chat_id": chat_id,
            "callback_uri": callback_uri,
            "callback_secret": callback_secret,
            "callback_id": callback_id,
        })

    def end_chat(self, chat_id):
        return self._post("endChat", {"chat_id": chat_id})


class XmppChat(_AbstractChatBridge):

    url = models.CharField(default="", max_length=255)
    secret = models.CharField(default="", max_length=255)


class BBBChat(_AbstractChatBridge):

    bbb = models.OneToOneField(BBB, on_delete=models.CASCADE)
    secret = models.CharField(default="", max_length=255)

    @property
    def url(self):
        return os.path.join(self.bbb.url, "chat")

    def start_chat(self, chat_id, chat_user, callback_uri, callback_secret, callback_id):
        return self._post("startChat", {
            "chat_id": chat_id,
            "chat_user": chat_user,
            "callback_uri": callback_uri,
            "callback_secret": callback_secret,
            "callback_id": callback_id,
        })


class BBBLive(models.Model):

    url = models.CharField(default="", max_length=255)
    secret = models.CharField(default="", max_length=255)

    def _post(self, endpoint, params):
        params["checksum"] = get_checksum(params, self.secret, endpoint)
        return requests.post(
            os.path.join(self.url, endpoint),
            json=params,
            headers={"user-agent": "bbb-controller"}
        )

    def start_stream(self, rtmp_uri, meeting_id, meeting_password):
        return self._post("startStream", {
            "rtmp_uri": rtmp_uri,
            "meeting_id": meeting_id,
            "meeting_password": meeting_password,
        })

    def stop_stream(self, meeting_id):
        return self._post("stopStream", {
            "meeting_id": meeting_id,
        })
