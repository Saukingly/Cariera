from django.contrib import admin
from .models import Career, CareerJourney, ChatMessage

@admin.register(Career)
class CareerAdmin(admin.ModelAdmin):
    """
    Admin interface for the Career model.
    """
    list_display = ('name', 'keywords')
    search_fields = ('name', 'keywords')

@admin.register(CareerJourney)
class CareerJourneyAdmin(admin.ModelAdmin):
    """
    Admin interface for the CareerJourney model.
    """
    list_display = ('title', 'user', 'created_at', 'updated_at')
    list_filter = ('user',)
    search_fields = ('title', 'user__username')
    readonly_fields = ('id', 'created_at', 'updated_at')

@admin.register(ChatMessage)
class ChatMessageAdmin(admin.ModelAdmin):
    """
    Admin interface for the ChatMessage model.
    """
    list_display = ('journey', 'sender_type', 'short_message', 'timestamp')
    list_filter = ('sender_type', 'journey')
    search_fields = ('message',)
    readonly_fields = ('timestamp',)

    def short_message(self, obj):
        """Returns the first 100 characters of a message."""
        return obj.message[:100]
    short_message.short_description = 'Message Snippet'