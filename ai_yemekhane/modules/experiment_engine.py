"""
A/B Test ve Deney Motoru
═══════════════════════════════════════════════════════════════

AI menü önerisi vs manuel menü performans karşılaştırması.
İstatistiksel anlamlılık testi (t-test) ve haftalık rapor üretimi.

Kullanım:
    from modules.experiment_engine import run_ab_experiment, get_experiment_summary
    result = run_ab_experiment(db, hafta_baslangic)
"""

import logging
from datetime import date, timedelta
from typing import Any, Optional

import numpy as np
from sqlalchemy import func as sqla_func
from sqlalchemy.orm import Session

from models import Menu, MenuOneriLog, UretimLog, MenuPuanlama

logger = logging.getLogger(__name__)

# scipy isteğe bağlı
try:
    from scipy import stats as scipy_stats
    _HAS_SCIPY = True
except ImportError:
    _HAS_SCIPY = False


# ═══════════════════════════════════════════════════════════════════
# YARDIMCI
# ═══════════════════════════════════════════════════════════════════

def _get_dish_metrics(db: Session, yemek_adi: str, baslangic: date, bitis: date) -> dict:
    """Bir yemeğin belirli dönemdeki israf ve puan metriklerini getirir."""
    israf = (
        db.query(sqla_func.avg(UretimLog.israf_orani))
        .filter(
            UretimLog.yemek_adi == yemek_adi,
            UretimLog.tarih >= baslangic,
            UretimLog.tarih <= bitis,
        )
        .scalar()
    )
    puan = (
        db.query(sqla_func.avg(MenuPuanlama.puan))
        .filter(
            MenuPuanlama.yemek_adi == yemek_adi,
            MenuPuanlama.tarih >= baslangic,
            MenuPuanlama.tarih <= bitis,
        )
        .scalar()
    )
    return {
        "yemek_adi": yemek_adi,
        "ort_israf": round(float(israf or 0), 1),
        "ort_puan": round(float(puan or 0), 2),
    }


def _collect_group_metrics(
    db: Session,
    yemek_listesi: list[str],
    baslangic: date,
    bitis: date,
) -> dict[str, list[float]]:
    """Bir grup yemeğin israf ve puan listelerini toplar."""
    israf_list = []
    puan_list = []
    for yemek in yemek_listesi:
        if not yemek:
            continue
        m = _get_dish_metrics(db, yemek, baslangic, bitis)
        if m["ort_israf"] > 0:
            israf_list.append(m["ort_israf"])
        if m["ort_puan"] > 0:
            puan_list.append(m["ort_puan"])
    return {"israf": israf_list, "puan": puan_list}


def _ttest(group_a: list[float], group_b: list[float]) -> dict:
    """İki gruba Welch t-test uygular. scipy yoksa basit karşılaştırma yapar."""
    if len(group_a) < 2 or len(group_b) < 2:
        return {
            "test": "insufficient_data",
            "p_value": None,
            "t_stat": None,
            "significant": False,
            "message": "Yeterli veri yok (her grupta en az 2 gözlem gerekli).",
        }

    mean_a = float(np.mean(group_a))
    mean_b = float(np.mean(group_b))
    diff = round(mean_a - mean_b, 2)

    if _HAS_SCIPY:
        t_stat, p_value = scipy_stats.ttest_ind(group_a, group_b, equal_var=False)
        return {
            "test": "welch_t_test",
            "t_stat": round(float(t_stat), 4),
            "p_value": round(float(p_value), 4),
            "significant": float(p_value) < 0.05,
            "mean_a": round(mean_a, 2),
            "mean_b": round(mean_b, 2),
            "diff": diff,
            "message": (
                f"p={float(p_value):.4f} — {'İstatistiksel olarak anlamlı fark VAR' if float(p_value) < 0.05 else 'Anlamlı fark YOK'}"
            ),
        }
    else:
        # scipy yoksa basit karşılaştırma
        return {
            "test": "simple_comparison",
            "t_stat": None,
            "p_value": None,
            "significant": abs(diff) > 5.0,  # %5'ten fazla fark varsa "anlamlı" say
            "mean_a": round(mean_a, 2),
            "mean_b": round(mean_b, 2),
            "diff": diff,
            "message": f"Fark: {diff} (scipy kurulu değil, basit karşılaştırma yapıldı)",
        }


# ═══════════════════════════════════════════════════════════════════
# ANA FONKSİYONLAR
# ═══════════════════════════════════════════════════════════════════

