"""
AI Tabanlı Akıllı Yemekhane Asistan Sistemi - Veritabanı Modelleri

Tablolar:
  - Yemek: Yemek bilgileri ve besin değerleri
  - Menu: Günlük menü planları
  - Kullanici: Kullanıcı profilleri
  - KullaniciYemekLog: Kullanıcı yemek tüketim kayıtları
  - MenuPuanlama: Anonim günlük menü puanlama kayıtları
  - Alert: Otomatik israf uyarı kayıtları
  - MenuOneriLog: AI menü önerisi kayıtları (A/B test)
"""

from datetime import date, datetime

from sqlalchemy import (
    Column,
    Integer,
    String,
    Float,
    Date,
    DateTime,
    Boolean,
    ForeignKey,
    Enum,
    create_engine,
)
from sqlalchemy.orm import declarative_base, relationship, sessionmaker

from config import active_config

# ─── Veritabanı motoru ve oturum ───────────────────────────────────
_engine_kwargs = {"echo": active_config.DEBUG}
if active_config.DATABASE_URL.startswith("sqlite"):
    _engine_kwargs["connect_args"] = {"check_same_thread": False}
else:
    _engine_kwargs["pool_size"] = 10
    _engine_kwargs["max_overflow"] = 20
    _engine_kwargs["pool_pre_ping"] = True

engine = create_engine(active_config.DATABASE_URL, **_engine_kwargs)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


