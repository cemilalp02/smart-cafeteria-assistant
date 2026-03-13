"""
AI Akıllı Yemekhane Asistan Sistemi — PDF Rapor Modülü
══════════════════════════════════════════════════════
Haftalık ve aylık raporları PDF olarak oluşturur.

reportlab kullanarak profesyonel görünümlü PDF raporlar üretir:
  - Haftalık özet: genel istatistikler, en beğenilen/az beğenilen yemekler,
    israf skoru, trend yönü
  - Aylık detaylı rapor: günlük detaylar, kategori bazlı analizler

NOT: Windows Arial fontu kullanarak Türkçe karakter desteği sağlar.
"""

import os
import io
import re
from datetime import date, datetime, timedelta

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm, mm
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    HRFlowable, KeepTogether,
)
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

from sqlalchemy import func as sqla_func
from models import SessionLocal, MenuPuanlama


# ═══════════════════════════════════════════════════════════════════
# FONT KAYDI — Türkçe karakter desteği
# ═══════════════════════════════════════════════════════════════════

_FONT_NAME = "Arial"
_FONT_REGISTERED = False


def _register_font():
    """Windows Arial fontunu kaydet (Türkçe karakter desteği için)."""
    global _FONT_REGISTERED
    if _FONT_REGISTERED:
        return

    # Windows font yolları
    font_paths = [
        r"C:\Windows\Fonts\arial.ttf",
        r"C:\Windows\Fonts\Arial.ttf",
        r"C:\Windows\Fonts\arialuni.ttf",
    ]

    for path in font_paths:
        if os.path.exists(path):
            try:
                pdfmetrics.registerFont(TTFont("Arial", path))
                # Bold variant
                bold_paths = [
                    r"C:\Windows\Fonts\arialbd.ttf",
                    r"C:\Windows\Fonts\Arialbd.ttf",
                ]
                for bp in bold_paths:
                    if os.path.exists(bp):
                        pdfmetrics.registerFont(TTFont("Arial-Bold", bp))
                        break
                _FONT_REGISTERED = True
                print(f"✅ PDF font kaydedildi: {path}")
                return
            except Exception as e:
                print(f"⚠️ Font kayıt hatası: {e}")

    # Fallback — DejaVuSans (Linux/Mac)
    try:
        import subprocess
        result = subprocess.run(["fc-list", ":family=DejaVu Sans", "file"],
                                capture_output=True, text=True, timeout=5)
        if result.stdout:
            path = result.stdout.strip().split(":")[0]
            pdfmetrics.registerFont(TTFont("Arial", path))
            _FONT_REGISTERED = True
            return
    except Exception:
        pass

    print("⚠️ Unicode font bulunamadı. Varsayılan Helvetica kullanılacak (Türkçe sorunlu).")


def _strip_emoji(text: str) -> str:
    """Emoji karakterlerini metinden çıkarır."""
    # Emoji Unicode aralıkları
    emoji_pattern = re.compile(
        "["
        "\U0001F600-\U0001F64F"  # Yüz ifadeleri
        "\U0001F300-\U0001F5FF"  # Semboller & Resimler
        "\U0001F680-\U0001F6FF"  # Ulaşım & Harita
        "\U0001F1E0-\U0001F1FF"  # Bayraklar
        "\U00002702-\U000027B0"
        "\U000024C2-\U0001F251"
        "\U0001f926-\U0001f937"
        "\U00010000-\U0010ffff"
        "\u200d"
        "\u2640-\u2642"
        "\u2600-\u2B55"
        "\u23cf"
        "\u23e9"
        "\u231a"
        "\ufe0f"
        "\u3030"
        "]+",
        flags=re.UNICODE,
    )
    return emoji_pattern.sub("", text).strip()


# ═══════════════════════════════════════════════════════════════════
# YARDIMCI FONKSİYONLAR
# ═══════════════════════════════════════════════════════════════════

