"""Gemini API client for Maya chatbot using google-genai SDK."""

import os
import json
import base64
import re
import threading
from functools import lru_cache
from google import genai
from google.genai import types
from django.conf import settings


def _normalize_user_name(value: str | None) -> str | None:
    if not value:
        return None
    v = str(value).strip()
    if not v:
        return None
    # Basic guardrails to avoid prompt bloat / injection
    v = v.replace("\n", " ").replace("\r", " ").strip()
    return v[:80]


_IDENT_RE = re.compile(r"^[A-Za-z0-9_]+$")


def _safe_ident(value: str, default: str) -> str:
    """
    Return a safe SQL identifier (table/column name) limited to [A-Za-z0-9_].
    Falls back to default if invalid.
    """
    v = (value or "").strip()
    if not v or not _IDENT_RE.match(v):
        return default
    return v


def _mysql_env():
    host = os.getenv("DB_HOST")
    dbname = os.getenv("DB_NAME")
    user = os.getenv("DB_USER")
    password = os.getenv("DB_PASS") or os.getenv("DB_PASSWORD") or ""
    port_str = os.getenv("DB_PORT", "3306")
    try:
        port = int(port_str)
    except ValueError:
        port = 3306
    return host, dbname, user, password, port


@lru_cache(maxsize=512)
def _fetch_user_name_from_mysql(user_id: str | None, user_email: str | None) -> str | None:
    """
    Fetch a single user's display name from external MySQL.

    Defaults (override via env if needed):
      - DB_USERS_TABLE=users
      - DB_USERS_ID_COLUMN=id
      - DB_USERS_EMAIL_COLUMN=email
      - DB_USERS_NAME_COLUMN=name
    """
    user_id = str(user_id).strip() if user_id is not None else None
    user_email = str(user_email).strip() if user_email else None

    if not user_id and not user_email:
        return None

    host, dbname, user, password, port = _mysql_env()
    if not host or not dbname or not user:
        return None

    try:
        import pymysql
    except Exception:
        return None

    table = _safe_ident(os.getenv("DB_USERS_TABLE", "users"), "users")
    id_col = _safe_ident(os.getenv("DB_USERS_ID_COLUMN", "id"), "id")
    email_col = _safe_ident(os.getenv("DB_USERS_EMAIL_COLUMN", "email"), "email")
    name_col = _safe_ident(os.getenv("DB_USERS_NAME_COLUMN", "name"), "name")

    try:
        conn = pymysql.connect(
            host=host,
            user=user,
            password=password,
            database=dbname,
            port=port,
            charset="utf8mb4",
            cursorclass=pymysql.cursors.Cursor,
        )
        try:
            with conn.cursor() as cur:
                if user_id:
                    cur.execute(
                        f"SELECT `{name_col}` FROM `{table}` WHERE `{id_col}` = %s LIMIT 1",
                        (user_id,),
                    )
                    row = cur.fetchone()
                    if row and row[0]:
                        return _normalize_user_name(row[0])
                if user_email:
                    cur.execute(
                        f"SELECT `{name_col}` FROM `{table}` WHERE `{email_col}` = %s LIMIT 1",
                        (user_email,),
                    )
                    row = cur.fetchone()
                    if row and row[0]:
                        return _normalize_user_name(row[0])
        finally:
            conn.close()
    except Exception:
        return None

    return None


@lru_cache(maxsize=512)
def _fetch_user_profile_from_mysql(user_id: str | None) -> dict | None:
    """
    Fetch user profile from external MySQL user_profiles table.

    Returns dict with keys: school, department, education_status, graduation_year,
    workplace, workplace_title (values can be None or str). Returns None on error
    or if no profile found.

    Env (optional): DB_USER_PROFILES_TABLE=user_profiles, DB_USER_PROFILES_USER_ID_COLUMN=user_id
    """
    user_id = str(user_id).strip() if user_id is not None else None
    if not user_id:
        return None

    host, dbname, user, password, port = _mysql_env()
    if not host or not dbname or not user:
        return None

    try:
        import pymysql
    except Exception:
        return None

    table = _safe_ident(os.getenv("DB_USER_PROFILES_TABLE", "user_profiles"), "user_profiles")
    user_id_col = _safe_ident(os.getenv("DB_USER_PROFILES_USER_ID_COLUMN", "user_id"), "user_id")

    columns = ["school", "department", "education_status", "graduation_year", "workplace", "workplace_title"]
    cols_safe = [c for c in columns if _IDENT_RE.match(c)]
    if not cols_safe:
        cols_safe = ["school", "department", "education_status", "graduation_year", "workplace", "workplace_title"]
    cols_list = ", ".join(f"`{c}`" for c in cols_safe)

    try:
        conn = pymysql.connect(
            host=host,
            user=user,
            password=password,
            database=dbname,
            port=port,
            charset="utf8mb4",
            cursorclass=pymysql.cursors.Cursor,
        )
        try:
            with conn.cursor() as cur:
                cur.execute(
                    f"SELECT {cols_list} FROM `{table}` WHERE `{user_id_col}` = %s LIMIT 1",
                    (user_id,),
                )
                row = cur.fetchone()
                if not row:
                    return None
                out = {}
                for i, key in enumerate(cols_safe):
                    if i < len(row):
                        val = row[i]
                        out[key] = _normalize_user_name(str(val)) if val is not None else None
                    else:
                        out[key] = None
                return out
        finally:
            conn.close()
    except Exception:
        return None

    return None


