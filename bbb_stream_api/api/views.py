from django.db.models import Count
from django.views.generic import TemplateView

from children.models import BBB, BBBChat, XmppChat, BBBLive
from stream.models import Stream


class StartStream(TemplateView):

    def post(self, request, *args, **kwargs):
        # TODO retrieve them from request
        meeting_id = "foobar"
        room_jid = "foobar"

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
            xmpp_chat=xmpp_chat,
            bbb_chat=bbb_chat,
            bbb_live=bbb_live,
        )
