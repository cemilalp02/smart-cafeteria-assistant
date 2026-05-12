# -*- coding: utf-8 -*-
"""
Türkçe Duygu Analizi Modülü — Gelişmiş Sentiment
═══════════════════════════════════════════════════
N-gram eşleştirme, olumsuzlama algılama, aspect-based sentiment,
emoji desteği ve TF-IDF + Logistic Regression fallback modeli.

Öğrenci yorumlarını Türkçe anahtar kelimeler + ML ile
pozitif / negatif / nötr olarak sınıflandırır.
"""

from __future__ import annotations

import logging
import os
import re
from datetime import date, timedelta
from typing import Any, Optional

import numpy as np
from sqlalchemy import func as sqla_func
from sqlalchemy.orm import Session

from models import MenuPuanlama

logger = logging.getLogger(__name__)

# Opsiyonel bağımlılıklar
try:
    import joblib
    _HAS_JOBLIB = True
except ImportError:
    _HAS_JOBLIB = False

try:
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.linear_model import LogisticRegression
    from sklearn.model_selection import cross_val_score
    from sklearn.pipeline import Pipeline
    _HAS_SKLEARN = True
except ImportError:
    _HAS_SKLEARN = False

# ═══════════════════════════════════════════════════════════════════
# MODEL PATHS
# ═══════════════════════════════════════════════════════════════════
MODEL_DIR = os.path.join(os.path.dirname(__file__), "..", "models_data")
TFIDF_MODEL_PATH = os.path.join(MODEL_DIR, "sentiment_tfidf_model.joblib")


# ═══════════════════════════════════════════════════════════════════
# 1) EMOJİ SENTIMENT HARİTASI
# ═══════════════════════════════════════════════════════════════════
EMOJI_POZITIF = {
    "😀": 0.6, "😃": 0.6, "😄": 0.7, "😁": 0.7, "😆": 0.6,
    "😊": 0.7, "🥰": 0.8, "😍": 0.8, "🤩": 0.8, "😋": 0.7,
    "🤤": 0.7, "👍": 0.6, "👌": 0.6, "💯": 0.8, "🔥": 0.7,
    "❤️": 0.7, "💕": 0.6, "😎": 0.5, "🥳": 0.7, "✨": 0.5,
    "⭐": 0.6, "🌟": 0.6, "💪": 0.5, "👏": 0.6, "🎉": 0.6,
    "😙": 0.5, "😚": 0.5, "🫶": 0.7, "♥️": 0.6,
}

EMOJI_NEGATIF = {
    "😡": -0.8, "😠": -0.7, "😤": -0.6, "🤮": -0.9, "🤢": -0.8,
    "👎": -0.6, "😖": -0.5, "😣": -0.5, "😩": -0.6, "😫": -0.6,
    "😒": -0.4, "😑": -0.3, "💩": -0.7, "🤬": -0.9, "😾": -0.5,
    "😰": -0.4, "😥": -0.4, "😢": -0.5, "😭": -0.6,
    "🙄": -0.3, "😞": -0.5, "😟": -0.4, "☹️": -0.5, "😓": -0.4,
    "🤦": -0.4,
}

# ═══════════════════════════════════════════════════════════════════
# 2) OLUMSUZLAMA (NEGATION) KELİMELERİ
# ═══════════════════════════════════════════════════════════════════
NEGATION_WORDS = frozenset({
    "değil", "değildi", "değilmiş", "degil",
    "yok", "yoktu", "olmamış", "olmadı", "olmaz",
    "olmamis", "olmadi", "hiç", "hic",
})

NEGATION_WINDOW = 3

