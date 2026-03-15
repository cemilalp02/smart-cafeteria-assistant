"""
Öğrenci Geri Bildirim Analizi Modülü — Gemini NLP Entegrasyonu
═══════════════════════════════════════════════════════════════════
MenuPuanlama tablosundaki puanları ve yorumları analiz ederek:
  - Duygu dağılımı (pozitif / negatif / nötr)
  - En sık tekrarlanan şikayet temaları
  - Yemek bazlı duygu skoru
  - Gelecek ay menü planlaması için AI raporu

UretimLog verileri ile birleştirilerek hangi yemeklerin
menüde kalması, azaltılması veya çıkarılması gerektiğini önerir.
"""

from __future__ import annotations

import json
from datetime import date, timedelta
from typing import Any, Optional

from sqlalchemy import func
from sqlalchemy.orm import Session

from config import active_config
from models import MenuPuanlama, UretimLog


# ──────────────────────────────────────────────────────────────────
# 1) Veri Toplama
# ──────────────────────────────────────────────────────────────────

def _collect_feedback_data(db: Session, gun: int = 30) -> dict[str, Any]:
    """
    Son N gündeki puanlama ve üretim verilerini toplar.

    Returns:
        dict: yemek_bazli veriler, yorumlar, genel istatistikler
    """
    bugun = date.today()
    baslangic = bugun - timedelta(days=gun)

    # ── Yemek bazlı puan ortalamaları ──
    puan_sonuclari = (
        db.query(
            MenuPuanlama.yemek_adi,
            MenuPuanlama.kategori,
            func.avg(MenuPuanlama.puan).label("ortalama"),
            func.count(MenuPuanlama.id).label("toplam_oy"),
            func.min(MenuPuanlama.puan).label("min_puan"),
            func.max(MenuPuanlama.puan).label("max_puan"),
        )
        .filter(MenuPuanlama.tarih >= baslangic)
        .group_by(MenuPuanlama.yemek_adi, MenuPuanlama.kategori)
        .order_by(func.avg(MenuPuanlama.puan))
        .all()
    )

    # ── Tüm yorumlar ──
    yorumlar = (
        db.query(
            MenuPuanlama.yemek_adi,
            MenuPuanlama.puan,
            MenuPuanlama.yorum,
            MenuPuanlama.tarih,
        )
        .filter(
            MenuPuanlama.tarih >= baslangic,
            MenuPuanlama.yorum.isnot(None),
            MenuPuanlama.yorum != "",
        )
        .order_by(MenuPuanlama.created_at.desc())
        .limit(200)  # Son 200 yorum
        .all()
    )

    # ── Üretim/tüketim verileri ──
    uretim_sonuclari = (
        db.query(
            UretimLog.yemek_adi,
            func.avg(UretimLog.tuketim_orani).label("ort_tuketim"),
            func.avg(UretimLog.israf_orani).label("ort_israf"),
            func.sum(UretimLog.uretilen_porsiyon).label("toplam_uretilen"),
            func.sum(UretimLog.kalan_porsiyon).label("toplam_kalan"),
        )
        .filter(UretimLog.tarih >= baslangic)
        .group_by(UretimLog.yemek_adi)
        .all()
    )

    # Üretim verilerini dict'e çevir
    uretim_map = {}
    for row in uretim_sonuclari:
        uretim_map[row.yemek_adi] = {
            "ort_tuketim_orani": round(float(row.ort_tuketim or 0), 1),
            "ort_israf_orani": round(float(row.ort_israf or 0), 1),
            "toplam_uretilen": round(float(row.toplam_uretilen or 0), 1),
            "toplam_kalan": round(float(row.toplam_kalan or 0), 1),
        }

    # ── Yemek bazlı birleşik veri ──
    yemek_verileri = []
    for row in puan_sonuclari:
        yemek_adi = row.yemek_adi
        uretim = uretim_map.get(yemek_adi, {})

        yemek_verileri.append({
            "yemek_adi": yemek_adi,
            "kategori": row.kategori,
            "puan_ortalama": round(float(row.ortalama), 2),
            "toplam_oy": row.toplam_oy,
            "min_puan": row.min_puan,
            "max_puan": row.max_puan,
            "ort_tuketim_orani": uretim.get("ort_tuketim_orani"),
            "ort_israf_orani": uretim.get("ort_israf_orani"),
            "toplam_uretilen": uretim.get("toplam_uretilen"),
            "toplam_kalan": uretim.get("toplam_kalan"),
        })

    # ── Yorum listesi ──
    yorum_listesi = [
        {
            "yemek_adi": y.yemek_adi,
            "puan": y.puan,
            "yorum": y.yorum,
            "tarih": str(y.tarih),
        }
        for y in yorumlar
    ]

    # ── Genel istatistik ──
    toplam_puan = (
        db.query(
            func.count(MenuPuanlama.id).label("toplam"),
            func.avg(MenuPuanlama.puan).label("genel_ort"),
        )
        .filter(MenuPuanlama.tarih >= baslangic)
        .first()
    )

    return {
        "donem": {"baslangic": str(baslangic), "bitis": str(bugun), "gun": gun},
        "genel": {
            "toplam_puanlama": toplam_puan.toplam if toplam_puan.toplam else 0,
            "genel_ortalama": round(float(toplam_puan.genel_ort), 2) if toplam_puan.genel_ort else 0,
            "toplam_yorum": len(yorum_listesi),
            "toplam_yemek": len(yemek_verileri),
        },
        "yemek_verileri": yemek_verileri,
        "yorumlar": yorum_listesi,
    }


