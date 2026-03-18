"""
AI Tabanlı Akıllı Yemekhane Asistan Sistemi - Veritabanı Modelleri

Tablolar:
  - Yemek: Yemek bilgileri ve besin değerleri
  - Menu: Günlük menü planları
  - Kullanici: Kullanıcı profilleri
  - KullaniciYemekLog: Kullanıcı yemek tüketim kayıtları
  - MenuPuanlama: Anonim günlük menü puanlama kayıtları
  - Alert: Otomatik israf uyarı kayıtları
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
engine = create_engine(
    active_config.DATABASE_URL,
    echo=active_config.DEBUG,
    connect_args={"check_same_thread": False},  # SQLite için gerekli
)

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
        comment="corba | ana_yemek | pilav | tatli | salata | icecek",
    )
    kalori = Column(Float, nullable=False, default=0.0)
    protein = Column(Float, nullable=False, default=0.0)
    karbonhidrat = Column(Float, nullable=False, default=0.0)
    yag = Column(Float, nullable=False, default=0.0)

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
    pilav = Column(String(100), nullable=True)
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
            "pilav": self.pilav,
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
        comment="corba | ana_yemek | pilav | tatli | salata | icecek",
    )
    puan = Column(Integer, nullable=False, comment="1-5 arası yıldız puanı")
    yorum = Column(String(500), nullable=True, default=None)
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
        comment="corba | ana_yemek | pilav | tatli | salata",
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
            "created_at": str(self.created_at),
        }


# ─── Tabloları oluştur ────────────────────────────────────────────
def init_db():
    """Tüm tabloları veritabanında oluşturur."""
    Base.metadata.create_all(bind=engine)
    print("✅ Veritabanı tabloları oluşturuldu.")


if __name__ == "__main__":
    init_db()