# ═══════════════════════════════════════════════════════════════════
# 3) N-GRAM SÖZLÜKLER (2-3 kelimelik ifadeler — öncelikli)
# ═══════════════════════════════════════════════════════════════════
NGRAM_SKORLAR: dict[str, float] = {
    # ── Pozitif bigrams ──
    "fena değil": 0.6,
    "fena değildi": 0.6,
    "fena degil": 0.6,
    "idare eder": 0.3,
    "idare ederdi": 0.3,
    "tam kıvam": 0.8,
    "tam kivam": 0.8,
    "tam kıvamında": 0.8,
    "tam pişmiş": 0.7,
    "tam pismis": 0.7,
    "tuzu yerinde": 0.7,
    "çok güzel": 0.9,
    "cok guzel": 0.9,
    "çok lezzetli": 0.9,
    "çok iyi": 0.8,
    "gayet güzel": 0.8,
    "gayet iyi": 0.7,
    "elinize sağlık": 0.8,
    "eline sağlık": 0.8,
    "eline saglik": 0.8,
    "emeğinize sağlık": 0.8,
    "harika olmuş": 0.9,
    "süper olmuş": 0.9,
    "güzel olmuş": 0.8,
    "iyi pişmiş": 0.7,
    "tam olmuş": 0.7,
    "çok doyurucu": 0.8,
    "tekrar olsun": 0.7,
    "baya iyi": 0.7,
    "bayağı iyi": 0.7,
    "pek güzel": 0.7,
    # ── Pozitif trigrams ──
    "bir harika bu": 0.9,
    "çok güzel olmuş": 0.9,
    "tam kıvamında olmuş": 0.9,
    # ── Negatif bigrams ──
    "hiç güzel değil": -0.9,
    "çok kötü": -0.9,
    "çok tuzlu": -0.7,
    "aşırı tuzlu": -0.8,
    "asiri tuzlu": -0.8,
    "aşırı yağlı": -0.7,
    "çok yağlı": -0.7,
    "hiç pişmemiş": -0.9,
    "hiç iyi değil": -0.9,
    "yenmez bu": -0.9,
    "yenilmez bu": -0.9,
    "hep aynı": -0.5,
    "her gün aynı": -0.6,
    "hiç beğenmedim": -0.8,
    "hiç sevmedim": -0.8,
    "midemi bulandırdı": -0.9,
    "tadı yok": -0.6,
    "tuzu yok": -0.6,
    "lezzeti yok": -0.7,
    "çok az": -0.6,
    "çok soğuk": -0.7,
    "buz gibi": -0.7,
    "taş gibi": -0.8,
    "tas gibi": -0.8,
    "yarım kalmış": -0.6,
    "baya kötü": -0.8,
    "bayağı kötü": -0.8,
    "tadı tuzu yok": -0.8,
    "hiç güzel olmamış": -0.9,
    "kötü kokulu": -0.8,
}

# N-gramları uzunluğuna göre sırala (uzun olanlar önce eşleşsin)
_NGRAM_SORTED = sorted(NGRAM_SKORLAR.items(), key=lambda x: len(x[0]), reverse=True)

# ASCII-folded n-gram haritası (Türkçe karaktersiz girişler için)
_TR_ASCII_TABLE_LOWER = str.maketrans(
    "çğıöşü", "cgiosu",
)
_NGRAM_FOLDED: dict[str, float] = {}
for _ng, _ns in NGRAM_SKORLAR.items():
    _folded = _ng.translate(_TR_ASCII_TABLE_LOWER)
    if _folded != _ng and _folded not in NGRAM_SKORLAR:
        _NGRAM_FOLDED[_folded] = _ns
_NGRAM_ALL_SORTED = sorted(
    list(NGRAM_SKORLAR.items()) + list(_NGRAM_FOLDED.items()),
    key=lambda x: len(x[0]), reverse=True,
)

# ═══════════════════════════════════════════════════════════════════
# 4) TEKİL KELİME SÖZLÜĞÜ (skor ağırlıklı)
# ═══════════════════════════════════════════════════════════════════
POZITIF_KELIMELER: dict[str, float] = {
    "güzel": 0.6, "lezzetli": 0.7, "harika": 0.8, "muhteşem": 0.9,
    "süper": 0.8, "enfes": 0.8, "mükemmel": 0.9, "nefis": 0.8,
    "taze": 0.5, "sıcak": 0.4, "doyurucu": 0.6, "zengin": 0.5,
    "hoş": 0.5, "iyi": 0.5, "bayıldım": 0.8, "sevdim": 0.7,
    "beğendim": 0.7, "başarılı": 0.7, "kaliteli": 0.6, "pişmiş": 0.4,
    "olmuş": 0.3, "bol": 0.5, "dolu": 0.4, "yeterli": 0.4,
    "şahane": 0.9, "bomba": 0.8, "efsane": 0.8,
    "teşekkür": 0.5, "bravo": 0.7, "helal": 0.6,
    "güzeldi": 0.6, "iyiydi": 0.5, "memnun": 0.6,
    "tatmin": 0.6, "müthiş": 0.8, "aferin": 0.6,
}