# ──────────────────────────────────────────────────────────────────
# 2) Gemini Prompt Oluşturma
# ──────────────────────────────────────────────────────────────────

def _build_gemini_prompt(data: dict[str, Any]) -> str:
    """Toplanan veriyi Gemini'ye gönderilecek yapılandırılmış bir prompt olarak hazırlar."""

    yemek_ozet = ""
    for y in data["yemek_verileri"]:
        tuketim = f", tüketim oranı: %{y['ort_tuketim_orani']}" if y.get("ort_tuketim_orani") else ""
        israf = f", israf oranı: %{y['ort_israf_orani']}" if y.get("ort_israf_orani") else ""
        yemek_ozet += (
            f"- {y['yemek_adi']} ({y['kategori']}): "
            f"puan ort: {y['puan_ortalama']}/5, oy: {y['toplam_oy']}"
            f"{tuketim}{israf}\n"
        )

    yorum_ozet = ""
    for yr in data["yorumlar"][:50]:  # İlk 50 yorum
        yorum_ozet += f"- [{yr['yemek_adi']}] {yr['puan']}⭐: \"{yr['yorum']}\"\n"

    prompt = f"""Sen bir yemekhane yönetim danışmanısın. Aşağıdaki öğrenci geri bildirim verilerini analiz et.

## VERİLER

### Dönem: {data['donem']['baslangic']} — {data['donem']['bitis']} ({data['donem']['gun']} gün)
Toplam puanlama: {data['genel']['toplam_puanlama']}, Genel ortalama: {data['genel']['genel_ortalama']}/5

### Yemek Bazlı İstatistikler:
{yemek_ozet}

### Öğrenci Yorumları:
{yorum_ozet if yorum_ozet else "(Yorum bulunmuyor)"}

## İSTENENLER

Lütfen aşağıdaki analizi JSON formatında döndür. Yanıtın SADECE JSON olsun, başka bir şey yazma.

{{
  "duygu_dagilimi": {{
    "pozitif": <pozitif yorum sayısı tahmini>,
    "negatif": <negatif yorum sayısı tahmini>,
    "notr": <nötr yorum sayısı tahmini>
  }},
  "en_sik_temalar": [
    {{"tema": "<tema adı>", "sayi": <yaklaşık tekrar sayısı>, "ornek_yorum": "<örnek>"}},
    ...
  ],
  "yemek_duygu_skorlari": [
    {{"yemek_adi": "<yemek>", "skor": <-1.0 ile +1.0 arası>, "ozet": "<kısa değerlendirme>"}},
    ...
  ],
  "menu_onerileri": [
    {{
      "yemek_adi": "<yemek>",
      "aksiyon": "<KALDIR | AZALT | KORU | ARTIR>",
      "gerekce": "<neden bu aksiyon önerildi>"
    }},
    ...
  ],
  "genel_degerlendirme": "<genel memnuniyet durumu ve menü kalitesi hakkında 2-3 cümle>"
}}

ÖNEMLI: Sadece geçerli JSON döndür, markdown veya açıklama ekleme."""

    return prompt


