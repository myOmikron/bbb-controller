from django.contrib import admin

from api.models import Channel


@admin.register(Channel)
class ChannelAdmin(admin.ModelAdmin):
    pass
