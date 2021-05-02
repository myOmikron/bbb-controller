from django.db import models
from django.utils.functional import cached_property

from children.models import BBBChat, BBBLive, StreamFrontend


class Channel(models.Model):
    meeting_id = models.CharField(default="", max_length=255)
    rtmp_uri = models.CharField(default="", max_length=255)
    frontends = models.ManyToManyField(StreamFrontend)

    internal_meeting_id = models.CharField(default="", max_length=255, blank=True)
    bbb_chat = models.ForeignKey(BBBChat, on_delete=models.CASCADE, null=True, blank=True)
    bbb_live = models.ForeignKey(BBBLive, on_delete=models.CASCADE, null=True, blank=True)

    @cached_property
    def meeting_password(self):
        return str(self.bbb_chat.bbb.api.get_meeting_info(self.meeting_id)["xml"]["attendeePW"])