def resolve_user_profile(user_id: str | None) -> dict | None:
    """Return user profile dict from MySQL (user_profiles) for the given user_id, or None."""
    return _fetch_user_profile_from_mysql(user_id)


@lru_cache(maxsize=512)
def _fetch_user_education_ids(user_id: str | None) -> list:
    """
    Fetch comma-separated education IDs from users.educations column.
    
    Returns list of integers (e.g., [84, 209, 404]).
    """
    user_id = str(user_id).strip() if user_id is not None else None
    if not user_id:
        return []
    
    host, dbname, user, password, port = _mysql_env()
    if not host or not dbname or not user:
        return []
    
    try:
        import pymysql
    except Exception:
        return []
    
    table = _safe_ident(os.getenv("DB_USERS_TABLE", "users"), "users")
    id_col = _safe_ident(os.getenv("DB_USERS_ID_COLUMN", "id"), "id")
    edu_col = _safe_ident(os.getenv("DB_USERS_EDUCATIONS_COLUMN", "educations"), "educations")
    
    try:
        conn = pymysql.connect(
            host=host,
            user=user,
            password=password,
            database=dbname,
            port=port,
            charset="utf8mb4",
            cursorclass=pymysql.cursors.Cursor,
        )
        try:
            with conn.cursor() as cur:
                cur.execute(
                    f"SELECT `{edu_col}` FROM `{table}` WHERE `{id_col}` = %s LIMIT 1",
                    (user_id,),
                )
                row = cur.fetchone()
                if not row or not row[0]:
                    return []
                
                # Parse comma-separated string: "84,209,404" -> [84, 209, 404]
                edu_str = str(row[0]).strip()
                if not edu_str:
                    return []
                
                edu_ids = []
                for part in edu_str.split(','):
                    part = part.strip()
                    if part:
                        try:
                            edu_ids.append(int(part))
                        except ValueError:
                            continue
                
                return edu_ids
        finally:
            conn.close()
    except Exception:
        return []
    
    return []


@lru_cache(maxsize=512)
def _fetch_education_names(edu_ids_tuple: tuple) -> list:
    """
    Fetch education names from educations table by IDs.
    
    Args:
        edu_ids_tuple: Tuple of education IDs (e.g., (84, 209, 404))
    
    Returns:
        List of education names (e.g., ["WEB TASARIM", "MSCD", "PYTHON"])
    """
    if not edu_ids_tuple:
        return []
    
    host, dbname, user, password, port = _mysql_env()
    if not host or not dbname or not user:
        return []
    
    try:
        import pymysql
    except Exception:
        return []
    
    table = _safe_ident(os.getenv("DB_EDUCATIONS_TABLE", "educations"), "educations")
    id_col = _safe_ident(os.getenv("DB_EDUCATIONS_ID_COLUMN", "edu_id"), "edu_id")
    name_col = _safe_ident(os.getenv("DB_EDUCATIONS_NAME_COLUMN", "edu_name"), "edu_name")
    
    try:
        conn = pymysql.connect(
            host=host,
            user=user,
            password=password,
            database=dbname,
            port=port,
            charset="utf8mb4",
            cursorclass=pymysql.cursors.Cursor,
        )
        try:
            with conn.cursor() as cur:
                # Build safe IN clause: WHERE edu_id IN (84, 209, 404)
                placeholders = ','.join(['%s'] * len(edu_ids_tuple))
                query = f"SELECT `{name_col}` FROM `{table}` WHERE `{id_col}` IN ({placeholders})"
                cur.execute(query, edu_ids_tuple)
                
                rows = cur.fetchall()
                return [str(row[0]).strip() for row in rows if row and row[0]]
        finally:
            conn.close()
    except Exception:
        return []
    
    return []


