"""URL configuration for chatbot app."""

from django.urls import path
from .views import (
    HealthView,
    ChatView,
    NewChatView,
    DeleteChatView,
    ChatHistoryView,
    UserSessionsView,
    UserChatHistoryView,
)

urlpatterns = [
    path('health', HealthView.as_view(), name='health'),
    path('chat', ChatView.as_view(), name='chat'),
    path('new-chat', NewChatView.as_view(), name='new-chat'),
    path('chat/<str:session_id>', DeleteChatView.as_view(), name='delete-chat'),
    path('chat-history/<str:session_id>', ChatHistoryView.as_view(), name='chat-history'),
    path('user-chat-history/<str:user_id>', UserChatHistoryView.as_view(), name='user-chat-history'),
    path('user-sessions/<str:user_id>', UserSessionsView.as_view(), name='user-sessions'),
]