# ─── Yardımcı: DB oturumu oluştur ─────────────────────────────────
def get_db():
    """FastAPI dependency olarak kullanılacak DB oturumu üreteci."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# ═══════════════════════════════════════════════════════════════════
# MODEL: Yemek
# ═══════════════════════════════════════════════════════════════════
class Yemek(Base):
    """Yemek bilgileri ve besin değerleri tablosu."""

    __tablename__ = "yemekler"

    id = Column(Integer, primary_key=True, autoincrement=True)
    ad = Column(String(100), nullable=False, unique=True)
    kategori = Column(
        String(50),
        nullable=False,
        comment="corba | ana_yemek | yan_yemek | tatli | salata | icecek",
    )
    kalori = Column(Float, nullable=False, default=0.0)
    protein = Column(Float, nullable=False, default=0.0)
    karbonhidrat = Column(Float, nullable=False, default=0.0)
    yag = Column(Float, nullable=False, default=0.0)
    # ── Maliyet Alanı (nullable — mevcut sistemi bozmaz) ──
    birim_maliyet = Column(
        Float,
        nullable=True,
        default=None,
        comment="Porsiyon başı maliyet (TL)",
    )

    # İlişki
    yemek_loglari = relationship("KullaniciYemekLog", back_populates="yemek")

    def __repr__(self):
        return f"<Yemek(id={self.id}, ad='{self.ad}', kalori={self.kalori})>"

    def to_dict(self):
        return {
            "id": self.id,
            "ad": self.ad,
            "kategori": self.kategori,
            "kalori": self.kalori,
            "protein": self.protein,
            "karbonhidrat": self.karbonhidrat,
            "yag": self.yag,
            "birim_maliyet": self.birim_maliyet,
        }


# ═══════════════════════════════════════════════════════════════════
# MODEL: Menu
# ═══════════════════════════════════════════════════════════════════
class Menu(Base):
    """Günlük menü planı tablosu."""

    __tablename__ = "menuler"

    id = Column(Integer, primary_key=True, autoincrement=True)
    tarih = Column(Date, nullable=False, default=date.today)
    gun = Column(
        String(20),
        nullable=False,
        comment="Pazartesi, Salı, Çarşamba, Perşembe, Cuma",
    )
    corba = Column(String(100), nullable=True)
    ana_yemek = Column(String(100), nullable=True)
    yan_yemek = Column(String(100), nullable=True)
    tatli = Column(String(100), nullable=True)
    salata = Column(String(100), nullable=True)

    def __repr__(self):
        return f"<Menu(id={self.id}, tarih={self.tarih}, gun='{self.gun}')>"

    def to_dict(self):
        return {
            "id": self.id,
            "tarih": str(self.tarih),
            "gun": self.gun,
            "corba": self.corba,
            "ana_yemek": self.ana_yemek,
            "yan_yemek": self.yan_yemek,
            "tatli": self.tatli,
            "salata": self.salata,
        }


# ═══════════════════════════════════════════════════════════════════
# MODEL: Kullanici
# ═══════════════════════════════════════════════════════════════════
class Kullanici(Base):
    """Kullanıcı profili tablosu."""

    __tablename__ = "kullanicilar"

    id = Column(Integer, primary_key=True, autoincrement=True)
    ad = Column(String(100), nullable=False)
    email = Column(String(150), nullable=False, unique=True)
    gunluk_kalori_hedefi = Column(Float, nullable=False, default=2000.0)

    # İlişki
    yemek_loglari = relationship("KullaniciYemekLog", back_populates="kullanici")

    def __repr__(self):
        return f"<Kullanici(id={self.id}, ad='{self.ad}')>"

    def to_dict(self):
        return {
            "id": self.id,
            "ad": self.ad,
            "email": self.email,
            "gunluk_kalori_hedefi": self.gunluk_kalori_hedefi,
        }


# ═══════════════════════════════════════════════════════════════════
# MODEL: KullaniciYemekLog
# ═══════════════════════════════════════════════════════════════════
class KullaniciYemekLog(Base):
    """Kullanıcı yemek tüketim kaydı tablosu."""

    __tablename__ = "kullanici_yemek_log"

    id = Column(Integer, primary_key=True, autoincrement=True)
    kullanici_id = Column(
        Integer,
        ForeignKey("kullanicilar.id"),
        nullable=False,
    )
    yemek_id = Column(
        Integer,
        ForeignKey("yemekler.id"),
        nullable=False,
    )
    tarih = Column(DateTime, nullable=False, default=datetime.utcnow)
    miktar = Column(Float, nullable=False, default=1.0, comment="Porsiyon miktarı")
    kaynak_tipi = Column(
        String(20),
        nullable=False,
        default="manuel",
        comment="foto | chatbot | manuel",
    )

    # İlişkiler
    kullanici = relationship("Kullanici", back_populates="yemek_loglari")
    yemek = relationship("Yemek", back_populates="yemek_loglari")

    def __repr__(self):
        return (
            f"<KullaniciYemekLog(id={self.id}, "
            f"kullanici_id={self.kullanici_id}, "
            f"yemek_id={self.yemek_id})>"
        )

    def to_dict(self):
        return {
            "id": self.id,
            "kullanici_id": self.kullanici_id,
            "yemek_id": self.yemek_id,
            "tarih": str(self.tarih),
            "miktar": self.miktar,
            "kaynak_tipi": self.kaynak_tipi,
        }


# ═══════════════════════════════════════════════════════════════════
# MODEL: MenuPuanlama (Anonim)
# ═══════════════════════════════════════════════════════════════════
class MenuPuanlama(Base):
    """Anonim günlük menü puanlama tablosu.
    Kullanıcı bilgisi tutulmaz, puanlama tamamen anonimdir.
    """

    __tablename__ = "menu_puanlama"

    id = Column(Integer, primary_key=True, autoincrement=True)
    tarih = Column(Date, nullable=False, default=date.today)
    yemek_adi = Column(String(100), nullable=False)
    kategori = Column(
        String(50),
        nullable=False,
        comment="corba | ana_yemek | yan_yemek | tatli | salata | icecek",
    )
    puan = Column(Integer, nullable=False, comment="1-5 arası yıldız puanı")
    yorum = Column(String(500), nullable=True, default=None)
    israf_self_report = Column(
        Integer,
        nullable=True,
        default=None,
        comment="Öğrenci israf self-report: 0=hiç, 1=az(<%25), 2=orta(%25-50), 3=çok(>%50)",
    )
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    def __repr__(self):
        return (
            f"<MenuPuanlama(id={self.id}, tarih={self.tarih}, "
            f"yemek='{self.yemek_adi}', puan={self.puan})>"
        )

    def to_dict(self):
        return {
            "id": self.id,
            "tarih": str(self.tarih),
            "yemek_adi": self.yemek_adi,
            "kategori": self.kategori,
            "puan": self.puan,
            "yorum": self.yorum,
            "israf_self_report": self.israf_self_report,
            "created_at": str(self.created_at),
        }


# ═══════════════════════════════════════════════════════════════════
# MODEL: Alert (Otomatik Uyarı)
# ═══════════════════════════════════════════════════════════════════
class Alert(Base):
    """Otomatik israf ve kalite uyarıları tablosu."""

    __tablename__ = "alerts"

    id = Column(Integer, primary_key=True, autoincrement=True)
    tarih = Column(Date, nullable=False, default=date.today)
    seviye = Column(
        String(20),
        nullable=False,
        comment="KRITIK | UYARI | DIKKAT | BILGI",
    )
    yemek_adi = Column(String(100), nullable=True)
    kategori = Column(String(50), nullable=True)
    mesaj = Column(String(500), nullable=False)
    aktif = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    def __repr__(self):
        return (
            f"<Alert(id={self.id}, seviye='{self.seviye}', "
            f"yemek='{self.yemek_adi}', aktif={self.aktif})>"
        )

    def to_dict(self):
        return {
            "id": self.id,
            "tarih": str(self.tarih),
            "seviye": self.seviye,
            "yemek_adi": self.yemek_adi,
            "kategori": self.kategori,
            "mesaj": self.mesaj,
            "aktif": self.aktif,
            "created_at": str(self.created_at),
        }


# ═══════════════════════════════════════════════════════════════════
# MODEL: UretimLog (Günlük Üretim & Tüketim Kaydı)
# ═══════════════════════════════════════════════════════════════════
class UretimLog(Base):
    """Günlük üretim miktarı ve kalan (israf) miktarı kaydı.

    Yemekhane yöneticisi her gün üretilen porsiyon sayısı ve
    yemek sonunda kalan (çöpe giden) porsiyon sayısını girer.
    Sistem tüketim oranını otomatik hesaplar.
    """

    __tablename__ = "uretim_log"

    id = Column(Integer, primary_key=True, autoincrement=True)
    tarih = Column(Date, nullable=False, default=date.today)
    yemek_adi = Column(String(100), nullable=False)
    kategori = Column(
        String(50),
        nullable=False,
        comment="corba | ana_yemek | yan_yemek | tatli | salata",
    )
    uretilen_porsiyon = Column(
        Float, nullable=False, comment="Üretilen toplam porsiyon sayısı"
    )
    kalan_porsiyon = Column(
        Float, nullable=False, comment="Yemek sonunda kalan (israf) porsiyon"
    )
    tuketim_orani = Column(
        Float, nullable=True, comment="Otomatik hesaplanan tüketim yüzdesi"
    )
    israf_orani = Column(
        Float, nullable=True, comment="Otomatik hesaplanan israf yüzdesi"
    )
    notlar = Column(String(500), nullable=True, default=None)
    # ── IoT Tartı Alanları (nullable — mevcut sistemi bozmaz) ──
    tartilan_israf_kg = Column(
        Float,
        nullable=True,
        default=None,
        comment="IoT tartıdan gelen gerçek israf ağırlığı (kg)",
    )
    tartilan_israf_kaynagi = Column(
        String(30),
        nullable=True,
        default=None,
        comment="Veri kaynağı: iot_tarti | simulasyon | manuel",
    )
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    def __repr__(self):
        return (
            f"<UretimLog(id={self.id}, tarih={self.tarih}, "
            f"yemek='{self.yemek_adi}', üretilen={self.uretilen_porsiyon}, "
            f"kalan={self.kalan_porsiyon})>"
        )

    def to_dict(self):
        return {
            "id": self.id,
            "tarih": str(self.tarih),
            "yemek_adi": self.yemek_adi,
            "kategori": self.kategori,
            "uretilen_porsiyon": self.uretilen_porsiyon,
            "kalan_porsiyon": self.kalan_porsiyon,
            "tuketim_orani": self.tuketim_orani,
            "israf_orani": self.israf_orani,
            "notlar": self.notlar,
            "tartilan_israf_kg": self.tartilan_israf_kg,
            "tartilan_israf_kaynagi": self.tartilan_israf_kaynagi,
            "created_at": str(self.created_at),
        }


# ═══════════════════════════════════════════════════════════════════
# MODEL: MenuOneriLog (AI Menü Önerisi — A/B Test)
# ═══════════════════════════════════════════════════════════════════
class MenuOneriLog(Base):
    """AI menü optimizasyonu önerisi kaydı.

    Her haftalık menü önerisi oluşturulduğunda bu tabloya yazılır.
    Gerçek menü (Menu tablosu / UretimLog) ile karşılaştırılarak
    A/B test raporu üretilir.
    """

    __tablename__ = "menu_oneri_log"

    id = Column(Integer, primary_key=True, autoincrement=True)
    hafta_baslangic = Column(Date, nullable=False, comment="Önerilen haftanın Pazartesi tarihi")
    gun = Column(String(20), nullable=False)
    tarih = Column(Date, nullable=False)
    corba = Column(String(100), nullable=True)
    ana_yemek = Column(String(100), nullable=True)
    yan_yemek = Column(String(100), nullable=True)
    tatli = Column(String(100), nullable=True)
    salata = Column(String(100), nullable=True)
    toplam_skor = Column(Float, nullable=True, comment="Multi-objective toplam skor")
    beslenme_skoru = Column(Float, nullable=True)
    israf_skoru = Column(Float, nullable=True)
    maliyet_skoru = Column(Float, nullable=True)
    populerlik_skoru = Column(Float, nullable=True)
    toplam_kalori = Column(Float, nullable=True)
    toplam_protein = Column(Float, nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    def __repr__(self):
        return f"<MenuOneriLog(id={self.id}, tarih={self.tarih}, gun='{self.gun}')>"

    def to_dict(self):
        return {
            "id": self.id,
            "hafta_baslangic": str(self.hafta_baslangic),
            "gun": self.gun,
            "tarih": str(self.tarih),
            "corba": self.corba,
            "ana_yemek": self.ana_yemek,
            "yan_yemek": self.yan_yemek,
            "tatli": self.tatli,
            "salata": self.salata,
            "toplam_skor": self.toplam_skor,
            "beslenme_skoru": self.beslenme_skoru,
            "israf_skoru": self.israf_skoru,
            "maliyet_skoru": self.maliyet_skoru,
            "populerlik_skoru": self.populerlik_skoru,
            "toplam_kalori": self.toplam_kalori,
            "toplam_protein": self.toplam_protein,
            "created_at": str(self.created_at),
        }


# ═══════════════════════════════════════════════════════════════════
# MODEL: MenuAlternatif (Haftalık Oylama Alternatifleri)
# ═══════════════════════════════════════════════════════════════════
class MenuAlternatif(Base):
    """AI tarafından üretilen haftalık menü alternatifleri (A/B/C)."""

    __tablename__ = "menu_alternatif"

    id = Column(Integer, primary_key=True, autoincrement=True)
    hafta = Column(String(10), nullable=False, comment="ISO hafta: 2026-W19")
    alternatif = Column(String(1), nullable=False, comment="A / B / C")
    etiket = Column(String(30), nullable=False, comment="Dengeli / Popüler / Ekonomik")
    menu_json = Column(String(5000), nullable=False, comment="5 günlük menü JSON")
    skor_israf = Column(Float, nullable=True)
    skor_maliyet = Column(Float, nullable=True)
    skor_populerlik = Column(Float, nullable=True)
    skor_beslenme = Column(Float, nullable=True)
    oy_sayisi = Column(Integer, nullable=False, default=0)
    aktif = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    def __repr__(self):
        return f"<MenuAlternatif(hafta='{self.hafta}', alt='{self.alternatif}', etiket='{self.etiket}')>"

    def to_dict(self):
        import json as _json
        return {
            "id": self.id,
            "hafta": self.hafta,
            "alternatif": self.alternatif,
            "etiket": self.etiket,
            "menu": _json.loads(self.menu_json) if self.menu_json else [],
            "skor_israf": self.skor_israf,
            "skor_maliyet": self.skor_maliyet,
            "skor_populerlik": self.skor_populerlik,
            "skor_beslenme": self.skor_beslenme,
            "oy_sayisi": self.oy_sayisi,
            "aktif": self.aktif,
            "created_at": str(self.created_at),
        }


# ═══════════════════════════════════════════════════════════════════
# MODEL: MenuOylama (Öğrenci Oyları)
# ═══════════════════════════════════════════════════════════════════
class MenuOylama(Base):
    """Öğrencilerin menü alternatifi oyları (anonim)."""

    __tablename__ = "menu_oylama"

    id = Column(Integer, primary_key=True, autoincrement=True)
    hafta = Column(String(10), nullable=False, comment="ISO hafta: 2026-W19")
    secilen_alternatif = Column(String(1), nullable=False, comment="A / B / C")
    anonim_id = Column(String(64), nullable=True, comment="Tarayıcı parmak izi — mükerrer oy engeli")
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    def __repr__(self):
        return f"<MenuOylama(hafta='{self.hafta}', secilen='{self.secilen_alternatif}')>"


# ═══════════════════════════════════════════════════════════════════
# MODEL: AnomaliKaydi (Anomali Tespit Kayıtları — Öneri 4B)
# ═══════════════════════════════════════════════════════════════════
class AnomaliKaydi(Base):
    """Otomatik anomali tespit sistemi tarafından üretilen kayıtlar.

    Z-score ve Isolation Forest yöntemleriyle tespit edilen anormal
    israf/tüketim olaylarını saklar. Yönetici 'çözüldü' olarak
    işaretleyebilir, geçmiş analizleri için pattern çıkarımı yapılır.
    """

    __tablename__ = "anomali_kayitlari"

    id = Column(Integer, primary_key=True, autoincrement=True)
    tarih = Column(Date, nullable=False, default=date.today, index=True)
    yemek_adi = Column(String(100), nullable=True)
    kategori = Column(String(50), nullable=True)

    # Anomali metadata
    anomali_tipi = Column(
        String(40),
        nullable=False,
        comment="ISRAF_ARTIS | ISRAF_DUSUS | TUKETIM_DUSUS | KATEGORI_SAPMA",
    )
    yontem = Column(
        String(30),
        nullable=False,
        comment="zscore | isolation_forest | combined",
    )
    skor = Column(
        Float,
        nullable=False,
        comment="Anomali şiddet skoru (0-1, 1=en şiddetli)",
    )
    siddet = Column(
        String(20),
        nullable=False,
        comment="DUSUK | ORTA | YUKSEK | KRITIK",
    )

    # Sayısal değerler
    beklenen_deger = Column(Float, nullable=True, comment="Modelin beklediği değer")
    gerceklesen_deger = Column(Float, nullable=True, comment="Gerçekleşen değer")
    sapma_yuzdesi = Column(Float, nullable=True, comment="Sapma yüzdesi (%)")

    # Açıklama ve durum
    aciklama = Column(String(500), nullable=False)
    cozuldu_mu = Column(Boolean, nullable=False, default=False)
    cozum_notu = Column(String(500), nullable=True, default=None)
    cozum_tarihi = Column(DateTime, nullable=True, default=None)

    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    def __repr__(self):
        return (
            f"<AnomaliKaydi(id={self.id}, tip='{self.anomali_tipi}', "
            f"yemek='{self.yemek_adi}', siddet='{self.siddet}', skor={self.skor:.2f})>"
        )

    def to_dict(self):
        return {
            "id": self.id,
            "tarih": str(self.tarih),
            "yemek_adi": self.yemek_adi,
            "kategori": self.kategori,
            "anomali_tipi": self.anomali_tipi,
            "yontem": self.yontem,
            "skor": round(self.skor, 4) if self.skor is not None else None,
            "siddet": self.siddet,
            "beklenen_deger": round(self.beklenen_deger, 2) if self.beklenen_deger is not None else None,
            "gerceklesen_deger": round(self.gerceklesen_deger, 2) if self.gerceklesen_deger is not None else None,
            "sapma_yuzdesi": round(self.sapma_yuzdesi, 1) if self.sapma_yuzdesi is not None else None,
            "aciklama": self.aciklama,
            "cozuldu_mu": self.cozuldu_mu,
            "cozum_notu": self.cozum_notu,
            "cozum_tarihi": str(self.cozum_tarihi) if self.cozum_tarihi else None,
            "created_at": str(self.created_at),
        }


# ═══════════════════════════════════════════════════════════════════
# MODEL: PushToken (Expo Push Notification token'ları)
# ═══════════════════════════════════════════════════════════════════
class PushToken(Base):
    """Mobil cihazların Expo push token'larını kalıcı olarak saklar."""

    __tablename__ = "push_tokens"

    id = Column(Integer, primary_key=True, autoincrement=True)
    token = Column(String(200), nullable=False, unique=True, index=True)
    platform = Column(String(20), nullable=True, default=None)  # ios | android | web
    aktif = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    last_seen_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    def to_dict(self):
        return {
            "id": self.id,
            "token": self.token,
            "platform": self.platform,
            "aktif": self.aktif,
            "created_at": str(self.created_at),
            "last_seen_at": str(self.last_seen_at),
        }


# ─── Tabloları oluştur ────────────────────────────────────────────
def init_db():
    """Tüm tabloları veritabanında oluşturur."""
    Base.metadata.create_all(bind=engine)
    print("[OK] Veritabani tablolari olusturuldu.")


if __name__ == "__main__":
    init_db()