def resolve_user_educations(user_id: str | None) -> list:
    """
    Get list of education names for a user from Arıbilgi platform.
    
    Returns:
        List of education names (e.g., ["WEB TASARIM E??T?M? KAAN HOCA (493)", "MSCD ?SMA?L HOCA (766)"])
    """
    edu_ids = _fetch_user_education_ids(user_id)
    if not edu_ids:
        return []
    # Convert to tuple for lru_cache compatibility
    return _fetch_education_names(tuple(edu_ids))


def _format_user_educations_for_prompt(educations: list) -> str:
    """Format user educations as prompt lines; empty string if no educations."""
    if not educations:
        return ""
    
    # Clean up education names (remove course codes if too verbose)
    edu_list = "\n- ".join(educations)
    
    return (
        "\n\nKULLANICININ ALDIĞI EĞİTİMLER (Arıbilgi platformu):\n"
        f"- {edu_list}\n"
        "Bu bilgileri biliyorsun; kullanıcı sorduğunda kullanabilirsin."
    )


def resolve_user_name(*, user_id: str | None = None, user_email: str | None = None, user_name: str | None = None) -> str | None:
    """
    Resolve user name using (in order):
      1) MySQL lookup by user_id/email (if provided)
      2) Provided user_name (fallback)
    """
    db_name = _fetch_user_name_from_mysql(user_id, user_email)
    if db_name:
        return db_name
    return _normalize_user_name(user_name)


def _format_user_profile_for_prompt(profile: dict | None) -> str:
    """Format user profile dict as prompt lines; empty string if no useful data."""
    if not profile or not isinstance(profile, dict):
        return ""
    labels = {
        "school": "Okul",
        "department": "Bölüm",
        "education_status": "Eğitim durumu",
        "graduation_year": "Mezuniyet yılı",
        "workplace": "İş yeri",
        "workplace_title": "İş unvanı",
    }
    lines = []
    for key, label in labels.items():
        val = profile.get(key)
        if val is not None and str(val).strip():
            lines.append(f"- {label}: {_normalize_user_name(str(val))}")
    if not lines:
        return ""
    return "\n\nKULLANICI PROFİLİ (bu bilgileri biliyorsun; kullanıcı sorduğunda kullan):\n" + "\n".join(lines)


def load_user_memories(user_id: str | None) -> list:
    """Load all memories for a user from MySQL (via Django ORM + router)."""
    if not user_id:
        return []
    try:
        from .models import UserMemory
        return list(UserMemory.objects.filter(user_id=user_id).values('category', 'content'))
    except Exception as e:
        print(f"Failed to load memories: {e}")
        return []


def save_user_memory(user_id: str, category: str, content: str, session_id: str | None = None):
    """Save or update a single memory category for a user."""
    try:
        from .models import UserMemory
        UserMemory.objects.update_or_create(
            user_id=user_id,
            category=category,
            defaults={
                'content': content,
                'source_session': session_id,
            }
        )
    except Exception as e:
        print(f"Failed to save memory: {e}")


