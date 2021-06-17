from django.contrib import admin

from api.models import Channel, Channel2Frontend


@admin.register(Channel2Frontend)
class C2FAdmin(admin.ModelAdmin):
    pass


@admin.register(Channel)
class ChannelAdmin(admin.ModelAdmin):
    list_display = ("__str__", "streamed", "bigbluebutton", "bbb_live")

    def streamed(self, channel):
        return channel.bbb_live is not None
    streamed.boolean = True

    def bigbluebutton(self, channel: Channel):
        if channel.bbb_chat is None:
            return "-"
        else:
            return str(channel.bbb_chat.bbb)
