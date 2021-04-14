import json
import os

from django.db.models import Count
from django.http import JsonResponse, HttpResponseRedirect
from django.utils.http import urlencode
from rc_protocol import get_checksum

from bbb_common_api.views import PostApiPoint, GetApiPoint
from children.models import BBB, BBBChat, BBBLive, StreamFrontend
from api.models import Channel


def _forward_response(name: str, response: dict, status=500):
    msg = f"Couldn't start '{name}': {response['message']}"
    return JsonResponse(
        {"success": False, "message": msg},
        status=status,
        reason=msg
    )


class OpenChannel(PostApiPoint):

    endpoint = "openChannel"
    required_parameters = ["meeting_id"]

    def safe_post(self, request, parameters, *args, **kwargs):
        meeting_id = parameters["meeting_id"]

        if Channel.objects.filter(meeting_id=meeting_id).count() > 0:
            return JsonResponse(
                {"success": False, "message": "The channel has already been opened."},
                status=304,
                reason="The channel has already been opened."
            )

        # Get frontend with least running streams
        frontend = StreamFrontend.objects.annotate(channels=Count("channel")).earliest("channels")

        # Open frontend's channel
        response = frontend.open_channel(**parameters)
        if not response["success"]:
            return _forward_response("streaming channel", response)

        # Generate rtmp uri from streaming key and frontend url
        _key = response["content"]["streaming_key"]
        rtmp_uri = os.path.join(frontend.url, "stream", _key)
        _replace = "http"
        if rtmp_uri.startswith("https"):
            _replace = "https"
        rtmp_uri = rtmp_uri.replace(_replace, "rtmp")

        # Register channel in db
        Channel.objects.create(
            meeting_id=meeting_id,
            rtmp_uri=rtmp_uri,
            frontend=frontend,
            internal_meeting_id="",
            bbb_chat=None,
            bbb_live=None,
        )

        return JsonResponse(
            {"success": True, "message": "Channel opened."}
        )


class StartStream(PostApiPoint):

    endpoint = "startStream"
    required_parameters = ["meeting_id"]

    def safe_post(self, request, parameters, *args, **kwargs):
        meeting_id = parameters["meeting_id"]

        if Channel.objects.filter(meeting_id=meeting_id).count() == 0:
            return JsonResponse(
                {"success": False, "message": "There is no channel for this meeting"},
                status=404,
                reason="There is no channel for this meeting"
            )
        channel = Channel.objects.filter(meeting_id=meeting_id).last()

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

        # Get bbb-chat for bbb instance
        bbb_chat = BBBChat.objects.get(bbb=bbb)

        # Get bbb-live with least running streams
        bbb_live = BBBLive.objects.annotate(channels=Count("channel")).earliest("channels")

        # Update channel with bbb and streamer
        channel.internal_meeting_id = str(bbb.api.get_meeting_info(meeting_id)["xml"]["internalMeetingID"])
        channel.bbb_chat = bbb_chat
        channel.bbb_live = bbb_live
        channel.save()

        # Start bbb-chat
        response = channel.bbb_chat.start_chat(
            meeting_id,
            "Stream",
            channel.frontend.api_url,
            channel.frontend.secret
        )
        if not response["success"]:
            return _forward_response("bbb-chat", response)

        # Start frontend's chat
        response = channel.frontend.start_chat(
            meeting_id,
            bbb_chat.url,
            bbb_chat.secret
        )
        if not response["success"]:
            bbb_chat.end_chat(meeting_id)
            return _forward_response("frontend-chat", response)

        # Start bbb-live
        response = channel.bbb_live.start_stream(
            channel.rtmp_uri,
            meeting_id,
            channel.meeting_password
        )
        if not response["success"]:
            channel.frontend.end_chat(meeting_id)
            bbb_chat.end_chat(meeting_id)
            return _forward_response("bbb-live", response)

        # Report success
        return JsonResponse(
            {"success": True, "message": "Stream started successfully."}
        )


class JoinStream(GetApiPoint):

    endpoint = "joinStream"
    required_parameters = ["meeting_id", "user_name"]

    def safe_get(self, request, *args, **kwargs):
        meeting_id = request.GET["meeting_id"]
        user_name = request.GET["user_name"]

        try:
            channel = Channel.objects.get(meeting_id=meeting_id)
        except Channel.DoesNotExist:
            return JsonResponse(
                {"success": False, "message": "No channel was opened for this meeting"},
                status=404,
                reason="No channel was opened for this meeting"
            )

        get = {
            "meeting_id": meeting_id,
            "user_name": user_name,
        }
        get["checksum"] = get_checksum(get, channel.frontend.secret, "join")

        return HttpResponseRedirect(
            os.path.join(channel.frontend.url, "api/v1/join?") + urlencode(get)
        )


class EndStream(PostApiPoint):

    endpoint = "endStream"
    required_parameters = ["meeting_id"]

    def safe_post(self, request, parameters, *args, **kwargs):
        meeting_id = parameters["meeting_id"]

        try:
            channel = Channel.objects.get(meeting_id=meeting_id)
        except Channel.DoesNotExist:
            return JsonResponse(
                {"success": False, "message": "No channel was opened for this meeting"},
                status=404,
                reason="No channel was opened for this meeting"
            )

        channel.bbb_chat.end_chat(channel.meeting_id)
        channel.frontend.end_chat(channel.meeting_id)
        channel.bbb_live.stop_stream(channel.meeting_id)
        channel.frontend.close_channel(channel.meeting_id)
        channel.delete()

        return JsonResponse(
            {"success": True, "message": "Stream stopped successfully."}
        )


class BBBObserver(PostApiPoint):

    endpoint = "bbbObserver"
    required_parameters = ["event"]

    def safe_post(self, request, parameters, *args, **kwargs):
        """
        'event': {
            'header': {
                'name': 'MeetingEndingEvtMsg',
                'meetingId': '[internalMeetingId]',
                'userId': 'not-used'
            },
            'body': {
                'meetingId': '[internalMeetingId]',
                'reason': 'ENDED_FROM_API'
            }
        }
        """
        event = json.loads(parameters["event"])
        header = event["header"]
        body = event["body"]

        if header["name"] != "MeetingEndingEvtMsg":
            return JsonResponse(
                {"success": False, "message": "Uninteresting event"},
                status=400,
                reason="Uninteresting event"
            )

        # Get stream for meeting
        try:
            channel = Channel.objects.get(internal_meeting_id=header["meetingId"])
        except Channel.DoesNotExist:
            return JsonResponse(
                {"success": True, "message": "This meeting had no stream."},
                status=304,
                reason="This meeting had no stream."
            )

        # Stop stream
        channel.bbb_chat.end_chat(channel.meeting_id)
        channel.frontend.end_chat(channel.meeting_id)
        channel.bbb_live.stop_stream(channel.meeting_id)
        channel.frontend.close_channel(channel.meeting_id)
        channel.delete()

        return JsonResponse(
            {"success": True, "message": "Stream stopped successfully."}
        )
