"""
Database router for Maya chatbot.

Routes chat-related models (ChatLog, ChatMessage, UserMemory) to MySQL.
Everything else (BotSettings, auth, admin, sessions) stays on SQLite.
"""

# Model names that should go to MySQL
MYSQL_MODELS = {'chatlog', 'chatmessage', 'usermemory'}


class ChatDatabaseRouter:
    """Route chat models to MySQL, everything else to default (SQLite)."""

    def db_for_read(self, model, **hints):
        if model._meta.model_name in MYSQL_MODELS:
            return 'mysql'
        return 'default'

    def db_for_write(self, model, **hints):
        if model._meta.model_name in MYSQL_MODELS:
            return 'mysql'
        return 'default'

    def allow_relation(self, obj1, obj2, **hints):
        """Allow relations between all models."""
        return True

    def allow_migrate(self, db, app_label, model_name=None, **hints):
        """
        Ensure chat models only appear in MySQL,
        and everything else only appears in default (SQLite).
        """
        if model_name in MYSQL_MODELS:
            return db == 'mysql'
        return db == 'default'
