"""
Modül 3: Chatbot Yemekhane Asistanı
─────────────────────────────────────────────
Google Gemini 2.0 Flash API tabanlı yemekhane asistan chatbot modülü.
Kullanıcılara menü, besin değeri, kalori takibi ve diyet önerisi
konularında yardımcı olur.

Özellikler:
  - Gemini 2.0 Flash (ücretsiz katman)
  - Function Calling (Tool Use)
  - Session bazlı konuşma geçmişi
  - Günlük kalori takibi
"""

from datetime import date, datetime
from typing import Any

import google.generativeai as genai

from config import active_config
from models import SessionLocal, Yemek, Menu, Kullanici, KullaniciYemekLog, MenuPuanlama, Alert

# ─── Sabitler ──────────────────────────────────────────────────────
SYSTEM_PROMPT = """\
Sen bir üniversite yemekhane beslenme asistanısın. Adın "Yemekhane Asistanı".

Görevlerin:
1. Öğrencilere yedikleri yemeklerin besin değerlerini söylemek
2. Günlük kalori takibi yapmak
3. Sağlıklı beslenme önerileri vermek
4. Bugünkü menü hakkında bilgi vermek
5. Yemek kayıtlarını tutmak
6. Yemek puanlamaları hakkında bilgi vermek
7. Öğrencilerin yemek puanlamasına yardımcı olmak

Kurallar:
- Her zaman Türkçe yanıt ver
- Kısa, samimi ve yardımsever ol
- Kullanıcı yemek söylediğinde, önce get_nutrition aracıyla besin değerlerini kontrol et
- Yemek kaydı istendiğinde log_meal aracını kullan
- Günlük rapor istendiğinde get_daily_report aracını kullan
- Menü sorulduğunda get_today_menu aracını kullan
- Yemek puanları sorulduğunda get_meal_ratings aracını kullan
- Kullanıcı puan vermek istediğinde rate_meal aracını kullan
- Besin değerlerini söylerken emoji kullan (🍽️ 📊 💪 🥗 ⭐)
- Tıbbi tavsiye verme, sadece genel beslenme bilgisi paylaş
- Bilmediğin konularda "Bu konuda yardımcı olamıyorum" de
- Kullanıcı birden fazla yemek söylerse, her birinin besin değerini ayrı ayrı kontrol et
- Günlük kalori hedefi varsayılan 2000 kcal'dir (kullanıcıya özel hedef varsa onu kullan)
- Puanlama tamamen anonimdir, kullanıcı ID gerekmez
- İsraf ve uyarı sorulduğunda get_waste_info aracını kullan
- Aktif uyarılar sorulduğunda get_alerts_info aracını kullan
"""

