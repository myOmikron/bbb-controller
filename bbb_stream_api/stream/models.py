from django.db import models
from children.models import XmppChat, BBBChat, BBBLive


class Stream(models.Model):
    meeting_id = models.CharField(default="", max_length=255)
    meeting_password = models.CharField(default="ap", max_length=255)
    rtmp_uri = models.CharField(default="", max_length=255)
    room_jid = models.CharField(default="", max_length=255)
    xmpp_chat = models.ForeignKey(XmppChat, on_delete=models.CASCADE)
    bbb_chat = models.ForeignKey(BBBChat, on_delete=models.CASCADE)
    bbb_live = models.ForeignKey(BBBLive, on_delete=models.CASCADE)

    def start(self):
        self.bbb_chat.start_chat(
            chat_id=self.meeting_id,
            chat_user="Live",
            callback_secret=self.xmpp_chat.secret,
            callback_uri=self.xmpp_chat.url,
            callback_id=self.room_jid
        ).raise_for_status()
        self.xmpp_chat.start_chat(
            chat_id=self.room_jid,
            callback_secret=self.bbb_chat.secret,
            callback_uri=self.bbb_chat.url,
            callback_id=self.meeting_id
        ).raise_for_status()

        # self.bbb_live.start_stream(
        #   self.rtmp_uri,
        #   self.meeting_id,
        #   self.meeting_password
        # )

    def end(self):
        self.bbb_chat.end_chat(self.meeting_id)
        self.xmpp_chat.end_chat(self.room_jid)

        # self.bbb_live.stop_stream(self.meeting_id)
