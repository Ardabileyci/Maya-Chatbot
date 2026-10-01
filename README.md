# Maya – Akademik Asistan

Öğrencilerin derslerde takıldıkları konularda sorularını yanıtlayan, **Google Gemini** destekli bir chatbot.

## Özellikler

- Akademik üslupla, öğretici ve açıklayıcı yanıtlar
- Programlama, matematik, fen bilimleri vb. konularda destek
- Sohbet geçmişi: yeni sohbet açma, eski sohbetleri görüntüleme ve silme
- Kullanıcıya özel bağlam (MySQL'deki kullanıcı ve eğitim bilgileri)
- Responsive arayüz

## Teknolojiler

- **Backend:** Python, Django 5
- **Frontend:** HTML, CSS, JavaScript (Vanilla)
- **LLM:** Google Gemini (`google-genai`)
- **Veritabanı:** SQLite (sohbet kayıtları) + MySQL (kullanıcı verileri)

## Proje Yapısı

```
server/
├── manage.py
├── requirements.txt
├── .env.example           # Ortam değişkenleri şablonu
├── maya_project/          # Django ayarları ve URL'ler
├── chatbot/               # API view'ları, modeller, Gemini istemcisi
│   ├── gemini_client.py
│   ├── views.py
│   └── db_router.py
└── client/                # Arayüz (Django tarafından sunulur)
    ├── index.html
    ├── styles.css
    ├── app.js
    └── assets/
```

## Kurulum

```bash
git clone <repo-url>
cd mayai/server
python3 -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env            # sonra .env içini doldur
python manage.py migrate
python manage.py runserver
```

Tarayıcıda `http://localhost:8000` adresini aç.

Gemini API anahtarını [Google AI Studio](https://aistudio.google.com/app/apikey)'dan alabilirsin.

## API Endpoint'leri

| Metot | Yol | Açıklama |
|-------|-----|----------|
| GET | `/api/health` | Sağlık kontrolü |
| POST | `/api/chat` | Mesaj gönder, Maya'nın yanıtını al |
| POST | `/api/new-chat` | Yeni sohbet başlat |
| DELETE | `/api/chat/<session_id>` | Sohbeti sil |
| GET | `/api/chat-history/<session_id>` | Sohbet geçmişi |
| GET | `/api/user-sessions/<user_id>` | Kullanıcının sohbetleri |
| GET | `/api/user-chat-history/<user_id>` | Kullanıcının tüm geçmişi |

## Notlar

- `settings.py` geliştirme için ayarlı (`DEBUG=True`, tüm host/origin'lere izin). Canlıya alırken bunları kısıtla.
- Gemini ücretsiz sürümünün günlük kota sınırları vardır.