# ─── Function Calling Tool Tanımları ──────────────────────────────
TOOL_DEFINITIONS = [
    {
        "function_declarations": [
            {
                "name": "get_nutrition",
                "description": "Veritabanından bir yemeğin besin değerlerini (kalori, protein, karbonhidrat, yağ) getirir. Kullanıcı bir yemek adı söylediğinde bu aracı kullan.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "yemek_adi": {
                            "type": "string",
                            "description": "Besin değeri sorgulanacak yemeğin adı. Örnek: 'Mercimek Çorbası', 'Pirinç Pilavı', 'Kuru Fasulye'"
                        }
                    },
                    "required": ["yemek_adi"]
                }
            },
            {
                "name": "log_meal",
                "description": "Kullanıcının yediği yemeği veritabanına kaydeder. Kullanıcı bir yemek yediğini söylediğinde bu aracı kullan.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "kullanici_id": {
                            "type": "integer",
                            "description": "Kullanıcının ID'si"
                        },
                        "yemek_adi": {
                            "type": "string",
                            "description": "Yenen yemeğin adı. Örnek: 'Kuru Fasulye'"
                        },
                        "miktar": {
                            "type": "number",
                            "description": "Porsiyon miktarı (varsayılan 1.0). Örnek: 1.0 = 1 porsiyon, 0.5 = yarım porsiyon"
                        }
                    },
                    "required": ["kullanici_id", "yemek_adi"]
                }
            },
            {
                "name": "get_daily_report",
                "description": "Kullanıcının belirtilen tarihteki günlük beslenme raporunu (toplam kalori, protein, karbonhidrat, yağ ve yenen yemekler) getirir.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "kullanici_id": {
                            "type": "integer",
                            "description": "Kullanıcının ID'si"
                        },
                        "tarih": {
                            "type": "string",
                            "description": "Rapor tarihi (YYYY-MM-DD formatında). Boş bırakılırsa bugünün tarihi kullanılır."
                        }
                    },
                    "required": ["kullanici_id"]
                }
            },
            {
                "name": "get_today_menu",
                "description": "Bugünkü yemekhane menüsünü getirir (çorba, ana yemek, pilav/makarna, tatlı, salata).",
                "parameters": {
                    "type": "object",
                    "properties": {},
                    "required": []
                }
            },
            {
                "name": "get_meal_ratings",
                "description": "Bir yemeğin anonim puanlama bilgilerini getirir. Ortalama puanı, toplam oy sayısı ve son yorumları döndürür. Kullanıcı 'puanlar nasıl', 'en beğenilen yemek' gibi sorular sorduğunda bu aracı kullan.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "yemek_adi": {
                            "type": "string",
                            "description": "Puanlama bilgisi istenen yemeğin adı. Boş bırakılırsa bugünün tüm puanları döner."
                        }
                    },
                    "required": []
                }
            },
            {
                "name": "rate_meal",
                "description": "Bir yemeğe anonim olarak 1-5 arası yıldız puan verir. Kullanıcı 'çorbaya 4 puan veriyorum' gibi söylediğinde bu aracı kullan.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "yemek_adi": {
                            "type": "string",
                            "description": "Puanlanacak yemeğin adı"
                        },
                        "puan": {
                            "type": "integer",
                            "description": "1-5 arası yıldız puanı"
                        },
                        "yorum": {
                            "type": "string",
                            "description": "Opsiyonel yorum"
                        }
                    },
                    "required": ["yemek_adi", "puan"]
                }
            },
            {
                "name": "get_waste_info",
                "description": "Yemek israfı hakkında bilgi verir. En çok israf edilen yemekler, haftalık israf özeti gibi. Kullanıcı 'israf', 'atık', 'artık' gibi kelimeler kullandığında bu aracı kullan.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "yemek_adi": {
                            "type": "string",
                            "description": "Belirli bir yemeğin israf bilgisi. Boş bırakılırsa genel israf raporu."
                        }
                    },
                    "required": []
                }
            },
            {
                "name": "get_alerts_info",
                "description": "Aktif uyarıları getirir. 'Hangi yemekler uyarıda?', 'Kritik uyarılar neler?' sorularında kullan.",
                "parameters": {
                    "type": "object",
                    "properties": {},
                    "required": []
                }
            }
        ]
    }
]

# ─── Session Yönetimi (In-Memory) ────────────────────────────────
# kullanici_id -> [{"role": "user"|"model", "parts": [...]}]
_chat_sessions: dict[int, list[dict]] = {}

MAX_HISTORY_LENGTH = 10  # Son 10 mesaj


def _get_chat_history(kullanici_id: int) -> list[dict]:
    """Kullanıcının chat geçmişini döndürür (son MAX_HISTORY_LENGTH mesaj)."""
    if kullanici_id not in _chat_sessions:
        _chat_sessions[kullanici_id] = []
    return _chat_sessions[kullanici_id][-MAX_HISTORY_LENGTH * 2:]