def _get_styles():
    """PDF stilleri oluşturur (Arial fontu ile)."""
    _register_font()

    styles = getSampleStyleSheet()
    font = "Arial" if _FONT_REGISTERED else "Helvetica"
    font_bold = "Arial-Bold" if _FONT_REGISTERED else "Helvetica-Bold"

    styles.add(ParagraphStyle(
        "ReportTitle",
        parent=styles["Title"],
        fontName=font_bold,
        fontSize=22,
        textColor=colors.HexColor("#1B4F72"),
        spaceAfter=6,
    ))
    styles.add(ParagraphStyle(
        "ReportSubtitle",
        parent=styles["Normal"],
        fontName=font,
        fontSize=11,
        textColor=colors.HexColor("#5D6D7E"),
        alignment=TA_CENTER,
        spaceAfter=20,
    ))
    styles.add(ParagraphStyle(
        "SectionTitle",
        parent=styles["Heading2"],
        fontName=font_bold,
        fontSize=14,
        textColor=colors.HexColor("#2E86C1"),
        spaceBefore=16,
        spaceAfter=8,
    ))
    styles.add(ParagraphStyle(
        "BodyText2",
        parent=styles["Normal"],
        fontName=font,
        fontSize=9,
    ))
    styles.add(ParagraphStyle(
        "SmallText",
        parent=styles["Normal"],
        fontName=font,
        fontSize=8,
        textColor=colors.HexColor("#8892A4"),
        alignment=TA_CENTER,
    ))
    return styles


def _make_table(data, col_widths=None):
    """Standart tablo stili ile tablo oluşturur."""
    font = "Arial" if _FONT_REGISTERED else "Helvetica"
    font_bold = "Arial-Bold" if _FONT_REGISTERED else "Helvetica-Bold"

    table = Table(data, colWidths=col_widths)
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#2E86C1")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), font_bold),
        ("FONTNAME", (0, 1), (-1, -1), font),
        ("FONTSIZE", (0, 0), (-1, 0), 10),
        ("FONTSIZE", (0, 1), (-1, -1), 9),
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#D5D8DC")),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [
            colors.HexColor("#F8F9FA"), colors.white
        ]),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ("LEFTPADDING", (0, 0), (-1, -1), 8),
        ("RIGHTPADDING", (0, 0), (-1, -1), 8),
    ]))
    return table


def _get_rating_stats(db, start_date, end_date):
    """Belirli tarih aralığındaki puanlama istatistiklerini döndürür."""
    query = db.query(
        MenuPuanlama.yemek_adi,
        MenuPuanlama.kategori,
        sqla_func.avg(MenuPuanlama.puan).label("ortalama"),
        sqla_func.count(MenuPuanlama.id).label("toplam_oy"),
    ).filter(
        MenuPuanlama.tarih >= start_date,
        MenuPuanlama.tarih <= end_date,
    ).group_by(
        MenuPuanlama.yemek_adi
    ).order_by(
        sqla_func.avg(MenuPuanlama.puan).desc()
    ).all()

    return query


def _get_category_stats(db, start_date, end_date):
    """Kategori bazlı istatistikleri döndürür."""
    query = db.query(
        MenuPuanlama.kategori,
        sqla_func.avg(MenuPuanlama.puan).label("ortalama"),
        sqla_func.count(MenuPuanlama.id).label("toplam_oy"),
    ).filter(
        MenuPuanlama.tarih >= start_date,
        MenuPuanlama.tarih <= end_date,
    ).group_by(
        MenuPuanlama.kategori
    ).all()

    return query


def _get_daily_stats(db, start_date, end_date):
    """Günlük ortalama puanları döndürür."""
    query = db.query(
        MenuPuanlama.tarih,
        sqla_func.avg(MenuPuanlama.puan).label("ortalama"),
        sqla_func.count(MenuPuanlama.id).label("toplam_oy"),
    ).filter(
        MenuPuanlama.tarih >= start_date,
        MenuPuanlama.tarih <= end_date,
    ).group_by(
        MenuPuanlama.tarih
    ).order_by(
        MenuPuanlama.tarih
    ).all()

    return query


# ═══════════════════════════════════════════════════════════════════
# HAFTALIK PDF RAPOR
# ═══════════════════════════════════════════════════════════════════

