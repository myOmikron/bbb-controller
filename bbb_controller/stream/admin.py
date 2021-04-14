from django.contrib import admin

from stream.models import Channel


@admin.register(Channel)
class ChannelAdmin(admin.ModelAdmin):
    pass