NEGATIF_KELIMELER: dict[str, float] = {
    "kötü": -0.6, "berbat": -0.8, "rezalet": -0.9, "iğrenç": -0.9,
    "korkunç": -0.8, "bayat": -0.7, "soğuk": -0.5, "tatsız": -0.6,
    "tuzsuz": -0.5, "yağlı": -0.4, "sert": -0.5, "pişmemiş": -0.7,
    "çiğ": -0.6, "yanmış": -0.7, "kokmuş": -0.8, "bozuk": -0.7,
    "eski": -0.5, "küflü": -0.8, "az": -0.3, "yetersiz": -0.5,
    "küçük": -0.3, "cılız": -0.4, "sulu": -0.3, "hamurumsu": -0.5,
    "beğenmedim": -0.7, "sevmedim": -0.7, "yenilmez": -0.8,
    "yenmez": -0.8, "olmamış": -0.5, "kötüydü": -0.6,
    "leş": -0.9, "feci": -0.8, "felaket": -0.9, "dandik": -0.7,
    "vasat": -0.4, "çöp": -0.8, "zehir": -0.9, "acı": -0.5,
    "ekşi": -0.5, "kokulu": -0.5, "kirli": -0.7, "pis": -0.7,
    "böcek": -0.9, "kıl": -0.8, "saç": -0.7, "boktan": -0.9,
}

# ASCII-folded tekil kelime haritaları (guzel→güzel, kotu→kötü vb.)
_POZ_FOLDED: dict[str, float] = {}
for _pk, _pv in POZITIF_KELIMELER.items():
    _f = _pk.translate(_TR_ASCII_TABLE_LOWER)
    if _f != _pk and _f not in POZITIF_KELIMELER:
        _POZ_FOLDED[_f] = _pv
_NEG_FOLDED: dict[str, float] = {}
for _nk, _nv in NEGATIF_KELIMELER.items():
    _f = _nk.translate(_TR_ASCII_TABLE_LOWER)
    if _f != _nk and _f not in NEGATIF_KELIMELER:
        _NEG_FOLDED[_f] = _nv

# Birleşik sözlükler (orijinal + folded)
_ALL_POZITIF = {**POZITIF_KELIMELER, **_POZ_FOLDED}
_ALL_NEGATIF = {**NEGATIF_KELIMELER, **_NEG_FOLDED}

# Folded negation words
_ALL_NEGATION = NEGATION_WORDS | frozenset(
    w.translate(_TR_ASCII_TABLE_LOWER) for w in NEGATION_WORDS
)

# ═══════════════════════════════════════════════════════════════════
# 5) ASPECT (BOYUT) KELİMELERİ + DUYGU YÖNLERİ
# ═══════════════════════════════════════════════════════════════════
ASPECT_KEYWORDS: dict[str, dict[str, list[str]]] = {
    "lezzet": {
        "pozitif": ["lezzetli", "güzel", "nefis", "enfes", "harika", "muhteşem", "şahane", "bomba"],
        "negatif": ["tatsız", "tuzsuz", "kötü", "acı", "ekşi", "berbat", "iğrenç"],
    },
    "porsiyon": {
        "pozitif": ["doyurucu", "bol", "yeterli", "dolu", "büyük"],
        "negatif": ["az", "yetersiz", "küçük", "cılız", "açık kaldım"],
    },
    "sıcaklık": {
        "pozitif": ["sıcak", "sıcacık", "ılık"],
        "negatif": ["soğuk", "donmuş", "buzlu", "buz gibi"],
    },
    "pişirme": {
        "pozitif": ["pişmiş", "kıvam", "kıvamında", "tam pişmiş"],
        "negatif": ["pişmemiş", "çiğ", "yanmış", "sert", "hamur", "hamurumsu"],
    },
    "tazelik": {
        "pozitif": ["taze", "günlük"],
        "negatif": ["bayat", "eski", "bozuk", "kokmuş", "küflü"],
    },
    "hijyen": {
        "pozitif": ["temiz", "hijyenik"],
        "negatif": ["kirli", "pis", "hijyen", "böcek", "kıl", "saç", "yabancı cisim"],
    },
    "çeşitlilik": {
        "pozitif": ["çeşitli", "farklı", "değişik", "yenilik"],
        "negatif": ["hep aynı", "tekrar", "monoton", "sıkıldım"],
    },
}

