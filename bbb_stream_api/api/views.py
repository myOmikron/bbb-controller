import json

from django.conf import settings
from django.db.models import Count
from django.http import JsonResponse
from django.views.generic import TemplateView
from rc_protocol import validate_checksum

from children.models import BBB, BBBChat, XmppChat, BBBLive
from stream.models import Stream


class StartStream(TemplateView):

    def post(self, request, *args, **kwargs):
        # Decode json
        try:
            parameters = json.loads(request.body)
        except json.decoder.JSONDecodeError:
            return JsonResponse(
                {"success": False, "message": "Decoding data failed"},
                status=400,
                reason="Decoding data failed"
            )

        # Validate checksum
        try:
            if not validate_checksum(parameters, settings.SHARED_SECRET,
                                     "startStream", settings.SHARED_SECRET_TIME_DELTA):
                return JsonResponse(
                    {"success": False, "message": "Checksum was incorrect."},
                    status=400,
                    reason="Checksum was incorrect."
                )
        except ValueError:
            return JsonResponse(
                {"success": False, "message": "No checksum was given."},
                status=400,
                reason="No checksum was given."
            )

        # TODO check for existence
        parameters: dict
        meeting_id = parameters["meeting_id"]
        room_jid = parameters["room_jid"]
        meeting_password = parameters.setdefault("meeting_password", "ap")
        rtmp_uri = parameters.setdefault("rtmp_uri", "")

        # Search in bbb instances for meeting id
        bbb = BBB.objects.first()  # TODO replace with searching code

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