def _add_to_history(kullanici_id: int, role: str, parts: list):
    """Chat geçmişine mesaj ekler."""
    if kullanici_id not in _chat_sessions:
        _chat_sessions[kullanici_id] = []
    _chat_sessions[kullanici_id].append({"role": role, "parts": parts})
    # Bellek yönetimi: çok uzun geçmişi kırp
    if len(_chat_sessions[kullanici_id]) > MAX_HISTORY_LENGTH * 4:
        _chat_sessions[kullanici_id] = _chat_sessions[kullanici_id][-MAX_HISTORY_LENGTH * 2:]


# ═══════════════════════════════════════════════════════════════════
# TOOL FONKSİYONLARI (Veritabanı İşlemleri)
# ═══════════════════════════════════════════════════════════════════

def _tool_get_nutrition(yemek_adi: str, db=None) -> dict:
    """Veritabanından yemek besin değerini sorgular."""
    close_db = False
    if db is None:
        db = SessionLocal()
        close_db = True

    try:
        yemek = (
            db.query(Yemek)
            .filter(Yemek.ad.ilike(f"%{yemek_adi}%"))
            .first()
        )

        if yemek:
            return {
                "bulundu": True,
                "yemek_adi": yemek.ad,
                "kalori": yemek.kalori,
                "protein": yemek.protein,
                "karbonhidrat": yemek.karbonhidrat,
                "yag": yemek.yag,
                "kategori": yemek.kategori
            }
        else:
            return {
                "bulundu": False,
                "yemek_adi": yemek_adi,
                "mesaj": f"'{yemek_adi}' veritabanında bulunamadı."
            }
    finally:
        if close_db:
            db.close()


def _tool_log_meal(kullanici_id: int, yemek_adi: str, miktar: float = 1.0, db=None) -> dict:
    """Kullanıcının yemek kaydını veritabanına ekler."""
    close_db = False
    if db is None:
        db = SessionLocal()
        close_db = True

    try:
        # Yemeği bul
        yemek = (
            db.query(Yemek)
            .filter(Yemek.ad.ilike(f"%{yemek_adi}%"))
            .first()
        )

        if not yemek:
            return {
                "basarili": False,
                "mesaj": f"'{yemek_adi}' veritabanında bulunamadı. Kayıt eklenemedi."
            }

        # Kullanıcı kontrolü
        kullanici = db.query(Kullanici).filter(Kullanici.id == kullanici_id).first()
        if not kullanici:
            return {
                "basarili": False,
                "mesaj": f"ID={kullanici_id} kullanıcı bulunamadı."
            }

        # Log ekle
        log = KullaniciYemekLog(
            kullanici_id=kullanici_id,
            yemek_id=yemek.id,
            tarih=datetime.now(),
            miktar=miktar,
            kaynak_tipi="chatbot"
        )
        db.add(log)
        db.commit()

        return {
            "basarili": True,
            "yemek_adi": yemek.ad,
            "miktar": miktar,
            "kalori": yemek.kalori * miktar,
            "protein": yemek.protein * miktar,
            "karbonhidrat": yemek.karbonhidrat * miktar,
            "yag": yemek.yag * miktar,
            "mesaj": f"{yemek.ad} ({miktar} porsiyon) kaydedildi."
        }
    finally:
        if close_db:
            db.close()