def extract_memories_from_chat(session_id: str, user_id: str):
    """
    Analyze a chat session with Gemini and extract key information
    about the student. Runs in background thread to avoid blocking.
    """
    try:
        from .models import ChatMessage

        messages = list(
            ChatMessage.objects.filter(session_id=session_id)
            .order_by('created_at')
            .values('role', 'content')
        )
        if len(messages) < 4:  # Need at least 2 exchanges
            return

        existing = load_user_memories(user_id)

        conversation_text = "\n".join(
            f"{'Öğrenci' if m['role'] == 'user' else 'Maya'}: {m['content']}"
            for m in messages[-20:]  # Son 20 mesaj yeterli
        )

        existing_text = "\n".join(
            f"- {m['category']}: {m['content']}"
            for m in existing
        ) if existing else "Henüz bilgi yok."

        extraction_prompt = f"""Aşağıdaki sohbeti analiz et ve öğrenci hakkında önemli bilgileri çıkar.

MEVCUT BİLGİLER:
{existing_text}

SON KONUŞMA:
{conversation_text}

Şu kategorilerde JSON formatında bilgi çıkar (sadece konuşmadan çıkarabildiğin bilgileri yaz, tahmin etme):

{{
  "interests": "Öğrencinin ilgi alanları, merak ettiği konular",
  "struggles": "Zorlandığı konular, sık sorduğu sorular",
  "learning_style": "Nasıl öğreniyor, ne tür açıklamaları seviyor",
  "current_topics": "Şu an ne üzerinde çalışıyor",
  "personal_notes": "Kişisel bilgiler (sınıf, bölüm vs - sadece kendisi söylediyse)",
  "summary": "Genel 1-2 cümlelik özet"
}}

KURALLAR:
- Mevcut bilgilerdeki HİÇBİR bilgiyi silme veya atlama. Eski bilgilerin TAMAMINI koru.
- Yeni konuşmadan çıkardığın bilgileri mevcut bilgilere EKLE.
- Sadece doğrudan çelişen bilgileri güncelle (örn: "27 yaşında" → kullanıcı "28 oldum" derse güncelle).
- Çelişmeyen bilgileri birleştir (örn: mevcut "2 köpeği var" + yeni "Python öğreniyor" → ikisini de yaz).
- Son konuşmada geçmeyen ama mevcut bilgilerde olan bilgileri OLDUĞU GİBİ koru, silme.
- Yeni bilgi yoksa o kategorideki mevcut bilgiyi aynen yaz, null yapma.
- Sadece konuşmadan çıkardıklarını ekle, tahmin etme veya uydurma.
- Türkçe yaz.
- SADECE JSON döndür, başka bir şey yazma."""

        client = get_client()
        response = client.models.generate_content(
            model=get_model_name(),
            contents=[extraction_prompt],
            config={"temperature": 0.2}
        )

        # Parse JSON response
        raw = response.text.strip()
        # Remove markdown code fences if present
        if raw.startswith('```'):
            raw = raw.split('\n', 1)[1] if '\n' in raw else raw[3:]
        if raw.endswith('```'):
            raw = raw[:-3]
        raw = raw.strip()

        memories = json.loads(raw)

        for category, content in memories.items():
            if content and str(content).lower() not in ('null', 'none', ''):
                save_user_memory(user_id, category, str(content), session_id)

    except Exception as e:
        print(f"Memory extraction error: {e}")


def trigger_memory_extraction(session_id: str, user_id: str):
    """Start memory extraction in a background thread."""
    if not user_id or not session_id:
        return
    thread = threading.Thread(
        target=extract_memories_from_chat,
        args=(session_id, str(user_id)),
        daemon=True
    )
    thread.start()


def _format_memories_for_prompt(user_id: str | None) -> str:
    """Format user memories as prompt lines for system instruction."""
    if not user_id:
        return ""
    memories = load_user_memories(user_id)
    if not memories:
        return ""
    labels = {
        'interests': 'İlgi alanları',
        'struggles': 'Zorlandığı konular',
        'learning_style': 'Öğrenme tarzı',
        'current_topics': 'Güncel konular',
        'personal_notes': 'Kişisel notlar',
        'summary': 'Genel özet',
    }
    lines = []
    for m in memories:
        label = labels.get(m['category'], m['category'])
        lines.append(f"- {label}: {m['content']}")
    if not lines:
        return ""
    return (
        "\n\nÖĞRENCİ HAFIZASI (önceki konuşmalardan öğrendiklerin):\n"
        + "\n".join(lines)
        + "\n\nBu bilgileri doğal şekilde kullan. "
        "'Geçen konuşmuştuk' gibi referans verebilirsin ama zorlama."
    )


