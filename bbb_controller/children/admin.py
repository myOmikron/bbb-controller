from django.contrib import admin

from children.models import *


@admin.register(BBBChat)
class BBBChatAdmin(admin.ModelAdmin):
    pass


@admin.register(BBB)
class BBBAdmin(admin.ModelAdmin):
    pass


@admin.register(BBBLive)
class BBBLiveAdmin(admin.ModelAdmin):
    pass


@admin.register(XmppChat)
class XmppChatAdmin(admin.ModelAdmin):
    pass


@admin.register(StreamFrontend)
class StreamFrontendAdmin(admin.ModelAdmin):
    pass
