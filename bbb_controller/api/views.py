import json
import os

from django.db.models import Count, F
from django.http import JsonResponse, HttpResponseRedirect
from django.utils.http import urlencode
from rc_protocol import get_checksum

from bbb_common_api.views import PostApiPoint, GetApiPoint
from children.models import BBB, BBBChat, BBBLive, StreamFrontend, StreamEdge, StreamChat
from api.models import Channel, Channel2Frontend


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
        # frontend = StreamFrontend.objects.annotate(channels=Count("channel")).earliest("channels")
        frontend = StreamEdge.objects.first()

        # Open frontend's channel
        response = frontend.open_channel(parameters["meeting_id"])
        if not response["success"]:
            return _forward_response("stream-edge", response)

        # Generate rtmp uri from streaming key and frontend url
        _key = response["content"]["streaming_key"]
        rtmp_uri = os.path.join(frontend.url, "stream", _key)
        _replace = "http"
        if rtmp_uri.startswith("https"):
            _replace = "https"
        rtmp_uri = rtmp_uri.replace(_replace, "rtmp")

        # Register channel in db
        channel = Channel.objects.create(
            meeting_id=meeting_id,
            rtmp_uri=rtmp_uri,
            internal_meeting_id="",
            bbb_chat=None,
            bbb_live=None,
        )

        # Signal all frontends to open the channel
        # TODO: what behaviour is desired, when a frontend breaks?
        errors = []
        for frontend in StreamFrontend.objects.all():
            response = frontend.open_channel(**parameters)
            if response["success"]:
                channel.frontends.add(frontend)
            else:
                errors.append((frontend.url, response["message"]))

        if errors:
            if len(errors) == 1:
                error_msg = f"Couldn't open '{errors[0][0]}': {errors[0][1]}"
            else:
                error_msg = "Multiple components couldn't stop. See 'errors' list."

            return JsonResponse(
                {"success": True, "message": error_msg, "errors": [f"'{error[0]}': {error[1]}" for error in errors]},
                status=500,
                reason=error_msg
            )
        else:
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
            StreamChat.objects.first().api_url,
            StreamChat.objects.first().secret
        )
        if not response["success"]:
            return _forward_response("bbb-chat", response)

        # Start stream's chat
        response = StreamChat.objects.first().start_chat(
            meeting_id,
            bbb_chat.url,
            bbb_chat.secret
        )
        if not response["success"]:
            bbb_chat.end_chat(meeting_id)
            return _forward_response("stream-chat", response)

        # Start bbb-live
        response = channel.bbb_live.start_stream(
            channel.rtmp_uri,
            meeting_id,
            channel.meeting_password
        )
        if not response["success"]:
            StreamChat.objects.first().end_chat(meeting_id)
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

        # Get frontend with least user and increase counter
        c2f = Channel2Frontend.objects.filter(channel=channel).order_by("viewers").first()
        c2f.viewers = F("viewers") + 1
        frontend = c2f.frontend

        get = {
            "meeting_id": meeting_id,
            "user_name": user_name,
        }
        get["checksum"] = get_checksum(get, frontend.secret, "join")
        return HttpResponseRedirect(
            os.path.join(frontend.url, "api/v1/join?") + urlencode(get)
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

        errors = []
        if channel.bbb_chat:
            response = channel.bbb_chat.end_chat(channel.meeting_id)
            if not response["success"]:
                errors.append(("bbb-chat", response))

        if channel.bbb_live:
            response = channel.bbb_live.stop_stream(channel.meeting_id)
            if not response["success"]:
                errors.append(("bbb-live", response))

        response = StreamChat.objects.first().end_chat(channel.meeting_id)
        if not response["success"]:
            errors.append(("stream-chat", response))

        response = StreamEdge.objects.first().close_channel(channel.meeting_id)
        if not response["success"]:
            errors.append(("stream-edge", response))

        for frontend in channel.frontends.all():
            response = frontend.close_channel(channel.meeting_id)
            if not response["success"]:
                errors.append(("stream-frontend", response))

        channel.delete()

        if errors:
            for i, error in enumerate(errors):
                component, response = error
                errors[i] = f"'{component}': {response['message']}"

            if len(errors) == 1:
                error_msg = f"Couldn't stop '{errors[0]}'"
            else:
                error_msg = "Multiple components couldn't stop. See 'errors' list."

            return JsonResponse(
                {"success": True, "message": error_msg, "errors": errors},
                status=500,
                reason=error_msg
            )
        else:
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