def get_system_prompt(user_name: str | None = None, user_profile: dict | None = None, user_id: str | None = None):
    """Get system prompt from database or use default, enriched with user identity, profile, and memories."""
    # Import here to avoid circular imports
    from .models import BotSettings
    
    default_prompt = """Sen "Arı Bilgi" adlı eğitim kurumunun "Maya" adındaki akademisyenisin.

GÖREV:
- Öğrencilerin derslerle ilgili sorularını yanıtla.
- Programlama, grafik tasarım, matematik, fen bilimleri vb. konularda akademik destek ver.
- Konuları açık, anlaşılır ve öğretici şekilde anlat.
- Genel sohbetlere doğal ve samimi şekilde karşılık ver.

ÜSLUP KURALLARI:
- Akademik, profesyonel ve net bir dil kullan.
- Öğretici ol, örneklerle açıkla.
- Emoji kullanma.
- Resmi ama samimi ol.

KONUŞMA KURALLARI:
- Kendini SADECE ilk mesajda tanıt, sonraki mesajlarda tekrar etme.
- Her mesajda "merhaba" deme, doğal konuşma akışını sürdür.
- Kullanıcının söylediği bilgileri (yaş, ilgi alanı, meslek vb.) hatırla ve sonraki mesajlarda kullan.
- Her cevabı Arı Bilgi'ye veya eğitime bağlamaya çalışma, doğal konuşma yap.
- "Başka sorun var mı?" gibi kalıp cümleler kullanma.
- Kullanıcının sorusunu DOĞRUDAN yanıtla, konuyu değiştirme.
"""

    base_prompt = BotSettings.get_setting('system_prompt', default_prompt)

    from datetime import datetime
    import locale
    try:
        locale.setlocale(locale.LC_TIME, 'tr_TR.UTF-8')
    except Exception:
        pass
    now = datetime.now()
    days_tr = ['Pazartesi', 'Salı', 'Çarşamba', 'Perşembe', 'Cuma', 'Cumartesi', 'Pazar']
    months_tr = ['Ocak', 'Şubat', 'Mart', 'Nisan', 'Mayıs', 'Haziran', 'Temmuz', 'Ağustos', 'Eylül', 'Ekim', 'Kasım', 'Aralık']
    day_name = days_tr[now.weekday()]
    month_name = months_tr[now.month - 1]
    date_str = f"{now.day} {month_name} {now.year} {day_name}, Saat: {now.strftime('%H:%M')}"
    base_prompt += f"\n\nGÜNCEL TARİH: {date_str}\n- Tarih veya gün sorulduğunda bu bilgiyi kullan."

    user_name = _normalize_user_name(user_name)
    if "[Öğrencinin İsmi]" in base_prompt:
        base_prompt = base_prompt.replace("[Öğrencinin İsmi]", user_name or "öğrenci")

    if user_name:
        base_prompt += (
            "\n\nKULLANICI BİLGİSİ:\n"
            f"- Kullanıcının adı: {user_name}\n"
            "- Kullanıcıya sadece ilk mesajda adıyla hitap et, sonraki mesajlarda sürekli isim kullanma.\n"
            "- Kullanıcının adını bilmiyorsan ASLA tahmin etme/uydurma."
        )
    else:
        base_prompt += (
            "\n\nKULLANICI BİLGİSİ:\n"
            "- Kullanıcının adı: (bilinmiyor)\n"
            "- Kullanıcının adını bilmiyorsan ASLA tahmin etme/uydurma; gerekirse sor."
        )

    # Add user educations from Arıbilgi platform (MySQL)
    educations = resolve_user_educations(user_id)
    edu_text = _format_user_educations_for_prompt(educations)
    if edu_text:
        base_prompt += "\n" + edu_text

    # Add user memories (from previous conversations)
    memory_text = _format_memories_for_prompt(user_id)
    if memory_text:
        base_prompt += memory_text

    return base_prompt


def get_model_name():
    """Get model name from database or use default."""
    from .models import BotSettings
    return BotSettings.get_setting('model_name', 'gemini-1.5-flash')


def get_temperature():
    """Get temperature from database or use default."""
    from .models import BotSettings
    temp_str = BotSettings.get_setting('temperature', '0.6')
    try:
        return float(temp_str)
    except ValueError:
        return 0.6


# Global client and chat sessions storage
_client = None
_chat_sessions = {}  # session_id -> {"chat": chat, "user_name": str|None, "user_profile": dict|None}


def get_client():
    """Get or create Gemini client."""
    global _client
    if _client is None:
        _client = genai.Client(api_key=os.getenv('GEMINI_API_KEY'))
    return _client


def _profile_equal(a: dict | None, b: dict | None) -> bool:
    """Compare two profile dicts for equality (for session invalidation)."""
    if a is None and b is None:
        return True
    if a is None or b is None:
        return False
    keys = {"school", "department", "education_status", "graduation_year", "workplace", "workplace_title"}
    for k in keys:
        if (a.get(k) or "") != (b.get(k) or ""):
            return False
    return True


def _load_recent_messages(user_id: str, limit: int = 20):
    """Load recent chat messages from DB for context continuity."""
    if not user_id:
        return []
    try:
        from .models import ChatMessage
        messages = ChatMessage.objects.using('mysql').filter(
            user_id=user_id
        ).order_by('-created_at')[:limit]
        result = []
        for msg in reversed(messages):
            result.append({"role": msg.role, "content": msg.content})
        return result
    except Exception as e:
        print(f"Error loading recent messages: {e}")
        return []


