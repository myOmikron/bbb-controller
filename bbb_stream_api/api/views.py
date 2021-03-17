from django.db.models import Count
from django.http import JsonResponse

from bbb_common_api.views import PostApiPoint
from children.models import BBB, BBBChat, XmppChat, BBBLive
from stream.models import Stream


class StartStream(PostApiPoint):

    endpoint = "startStream"
    required_parameters = ["meeting_id"]

    def safe_post(self, request, parameters, *args, **kwargs):
        meeting_id = parameters["meeting_id"]
        room_jid = parameters["room_jid"]
        rtmp_uri = parameters.setdefault("rtmp_uri", "")

        # Search in bbb instances for meeting id
        for bbb in BBB.objects.all():
            if bbb.api.is_meeting_running(meeting_id).is_meeting_running():
                break
        else:
            return JsonResponse(
                {"success": False, "message": "No matching running meeting found."},
                status=404,
                reason="No matching running meeting found."
            )

        # xmpp chat with least running streams
        xmpp_chat = XmppChat.objects.annotate(streams=Count("stream")).earliest("streams")

        # bbb chat for bbb instance
        bbb_chat = BBBChat.objects.get(bbb=bbb)

        # bbb live with least running streams
        bbb_live = BBBLive.objects.annotate(streams=Count("stream")).earliest("streams")

        # new stream to start
        stream = Stream.objects.create(
            meeting_id=meeting_id,
            room_jid=room_jid,
            rtmp_uri=rtmp_uri,
            xmpp_chat=xmpp_chat,
            bbb_chat=bbb_chat,
            bbb_live=bbb_live,
        )

        stream.start()

        return JsonResponse(
            {"success": True, "message": "Stream started successfully."}
        )


class JoinStream(PostApiPoint):

    endpoint = "joinStream"
    required_parameters = ["meeting_id", "user_name"]

    def safe_post(self, request, parameters, *args, **kwargs):
        meeting_id = parameters["meeting_id"]
        user_name = parameters["user_name"]

        pass  # TODO


class EndStream(PostApiPoint):

    endpoint = "endStream"
    required_parameters = ["meeting_id"]

    def safe_post(self, request, parameters, *args, **kwargs):
        meeting_id = parameters["meeting_id"]

        stream = Stream.objects.get(meeting_id=meeting_id)
        stream.end()
        stream.delete()

        return JsonResponse(
            {"success": True, "message": "Stream stopped successfully."}
        )
