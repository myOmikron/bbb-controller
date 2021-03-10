from django.contrib import admin

from stream.models import Stream


@admin.register(Stream)
class StreamAdmin(admin.ModelAdmin):
    pass
