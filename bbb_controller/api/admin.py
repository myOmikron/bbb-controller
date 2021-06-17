from django.contrib import admin

from api.models import Channel, Channel2Frontend


@admin.register(Channel2Frontend)
class C2FAdmin(admin.ModelAdmin):
    pass


@admin.register(Channel)
class ChannelAdmin(admin.ModelAdmin):
    list_display = ("__str__", "bigbluebutton", "streamed", "bbb_live")

    def streamed(self, channel):
        return channel.bbb_live is not None
    streamed.boolean = True

    def bigbluebutton(self, channel: Channel):
        return str(channel.bbb_chat.bbb)