def run_ab_experiment(
    db: Session,
    hafta_baslangic: date | None = None,
    hafta_sayisi: int = 4,
) -> dict[str, Any]:
    """
    A/B deneyi çalıştırır:
      A grubu = Gerçek menü (Menu tablosu)
      B grubu = AI önerisi (MenuOneriLog tablosu)

    Her iki grup için israf ve puan metriklerini karşılaştırır,
    t-test uygular.
    """
    if hafta_baslangic is None:
        hafta_baslangic = date.today() - timedelta(days=28)

    bitis = hafta_baslangic + timedelta(days=hafta_sayisi * 7)

    # ── Gerçek menü yemeklerini topla (A grubu) ──
    gercek_menuler = (
        db.query(Menu)
        .filter(Menu.tarih >= hafta_baslangic, Menu.tarih <= bitis)
        .all()
    )
    gercek_yemekler = set()
    for m in gercek_menuler:
        for attr in ["corba", "ana_yemek", "yan_yemek", "tatli", "salata"]:
            y = getattr(m, attr, None)
            if y:
                gercek_yemekler.add(y)

    # ── AI önerisi yemeklerini topla (B grubu) ──
    ai_oneriler = (
        db.query(MenuOneriLog)
        .filter(MenuOneriLog.tarih >= hafta_baslangic, MenuOneriLog.tarih <= bitis)
        .all()
    )
    ai_yemekler = set()
    for o in ai_oneriler:
        for attr in ["corba", "ana_yemek", "yan_yemek", "tatli", "salata"]:
            y = getattr(o, attr, None)
            if y:
                ai_yemekler.add(y)

    if not gercek_yemekler:
        return {
            "success": False,
            "message": "Belirtilen dönemde gerçek menü verisi bulunamadı.",
        }

    # Metrikleri topla
    gercek_metrics = _collect_group_metrics(db, list(gercek_yemekler), hafta_baslangic, bitis)
    ai_metrics = _collect_group_metrics(db, list(ai_yemekler), hafta_baslangic, bitis)

    # ── İsraf karşılaştırması (t-test) ──
    israf_test = _ttest(gercek_metrics["israf"], ai_metrics["israf"])

    # ── Puan karşılaştırması (t-test) ──
    puan_test = _ttest(
        ai_metrics["puan"] if ai_metrics["puan"] else [0],
        gercek_metrics["puan"] if gercek_metrics["puan"] else [0],
    )

    # Genel skorlar
    gercek_ort_israf = round(float(np.mean(gercek_metrics["israf"])), 1) if gercek_metrics["israf"] else 0
    ai_ort_israf = round(float(np.mean(ai_metrics["israf"])), 1) if ai_metrics["israf"] else 0
    gercek_ort_puan = round(float(np.mean(gercek_metrics["puan"])), 2) if gercek_metrics["puan"] else 0
    ai_ort_puan = round(float(np.mean(ai_metrics["puan"])), 2) if ai_metrics["puan"] else 0

    # Kazanan belirleme
    israf_kazanan = "ai" if ai_ort_israf < gercek_ort_israf else ("gercek" if gercek_ort_israf < ai_ort_israf else "esit")
    puan_kazanan = "ai" if ai_ort_puan > gercek_ort_puan else ("gercek" if gercek_ort_puan > ai_ort_puan else "esit")

    return {
        "success": True,
        "donem": {
            "baslangic": str(hafta_baslangic),
            "bitis": str(bitis),
            "hafta_sayisi": hafta_sayisi,
        },
        "grup_a_gercek_menu": {
            "yemek_sayisi": len(gercek_yemekler),
            "ort_israf": gercek_ort_israf,
            "ort_puan": gercek_ort_puan,
            "israf_orneklem": len(gercek_metrics["israf"]),
            "puan_orneklem": len(gercek_metrics["puan"]),
        },
        "grup_b_ai_oneri": {
            "yemek_sayisi": len(ai_yemekler),
            "ort_israf": ai_ort_israf,
            "ort_puan": ai_ort_puan,
            "israf_orneklem": len(ai_metrics["israf"]),
            "puan_orneklem": len(ai_metrics["puan"]),
        },
        "israf_testi": {
            **israf_test,
            "kazanan": israf_kazanan,
            "aciklama": (
                f"AI menüsü israfı {'%' + str(round(gercek_ort_israf - ai_ort_israf, 1)) + ' azaltıyor' if israf_kazanan == 'ai' else 'daha iyi değil'}"
            ),
        },
        "puan_testi": {
            **puan_test,
            "kazanan": puan_kazanan,
            "aciklama": (
                f"AI menüsü puanı {'daha yüksek' if puan_kazanan == 'ai' else 'daha düşük veya eşit'}"
            ),
        },
        "genel_sonuc": {
            "ai_daha_iyi": israf_kazanan == "ai" or puan_kazanan == "ai",
            "oneri": (
                "AI menü önerisi israfı azaltıyor ve/veya memnuniyeti artırıyor. Kullanımı önerilir."
                if (israf_kazanan == "ai" or puan_kazanan == "ai")
                else "Gerçek menü ile AI önerisi arasında belirgin fark yok. Daha fazla veri toplanması önerilir."
            ),
        },
        "scipy_aktif": _HAS_SCIPY,
    }


def get_experiment_summary(db: Session, son_hafta: int = 8) -> dict[str, Any]:
    """Son N haftanın haftalık A/B test özetini döndürür."""
    bugun = date.today()
    haftalik_sonuclar = []

    for i in range(son_hafta):
        hafta_bitis = bugun - timedelta(days=i * 7)
        hafta_bas = hafta_bitis - timedelta(days=6)

        result = run_ab_experiment(db, hafta_baslangic=hafta_bas, hafta_sayisi=1)
        if result.get("success"):
            haftalik_sonuclar.append({
                "hafta": f"{hafta_bas.strftime('%d.%m')} - {hafta_bitis.strftime('%d.%m')}",
                "gercek_israf": result["grup_a_gercek_menu"]["ort_israf"],
                "ai_israf": result["grup_b_ai_oneri"]["ort_israf"],
                "gercek_puan": result["grup_a_gercek_menu"]["ort_puan"],
                "ai_puan": result["grup_b_ai_oneri"]["ort_puan"],
                "israf_kazanan": result["israf_testi"]["kazanan"],
            })

    return {
        "success": True,
        "son_hafta": son_hafta,
        "haftalik_sonuclar": list(reversed(haftalik_sonuclar)),
        "scipy_aktif": _HAS_SCIPY,
    }
