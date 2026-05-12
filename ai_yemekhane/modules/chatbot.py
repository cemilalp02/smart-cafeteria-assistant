"""
Modül 3: Chatbot Yemekhane Asistanı
─────────────────────────────────────────────
Google Gemini 2.0 Flash API tabanlı yemekhane asistan chatbot modülü.
Kullanıcılara menü, besin değeri, puanlama ve genel beslenme
konularında yardımcı olur.

Özellikler:
  - Gemini 2.0 Flash (ücretsiz katman)
  - Function Calling (Tool Use)
  - Session bazlı konuşma geçmişi
  - Menü ve puanlama desteği
"""

import warnings
from datetime import date, timedelta
from typing import Any

# TODO(2027): google.generativeai paketi deprecated. Google'ın destek bitişinde
# (muhtemelen 2027) google.genai SDK'sına migration yapılmalı.
# Şimdilik FutureWarning'leri bastırıyoruz çünkü mevcut API sorunsuz çalışıyor.
with warnings.catch_warnings():
    warnings.simplefilter("ignore", FutureWarning)
    import google.generativeai as genai

from config import active_config
from models import SessionLocal, Yemek, Menu, MenuPuanlama, Alert, UretimLog

# ─── Sabitler ──────────────────────────────────────────────────────
SYSTEM_PROMPT = """\
Sen bir üniversite yemekhane beslenme asistanısın. Adın "Yemekhane Asistanı".

Görevlerin:
1. Öğrencilere yemeklerin besin değerlerini söylemek
2. Genel beslenme önerileri vermek
3. Bugünkü menü hakkında bilgi vermek
4. Yemek puanlamaları hakkında bilgi vermek
5. Öğrencilerin yemek puanlamasına yardımcı olmak

Kurallar:
- Her zaman Türkçe yanıt ver
- Kısa, samimi ve yardımsever ol
- Kullanıcı yemek söylediğinde, önce get_nutrition aracıyla besin değerlerini kontrol et
- Menü sorulduğunda get_today_menu aracını kullan
- Yemek puanları sorulduğunda get_meal_ratings aracını kullan
- Kullanıcı puan vermek istediğinde rate_meal aracını kullan
- Besin değerlerini söylerken emoji kullan (🍽️ 📊 💪 🥗 ⭐)
- Tıbbi tavsiye verme, sadece genel beslenme bilgisi paylaş
- Bilmediğin konularda "Bu konuda yardımcı olamıyorum" de
- Kullanıcı birden fazla yemek söylerse, her birinin besin değerini ayrı ayrı kontrol et
- Puanlama tamamen anonimdir, kullanıcı ID gerekmez
- İsraf ve uyarı sorulduğunda get_waste_info aracını kullan
- Aktif uyarılar sorulduğunda get_alerts_info aracını kullan
- Haftalık menü sorulduğunda get_weekly_menu aracını kullan
- İki gün karşılaştırması istendiğinde get_menu_comparison aracını kullan
- Öğrenci yorumları, geri bildirim analizi, memnuniyet durumu sorulduğunda analyze_student_feedback aracını kullan
- Popülerlik sıralaması, en beğenilen/az beğenilen yemek sorulduğunda get_popularity_ranking aracını kullan
- İsraf maliyeti, parasal kayıp, tasarruf sorulduğunda get_cost_analysis aracını kullan
- Bugün: {bugun_str} (tarih bilgisini kullanarak tarih hesaplayabilirsin)
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
                "name": "get_today_menu",
                "description": "Bugünkü yemekhane menüsünü getirir (çorba, ana yemek, yan yemek, tatlı, salata).",
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
            },
            {
                "name": "get_weekly_menu",
                "description": "Bu haftanın (Pazartesi-Cuma) tüm menüsünü getirir. Kullanıcı 'bu hafta ne var', 'haftalık menü', 'yarın ne çıkacak' gibi sorular sorduğunda bu aracı kullan.",
                "parameters": {
                    "type": "object",
                    "properties": {},
                    "required": []
                }
            },
            {
                "name": "get_menu_comparison",
                "description": "İki farklı tarihteki menüleri karşılaştırır: kalori toplamı, puan ortalaması ve yemek listesi ile karşılaştırma yapar. Kullanıcı 'dünkü menü mü daha iyiydi', 'pazartesi ile salı menüsünü karşılaştır' gibi sorular sorduğunda bu aracı kullan. Tarih formatı: YYYY-MM-DD",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "tarih1": {
                            "type": "string",
                            "description": "Birinci tarih (YYYY-MM-DD). Boş bırakılırsa bugün."
                        },
                        "tarih2": {
                            "type": "string",
                            "description": "İkinci tarih (YYYY-MM-DD). Boş bırakılırsa dün."
                        }
                    },
                    "required": []
                }
            },
            {
                "name": "analyze_student_feedback",
                "description": "Son 30 gundeki ogrenci geri bildirimlerini (puanlar ve yorumlar) analiz eder. Duygu dagilimi (pozitif/negatif/notr), en sik sikayet temalari, yemek bazli memnuniyet skorlari ve menu onerileri uretir. Kullanici 'yorumlari analiz et', 'ogrenciler ne dusunuyor', 'geri bildirim raporu', 'memnuniyet analizi', 'hangi yemekler begenilmiyor' gibi sorular sordugunda bu araci kullan.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "gun_sayisi": {
                            "type": "integer",
                            "description": "Son kac gunun verisi analiz edilecek. Varsayilan 30."
                        }
                    },
                    "required": []
                }
            },
            {
                "name": "get_popularity_ranking",
                "description": "Yemeklerin popülerlik sıralamasını (en beğenilen / en az beğenilen) getirir. Opsiyonel olarak kategori filtresi uygulanabilir. Kullanıcı 'en popüler yemek', 'en beğenilen çorba', 'en kötü yemek hangisi' gibi sorular sorduğunda bu aracı kullan.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "kategori": {
                            "type": "string",
                            "description": "Filtre: corba, ana_yemek, yan_yemek, tatli, salata. Boş bırakılırsa tüm kategoriler."
                        },
                        "limit": {
                            "type": "integer",
                            "description": "Kaç yemek listelensin. Varsayılan 5."
                        },
                        "siralama": {
                            "type": "string",
                            "description": "'en_iyi' veya 'en_kotu'. Varsayılan 'en_iyi'."
                        }
                    },
                    "required": []
                }
            },
            {
                "name": "get_cost_analysis",
                "description": "İsraf maliyeti analizi yapar. Toplam israf maliyeti, en pahalı israf yemekleri, AI tasarruf potansiyeli gibi bilgiler verir. Kullanıcı 'israf maliyeti', 'ne kadar para kaybediliyor', 'tasarruf potansiyeli', 'en pahalı israf' gibi sorular sorduğunda bu aracı kullan.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "gun": {
                            "type": "integer",
                            "description": "Son kaç günün verisi. Varsayılan 30."
                        }
                    },
                    "required": []
                }
            }
        ]
    }
]

# ─── Session Yönetimi (In-Memory + LRU) ──────────────────────────
# kullanici_id -> [{"role": "user"|"model", "parts": [...]}]
# OrderedDict LRU davranışı sağlar (en eski erişilen silinir).
from collections import OrderedDict

_chat_sessions: "OrderedDict[int, list[dict]]" = OrderedDict()

MAX_HISTORY_LENGTH = 10  # Her kullanıcı için son N mesaj çifti
MAX_USERS = 1000         # Aynı anda en fazla bu kadar aktif kullanıcı


def _get_chat_history(kullanici_id: int) -> list[dict]:
    """Kullanıcının chat geçmişini döndürür (LRU erişim kaydedilir)."""
    if kullanici_id not in _chat_sessions:
        _chat_sessions[kullanici_id] = []
    else:
        # LRU: erişilen kullanıcıyı sona taşı
        _chat_sessions.move_to_end(kullanici_id)
    return _chat_sessions[kullanici_id][-MAX_HISTORY_LENGTH * 2:]


def _add_to_history(kullanici_id: int, role: str, parts: list):
    """Chat geçmişine mesaj ekler. LRU + per-user max size uygular."""
    if kullanici_id not in _chat_sessions:
        _chat_sessions[kullanici_id] = []
    else:
        _chat_sessions.move_to_end(kullanici_id)

    _chat_sessions[kullanici_id].append({"role": role, "parts": parts})

    # Per-user limit: çok uzun geçmişi kırp
    if len(_chat_sessions[kullanici_id]) > MAX_HISTORY_LENGTH * 4:
        _chat_sessions[kullanici_id] = _chat_sessions[kullanici_id][-MAX_HISTORY_LENGTH * 2:]

    # Global limit: toplam kullanıcı MAX_USERS'ı aşarsa en eski erişileni sil
    while len(_chat_sessions) > MAX_USERS:
        _chat_sessions.popitem(last=False)


def clear_chat_history(kullanici_id: int) -> bool:
    """Bir kullanıcının chat geçmişini siler."""
    return _chat_sessions.pop(kullanici_id, None) is not None


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
                "yan_yemek": menu.yan_yemek or "Belirtilmemiş",
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
            for kat in ["corba", "ana_yemek", "yan_yemek", "tatli", "salata"]:
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


def _tool_analyze_feedback(gun_sayisi: int = 30, db=None) -> dict:
    """Ogrenci geri bildirimlerini analiz eder (duygu analizi, tema cikarimi, menu onerileri)."""
    close_db = False
    if db is None:
        db = SessionLocal()
        close_db = True

    try:
        from modules.feedback_analyzer import analyze_feedback
        result = analyze_feedback(db, gun=gun_sayisi)

        if not result.get("veri_var"):
            return {
                "analiz_yapildi": False,
                "mesaj": result.get("mesaj", "Yeterli veri bulunamadi."),
            }

        analiz = result.get("analiz", {})

        # Chatbot icin ozetlenmis veri
        ozet = {
            "analiz_yapildi": True,
            "donem": result.get("donem", {}),
            "genel_istatistik": result.get("genel", {}),
            "duygu_dagilimi": analiz.get("duygu_dagilimi", {}),
            "genel_degerlendirme": analiz.get("genel_degerlendirme", ""),
            "kaynak": analiz.get("kaynak", "bilinmiyor"),
        }

        # En sik temalar (varsa)
        temalar = analiz.get("en_sik_temalar", [])
        if temalar:
            ozet["en_sik_temalar"] = temalar[:5]

        # En begenilmeyen 5 yemek
        skorlar = analiz.get("yemek_duygu_skorlari", [])
        if skorlar:
            ozet["en_dusuk_skorlu_yemekler"] = skorlar[:5]
            ozet["en_yuksek_skorlu_yemekler"] = skorlar[-5:]

        # Menu onerileri (KALDIR ve AZALT olanlar)
        onerileri = analiz.get("menu_onerileri", [])
        kritik = [o for o in onerileri if o.get("aksiyon") in ("KALDIR", "AZALT")]
        if kritik:
            ozet["kritik_menu_onerileri"] = kritik[:5]

        return ozet

    except Exception as e:
        return {"analiz_yapildi": False, "hata": str(e)}
    finally:
        if close_db:
            db.close()

def _tool_get_weekly_menu(db=None) -> dict:
    """Bu haftanın Pazartesi-Cuma menülerini veritabanından getirir."""
    close_db = False
    if db is None:
        db = SessionLocal()
        close_db = True

    try:
        bugun = date.today()
        pazartesi = bugun - timedelta(days=bugun.weekday())
        cuma = pazartesi + timedelta(days=4)

        menuler = (
            db.query(Menu)
            .filter(Menu.tarih >= pazartesi, Menu.tarih <= cuma)
            .order_by(Menu.tarih)
            .all()
        )

        if not menuler:
            return {
                "bulundu": False,
                "hafta": f"{pazartesi} — {cuma}",
                "mesaj": f"Bu hafta ({pazartesi} — {cuma}) için menü bulunamadı.",
            }

        haftalik = []
        for menu in menuler:
            haftalik.append({
                "tarih": str(menu.tarih),
                "gun": menu.gun,
                "corba": menu.corba or "-",
                "ana_yemek": menu.ana_yemek or "-",
                "yan_yemek": menu.yan_yemek or "-",
                "tatli": menu.tatli or "-",
                "salata": menu.salata or "-",
            })

        return {
            "bulundu": True,
            "hafta": f"{pazartesi} — {cuma}",
            "bugun": str(bugun),
            "toplam_gun": len(haftalik),
            "menuler": haftalik,
        }
    finally:
        if close_db:
            db.close()


def _tool_get_menu_comparison(tarih1: str = "", tarih2: str = "", db=None) -> dict:
    """İki farklı tarihteki menüleri kalori ve puan açısından karşılaştırır."""
    from sqlalchemy import func as sqla_func

    close_db = False
    if db is None:
        db = SessionLocal()
        close_db = True

    try:
        bugun = date.today()
        dun = bugun - timedelta(days=1)

        try:
            t1 = date.fromisoformat(tarih1) if tarih1 else bugun
        except ValueError:
            t1 = bugun
        try:
            t2 = date.fromisoformat(tarih2) if tarih2 else dun
        except ValueError:
            t2 = dun

        def _get_menu_data(tarih: date) -> dict:
            menu = db.query(Menu).filter(Menu.tarih == tarih).first()
            if not menu:
                return {"tarih": str(tarih), "bulundu": False, "mesaj": f"{tarih} için menü yok."}

            yemekler = {}
            for kat in ["corba", "ana_yemek", "yan_yemek", "tatli", "salata"]:
                yemek_adi = getattr(menu, kat, None)
                if yemek_adi and yemek_adi.strip():
                    yemekler[kat] = yemek_adi.strip()

            toplam_kalori = 0
            yemek_detay = []
            for kat, yemek_adi in yemekler.items():
                yemek_db = (
                    db.query(Yemek)
                    .filter(Yemek.ad.ilike(f"%{yemek_adi}%"))
                    .first()
                )
                kalori = float(yemek_db.kalori) if yemek_db and yemek_db.kalori else 0
                toplam_kalori += kalori
                yemek_detay.append({
                    "kategori": kat,
                    "yemek_adi": yemek_adi,
                    "kalori": round(kalori, 1),
                })

            puan_result = (
                db.query(
                    sqla_func.avg(MenuPuanlama.puan).label("ortalama"),
                    sqla_func.count(MenuPuanlama.id).label("toplam_oy"),
                )
                .filter(MenuPuanlama.tarih == tarih)
                .first()
            )
            ort_puan = round(float(puan_result.ortalama), 2) if puan_result and puan_result.ortalama else None
            toplam_oy = int(puan_result.toplam_oy or 0) if puan_result else 0

            return {
                "tarih": str(tarih),
                "gun": menu.gun,
                "bulundu": True,
                "yemekler": yemek_detay,
                "toplam_kalori": round(toplam_kalori, 1),
                "puan_ortalama": ort_puan,
                "toplam_oy": toplam_oy,
            }

        menu1_data = _get_menu_data(t1)
        menu2_data = _get_menu_data(t2)

        karsilastirma = {}
        if menu1_data.get("bulundu") and menu2_data.get("bulundu"):
            kal1 = menu1_data["toplam_kalori"]
            kal2 = menu2_data["toplam_kalori"]
            p1 = menu1_data["puan_ortalama"]
            p2 = menu2_data["puan_ortalama"]

            karsilastirma["kalori_farki"] = round(kal1 - kal2, 1)
            if p1 is not None and p2 is not None:
                karsilastirma["puan_farki"] = round(p1 - p2, 2)
                if p1 > p2:
                    karsilastirma["daha_populer"] = str(t1)
                elif p2 > p1:
                    karsilastirma["daha_populer"] = str(t2)
                else:
                    karsilastirma["daha_populer"] = "eşit"
            else:
                karsilastirma["puan_notu"] = "Yeterli puan verisi yok."

        return {
            "menu_1": menu1_data,
            "menu_2": menu2_data,
            "karsilastirma": karsilastirma,
        }
    finally:
        if close_db:
            db.close()


def _tool_get_popularity_ranking(kategori: str = "", limit: int = 5, siralama: str = "en_iyi", db=None) -> dict:
    """Yemeklerin popülerlik sıralamasını döndürür."""
    from sqlalchemy import func as sqla_func

    close_db = False
    if db is None:
        db = SessionLocal()
        close_db = True

    try:
        query = db.query(
            MenuPuanlama.yemek_adi,
            MenuPuanlama.kategori,
            sqla_func.avg(MenuPuanlama.puan).label("ortalama"),
            sqla_func.count(MenuPuanlama.id).label("toplam_oy"),
        )

        if kategori:
            query = query.filter(MenuPuanlama.kategori == kategori)

        # En az 2 oy olan yemekleri filtrele
        query = query.group_by(MenuPuanlama.yemek_adi).having(
            sqla_func.count(MenuPuanlama.id) >= 2
        )

        if siralama == "en_kotu":
            query = query.order_by(sqla_func.avg(MenuPuanlama.puan).asc())
        else:
            query = query.order_by(sqla_func.avg(MenuPuanlama.puan).desc())

        results = query.limit(limit).all()

        if not results:
            return {"bulundu": False, "mesaj": "Yeterli puanlama verisi bulunamadı."}

        KAT_LABELS = {
            "corba": "Çorba", "ana_yemek": "Ana Yemek",
            "yan_yemek": "Yan Yemek", "tatli": "Tatlı", "salata": "Salata/İçecek",
        }

        return {
            "bulundu": True,
            "siralama": siralama,
            "kategori_filtre": kategori or "tümü",
            "yemekler": [
                {
                    "sira": i + 1,
                    "yemek_adi": r.yemek_adi,
                    "kategori": KAT_LABELS.get(r.kategori, r.kategori or "-"),
                    "ortalama_puan": round(float(r.ortalama), 1),
                    "toplam_oy": r.toplam_oy,
                }
                for i, r in enumerate(results)
            ],
        }
    finally:
        if close_db:
            db.close()


def _tool_get_cost_analysis(gun: int = 30, db=None) -> dict:
    """İsraf maliyet analizi yapar."""
    from sqlalchemy import func as sqla_func

    close_db = False
    if db is None:
        db = SessionLocal()
        close_db = True

    PORSIYON_MALIYET = 35.0  # TL

    try:
        baslangic = date.today() - timedelta(days=gun)

        # Genel toplam
        toplam = db.query(
            sqla_func.sum(UretimLog.uretilen_porsiyon).label("uretilen"),
            sqla_func.sum(UretimLog.kalan_porsiyon).label("kalan"),
        ).filter(UretimLog.tarih >= baslangic).first()

        uretilen = int(toplam.uretilen or 0)
        kalan = int(toplam.kalan or 0)

        if uretilen == 0:
            return {"bulundu": False, "mesaj": "Üretim verisi bulunamadı."}

        israf_maliyet = round(kalan * PORSIYON_MALIYET, 2)
        toplam_maliyet = round(uretilen * PORSIYON_MALIYET, 2)
        israf_oran = round(kalan / uretilen * 100, 1)
        tasarruf = round(israf_maliyet * 0.30, 2)

        # En pahalı israf yemekleri (top 5)
        en_pahali = db.query(
            UretimLog.yemek_adi,
            sqla_func.sum(UretimLog.kalan_porsiyon).label("toplam_kalan"),
            sqla_func.avg(UretimLog.israf_orani).label("ort_israf"),
        ).filter(
            UretimLog.tarih >= baslangic
        ).group_by(
            UretimLog.yemek_adi
        ).order_by(
            sqla_func.sum(UretimLog.kalan_porsiyon).desc()
        ).limit(5).all()

        return {
            "bulundu": True,
            "donem_gun": gun,
            "toplam_uretim_porsiyon": uretilen,
            "toplam_israf_porsiyon": kalan,
            "israf_orani": f"%{israf_oran}",
            "toplam_uretim_maliyeti": f"{toplam_maliyet:.0f} TL",
            "israf_maliyeti": f"{israf_maliyet:.0f} TL",
            "ai_tasarruf_potansiyeli": f"{tasarruf:.0f} TL",
            "en_pahali_israf_yemekleri": [
                {
                    "yemek": r.yemek_adi,
                    "israf_porsiyon": int(r.toplam_kalan or 0),
                    "israf_maliyeti": f"{int(r.toplam_kalan or 0) * PORSIYON_MALIYET:.0f} TL",
                    "ort_israf_orani": f"%{r.ort_israf:.1f}",
                }
                for r in en_pahali
            ],
        }
    finally:
        if close_db:
            db.close()


# ─── Tool Dispatch ────────────────────────────────────────────────
def _execute_tool(function_name: str, function_args: dict, db=None) -> dict:
    """Function calling sonuçlarını çalıştırır."""
    if function_name == "get_nutrition":
        return _tool_get_nutrition(
            yemek_adi=function_args.get("yemek_adi", ""),
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
    elif function_name == "get_weekly_menu":
        return _tool_get_weekly_menu(db=db)
    elif function_name == "get_menu_comparison":
        return _tool_get_menu_comparison(
            tarih1=function_args.get("tarih1", ""),
            tarih2=function_args.get("tarih2", ""),
            db=db,
        )
    elif function_name == "analyze_student_feedback":
        return _tool_analyze_feedback(
            gun_sayisi=int(function_args.get("gun_sayisi", 30)),
            db=db,
        )
    elif function_name == "get_popularity_ranking":
        return _tool_get_popularity_ranking(
            kategori=function_args.get("kategori", ""),
            limit=int(function_args.get("limit", 5)),
            siralama=function_args.get("siralama", "en_iyi"),
            db=db,
        )
    elif function_name == "get_cost_analysis":
        return _tool_get_cost_analysis(
            gun=int(function_args.get("gun", 30)),
            db=db,
        )
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

    # System prompt'a bugünün tarihini ekle
    bugun_str = date.today().isoformat()
    formatted_prompt = SYSTEM_PROMPT.format(bugun_str=bugun_str)

    model = genai.GenerativeModel(
        model_name="gemini-2.5-flash",
        system_instruction=formatted_prompt,
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
        kullanici_id: Oturum geçmişini ayırmak için isteğe bağlı kimlik.
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
            f"Yan Yemek: {menu.get('yan_yemek', '?')}, "
            f"Tatlı: {menu.get('tatli', '?')}, "
            f"Salata: {menu.get('salata', '?')}]"
        )

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

        gunluk_toplam = 0.0

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


# ─── Yardımcı Fonksiyonlar ────────────────────────────────────────

def _generate_suggestions(user_message: str) -> list[str]:
    """Mesaja göre takip sorusu önerileri üretir."""
    mesaj = user_message.lower()

    if any(word in mesaj for word in ["haftalık", "haftalik", "bu hafta", "haftanın"]):
        return [
            "Bu hafta en düşük kalorili gün hangisi?",
            "Dünkü menü mü daha iyiydi?",
            "Bugünkü menü ne?",
        ]
    elif any(word in mesaj for word in ["karşılaştır", "kıyasla", "dün", "önceki"]):
        return [
            "Bu haftanın menüsü ne?",
            "Bugünkü menünün kalorisi ne kadar?",
            "En beğenilen yemek hangisi?",
        ]
    elif "menü" in mesaj or "menu" in mesaj:
        return [
            "Bu hafta ne çıkacak?",
            "Dünkü menü mü daha iyiydi?",
            "Bu menünün toplam kalorisi ne kadar?",
        ]
    elif "kalori" in mesaj or "rapor" in mesaj:
        return [
            "Bu yemek protein açısından nasıl?",
            "Menüde daha hafif seçenek var mı?",
            "Bugünkü menü ne?",
        ]
    elif any(word in mesaj for word in ["yedim", "içtim", "yemek"]):
        return [
            "Bu yemeğin besin değeri nedir?",
            "Bu yemeğe puan ver",
            "Bugünkü menü ne?",
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
            "Bu hafta ne çıkacak?",
            "Dünkü menü mü daha iyiydi?",
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