def get_or_create_chat(session_id: str, user_name: str | None = None, user_profile: dict | None = None, user_id: str | None = None):
    """
    Get existing chat session or create a new one.
    
    Args:
        session_id: Unique identifier for the chat session
        user_name: Resolved user display name
        user_profile: User profile dict (school, department, etc.) from user_profiles
        user_id: User ID for memory loading
    
    Returns:
        Chat object for this session
    """
    global _chat_sessions
    
    user_name = _normalize_user_name(user_name)
    existing = _chat_sessions.get(session_id)
    if existing is None:
        client = get_client()
        chat = client.chats.create(
            model=get_model_name(),
            config={
                "system_instruction": get_system_prompt(user_name, user_profile, user_id=user_id),
                "temperature": get_temperature(),
            },
        )

        recent = _load_recent_messages(user_id)
        if recent:
            context_lines = []
            for msg in recent:
                role_label = "Kullanıcı" if msg["role"] == "user" else "Maya"
                context_lines.append(f"{role_label}: {msg['content']}")
            context_text = (
                "ÖNCEKİ KONUŞMA GEÇMİŞİ (kullanıcıyla daha önce yapılan son konuşmalar):\n"
                + "\n".join(context_lines)
                + "\n\nYukarıdaki konuşma geçmişini hatırla. Kullanıcı bir konuya devam etmek isterse "
                "bu bağlamı kullanarak doğrudan yanıt ver, tekrar sorma."
            )
            try:
                chat.send_message(context_text)
            except Exception as e:
                print(f"Error injecting chat history: {e}")

        _chat_sessions[session_id] = {"chat": chat, "user_name": user_name, "user_profile": user_profile}

    return _chat_sessions[session_id]["chat"]


def get_gemini_response(session_id: str, user_message: str, user_name: str | None = None, user_profile: dict | None = None, user_id: str | None = None) -> str:
    """
    Get response from Gemini API using chat session.
    
    Args:
        session_id: Unique identifier for the chat session
        user_message: The user's message
        user_name: Resolved user display name
        user_profile: User profile (school, department, etc.) for system prompt
        user_id: User ID for memory loading
    
    Returns:
        Response text or error message
    """
    try:
        chat = get_or_create_chat(session_id, user_name=user_name, user_profile=user_profile, user_id=user_id)
        response = chat.send_message(user_message)
        return response.text.strip()
    except Exception as e:
        print(f"Gemini API error: {e}")
        return "Şu an yanıt veremiyorum. Lütfen daha sonra tekrar deneyin."


def get_gemini_response_with_image(session_id: str, user_message: str, image_base64: str, mime_type: str = 'image/jpeg', user_name: str | None = None, user_profile: dict | None = None, user_id: str | None = None) -> str:
    """
    Get response from Gemini API with image.
    
    Args:
        session_id: Unique identifier for the chat session
        user_message: The user's message/question about the image
        image_base64: Base64 encoded image data
        mime_type: Image MIME type (image/jpeg, image/png, etc.)
        user_name: Resolved user display name
        user_profile: User profile for system prompt
    
    Returns:
        Response text or error message
    """
    try:
        client = get_client()
        
        # Decode base64 to bytes
        image_bytes = base64.b64decode(image_base64)
        
        # Build the prompt with system instruction (include profile so AI knows user context)
        system_prompt = get_system_prompt(user_name=_normalize_user_name(user_name), user_profile=user_profile, user_id=user_id)
        full_prompt = f"{system_prompt}\n\nKullanıcı bir görsel paylaştı. Kullanıcının mesajı: {user_message or 'Bu görseli açıkla.'}"
        
        response = client.models.generate_content(
            model=get_model_name(),
            contents=[
                types.Part.from_bytes(
                    data=image_bytes,
                    mime_type=mime_type,
                ),
                full_prompt
            ],
            config={
                "temperature": get_temperature()
            }
        )
        
        return response.text.strip()
    except Exception as e:
        print(f"Gemini Vision API error: {e}")
        return "Görsel işlenirken bir hata oluştu. Lütfen tekrar deneyin."


def clear_session(session_id: str) -> bool:
    """
    Clear a chat session (start fresh conversation).
    
    Args:
        session_id: Session to clear
    
    Returns:
        True if session was cleared, False if it didn't exist
    """
    global _chat_sessions
    if session_id in _chat_sessions:
        del _chat_sessions[session_id]
        return True
    return False


def clear_all_sessions():
    """Clear all chat sessions (useful when prompt changes)."""
    global _chat_sessions
    _chat_sessions = {}