TEMA_KELIMELER = {
    "sıcaklık": ["soğuk", "ılık", "sıcak", "donmuş", "buzlu"],
    "porsiyon": ["az", "yetersiz", "küçük", "cılız", "porsiyon", "doyurucu", "bol", "yeterli"],
    "lezzet": ["tatsız", "tuzsuz", "tuzlu", "lezzetli", "güzel", "kötü", "acı", "ekşi"],
    "pişirme": ["pişmemiş", "çiğ", "yanmış", "sert", "hamur", "pişmiş", "kıvam"],
    "tazelik": ["bayat", "taze", "eski", "bozuk", "kokmuş", "küflü"],
    "hijyen": ["kirli", "pis", "hijyen", "böcek", "kıl", "saç", "yabancı cisim"],
    "çeşitlilik": ["hep aynı", "tekrar", "değişiklik", "monoton", "çeşit"],
}

# ═══════════════════════════════════════════════════════════════════
# TF-IDF MODEL — Lazy singleton
# ═══════════════════════════════════════════════════════════════════
_tfidf_pipeline: Optional[Pipeline] = None


# ═══════════════════════════════════════════════════════════════════
# YARDIMCI FONKSİYONLAR
# ═══════════════════════════════════════════════════════════════════

_TR_FOLD_TABLE = str.maketrans(
    "çğıiöşüÇĞİÖŞÜ",
    "cgiiösuCGIOSU",  # ö stays — only consonants + ı→i folded
)

_TR_ASCII_TABLE = str.maketrans(
    "çğıiöşüÇĞİÖŞÜ",
    "cgiiosuCGIOSU",
)


def _normalize_text(text: str) -> str:
    """Metni küçük harfe çevirir, fazla boşlukları temizler."""
    return re.sub(r"\s+", " ", text.lower().strip())


def _ascii_fold(text: str) -> str:
    """Türkçe karakterleri ASCII karşılıklarına dönüştürür."""
    return text.translate(_TR_ASCII_TABLE)


def _extract_emoji_score(text: str) -> float:
    """Metindeki emojilerin toplam sentiment skorunu döndürür."""
    skor = 0.0
    for ch in text:
        if ch in EMOJI_POZITIF:
            skor += EMOJI_POZITIF[ch]
        elif ch in EMOJI_NEGATIF:
            skor += EMOJI_NEGATIF[ch]
    return skor


def _extract_ngram_score(lower: str) -> tuple[float, str]:
    """
    N-gram eşleştirme: uzun ifadeler önce kontrol edilir.
    Eşleşen n-gram'lar metinden çıkarılır (tekrar sayılmaması için).
    Returns: (toplam skor, temizlenmiş metin)
    """
    skor = 0.0
    remaining = lower
    for ngram, ngram_skor in _NGRAM_ALL_SORTED:
        if ngram in remaining:
            skor += ngram_skor
            remaining = remaining.replace(ngram, " ")
    return skor, remaining


def _apply_negation(words: list[str], word_scores: list[float]) -> list[float]:
    """
    Olumsuzlama penceresi: Türkçe dil yapısına uygun negation handling.

    Kural:
      - "değil", "yok", "olmadı" vb. SONRASI gelen kelimeleri ETKİLEMEZ.
        Bunlar ÖNCEKİ kelimeye uygulanır: "güzel değil" → güzel(-)
      - "hiç", "hiçbir" gibi ÖNCE gelen olumsuzlayıcılar sonraki kelimeleri etkiler:
        "hiç güzel" → güzel(-)

    Her skor en fazla bir kez ters çevrilir (double negation önlenir).
    """
    result = list(word_scores)
    flipped = [False] * len(word_scores)

    # "hiç", "hiçbir" öne gelen negatörler
    PRE_NEGATORS = {"hiç", "hic", "hiçbir", "hicbir", "asla", "hiçte", "hicte"}

    for i, w in enumerate(words):
        if w not in _ALL_NEGATION:
            continue

        if w in PRE_NEGATORS:
            # SONRAKI pencereyi ters çevir (önceki değil)
            end = min(len(words), i + NEGATION_WINDOW + 1)
            for j in range(i + 1, end):
                if result[j] != 0.0 and not flipped[j]:
                    result[j] = -result[j]
                    flipped[j] = True
        else:
            # "değil", "yok" gibi sondaki negatörler: ÖNCEKI pencereyi ters çevir
            start = max(0, i - NEGATION_WINDOW)
            for j in range(start, i):
                if result[j] != 0.0 and not flipped[j]:
                    result[j] = -result[j]
                    flipped[j] = True

    return result


