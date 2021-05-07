from django.contrib import admin

from api.models import Channel, Channel2Frontend


@admin.register(Channel2Frontend)
class C2FAdmin(admin.ModelAdmin):
    pass


@admin.register(Channel)
class ChannelAdmin(admin.ModelAdmin):
    pass