def generate_weekly_pdf(db=None) -> bytes:
    """
    Son 7 günlük haftalık özet raporunu PDF olarak üretir.
    """
    close_db = False
    if db is None:
        db = SessionLocal()
        close_db = True

    try:
        today = date.today()
        start = today - timedelta(days=6)

        buf = io.BytesIO()
        doc = SimpleDocTemplate(
            buf, pagesize=A4,
            topMargin=2 * cm, bottomMargin=2 * cm,
            leftMargin=2.5 * cm, rightMargin=2.5 * cm,
        )
        styles = _get_styles()
        elements = []

        # ─── Başlık ─────────────────────────────────────────────
        elements.append(Paragraph(
            "Akilli Yemekhane - Haftalik Rapor", styles["ReportTitle"]
        ))
        elements.append(Paragraph(
            f"{start.strftime('%d.%m.%Y')} - {today.strftime('%d.%m.%Y')}",
            styles["ReportSubtitle"],
        ))
        elements.append(HRFlowable(
            width="100%", thickness=1,
            color=colors.HexColor("#2E86C1"), spaceAfter=16,
        ))

        # ─── Genel İstatistikler ────────────────────────────────
        all_ratings = _get_rating_stats(db, start, today)
        total_votes = sum(r.toplam_oy for r in all_ratings)
        if all_ratings:
            overall_avg = sum(r.ortalama * r.toplam_oy for r in all_ratings) / max(total_votes, 1)
        else:
            overall_avg = 0

        elements.append(Paragraph("Genel Ozet", styles["SectionTitle"]))

        summary_data = [
            ["Metrik", _strip_emoji("Deger")],
            ["Rapor Donemi", f"{start.strftime('%d.%m.%Y')} - {today.strftime('%d.%m.%Y')}"],
            ["Toplam Puanlama Sayisi", str(total_votes)],
            ["Genel Ortalama Puan", f"{overall_avg:.1f} / 5"],
            [_strip_emoji("Degerlendirilen Yemek Sayisi"), str(len(all_ratings))],
        ]
        elements.append(_make_table(summary_data, col_widths=[7 * cm, 8 * cm]))
        elements.append(Spacer(1, 16))

        # ─── En Beğenilen 10 Yemek ──────────────────────────────
        elements.append(Paragraph(
            "En Begenilen Yemekler (Top 10)", styles["SectionTitle"]
        ))
        if all_ratings:
            top_data = [["#", "Yemek Adi", "Kategori", "Ort. Puan", "Oy Sayisi"]]
            for i, r in enumerate(all_ratings[:10], 1):
                top_data.append([
                    str(i),
                    _strip_emoji(r.yemek_adi),
                    _strip_emoji(r.kategori or "-"),
                    f"{r.ortalama:.1f}",
                    str(r.toplam_oy),
                ])
            elements.append(_make_table(top_data, col_widths=[1.2*cm, 5*cm, 3*cm, 2.8*cm, 2.5*cm]))
        else:
            elements.append(Paragraph("Veri bulunamadi.", styles["BodyText2"]))
        elements.append(Spacer(1, 16))

        # ─── En Az Beğenilen 5 Yemek ────────────────────────────
        elements.append(Paragraph(
            "En Az Begenilen Yemekler", styles["SectionTitle"]
        ))
        if len(all_ratings) >= 5:
            bottom = list(reversed(all_ratings))[:5]
            bot_data = [["#", "Yemek Adi", "Kategori", "Ort. Puan", "Oy Sayisi"]]
            for i, r in enumerate(bottom, 1):
                bot_data.append([
                    str(i),
                    _strip_emoji(r.yemek_adi),
                    _strip_emoji(r.kategori or "-"),
                    f"{r.ortalama:.1f}",
                    str(r.toplam_oy),
                ])
            elements.append(_make_table(bot_data, col_widths=[1.2*cm, 5*cm, 3*cm, 2.8*cm, 2.5*cm]))
        else:
            elements.append(Paragraph("Yeterli veri yok.", styles["BodyText2"]))
        elements.append(Spacer(1, 16))

        # ─── Kategori Bazlı ─────────────────────────────────────
        cat_stats = _get_category_stats(db, start, today)
        elements.append(Paragraph(
            "Kategori Bazli Ortalamalar", styles["SectionTitle"]
        ))

        KAT_LABELS = {
            "corba": "Corbalar", "ana_yemek": "Ana Yemekler",
            "pilav": "Yan Yemek", "tatli": "Tatlilar",
            "salata": "Salatalar",
        }

        if cat_stats:
            cat_data = [["Kategori", "Ortalama Puan", "Toplam Oy"]]
            for c in cat_stats:
                cat_data.append([
                    KAT_LABELS.get(c.kategori, c.kategori or "-"),
                    f"{c.ortalama:.1f}",
                    str(c.toplam_oy),
                ])
            elements.append(_make_table(cat_data, col_widths=[5 * cm, 5 * cm, 4.5 * cm]))
        else:
            elements.append(Paragraph("Veri bulunamadi.", styles["BodyText2"]))
        elements.append(Spacer(1, 16))

        # ─── Günlük Trend ───────────────────────────────────────
        daily_stats = _get_daily_stats(db, start, today)
        elements.append(Paragraph(
            "Gunluk Puan Trendi", styles["SectionTitle"]
        ))

        if daily_stats:
            day_data = [["Tarih", "Ortalama Puan", "Oy Sayisi"]]
            for d in daily_stats:
                tarih_str = d.tarih.strftime("%d.%m.%Y") if hasattr(d.tarih, "strftime") else str(d.tarih)
                day_data.append([
                    tarih_str,
                    f"{d.ortalama:.1f}",
                    str(d.toplam_oy),
                ])
            elements.append(_make_table(day_data, col_widths=[5 * cm, 5 * cm, 4.5 * cm]))
        else:
            elements.append(Paragraph("Veri bulunamadi.", styles["BodyText2"]))

        # ─── Footer ─────────────────────────────────────────────
        elements.append(Spacer(1, 30))
        elements.append(HRFlowable(
            width="100%", thickness=0.5,
            color=colors.HexColor("#D5D8DC"), spaceAfter=8,
        ))
        elements.append(Paragraph(
            f"Bu rapor AI Akilli Yemekhane Asistan Sistemi tarafindan otomatik olusturulmustur. "
            f"Olusturma tarihi: {datetime.now().strftime('%d.%m.%Y %H:%M')}",
            styles["SmallText"],
        ))

        doc.build(elements)
        return buf.getvalue()

    finally:
        if close_db:
            db.close()