def _compute_sentiment_score(text: str) -> float:
    """
    Gelişmiş sentiment skoru hesaplama.
    Sıra: Emoji → N-gram → Tekil kelime + Negation
    Returns: -1.0 .. +1.0 arasında float skor
    """
    if not text:
        return 0.0

    # 1) Emoji skoru
    emoji_skor = _extract_emoji_score(text)

    # 2) Normalize
    lower = _normalize_text(text)

    # 3) N-gram skoru (eşleşenler metinden çıkarılır)
    ngram_skor, remaining = _extract_ngram_score(lower)

    # 4) Tekil kelime skorları (orijinal + ASCII-folded)
    words = remaining.split()
    word_scores = []
    for w in words:
        if w in _ALL_POZITIF:
            word_scores.append(_ALL_POZITIF[w])
        elif w in _ALL_NEGATIF:
            word_scores.append(_ALL_NEGATIF[w])
        else:
            word_scores.append(0.0)

    # 5) Negation uygula
    word_scores = _apply_negation(words, word_scores)
    kelime_skor = sum(word_scores)

    # 6) Toplam skor (ağırlıklı birleştir)
    toplam = emoji_skor * 1.0 + ngram_skor * 1.2 + kelime_skor * 1.0

    # Normalize: [-1, +1] aralığına kısıtla
    if toplam > 0:
        return min(1.0, toplam / max(1.0, abs(toplam) + 0.5))
    elif toplam < 0:
        return max(-1.0, toplam / max(1.0, abs(toplam) + 0.5))
    return 0.0


def _score_to_label(skor: float) -> str:
    """Float skoru etiket stringe çevirir."""
    if skor >= 0.15:
        return "pozitif"
    elif skor <= -0.15:
        return "negatif"
    return "notr"


# ═══════════════════════════════════════════════════════════════════
# TF-IDF + LOGİSTİC REGRESSİON FALLBACK
# ═══════════════════════════════════════════════════════════════════

def _load_tfidf_model() -> Optional[Pipeline]:
    """Eğitilmiş TF-IDF modelini yükler (lazy singleton)."""
    global _tfidf_pipeline
    if _tfidf_pipeline is not None:
        return _tfidf_pipeline
    if not _HAS_JOBLIB or not _HAS_SKLEARN:
        return None
    if not os.path.exists(TFIDF_MODEL_PATH):
        return None
    try:
        _tfidf_pipeline = joblib.load(TFIDF_MODEL_PATH)
        logger.info("TF-IDF sentiment modeli yuklendi: %s", TFIDF_MODEL_PATH)
        return _tfidf_pipeline
    except Exception as e:
        logger.warning("TF-IDF model yuklenemedi: %s", e)
        return None