def _tool_get_daily_report(kullanici_id: int, tarih: str | None = None, db=None) -> dict:
    """Kullanıcının günlük beslenme raporunu döndürür."""
    close_db = False
    if db is None:
        db = SessionLocal()
        close_db = True

    try:
        # Tarih belirle
        if tarih:
            rapor_tarihi = date.fromisoformat(tarih)
        else:
            rapor_tarihi = date.today()

        # Kullanıcı kontrolü
        kullanici = db.query(Kullanici).filter(Kullanici.id == kullanici_id).first()
        if not kullanici:
            return {
                "basarili": False,
                "mesaj": f"ID={kullanici_id} kullanıcı bulunamadı."
            }

        # O günkü loglar
        gun_baslangic = datetime(rapor_tarihi.year, rapor_tarihi.month, rapor_tarihi.day)
        gun_bitis = datetime(rapor_tarihi.year, rapor_tarihi.month, rapor_tarihi.day, 23, 59, 59)

        loglar = (
            db.query(KullaniciYemekLog)
            .filter(
                KullaniciYemekLog.kullanici_id == kullanici_id,
                KullaniciYemekLog.tarih >= gun_baslangic,
                KullaniciYemekLog.tarih <= gun_bitis,
            )
            .all()
        )

        toplam_kalori = 0.0
        toplam_protein = 0.0
        toplam_karbonhidrat = 0.0
        toplam_yag = 0.0
        yenen_yemekler = []

        for log in loglar:
            yemek = db.query(Yemek).filter(Yemek.id == log.yemek_id).first()
            if yemek:
                miktar = log.miktar
                kalori = yemek.kalori * miktar
                toplam_kalori += kalori
                toplam_protein += yemek.protein * miktar
                toplam_karbonhidrat += yemek.karbonhidrat * miktar
                toplam_yag += yemek.yag * miktar
                yenen_yemekler.append({
                    "yemek": yemek.ad,
                    "miktar": miktar,
                    "kalori": round(kalori, 1)
                })

        hedef = kullanici.gunluk_kalori_hedefi
        kalan = hedef - toplam_kalori

        return {
            "basarili": True,
            "tarih": str(rapor_tarihi),
            "kullanici_adi": kullanici.ad,
            "toplam_kalori": round(toplam_kalori, 1),
            "toplam_protein": round(toplam_protein, 1),
            "toplam_karbonhidrat": round(toplam_karbonhidrat, 1),
            "toplam_yag": round(toplam_yag, 1),
            "kalori_hedefi": hedef,
            "kalan_kalori": round(kalan, 1),
            "hedef_yuzdesi": round((toplam_kalori / hedef) * 100, 1) if hedef > 0 else 0,
            "yenen_yemekler": yenen_yemekler,
            "ogun_sayisi": len(yenen_yemekler)
        }
    finally:
        if close_db:
            db.close()


def _tool_get_today_menu(db=None) -> dict:
    """Bugünkü menüyü veritabanından getirir."""
    close_db = False
    if db is None:
        db = SessionLocal()
        close_db = True

    try:
        bugun = date.today()
        menu = db.query(Menu).filter(Menu.tarih == bugun).first()

        if menu:
            return {
                "bulundu": True,
                "tarih": str(bugun),
                "gun": menu.gun,
                "corba": menu.corba or "Belirtilmemiş",
                "ana_yemek": menu.ana_yemek or "Belirtilmemiş",
                "pilav": menu.pilav or "Belirtilmemiş",
                "tatli": menu.tatli or "Belirtilmemiş",
                "salata": menu.salata or "Belirtilmemiş"
            }
        else:
            return {
                "bulundu": False,
                "tarih": str(bugun),
                "mesaj": f"Bugün ({bugun}) için menü bulunamadı."
            }
    finally:
        if close_db:
            db.close()