# ═══════════════════════════════════════════════════════════════════
# AYLIK PDF RAPOR
# ═══════════════════════════════════════════════════════════════════

def generate_monthly_pdf(db=None) -> bytes:
    """
    Son 30 günlük aylık detaylı raporunu PDF olarak üretir.
    """
    close_db = False
    if db is None:
        db = SessionLocal()
        close_db = True

    try:
        today = date.today()
        start = today - timedelta(days=29)

        buf = io.BytesIO()
        doc = SimpleDocTemplate(
            buf, pagesize=A4,
            topMargin=2 * cm, bottomMargin=2 * cm,
            leftMargin=2.5 * cm, rightMargin=2.5 * cm,
        )
        styles = _get_styles()
        elements = []

        # ─── Başlık ─────────────────────────────────────────────
        elements.append(Paragraph(
            "Akilli Yemekhane - Aylik Detayli Rapor", styles["ReportTitle"]
        ))
        elements.append(Paragraph(
            f"{start.strftime('%d.%m.%Y')} - {today.strftime('%d.%m.%Y')} (30 Gun)",
            styles["ReportSubtitle"],
        ))
        elements.append(HRFlowable(
            width="100%", thickness=1,
            color=colors.HexColor("#2E86C1"), spaceAfter=16,
        ))

        # ─── Genel İstatistikler ────────────────────────────────
        all_ratings = _get_rating_stats(db, start, today)
        total_votes = sum(r.toplam_oy for r in all_ratings)
        if all_ratings:
            overall_avg = sum(r.ortalama * r.toplam_oy for r in all_ratings) / max(total_votes, 1)
        else:
            overall_avg = 0

        elements.append(Paragraph("30 Gunluk Genel Ozet", styles["SectionTitle"]))

        summary_data = [
            ["Metrik", "Deger"],
            ["Rapor Donemi", f"{start.strftime('%d.%m.%Y')} - {today.strftime('%d.%m.%Y')}"],
            ["Toplam Puanlama", str(total_votes)],
            ["Genel Ortalama", f"{overall_avg:.1f} / 5"],
            ["Farkli Yemek", str(len(all_ratings))],
        ]
        elements.append(_make_table(summary_data, col_widths=[7 * cm, 8 * cm]))
        elements.append(Spacer(1, 16))

        # ─── Tüm Yemekler Detaylı Tablo ─────────────────────────
        elements.append(Paragraph(
            "Tum Yemekler - Detayli Istatistik", styles["SectionTitle"]
        ))
        if all_ratings:
            full_data = [["#", "Yemek", "Kategori", "Ort.", "Oy", "Seviye"]]
            for i, r in enumerate(all_ratings, 1):
                if r.ortalama >= 4.0:
                    level = "Cok Iyi"
                elif r.ortalama >= 3.0:
                    level = "Iyi"
                elif r.ortalama >= 2.0:
                    level = "Orta"
                else:
                    level = "Kotu"
                full_data.append([
                    str(i), _strip_emoji(r.yemek_adi),
                    _strip_emoji(r.kategori or "-"),
                    f"{r.ortalama:.1f}", str(r.toplam_oy), level,
                ])
            elements.append(_make_table(
                full_data,
                col_widths=[1*cm, 4.5*cm, 2.8*cm, 1.8*cm, 1.8*cm, 2.6*cm],
            ))
        else:
            elements.append(Paragraph("Veri bulunamadi.", styles["BodyText2"]))
        elements.append(Spacer(1, 16))

        # ─── Kategori Bazlı ─────────────────────────────────────
        cat_stats = _get_category_stats(db, start, today)
        elements.append(Paragraph("Kategori Performansi", styles["SectionTitle"]))

        KAT_LABELS = {
            "corba": "Corbalar", "ana_yemek": "Ana Yemekler",
            "pilav": "Yan Yemek", "tatli": "Tatlilar",
            "salata": "Salatalar",
        }
        if cat_stats:
            cat_data = [["Kategori", "Ortalama", "Oy"]]
            for c in cat_stats:
                cat_data.append([
                    KAT_LABELS.get(c.kategori, c.kategori or "-"),
                    f"{c.ortalama:.1f}", str(c.toplam_oy),
                ])
            elements.append(_make_table(cat_data, col_widths=[5*cm, 5*cm, 4.5*cm]))

        # ─── Günlük Detay ───────────────────────────────────────
        daily_stats = _get_daily_stats(db, start, today)
        elements.append(Spacer(1, 16))
        elements.append(Paragraph(
            "Gunluk Puan Trendi (30 Gun)", styles["SectionTitle"]
        ))

        if daily_stats:
            day_data = [["Tarih", "Ort. Puan", "Oy", "Durum"]]
            for d in daily_stats:
                tarih_str = d.tarih.strftime("%d.%m.%Y") if hasattr(d.tarih, "strftime") else str(d.tarih)
                if d.ortalama >= 3.5:
                    durum = "Iyi"
                elif d.ortalama >= 2.5:
                    durum = "Orta"
                else:
                    durum = "Kotu"
                day_data.append([tarih_str, f"{d.ortalama:.1f}", str(d.toplam_oy), durum])
            elements.append(_make_table(day_data, col_widths=[4*cm, 3.5*cm, 3*cm, 4*cm]))

        # ─── Footer ─────────────────────────────────────────────
        elements.append(Spacer(1, 30))
        elements.append(HRFlowable(
            width="100%", thickness=0.5,
            color=colors.HexColor("#D5D8DC"), spaceAfter=8,
        ))
        elements.append(Paragraph(
            f"Bu rapor AI Akilli Yemekhane Asistan Sistemi tarafindan otomatik olusturulmustur. "
            f"Olusturma tarihi: {datetime.now().strftime('%d.%m.%Y %H:%M')}",
            styles["SmallText"],
        ))

        doc.build(elements)
        return buf.getvalue()

    finally:
        if close_db:
            db.close()
