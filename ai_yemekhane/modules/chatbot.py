"""
Modül 3: Chatbot Yemekhane Asistanı
─────────────────────────────────────────────
LLM (Gemini API) tabanlı yemekhane asistan chatbot modülü.
Kullanıcılara menü, besin değeri, diyet önerisi gibi
konularda yardımcı olur.

Kullanılan teknolojiler:
  - Google Generative AI (Gemini) API
"""

from typing import Any

from config import active_config

# ─── Sabitler ──────────────────────────────────────────────────────
SYSTEM_PROMPT = """
Sen bir üniversite yemekhane asistanısın. Görevlerin:
1. Bugünkü ve haftalık menü hakkında bilgi vermek
2. Yemeklerin besin değerlerini açıklamak
3. Kişiselleştirilmiş diyet önerileri sunmak
4. Kalori hesaplama ve günlük alım takibi yapma
5. Sağlıklı beslenme tavsiyeleri vermek

Kurallar:
- Türkçe yanıt ver
- Kısa ve öz cevaplar ver
- Bilmediğin konularda "Bu konuda yardımcı olamıyorum" de
- Tıbbi tavsiye verme, sadece genel beslenme bilgisi paylaş
- Samimi ve yardımsever ol
"""


# ═══════════════════════════════════════════════════════════════════
# FONKSİYON: Chatbot Başlatma
# ═══════════════════════════════════════════════════════════════════
def init_chatbot(api_key: str | None = None) -> Any:
    """
    Gemini API ile chatbot'u başlatır.

    Args:
        api_key: Google Gemini API anahtarı.
            None ise config'den okunur.

    Returns:
        Chatbot model nesnesi (şu an placeholder olarak None).

    TODO:
        - google.generativeai kütüphanesini kullan
        - Gemini Pro modeli ile chat oturumu başlat
        - System prompt'u ayarla
        - Hata yönetimi (API key yoksa, rate limit, vb.)
    """
    key = api_key or active_config.GEMINI_API_KEY

    if not key:
        print("⚠️ GEMINI_API_KEY ayarlanmamış! Chatbot placeholder modda çalışacak.")
        return None

    print("⏳ Gemini chatbot başlatılıyor...")

    # TODO: Gerçek Gemini API başlatma
    # import google.generativeai as genai
    # genai.configure(api_key=key)
    # model = genai.GenerativeModel("gemini-pro")
    # chat = model.start_chat(history=[])
    model = None

    print("✅ Chatbot başlatıldı (placeholder).")
    return model


# ═══════════════════════════════════════════════════════════════════
# FONKSİYON: Chatbot Yanıtı Al
# ═══════════════════════════════════════════════════════════════════
def get_response(
    model: Any,
    user_message: str,
    chat_history: list[dict] | None = None,
    context: dict | None = None,
) -> dict:
    """
    Kullanıcı mesajına chatbot yanıtı üretir.

    Args:
        model: Başlatılmış chatbot modeli.
        user_message: Kullanıcının mesajı.
        chat_history: Önceki mesaj geçmişi.
            [{"role": "user"|"assistant", "content": str}, ...]
        context: Ek bağlam bilgisi (bugünkü menü, vb.).

    Returns:
        dict: {
            "response": str,        # Chatbot'un yanıtı
            "suggestions": list,     # Önerilen takip soruları
            "detected_intent": str,  # Tespit edilen niyet
        }

    TODO:
        - Gemini API ile gerçek yanıt üretme
        - Bağlam (context) entegrasyonu
        - Intent detection (menü sorgusu, besin değeri, öneri, vb.)
        - Yanıt formatlama
    """
    print(f"💬 Kullanıcı mesajı: {user_message}")

    # TODO: Gerçek Gemini API çağrısı
    # if model:
    #     prompt = f"{SYSTEM_PROMPT}\n\nBağlam: {context}\n\nKullanıcı: {user_message}"
    #     response = model.generate_content(prompt)
    #     return {
    #         "response": response.text,
    #         "suggestions": [],
    #         "detected_intent": "genel",
    #     }

    # Placeholder: Basit kural tabanlı yanıt
    mesaj_kucuk = user_message.lower()

    if "menü" in mesaj_kucuk or "menu" in mesaj_kucuk:
        yanit = (
            "Bugünkü menümüz: Mercimek Çorbası, Tavuk Sote, "
            "Pirinç Pilavı, Sütlaç ve Mevsim Salata. "
            "Afiyet olsun! 😊"
        )
        niyet = "menu_sorgusu"
        oneriler = [
            "Kaç kalori bu menü?",
            "Yarınki menü ne?",
            "Diyet önerisi ver",
        ]

    elif "kalori" in mesaj_kucuk:
        yanit = (
            "Bugünkü menünün toplam kalorisi yaklaşık 720 kcal'dir. "
            "Günlük 2000 kcal hedefinin %36'sı. 📊"
        )
        niyet = "kalori_sorgusu"
        oneriler = [
            "Hangi yemek en düşük kalorili?",
            "Protein değerleri nedir?",
        ]

    elif "merhaba" in mesaj_kucuk or "selam" in mesaj_kucuk:
        yanit = (
            "Merhaba! 👋 Ben yemekhane asistanıyım. "
            "Menü, besin değerleri veya diyet önerileri "
            "hakkında yardımcı olabilirim. Ne sormak istersiniz?"
        )
        niyet = "selamlama"
        oneriler = [
            "Bugünkü menü ne?",
            "Sağlıklı bir öğün öner",
            "Hangi yemekler glutensiz?",
        ]

    else:
        yanit = (
            "Anlıyorum. Menü bilgisi, besin değerleri veya "
            "diyet önerileri konusunda size yardımcı olabilirim. "
            "Başka bir sorunuz var mı? 🤔"
        )
        niyet = "genel"
        oneriler = [
            "Bugünkü menü ne?",
            "Kalori hesapla",
            "Yemek öner",
        ]

    print(f"🤖 Yanıt: {yanit[:50]}...")
    return {
        "response": yanit,
        "suggestions": oneriler,
        "detected_intent": niyet,
    }


# ═══════════════════════════════════════════════════════════════════
# FONKSİYON: Yemek Önerisi Al
# ═══════════════════════════════════════════════════════════════════
def get_meal_recommendation(
    model: Any,
    kullanici_bilgi: dict,
    bugunki_menu: dict | None = None,
) -> dict:
    """
    Kullanıcı profiline göre kişiselleştirilmiş yemek önerisi verir.

    Args:
        model: Chatbot modeli.
        kullanici_bilgi: Kullanıcı bilgileri.
            {"kalori_hedefi": float, "alinan_kalori": float, ...}
        bugunki_menu: Bugünkü menü bilgisi (opsiyonel).

    Returns:
        dict: {
            "oneri": str,
            "kalan_kalori": float,
            "onerilen_yemekler": list[str],
        }

    TODO:
        - Gemini API ile kişiselleştirilmiş öneri
        - Kalan kalori hesabına göre yemek önerisi
        - Diyet kısıtlamaları (vejetaryen, glutensiz, vb.)
    """
    kalori_hedefi = kullanici_bilgi.get("kalori_hedefi", 2000)
    alinan = kullanici_bilgi.get("alinan_kalori", 0)
    kalan = kalori_hedefi - alinan

    # Placeholder
    return {
        "oneri": f"Günlük hedefinize {kalan:.0f} kcal kaldı. "
                 f"Hafif bir öğün tercih etmenizi öneririm.",
        "kalan_kalori": kalan,
        "onerilen_yemekler": ["Mevsim Salata", "Mercimek Çorbası"],
    }