def _tool_get_meal_ratings(yemek_adi: str = None, db=None) -> dict:
    """Yemek puanlama bilgilerini veritabanından getirir."""
    from sqlalchemy import func as sqla_func

    close_db = False
    if db is None:
        db = SessionLocal()
        close_db = True

    try:
        bugun = date.today()

        if yemek_adi:
            # Belirli bir yemeğin puanları
            result = (
                db.query(
                    sqla_func.avg(MenuPuanlama.puan).label("ortalama"),
                    sqla_func.count(MenuPuanlama.id).label("toplam_oy"),
                )
                .filter(MenuPuanlama.yemek_adi.ilike(f"%{yemek_adi}%"))
                .first()
            )

            # Son yorumlar
            son_yorumlar = (
                db.query(MenuPuanlama)
                .filter(
                    MenuPuanlama.yemek_adi.ilike(f"%{yemek_adi}%"),
                    MenuPuanlama.yorum.isnot(None),
                    MenuPuanlama.yorum != "",
                )
                .order_by(MenuPuanlama.created_at.desc())
                .limit(3)
                .all()
            )

            if result and result.toplam_oy and result.toplam_oy > 0:
                return {
                    "bulundu": True,
                    "yemek_adi": yemek_adi,
                    "ortalama_puan": round(float(result.ortalama), 1),
                    "toplam_oy": result.toplam_oy,
                    "son_yorumlar": [
                        {"puan": y.puan, "yorum": y.yorum}
                        for y in son_yorumlar
                    ],
                }
            return {
                "bulundu": False,
                "yemek_adi": yemek_adi,
                "mesaj": f"'{yemek_adi}' için henüz puanlama yapılmamış."
            }
        else:
            # Bugünün tüm puanları
            sonuclar = (
                db.query(
                    MenuPuanlama.yemek_adi,
                    sqla_func.avg(MenuPuanlama.puan).label("ortalama"),
                    sqla_func.count(MenuPuanlama.id).label("toplam_oy"),
                )
                .filter(MenuPuanlama.tarih == bugun)
                .group_by(MenuPuanlama.yemek_adi)
                .all()
            )

            if sonuclar:
                return {
                    "bulundu": True,
                    "tarih": str(bugun),
                    "yemekler": [
                        {
                            "yemek_adi": row.yemek_adi,
                            "ortalama": round(float(row.ortalama), 1),
                            "toplam_oy": row.toplam_oy,
                        }
                        for row in sonuclar
                    ],
                }
            return {
                "bulundu": False,
                "tarih": str(bugun),
                "mesaj": "Bugün için henüz puanlama yapılmamış."
            }
    finally:
        if close_db:
            db.close()


def _tool_rate_meal(yemek_adi: str, puan: int, yorum: str = None, db=None) -> dict:
    """Anonim olarak yemek puanlaması yapar."""
    close_db = False
    if db is None:
        db = SessionLocal()
        close_db = True

    try:
        if puan < 1 or puan > 5:
            return {"basarili": False, "mesaj": "Puan 1-5 arası olmalıdır."}

        yeni_puan = MenuPuanlama(
            tarih=date.today(),
            yemek_adi=yemek_adi,
            kategori="ana_yemek",  # Varsayılan, chatbot tam kategoriyi bilmeyebilir
            puan=puan,
            yorum=yorum,
        )

        # Kategoriyi tahmin et
        yemek = db.query(Yemek).filter(Yemek.ad.ilike(f"%{yemek_adi}%")).first()
        if yemek:
            yeni_puan.yemek_adi = yemek.ad  # Doğru isim
            yeni_puan.kategori = yemek.kategori

        # Bugünkü menüdeki kategoriyi kontrol et
        bugun_menu = db.query(Menu).filter(Menu.tarih == date.today()).first()
        if bugun_menu:
            for kat in ["corba", "ana_yemek", "pilav", "tatli", "salata"]:
                menu_yemek = getattr(bugun_menu, kat, None)
                if menu_yemek and yemek_adi.lower() in menu_yemek.lower():
                    yeni_puan.kategori = kat
                    yeni_puan.yemek_adi = menu_yemek
                    break

        db.add(yeni_puan)
        db.commit()

        return {
            "basarili": True,
            "yemek_adi": yeni_puan.yemek_adi,
            "puan": puan,
            "mesaj": f"{yeni_puan.yemek_adi} için {puan}⭐ puanınız kaydedildi. Teşekkürler!"
        }
    finally:
        if close_db:
            db.close()


def _tool_get_waste_info(yemek_adi: str = None, db=None) -> dict:
    """Yemek israf bilgisini getirir."""
    try:
        from modules.waste_analyzer import get_weekly_waste_report, calculate_waste_score
        if yemek_adi:
            return calculate_waste_score(yemek_adi, db=db)
        else:
            return get_weekly_waste_report(db=db)
    except Exception as e:
        return {"hata": str(e)}


