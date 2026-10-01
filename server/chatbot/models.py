"""Database models for Maya chatbot."""

from django.db import models


class BotSettings(models.Model):
    """Model for storing bot settings like prompts and model configuration."""
    
    SETTING_TYPES = [
        ('system_prompt', 'Sistem Promptu'),
        ('model_name', 'Model Adı'),
        ('temperature', 'Sıcaklık'),
        ('other', 'Diğer'),
    ]
    
    name = models.CharField(
        max_length=100, 
        unique=True, 
        verbose_name="Ayar Adı",
        help_text="Ayarın benzersiz tanımlayıcısı (ör: system_prompt, model_name)"
    )
    setting_type = models.CharField(
        max_length=50, 
        choices=SETTING_TYPES, 
        default='other',
        verbose_name="Ayar Tipi"
    )
    value = models.TextField(
        verbose_name="Değer",
        help_text="Ayarın değeri"
    )
    description = models.CharField(
        max_length=255, 
        blank=True, 
        verbose_name="Açıklama",
        help_text="Bu ayarın ne işe yaradığının kısa açıklaması"
    )
    is_active = models.BooleanField(
        default=True, 
        verbose_name="Aktif",
        help_text="Bu ayar aktif mi?"
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Oluşturulma")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Güncellenme")

    class Meta:
        verbose_name = "Bot Ayarı"
        verbose_name_plural = "Bot Ayarları"
        ordering = ['setting_type', 'name']

    def __str__(self):
        return f"{self.get_setting_type_display()}: {self.name}"

    @classmethod
    def get_setting(cls, name: str, default: str = "") -> str:
        """Get a setting value by name."""
        try:
            setting = cls.objects.get(name=name, is_active=True)
            return setting.value
        except cls.DoesNotExist:
            return default


class ChatLog(models.Model):
    """Model for logging chat interactions (stored in MySQL)."""
    
    session_id = models.CharField(max_length=100, db_index=True, verbose_name="Oturum ID")
    user_id = models.CharField(max_length=100, blank=True, null=True, db_index=True, verbose_name="Kullanıcı ID")
    user_message = models.TextField(verbose_name="Kullanıcı Mesajı")
    bot_response = models.TextField(verbose_name="Bot Yanıtı")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Tarih")

    class Meta:
        verbose_name = "Sohbet Logu"
        verbose_name_plural = "Sohbet Logları"
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.session_id[:8]}... - {self.created_at.strftime('%d/%m/%Y %H:%M')}"


class ChatMessage(models.Model):
    """Individual chat messages for history loading (stored in MySQL)."""
    
    ROLE_CHOICES = [
        ('user', 'Kullanıcı'),
        ('assistant', 'Maya'),
    ]
    
    session_id = models.CharField(max_length=100, db_index=True, verbose_name="Oturum ID")
    user_id = models.CharField(max_length=100, blank=True, null=True, db_index=True, verbose_name="Kullanıcı ID")
    role = models.CharField(max_length=10, choices=ROLE_CHOICES, verbose_name="Rol")
    content = models.TextField(verbose_name="İçerik")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Tarih")

    class Meta:
        verbose_name = "Sohbet Mesajı"
        verbose_name_plural = "Sohbet Mesajları"
        ordering = ['created_at']

    def __str__(self):
        return f"[{self.get_role_display()}] {self.content[:40]}..."


class UserMemory(models.Model):
    """Per-user memory extracted from conversations (stored in MySQL)."""
    
    CATEGORY_CHOICES = [
        ('interests', 'İlgi Alanları'),
        ('struggles', 'Zorlandığı Konular'),
        ('learning_style', 'Öğrenme Tarzı'),
        ('current_topics', 'Güncel Konular'),
        ('personal_notes', 'Kişisel Notlar'),
        ('summary', 'Genel Özet'),
    ]
    
    user_id = models.CharField(max_length=100, db_index=True, verbose_name="Kullanıcı ID")
    category = models.CharField(max_length=50, choices=CATEGORY_CHOICES, verbose_name="Kategori")
    content = models.TextField(verbose_name="İçerik")
    source_session = models.CharField(max_length=100, blank=True, null=True, verbose_name="Kaynak Oturum")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Oluşturulma")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Güncellenme")

    class Meta:
        verbose_name = "Kullanıcı Hafızası"
        verbose_name_plural = "Kullanıcı Hafızaları"
        unique_together = ('user_id', 'category')

    def __str__(self):
        return f"{self.user_id} - {self.get_category_display()}"
