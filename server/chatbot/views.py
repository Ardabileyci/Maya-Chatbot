"""API views for Maya chatbot."""

import json
import uuid
from django.http import JsonResponse
from django.views import View
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator

from .gemini_client import (
    get_gemini_response,
    get_gemini_response_with_image,
    clear_session,
    resolve_user_name,
    trigger_memory_extraction,
)
from .models import ChatLog, ChatMessage


def TurkishJsonResponse(data, **kwargs):
    """JsonResponse that properly displays Turkish characters."""
    return JsonResponse(data, json_dumps_params={'ensure_ascii': False}, **kwargs)


@method_decorator(csrf_exempt, name='dispatch')
class HealthView(View):
    """Health check endpoint."""
    
    def get(self, request):
        return TurkishJsonResponse({
            "status": "healthy",
            "message": "Maya Akademik Asistan API çalışıyor."
        })


@method_decorator(csrf_exempt, name='dispatch')
class ChatView(View):
    """Chat endpoint for Maya chatbot."""
    
    def post(self, request):
        try:
            # Parse JSON body
            data = json.loads(request.body)
            user_message = data.get('message', '').strip()
            session_id = data.get('session_id')
            image_base64 = data.get('image')  # Optional: base64 encoded image
            mime_type = data.get('mime_type', 'image/jpeg')
            # Optional user identity (preferred: user_id/email, fallback: user_name)
            # Accept both snake_case and camelCase keys (to support different frontends/PHP integrations)
            user_id = data.get('user_id') or data.get('userId')
            user_email = data.get('user_email') or data.get('userEmail') or data.get('email')
            user_name = data.get('user_name') or data.get('userName')
            
            # Allow empty message if image is provided
            if not user_message and not image_base64:
                return TurkishJsonResponse(
                    {"error": "Mesaj veya görsel gerekli."},
                    status=400
                )
            
            # Use provided session_id or generate new one
            if not session_id:
                session_id = str(uuid.uuid4())

            # Resolve user identity from MySQL
            user_id_str = str(user_id).strip() if user_id is not None else None
            resolved_name = resolve_user_name(
                user_id=user_id_str,
                user_email=str(user_email).strip() if user_email else None,
                user_name=str(user_name).strip() if user_name else None,
            )

            # Get response from Gemini (with or without image)
            # Note: user educations are now fetched inside get_system_prompt() using user_id
            if image_base64:
                reply = get_gemini_response_with_image(
                    session_id, user_message, image_base64, mime_type,
                    user_name=resolved_name, user_profile=None, user_id=user_id_str
                )
            else:
                reply = get_gemini_response(
                    session_id, user_message,
                    user_name=resolved_name, user_profile=None, user_id=user_id_str
                )
            
            # Save to MySQL: ChatLog (admin overview)
            try:
                ChatLog.objects.create(
                    session_id=session_id,
                    user_id=user_id_str,
                    user_message=user_message,
                    bot_response=reply
                )
            except Exception as log_error:
                print(f"Failed to log chat: {log_error}")
            
            # Save to MySQL: ChatMessage (individual messages for history loading)
            try:
                if user_message:
                    ChatMessage.objects.create(
                        session_id=session_id,
                        user_id=user_id_str,
                        role='user',
                        content=user_message
                    )
                ChatMessage.objects.create(
                    session_id=session_id,
                    user_id=user_id_str,
                    role='assistant',
                    content=reply
                )
            except Exception as msg_error:
                print(f"Failed to save messages: {msg_error}")
            
            # Trigger memory extraction in background (non-blocking)
            if user_id_str:
                trigger_memory_extraction(session_id, user_id_str)
            
            return TurkishJsonResponse({
                "reply": reply,
                "session_id": session_id
            })
            
        except json.JSONDecodeError:
            return TurkishJsonResponse(
                {"error": "Geçersiz JSON formatı."},
                status=400
            )
        except Exception as e:
            print(f"Chat error: {e}")
            session_id = data.get('session_id') if 'data' in dir() else str(uuid.uuid4())
            return TurkishJsonResponse({
                "reply": "Bir hata oluştu. Lütfen tekrar deneyin.",
                "session_id": session_id
            })


@method_decorator(csrf_exempt, name='dispatch')
class NewChatView(View):
    """Create a new chat session."""
    
    def post(self, request):
        new_session_id = str(uuid.uuid4())
        return TurkishJsonResponse({
            "session_id": new_session_id,
            "message": "Yeni sohbet başlatıldı."
        })


@method_decorator(csrf_exempt, name='dispatch')
class DeleteChatView(View):
    """Delete a chat session."""
    
    def delete(self, request, session_id):
        cleared = clear_session(session_id)
        if cleared:
            return TurkishJsonResponse({"message": "Sohbet geçmişi silindi."})
        return TurkishJsonResponse({"message": "Bu oturum zaten mevcut değildi."})


@method_decorator(csrf_exempt, name='dispatch')
class ChatHistoryView(View):
    """Get chat history for a specific session."""
    
    def get(self, request, session_id):
        try:
            messages = list(
                ChatMessage.objects.filter(session_id=session_id)
                .order_by('created_at')
                .values('role', 'content', 'created_at')[:100]
            )
            
            # Convert datetime to string
            for msg in messages:
                if msg.get('created_at'):
                    msg['created_at'] = msg['created_at'].isoformat()
            
            return TurkishJsonResponse({
                'session_id': session_id,
                'messages': messages
            })
        except Exception as e:
            print(f"Chat history error: {e}")
            return TurkishJsonResponse({
                'session_id': session_id,
                'messages': []
            })


@method_decorator(csrf_exempt, name='dispatch')
class UserChatHistoryView(View):
    """Get recent chat history for a user (across all sessions)."""
    
    def get(self, request, user_id):
        try:
            messages = list(
                ChatMessage.objects.filter(user_id=user_id)
                .order_by('-created_at')[:100]
            )
            messages.reverse()
            
            result = []
            for msg in messages:
                result.append({
                    'role': msg.role,
                    'content': msg.content,
                    'created_at': msg.created_at.isoformat() if msg.created_at else None,
                    'session_id': msg.session_id,
                })
            
            return TurkishJsonResponse({
                'user_id': user_id,
                'messages': result
            })
        except Exception as e:
            print(f"User chat history error: {e}")
            return TurkishJsonResponse({
                'user_id': user_id,
                'messages': []
            })


@method_decorator(csrf_exempt, name='dispatch')
class UserSessionsView(View):
    """Get all chat sessions for a user."""
    
    def get(self, request, user_id):
        try:
            from django.db.models import Max, Min, Count
            
            sessions = list(
                ChatMessage.objects.filter(user_id=user_id)
                .values('session_id')
                .annotate(
                    last_activity=Max('created_at'),
                    first_message=Min('content'),
                    message_count=Count('id')
                )
                .order_by('-last_activity')[:20]
            )
            
            for s in sessions:
                if s.get('last_activity'):
                    s['last_activity'] = s['last_activity'].isoformat()
                # Truncate first message for preview
                if s.get('first_message') and len(s['first_message']) > 60:
                    s['first_message'] = s['first_message'][:60] + '...'
            
            return TurkishJsonResponse({
                'user_id': user_id,
                'sessions': sessions
            })
        except Exception as e:
            print(f"User sessions error: {e}")
            return TurkishJsonResponse({
                'user_id': user_id,
                'sessions': []
            })