def _tool_get_alerts_info(db=None) -> dict:
    """Aktif uyarıları getirir."""
    try:
        from modules.alert_system import get_active_alerts
        return get_active_alerts(db=db)
    except Exception as e:
        return {"hata": str(e)}


# ─── Tool Dispatch ────────────────────────────────────────────────
def _execute_tool(function_name: str, function_args: dict, db=None) -> dict:
    """Function calling sonuçlarını çalıştırır."""
    if function_name == "get_nutrition":
        return _tool_get_nutrition(
            yemek_adi=function_args.get("yemek_adi", ""),
            db=db,
        )
    elif function_name == "log_meal":
        return _tool_log_meal(
            kullanici_id=function_args.get("kullanici_id", 0),
            yemek_adi=function_args.get("yemek_adi", ""),
            miktar=function_args.get("miktar", 1.0),
            db=db,
        )
    elif function_name == "get_daily_report":
        return _tool_get_daily_report(
            kullanici_id=function_args.get("kullanici_id", 0),
            tarih=function_args.get("tarih"),
            db=db,
        )
    elif function_name == "get_today_menu":
        return _tool_get_today_menu(db=db)
    elif function_name == "get_meal_ratings":
        return _tool_get_meal_ratings(
            yemek_adi=function_args.get("yemek_adi", ""),
            db=db,
        )
    elif function_name == "rate_meal":
        return _tool_rate_meal(
            yemek_adi=function_args.get("yemek_adi", ""),
            puan=int(function_args.get("puan", 3)),
            yorum=function_args.get("yorum"),
            db=db,
        )
    elif function_name == "get_waste_info":
        return _tool_get_waste_info(
            yemek_adi=function_args.get("yemek_adi", ""),
            db=db,
        )
    elif function_name == "get_alerts_info":
        return _tool_get_alerts_info(db=db)
    else:
        return {"hata": f"Bilinmeyen fonksiyon: {function_name}"}


# ═══════════════════════════════════════════════════════════════════
# FONKSİYON: Chatbot Başlatma
# ═══════════════════════════════════════════════════════════════════
def init_chatbot(api_key: str | None = None) -> Any:
    """
    Gemini API ile chatbot modelini yapılandırır ve döndürür.

    Returns:
        genai.GenerativeModel veya None (API key yoksa)
    """
    key = api_key or active_config.GEMINI_API_KEY

    if not key:
        print("⚠️ GEMINI_API_KEY ayarlanmamış! Chatbot çalışmayacak.")
        return None

    print("⏳ Gemini 2.0 Flash chatbot başlatılıyor...")

    genai.configure(api_key=key)

    model = genai.GenerativeModel(
        model_name="gemini-2.5-flash",
        system_instruction=SYSTEM_PROMPT,
        tools=TOOL_DEFINITIONS,
    )

    print("✅ Gemini 2.0 Flash chatbot başlatıldı.")
    return model