# ──────────────────────────────────────────────────────────────────
# 3) Yerel Fallback Analiz (Gemini yoksa)
# ──────────────────────────────────────────────────────────────────

def _local_fallback_analysis(data: dict[str, Any]) -> dict[str, Any]:
    """
    Gemini API olmadan, puan tabanlı basit analiz yapar.
    Puan >= 4 → pozitif, puan <= 2 → negatif, 3 → nötr
    """
    pozitif = 0
    negatif = 0
    notr = 0

    for yr in data["yorumlar"]:
        if yr["puan"] >= 4:
            pozitif += 1
        elif yr["puan"] <= 2:
            negatif += 1
        else:
            notr += 1

    # Yorum yoksa puanlamalardan tahmin et
    if not data["yorumlar"]:
        for y in data["yemek_verileri"]:
            oy = y["toplam_oy"]
            if y["puan_ortalama"] >= 4.0:
                pozitif += oy
            elif y["puan_ortalama"] <= 2.0:
                negatif += oy
            else:
                notr += oy

    # Yemek duygu skorları (puan tabanlı)
    yemek_skorlari = []
    for y in data["yemek_verileri"]:
        # Puanı -1..+1 aralığına dönüştür: (puan - 3) / 2
        skor = round((y["puan_ortalama"] - 3) / 2, 2)
        skor = max(-1.0, min(1.0, skor))

        if skor >= 0.3:
            ozet = "Beğeniliyor"
        elif skor <= -0.3:
            ozet = "Beğenilmiyor"
        else:
            ozet = "Ortalama"

        yemek_skorlari.append({
            "yemek_adi": y["yemek_adi"],
            "skor": skor,
            "ozet": ozet,
        })

    # Sırala: en düşükten en yükseğe
    yemek_skorlari.sort(key=lambda x: x["skor"])

    # Menü önerileri
    menu_onerileri = []
    for y in data["yemek_verileri"]:
        puan = y["puan_ortalama"]
        israf = y.get("ort_israf_orani") or 0

        if puan < 2.0 and israf > 30:
            aksiyon = "KALDIR"
            gerekce = f"Düşük puan ({puan}/5) ve yüksek israf oranı (%{israf})"
        elif puan < 2.5 or israf > 25:
            aksiyon = "AZALT"
            gerekce = f"Puan: {puan}/5" + (f", israf: %{israf}" if israf else "")
        elif puan >= 4.0:
            aksiyon = "ARTIR"
            gerekce = f"Yüksek memnuniyet ({puan}/5)"
        else:
            aksiyon = "KORU"
            gerekce = f"Ortalama performans ({puan}/5)"

        menu_onerileri.append({
            "yemek_adi": y["yemek_adi"],
            "aksiyon": aksiyon,
            "gerekce": gerekce,
        })

    # Genel değerlendirme
    genel_ort = data["genel"]["genel_ortalama"]
    if genel_ort >= 4.0:
        genel = f"Genel memnuniyet yüksek ({genel_ort}/5). Menü kalitesi iyi durumda."
    elif genel_ort >= 3.0:
        genel = f"Genel memnuniyet orta seviyede ({genel_ort}/5). Bazı yemeklerde iyileştirme yapılabilir."
    else:
        genel = f"Genel memnuniyet düşük ({genel_ort}/5). Menüde ciddi değişiklikler yapılması önerilir."

    return {
        "duygu_dagilimi": {
            "pozitif": pozitif,
            "negatif": negatif,
            "notr": notr,
        },
        "en_sik_temalar": [],
        "yemek_duygu_skorlari": yemek_skorlari,
        "menu_onerileri": menu_onerileri,
        "genel_degerlendirme": genel,
        "kaynak": "yerel_analiz",
    }


