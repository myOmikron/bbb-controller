import os

from django.conf import settings
from django.db import models
from django.utils.functional import cached_property
from bigbluebutton_api_python import BigBlueButton
from rc_protocol import get_checksum
import requests


def _post(base_url, secret, endpoint, params):
    params["checksum"] = get_checksum(params, secret, endpoint)
    return requests.post(
        os.path.join(base_url, endpoint),
        json=params,
        headers={"user-agent": "bbb-controller"},
        verify=settings.VERIFY_SSL_CERTS
    )


class BBB(models.Model):

    url = models.CharField(default="", max_length=255)
    secret = models.CharField(default="", max_length=255)

    @cached_property
    def api(self):
        return BigBlueButton(self.url, self.secret)


class XmppChat(models.Model):

    url = models.CharField(default="", max_length=255)
    secret = models.CharField(default="", max_length=255)

    def start_chat(self, room_jid, bbb_uri, bbb_secret, meeting_id):
        return _post(self.url, self.secret, "startChat", {
            "chat_id": room_jid,
            "callback_uri": bbb_uri,
            "callback_secret": bbb_secret,
            "callback_id": meeting_id,
        })

    def end_chat(self, chat_id):
        return _post(self.url, self.secret, "endChat", {"chat_id": chat_id})


class BBBChat(models.Model):

    bbb = models.OneToOneField(BBB, on_delete=models.CASCADE)
    secret = models.CharField(default="", max_length=255)

    @property
    def url(self):
        return os.path.join(self.bbb.url, "chat")

    def start_chat(self, meeting_id, chat_user, xmpp_uri, xmpp_secret, room_jid):
        return _post(self.url, self.secret, "startChat", {
            "chat_id": meeting_id,
            "chat_user": chat_user,
            "callback_uri": xmpp_uri,
            "callback_secret": xmpp_secret,
            "callback_id": room_jid,
        })

    def end_chat(self, meeting_id):
        return _post(self.url, self.secret, "endChat", {"chat_id": meeting_id})


class BBBLive(models.Model):

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