# ═══════════════════════════════════════════════════════════════════
# FONKSİYON: Chatbot Yanıtı Al
# ═══════════════════════════════════════════════════════════════════
def get_response(
    model: Any,
    user_message: str,
    kullanici_id: int = 0,
    context: dict | None = None,
    db=None,
) -> dict:
    """
    Kullanıcı mesajına chatbot yanıtı üretir.

    Args:
        model: Başlatılmış Gemini modeli.
        user_message: Kullanıcının mesajı.
        kullanici_id: Kullanıcı ID (session ve function calling için).
        context: Ek bağlam bilgisi.
        db: SQLAlchemy DB session.

    Returns:
        dict: {
            "response": str,
            "suggestions": list,
            "gunluk_toplam": float,
        }
    """
    print(f"💬 [{kullanici_id}] Kullanıcı: {user_message}")

    # Model yoksa placeholder yanıt
    if model is None:
        return _placeholder_response(user_message)

    # Mesajı hazırla — bağlam bilgisi ekle
    enriched_message = user_message
    if context and context.get("bugunki_menu"):
        menu = context["bugunki_menu"]
        enriched_message += (
            f"\n\n[Sistem Bilgisi: Bugünkü menü: "
            f"Çorba: {menu.get('corba', '?')}, "
            f"Ana Yemek: {menu.get('ana_yemek', '?')}, "
            f"Pilav: {menu.get('pilav', '?')}, "
            f"Tatlı: {menu.get('tatli', '?')}, "
            f"Salata: {menu.get('salata', '?')}]"
        )

    if kullanici_id > 0:
        enriched_message += f"\n[Sistem Bilgisi: Kullanıcı ID = {kullanici_id}]"

    # Chat geçmişini al
    history = _get_chat_history(kullanici_id)

    try:
        # Chat oturumu başlat
        chat = model.start_chat(history=history)

        # Mesaj gönder
        response = chat.send_message(enriched_message)

        # Function calling loop — model tool çağrısı yapıyorsa handle et
        max_iterations = 5
        iteration = 0

        while response.candidates and iteration < max_iterations:
            candidate = response.candidates[0]
            content = candidate.content

            # Function call var mı kontrol et
            has_function_call = False
            for part in content.parts:
                if part.function_call:
                    has_function_call = True
                    break

            if not has_function_call:
                break

            # Her function call'ı çalıştır
            function_responses = []
            for part in content.parts:
                if part.function_call:
                    fn_name = part.function_call.name
                    fn_args = dict(part.function_call.args)

                    print(f"🔧 Tool çağrısı: {fn_name}({fn_args})")

                    # Eğer log_meal veya get_daily_report ise ve kullanici_id yoksa ekle
                    if fn_name in ("log_meal", "get_daily_report") and kullanici_id > 0:
                        fn_args.setdefault("kullanici_id", kullanici_id)

                    # Tool'u çalıştır
                    result = _execute_tool(fn_name, fn_args, db=db)
                    print(f"📋 Tool sonucu: {result}")

                    function_responses.append(
                        genai.protos.Part(
                            function_response=genai.protos.FunctionResponse(
                                name=fn_name,
                                response={"result": result}
                            )
                        )
                    )

            # Tool sonuçlarını Gemini'ye gönder
            response = chat.send_message(
                genai.protos.Content(parts=function_responses)
            )
            iteration += 1

        # Yanıt metnini al
        yanit_text = ""
        if response.candidates:
            for part in response.candidates[0].content.parts:
                if part.text:
                    yanit_text += part.text

        if not yanit_text:
            yanit_text = "Yanıt üretilirken bir sorun oluştu. Lütfen tekrar deneyin."

        # Chat geçmişine ekle
        _add_to_history(kullanici_id, "user", [enriched_message])
        _add_to_history(kullanici_id, "model", [yanit_text])

        # Günlük kalori toplamını hesapla
        gunluk_toplam = 0.0
        if kullanici_id > 0:
            rapor = _tool_get_daily_report(kullanici_id=kullanici_id, db=db)
            if rapor.get("basarili"):
                gunluk_toplam = rapor.get("toplam_kalori", 0.0)

        print(f"🤖 [{kullanici_id}] Yanıt: {yanit_text[:80]}...")

        return {
            "response": yanit_text,
            "suggestions": _generate_suggestions(user_message),
            "gunluk_toplam": gunluk_toplam,
        }

    except Exception as e:
        print(f"❌ Gemini API hatası: {e}")
        return {
            "response": f"Bir hata oluştu: {str(e)}. Lütfen tekrar deneyin.",
            "suggestions": ["Bugünkü menü ne?", "Yardım"],
            "gunluk_toplam": 0.0,
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
    """
    if model is None:
        kalori_hedefi = kullanici_bilgi.get("kalori_hedefi", 2000)
        alinan = kullanici_bilgi.get("alinan_kalori", 0)
        kalan = kalori_hedefi - alinan
        return {
            "oneri": f"Günlük hedefinize {kalan:.0f} kcal kaldı. "
                     f"Hafif bir öğün tercih etmenizi öneririm.",
            "kalan_kalori": kalan,
            "onerilen_yemekler": ["Mevsim Salata", "Mercimek Çorbası"],
        }

    try:
        prompt = (
            f"Kullanıcı bilgileri: {kullanici_bilgi}\n"
            f"Bugünkü menü: {bugunki_menu}\n\n"
            f"Bu kullanıcıya kişiselleştirilmiş yemek önerisi ver. "
            f"Kalan kalori miktarına göre menüden uygun yemekleri öner."
        )

        response = model.generate_content(prompt)
        yanit = response.text if response.text else "Öneri üretilemedi."

        kalori_hedefi = kullanici_bilgi.get("kalori_hedefi", 2000)
        alinan = kullanici_bilgi.get("alinan_kalori", 0)
        kalan = kalori_hedefi - alinan

        return {
            "oneri": yanit,
            "kalan_kalori": kalan,
            "onerilen_yemekler": [],
        }

    except Exception as e:
        print(f"❌ Yemek önerisi hatası: {e}")
        return {
            "oneri": "Öneri üretilirken bir hata oluştu.",
            "kalan_kalori": 0,
            "onerilen_yemekler": [],
        }


# ─── Yardımcı Fonksiyonlar ────────────────────────────────────────

def _generate_suggestions(user_message: str) -> list[str]:
    """Mesaja göre takip sorusu önerileri üretir."""
    mesaj = user_message.lower()

    if "menü" in mesaj or "menu" in mesaj:
        return [
            "Bu menünün toplam kalorisi ne kadar?",
            "Hangi yemek en düşük kalorili?",
            "Diyet için hangi yemeği seçmeliyim?",
        ]
    elif "kalori" in mesaj or "rapor" in mesaj:
        return [
            "Protein alımım yeterli mi?",
            "Akşam ne yemeliyim?",
            "Bu haftanın ortalaması nedir?",
        ]
    elif any(word in mesaj for word in ["yedim", "içtim", "yemek"]):
        return [
            "Günlük raporumu göster",
            "Kalan kalorimi söyle",
            "Bu yemeğe puan ver",
        ]
    elif any(word in mesaj for word in ["puan", "puanlama", "beğenilen", "yıldız", "oy"]):
        return [
            "En beğenilen yemek hangisi?",
            "Bugün yemekler nasıl puanlanmış?",
            "Çorbaya 4 puan veriyorum",
        ]
    elif any(word in mesaj for word in ["israf", "atık", "artık", "çöp"]):
        return [
            "Bu hafta en çok israf edilen yemek?",
            "Bugünkü israf oranı nedir?",
            "Hangi yemekler uyarıda?",
        ]
    elif any(word in mesaj for word in ["uyarı", "kritik", "alarm"]):
        return [
            "Aktif uyarılar neler?",
            "Kritik uyarılı yemekler hangileri?",
            "Bugünkü israf raporu",
        ]
    else:
        return [
            "Bugünkü menü ne?",
            "Günlük kalori raporumu göster",
            "Sağlıklı bir öğün öner",
        ]


def _placeholder_response(user_message: str) -> dict:
    """API key olmadığında basit placeholder yanıt döndürür."""
    return {
        "response": (
            "⚠️ Chatbot şu an aktif değil (API anahtarı ayarlanmamış). "
            "Lütfen .env dosyasında GEMINI_API_KEY değerini ayarlayın."
        ),
        "suggestions": ["Yardım"],
        "gunluk_toplam": 0.0,
    }