# ──────────────────────────────────────────────────────────────────
# 4) Gemini API ile Analiz
# ──────────────────────────────────────────────────────────────────

def _gemini_analysis(prompt: str) -> Optional[dict[str, Any]]:
    """Gemini API'ye prompt gönderip JSON yanıt döner."""
    api_key = active_config.GEMINI_API_KEY
    if not api_key:
        return None

    try:
        import google.generativeai as genai
        genai.configure(api_key=api_key)

        model = genai.GenerativeModel("gemini-2.5-flash")
        response = model.generate_content(prompt)

        if not response.text:
            return None

        # JSON parse
        text = response.text.strip()

        # Markdown code block varsa temizle
        if text.startswith("```"):
            lines = text.split("\n")
            # İlk ve son satırı (``` ile başlayanları) kaldır
            lines = [l for l in lines if not l.strip().startswith("```")]
            text = "\n".join(lines)

        result = json.loads(text)
        result["kaynak"] = "gemini_ai"
        return result

    except json.JSONDecodeError as e:
        print(f"⚠️ Gemini JSON parse hatası: {e}")
        return None
    except Exception as e:
        print(f"⚠️ Gemini API hatası: {e}")
        return None


# ──────────────────────────────────────────────────────────────────
# 5) Ana Fonksiyon
# ──────────────────────────────────────────────────────────────────

def analyze_feedback(db: Session, gun: int = 30) -> dict[str, Any]:
    """
    Öğrenci geri bildirimlerini analiz eder.

    Gemini API varsa NLP analizi yapar, yoksa yerel puan tabanlı analiz.

    Args:
        db: SQLAlchemy session
        gun: Son kaç günün verisi analiz edilecek

    Returns:
        dict: {
            "success": True,
            "donem": {...},
            "genel": {...},
            "analiz": {
                "duygu_dagilimi": {...},
                "en_sik_temalar": [...],
                "yemek_duygu_skorlari": [...],
                "menu_onerileri": [...],
                "genel_degerlendirme": "...",
                "kaynak": "gemini_ai" | "yerel_analiz"
            },
            "yemek_verileri": [...],
            "yorumlar": [...]
        }
    """
    # Veri topla
    data = _collect_feedback_data(db, gun)

    if data["genel"]["toplam_puanlama"] == 0:
        return {
            "success": True,
            "veri_var": False,
            "mesaj": "Belirtilen dönemde puanlama verisi bulunamadı. "
                     "Önce 'Yemek Puanla' sayfasından yemeklere puan verin.",
            "donem": data["donem"],
            "genel": data["genel"],
        }

    # Gemini ile analiz dene
    prompt = _build_gemini_prompt(data)
    analiz = _gemini_analysis(prompt)

    # Başarısız olursa fallback
    if analiz is None:
        analiz = _local_fallback_analysis(data)

    return {
        "success": True,
        "veri_var": True,
        "donem": data["donem"],
        "genel": data["genel"],
        "analiz": analiz,
        "yemek_verileri": data["yemek_verileri"],
        "yorumlar": data["yorumlar"][:20],  # Son 20 yorum
    }