def train_sentiment_model(db: Session, min_samples: int = 50) -> dict[str, Any]:
    """
    MenuPuanlama tablosundaki puan + yorum verisiyle
    TF-IDF + LogisticRegression modeli eğitir.

    Etiketleme: puan >= 4 → pozitif, puan <= 2 → negatif, else → nötr
    """
    if not _HAS_SKLEARN or not _HAS_JOBLIB:
        return {"success": False, "message": "sklearn veya joblib kurulu degil."}

    rows = (
        db.query(MenuPuanlama.yorum, MenuPuanlama.puan)
        .filter(MenuPuanlama.yorum.isnot(None), MenuPuanlama.yorum != "")
        .all()
    )

    if len(rows) < min_samples:
        return {
            "success": False,
            "message": f"Yetersiz yorumlu veri: {len(rows)}/{min_samples}",
            "sample_count": len(rows),
        }

    texts, labels = [], []
    for yorum, puan in rows:
        txt = _normalize_text(yorum)
        if len(txt) < 3:
            continue
        if puan >= 4:
            labels.append("pozitif")
        elif puan <= 2:
            labels.append("negatif")
        else:
            labels.append("notr")
        texts.append(txt)

    if len(texts) < min_samples:
        return {"success": False, "message": f"Filtreleme sonrasi yetersiz: {len(texts)}"}

    pipeline = Pipeline([
        ("tfidf", TfidfVectorizer(
            max_features=3000,
            ngram_range=(1, 3),
            sublinear_tf=True,
            min_df=2,
        )),
        ("clf", LogisticRegression(
            max_iter=500,
            class_weight="balanced",
            C=1.0,
            random_state=42,
        )),
    ])

    # Cross-validation
    cv_scores = cross_val_score(pipeline, texts, labels, cv=min(5, len(texts) // 10), scoring="f1_macro")

    # Final fit
    pipeline.fit(texts, labels)

    # Kaydet
    os.makedirs(MODEL_DIR, exist_ok=True)
    joblib.dump(pipeline, TFIDF_MODEL_PATH)

    global _tfidf_pipeline
    _tfidf_pipeline = pipeline

    logger.info("TF-IDF sentiment modeli egitildi: %d ornek, CV F1=%.3f", len(texts), np.mean(cv_scores))

    return {
        "success": True,
        "message": f"Model egitildi: {len(texts)} ornek",
        "sample_count": len(texts),
        "cv_f1_macro": round(float(np.mean(cv_scores)), 3),
        "cv_f1_std": round(float(np.std(cv_scores)), 3),
        "model_path": TFIDF_MODEL_PATH,
        "label_distribution": {
            "pozitif": labels.count("pozitif"),
            "negatif": labels.count("negatif"),
            "notr": labels.count("notr"),
        },
    }


def _predict_with_tfidf(text: str) -> Optional[str]:
    """TF-IDF modeli varsa tahmin döndürür, yoksa None."""
    model = _load_tfidf_model()
    if model is None:
        return None
    try:
        pred = model.predict([_normalize_text(text)])[0]
        return pred
    except Exception:
        return None


# ═══════════════════════════════════════════════════════════════════
# ASPECT-BASED SENTIMENT
# ═══════════════════════════════════════════════════════════════════

def _extract_aspect_sentiments(text: str) -> list[dict[str, Any]]:
    """
    Yorumdan boyut bazlı (aspect-based) sentiment çıkarır.
    Her aspect için: tespit edildi mi, duygu yönü, eşleşen kelimeler.
    """
    if not text:
        return []

    lower = _normalize_text(text)
    result = []

    for aspect, yonler in ASPECT_KEYWORDS.items():
        poz_eslesen = [k for k in yonler["pozitif"] if k in lower]
        neg_eslesen = [k for k in yonler["negatif"] if k in lower]

        if not poz_eslesen and not neg_eslesen:
            continue

        if len(poz_eslesen) > len(neg_eslesen):
            durum = "pozitif"
        elif len(neg_eslesen) > len(poz_eslesen):
            durum = "negatif"
        else:
            durum = "notr"

        result.append({
            "aspect": aspect,
            "durum": durum,
            "pozitif_kelimeler": poz_eslesen,
            "negatif_kelimeler": neg_eslesen,
        })

    return result


# ═══════════════════════════════════════════════════════════════════
# DUYGU ANALİZ FONKSİYONLARI (Public API)
# ═══════════════════════════════════════════════════════════════════

def _analyze_text(text: str) -> str:
    """
    Tek bir yorumu pozitif/negatif/nötr olarak sınıflandırır.

    Öncelik sırası:
      1. TF-IDF model (varsa)
      2. Kural tabanlı: emoji + n-gram + tekil kelime + negation
    """
    if not text:
        return "notr"

    # Kural tabanlı skor
    skor = _compute_sentiment_score(text)
    rule_label = _score_to_label(skor)

    # TF-IDF model varsa önce onu dene
    tfidf_pred = _predict_with_tfidf(text)
    if tfidf_pred is not None:
        # Negation kelimesi varsa ve TF-IDF ile kural-tabanlı sonuç çelişiyorsa
        # kural-tabanlı sistemi tercih et (TF-IDF negation'da zayıf)
        lower = _normalize_text(text)
        has_negation = any(w in lower.split() for w in _ALL_NEGATION)
        if has_negation and tfidf_pred != rule_label:
            return rule_label
        return tfidf_pred

    return rule_label


def _analyze_text_detailed(text: str) -> dict[str, Any]:
    """
    Detaylı sentiment analizi: skor, etiket, aspect'ler, kullanılan yöntem.
    """
    if not text:
        return {"label": "notr", "skor": 0.0, "method": "empty", "aspects": []}

    method = "rule_based"
    tfidf_pred = _predict_with_tfidf(text)
    if tfidf_pred is not None:
        method = "tfidf_model"

    skor = _compute_sentiment_score(text)
    label = tfidf_pred if tfidf_pred else _score_to_label(skor)
    aspects = _extract_aspect_sentiments(text)

    return {
        "label": label,
        "skor": round(skor, 3),
        "method": method,
        "aspects": aspects,
    }


def _detect_themes(text: str) -> list[str]:
    """Yorumdaki temaları tespit eder."""
    if not text:
        return []

    lower = _normalize_text(text)
    bulunan = []

    for tema, kelimeler in TEMA_KELIMELER.items():
        if any(k in lower for k in kelimeler):
            bulunan.append(tema)

    return bulunan


def _combined_sentiment(puan: int, yorum: str = "") -> str:
    """Puan + yorum birleştirilerek sentiment belirlenir."""
    if yorum:
        text_sent = _analyze_text(yorum)
        # Yorum varsa ağırlıklı olarak yorum belirler
        if text_sent != "notr":
            return text_sent

    # Yorum nötr veya yoksa puana bak
    if puan >= 4:
        return "pozitif"
    elif puan <= 2:
        return "negatif"
    return "notr"


# ═══════════════════════════════════════════════════════════════════
# ANA ANALİZ FONKSİYONU
# ═══════════════════════════════════════════════════════════════════

def analyze_sentiment(db: Session, gun: int = 30) -> dict[str, Any]:
    """
    Son N gündeki tüm puanlamaları sentiment analiz eder.

    Returns:
        dict: duygu dağılımı, tema analizi, yemek bazlı skorlar
    """
    baslangic = date.today() - timedelta(days=gun)

    # Tüm puanlamalar
    puanlamalar = (
        db.query(
            MenuPuanlama.yemek_adi,
            MenuPuanlama.kategori,
            MenuPuanlama.puan,
            MenuPuanlama.yorum,
            MenuPuanlama.tarih,
        )
        .filter(MenuPuanlama.tarih >= baslangic)
        .order_by(MenuPuanlama.created_at.desc())
        .all()
    )

    if not puanlamalar:
        return {
            "success": True,
            "veri_var": False,
            "mesaj": "Belirtilen dönemde puanlama verisi bulunamadı.",
        }

    # ── Duygu dağılımı ──
    duygu = {"pozitif": 0, "negatif": 0, "notr": 0}
    tema_sayaci: dict[str, int] = {}
    aspect_sayaci: dict[str, dict[str, int]] = {}
    yemek_duygular: dict[str, dict] = {}
    yontem_sayaci = {"rule_based": 0, "tfidf_model": 0}

    for p in puanlamalar:
        sent = _combined_sentiment(p.puan, p.yorum or "")
        duygu[sent] += 1

        # Tema tespiti (sadece yorumlu olanlar)
        if p.yorum:
            temalar = _detect_themes(p.yorum)
            for t in temalar:
                tema_sayaci[t] = tema_sayaci.get(t, 0) + 1

            # Aspect-based sentiment toplama
            aspects = _extract_aspect_sentiments(p.yorum)
            for asp in aspects:
                a_name = asp["aspect"]
                if a_name not in aspect_sayaci:
                    aspect_sayaci[a_name] = {"pozitif": 0, "negatif": 0, "notr": 0}
                aspect_sayaci[a_name][asp["durum"]] += 1

            # Yöntem takibi
            detail = _analyze_text_detailed(p.yorum)
            yontem_sayaci[detail["method"]] = yontem_sayaci.get(detail["method"], 0) + 1

        # Yemek bazlı
        if p.yemek_adi not in yemek_duygular:
            yemek_duygular[p.yemek_adi] = {
                "kategori": p.kategori,
                "pozitif": 0, "negatif": 0, "notr": 0,
                "toplam_puan": 0, "sayi": 0,
            }
        yd = yemek_duygular[p.yemek_adi]
        yd[sent] += 1
        yd["toplam_puan"] += p.puan
        yd["sayi"] += 1

    toplam = duygu["pozitif"] + duygu["negatif"] + duygu["notr"]

    # ── Yemek bazlı duygu skorları ──
    yemek_skorlari = []
    for yemek, yd in yemek_duygular.items():
        if yd["sayi"] == 0:
            continue
        ort_puan = round(yd["toplam_puan"] / yd["sayi"], 1)
        # Duygu skoru: -1.0 .. +1.0
        skor = round((yd["pozitif"] - yd["negatif"]) / yd["sayi"], 2)

        if skor >= 0.3:
            durum = "😀 Beğeniliyor"
        elif skor <= -0.3:
            durum = "😡 Beğenilmiyor"
        else:
            durum = "😐 Nötr"

        yemek_skorlari.append({
            "yemek_adi": yemek,
            "kategori": yd["kategori"],
            "duygu_skoru": skor,
            "durum": durum,
            "ort_puan": ort_puan,
            "pozitif": yd["pozitif"],
            "negatif": yd["negatif"],
            "notr": yd["notr"],
        })

    # Sırala: en kötüden en iyiye
    yemek_skorlari.sort(key=lambda x: x["duygu_skoru"])

    # ── Tema sıralaması ──
    tema_sirali = sorted(tema_sayaci.items(), key=lambda x: x[1], reverse=True)

    TEMA_LABELS = {
        "sıcaklık": "🌡️ Sıcaklık",
        "porsiyon": "🍽️ Porsiyon",
        "lezzet": "👅 Lezzet",
        "pişirme": "🔥 Pişirme",
        "tazelik": "🌿 Tazelik",
        "hijyen": "🧼 Hijyen",
        "çeşitlilik": "🔄 Çeşitlilik",
    }

    # ── Aspect özet ──
    aspect_ozet = []
    for asp_name, counts in aspect_sayaci.items():
        t = counts["pozitif"] + counts["negatif"] + counts["notr"]
        if t == 0:
            continue
        aspect_ozet.append({
            "aspect": TEMA_LABELS.get(asp_name, asp_name),
            "aspect_key": asp_name,
            "pozitif": counts["pozitif"],
            "negatif": counts["negatif"],
            "notr": counts["notr"],
            "toplam": t,
            "skor": round((counts["pozitif"] - counts["negatif"]) / t, 2),
        })
    aspect_ozet.sort(key=lambda x: x["toplam"], reverse=True)

    # Kullanılan analiz yöntemi
    tfidf_aktif = _load_tfidf_model() is not None

    return {
        "success": True,
        "veri_var": True,
        "donem_gun": gun,
        "toplam_puanlama": toplam,
        "analiz_yontemi": "tfidf_model + rule_based" if tfidf_aktif else "rule_based (n-gram + negation + emoji)",
        "yontem_dagilimi": yontem_sayaci,
        "duygu_dagilimi": {
            **duygu,
            "pozitif_yuzde": round(duygu["pozitif"] / toplam * 100, 1) if toplam > 0 else 0,
            "negatif_yuzde": round(duygu["negatif"] / toplam * 100, 1) if toplam > 0 else 0,
            "notr_yuzde": round(duygu["notr"] / toplam * 100, 1) if toplam > 0 else 0,
        },
        "tema_analizi": [
            {"tema": TEMA_LABELS.get(t, t), "sayi": s}
            for t, s in tema_sirali[:7]
        ],
        "aspect_analizi": aspect_ozet,
        "yemek_duygulari": yemek_skorlari,
        "en_begenilenler": [y for y in reversed(yemek_skorlari) if y["duygu_skoru"] >= 0.3][:5],
        "en_begenilmeyenler": [y for y in yemek_skorlari if y["duygu_skoru"] <= -0.3][:5],
    }
