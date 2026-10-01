"""Admin configuration for Maya chatbot."""

from django.contrib import admin
from django.utils.html import format_html
from django import forms
from .models import BotSettings, ChatLog, ChatMessage, UserMemory


# Sıcaklık seçenekleri
TEMPERATURE_CHOICES = [
    ('0.2', '0.2 (Çok Düşük - Çok tutarlı)'),
    ('0.3', '0.3 (Düşük - Tutarlı)'),
    ('0.5', '0.5 (Orta-Düşük)'),
    ('0.6', '0.6 (Orta - Dengeli)'),
    ('0.7', '0.7 (Orta-Yüksek)'),
    ('0.8', '0.8 (Yüksek - Yaratıcı)'),
    ('0.9', '0.9 (Çok Yüksek - Çok yaratıcı)'),
]

# Model seçenekleri
MODEL_CHOICES = [
    # Gemini 1.5 Serisi
    ('gemini-1.5-flash', 'Gemini 1.5 Flash (Hızlı)'),
    ('gemini-1.5-pro', 'Gemini 1.5 Pro (Güçlü)'),
    
    # Gemini 2.0 Serisi
    ('gemini-2.0-flash', 'Gemini 2.0 Flash (Hızlı & Dengeli)'),
    ('gemini-2.0-flash-lite', 'Gemini 2.0 Flash Lite (Ekonomik)'),
    
    # Gemini 2.5 Serisi (En Yeni)
    ('gemini-2.5-flash', 'Gemini 2.5 Flash (Yeni - Hızlı)'),
    ('gemini-2.5-flash-lite', 'Gemini 2.5 Flash Lite (Yeni - Ekonomik)'),
    ('gemini-2.5-pro', 'Gemini 2.5 Pro (Yeni - En Güçlü)'),
    
    # Gemini 3 Serisi (Preview)
    ('gemini-3-flash-preview', 'Gemini 3 Flash (Hızlı)'),
    ('gemini-3-pro-preview', 'Gemini 3 Pro (Güçlü)'),
]


class BotSettingsAdminForm(forms.ModelForm):
    """Custom form for BotSettings with dropdown choices."""
    
    class Meta:
        model = BotSettings
        fields = '__all__'
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # Eğer temperature ayarı ise dropdown göster
        if self.instance and self.instance.name == 'temperature':
            self.fields['value'] = forms.ChoiceField(
                choices=TEMPERATURE_CHOICES,
                label='Sıcaklık Değeri',
                help_text='Yanıtların yaratıcılık seviyesini seçin'
            )
        
        # Eğer model_name ayarı ise dropdown göster
        elif self.instance and self.instance.name == 'model_name':
            self.fields['value'] = forms.ChoiceField(
                choices=MODEL_CHOICES,
                label='Model',
                help_text='Kullanılacak Gemini modelini seçin'
            )


@admin.register(BotSettings)
class BotSettingsAdmin(admin.ModelAdmin):
    """Admin interface for Bot Settings."""
    
    form = BotSettingsAdminForm
    list_display = ['name', 'setting_type', 'short_value', 'is_active', 'updated_at']
    list_filter = ['setting_type', 'is_active']
    search_fields = ['name', 'value', 'description']
    list_editable = ['is_active']
    readonly_fields = ['created_at', 'updated_at']
    
    fieldsets = (
        ('Temel Bilgiler', {
            'fields': ('name', 'setting_type', 'is_active')
        }),
        ('Değer', {
            'fields': ('value', 'description'),
            'classes': ('wide',)
        }),
        ('Tarihler', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def short_value(self, obj):
        """Display truncated value in list view."""
        if len(obj.value) > 50:
            return obj.value[:50] + "..."
        return obj.value
    short_value.short_description = "Değer (Önizleme)"


class MultiDbModelAdmin(admin.ModelAdmin):
    """Base admin class for models stored in MySQL."""
    
    using = 'mysql'

    def save_model(self, request, obj, form, change):
        obj.save(using=self.using)

    def delete_model(self, request, obj):
        obj.delete(using=self.using)

    def get_queryset(self, request):
        return super().get_queryset(request).using(self.using)

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        kwargs['using'] = self.using
        return super().formfield_for_foreignkey(db_field, request, **kwargs)

    def formfield_for_manytomany(self, db_field, request, **kwargs):
        kwargs['using'] = self.using
        return super().formfield_for_manytomany(db_field, request, **kwargs)


@admin.register(ChatLog)
class ChatLogAdmin(MultiDbModelAdmin):
    """Admin interface for Chat Logs (MySQL)."""
    
    list_display = ['session_short', 'user_id', 'user_message_short', 'created_at']
    list_filter = ['created_at']
    search_fields = ['session_id', 'user_id', 'user_message', 'bot_response']
    readonly_fields = ['session_id', 'user_id', 'user_message', 'bot_response', 'created_at']
    # date_hierarchy = 'created_at'
    
    def session_short(self, obj):
        """Display truncated session ID."""
        return obj.session_id[:12] + "..."
    session_short.short_description = "Oturum"
    
    def user_message_short(self, obj):
        """Display truncated user message."""
        if len(obj.user_message) > 60:
            return obj.user_message[:60] + "..."
        return obj.user_message
    user_message_short.short_description = "Kullanıcı Mesajı"
    
    def has_add_permission(self, request):
        return False
    
    def has_change_permission(self, request, obj=None):
        return False


@admin.register(ChatMessage)
class ChatMessageAdmin(MultiDbModelAdmin):
    """Admin interface for Chat Messages (MySQL)."""
    
    list_display = ['session_short', 'user_id', 'role', 'content_short', 'created_at']
    list_filter = ['role', 'created_at']
    search_fields = ['session_id', 'user_id', 'content']
    readonly_fields = ['session_id', 'user_id', 'role', 'content', 'created_at']
    # date_hierarchy = 'created_at'
    
    def session_short(self, obj):
        return obj.session_id[:12] + "..."
    session_short.short_description = "Oturum"
    
    def content_short(self, obj):
        if len(obj.content) > 60:
            return obj.content[:60] + "..."
        return obj.content
    content_short.short_description = "İçerik"
    
    def has_add_permission(self, request):
        return False
    
    def has_change_permission(self, request, obj=None):
        return False


@admin.register(UserMemory)
class UserMemoryAdmin(MultiDbModelAdmin):
    """Admin interface for User Memories (MySQL)."""
    
    list_display = ['user_id', 'category', 'content_short', 'updated_at']
    list_filter = ['category', 'updated_at']
    search_fields = ['user_id', 'content']
    readonly_fields = ['created_at', 'updated_at']
    
    def content_short(self, obj):
        if len(obj.content) > 80:
            return obj.content[:80] + "..."
        return obj.content
    content_short.short_description = "İçerik"


# Customize admin site header
admin.site.site_header = "Maya Admin Panel"
admin.site.site_title = "Maya Yönetim"
admin.site.index_title = "Hoş Geldiniz - Maya Akademik Asistan Yönetimi"
