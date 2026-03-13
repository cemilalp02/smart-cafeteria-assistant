"""
Modül 3 Test Scripti: Chatbot Yemekhane Asistanı
═══════════════════════════════════════════════════
Gemini API entegrasyonunu, function calling'i ve
konuşma geçmişi yönetimini test eder.

Kullanım:
    cd ai_yemekhane
    python scripts/test_chatbot.py
"""

import os
import sys
import time

# Proje kök dizinini PATH'e ekle
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import active_config
from models import init_db, SessionLocal, Kullanici, Yemek, KullaniciYemekLog
from modules.chatbot import init_chatbot, get_response, get_meal_recommendation


def print_header(title: str):
    """Test başlığı yazdırır."""
    print(f"\n{'═' * 60}")
    print(f"  {title}")
    print(f"{'═' * 60}")


def print_test(num: int, desc: str):
    """Test numarası ve açıklaması."""
    print(f"\n{'─' * 50}")
    print(f"  TEST {num}: {desc}")
    print(f"{'─' * 50}")


def ensure_test_user(db) -> int:
    """Test kullanıcısı oluşturur veya mevcut olanı döndürür."""
    kullanici = db.query(Kullanici).filter(Kullanici.email == "test@chatbot.com").first()
    if not kullanici:
        kullanici = Kullanici(
            ad="Test Öğrenci",
            email="test@chatbot.com",
            gunluk_kalori_hedefi=2000.0,
        )
        db.add(kullanici)
        db.commit()
        db.refresh(kullanici)
        print(f"  ✅ Test kullanıcısı oluşturuldu: ID={kullanici.id}")
    else:
        print(f"  ℹ️  Mevcut test kullanıcısı: ID={kullanici.id}")
    return kullanici.id


def test_api_connection():
    """Test 1: Gemini API bağlantısını doğrular."""
    print_test(1, "Gemini API Bağlantı Kontrolü")

    api_key = active_config.GEMINI_API_KEY
    if not api_key:
        print("  ❌ GEMINI_API_KEY .env dosyasında ayarlanmamış!")
        print("  💡 .env dosyasına geçerli bir API key ekleyin.")
        return None

    print(f"  ✅ API Key bulundu: {api_key[:8]}...{api_key[-4:]}")

    model = init_chatbot(api_key)
    if model:
        print("  ✅ Gemini 2.0 Flash modeli başarıyla başlatıldı.")
    else:
        print("  ❌ Model başlatılamadı!")

    return model


def test_basic_chat(model, kullanici_id: int, db):
    """Test 2: Basit selamlama mesajı."""
    print_test(2, "Basit Selamlama")

    mesaj = "Merhaba! Ben bugün yemekhaneye geleceğim, ne yemeli?"
    print(f"  📤 Kullanıcı: {mesaj}")

    yanit = get_response(
        model=model,
        user_message=mesaj,
        kullanici_id=kullanici_id,
        db=db,
    )

    print(f"  📥 Chatbot: {yanit['response'][:200]}...")
    print(f"  💡 Öneriler: {yanit.get('suggestions', [])}")
    print(f"  📊 Günlük Toplam: {yanit.get('gunluk_toplam', 0)} kcal")

    assert yanit["response"], "Yanıt boş olmamalı!"
    print("  ✅ BAŞARILI")
    return yanit


def test_menu_query(model, kullanici_id: int, db):
    """Test 3: Bugünkü menü sorgusu."""
    print_test(3, "Menü Sorgusu")

    mesaj = "Bugün yemekhanede menüde ne var?"
    print(f"  📤 Kullanıcı: {mesaj}")

    yanit = get_response(
        model=model,
        user_message=mesaj,
        kullanici_id=kullanici_id,
        db=db,
    )

    print(f"  📥 Chatbot: {yanit['response'][:200]}...")

    assert yanit["response"], "Yanıt boş olmamalı!"
    print("  ✅ BAŞARILI")
    return yanit


def test_meal_logging(model, kullanici_id: int, db):
    """Test 4: Yemek loglama (function calling)."""
    print_test(4, "Yemek Loglama (Function Calling)")

    mesaj = "Öğlen kuru fasulye, pirinç pilavı ve cacık yedim"
    print(f"  📤 Kullanıcı: {mesaj}")

    yanit = get_response(
        model=model,
        user_message=mesaj,
        kullanici_id=kullanici_id,
        db=db,
    )

    print(f"  📥 Chatbot: {yanit['response'][:300]}...")
    print(f"  📊 Günlük Toplam: {yanit.get('gunluk_toplam', 0)} kcal")

    assert yanit["response"], "Yanıt boş olmamalı!"
    print("  ✅ BAŞARILI")
    return yanit


def test_daily_report(model, kullanici_id: int, db):
    """Test 5: Günlük rapor."""
    print_test(5, "Günlük Rapor Sorgusu")

    mesaj = "Bugünkü günlük beslenme raporumu göster"
    print(f"  📤 Kullanıcı: {mesaj}")

    yanit = get_response(
        model=model,
        user_message=mesaj,
        kullanici_id=kullanici_id,
        db=db,
    )

    print(f"  📥 Chatbot: {yanit['response'][:300]}...")
    print(f"  📊 Günlük Toplam: {yanit.get('gunluk_toplam', 0)} kcal")

    assert yanit["response"], "Yanıt boş olmamalı!"
    print("  ✅ BAŞARILI")
    return yanit


def test_nutrition_query(model, kullanici_id: int, db):
    """Test 6: Besin değeri sorgusu."""
    print_test(6, "Besin Değeri Sorgusu")

    mesaj = "Mercimek çorbasının kalori ve protein değeri ne kadar?"
    print(f"  📤 Kullanıcı: {mesaj}")

    yanit = get_response(
        model=model,
        user_message=mesaj,
        kullanici_id=kullanici_id,
        db=db,
    )

    print(f"  📥 Chatbot: {yanit['response'][:200]}...")

    assert yanit["response"], "Yanıt boş olmamalı!"
    print("  ✅ BAŞARILI")
    return yanit


def test_health_advice(model, kullanici_id: int, db):
    """Test 7: Beslenme tavsiyesi."""
    print_test(7, "Beslenme Tavsiyesi")

    mesaj = "Protein eksikliğim var mı? Bugün yeterli protein aldım mı?"
    print(f"  📤 Kullanıcı: {mesaj}")

    yanit = get_response(
        model=model,
        user_message=mesaj,
        kullanici_id=kullanici_id,
        db=db,
    )

    print(f"  📥 Chatbot: {yanit['response'][:300]}...")

    assert yanit["response"], "Yanıt boş olmamalı!"
    print("  ✅ BAŞARILI")
    return yanit


def test_meal_recommendation(model, kullanici_id: int, db):
    """Test 8: Yemek önerisi."""
    print_test(8, "Kişiselleştirilmiş Yemek Önerisi")

    kullanici_bilgi = {
        "kalori_hedefi": 2000,
        "alinan_kalori": 800,
    }

    sonuc = get_meal_recommendation(
        model=model,
        kullanici_bilgi=kullanici_bilgi,
    )

    print(f"  📥 Öneri: {sonuc['oneri'][:200]}...")
    print(f"  📊 Kalan Kalori: {sonuc.get('kalan_kalori', 0)} kcal")

    assert sonuc["oneri"], "Öneri boş olmamalı!"
    print("  ✅ BAŞARILI")
    return sonuc


# ─── Ana Çalıştırma ──────────────────────────────────────────────
def main():
    print_header("Modül 3: Chatbot Yemekhane Asistanı - Test Süreci")

    # Veritabanını başlat
    init_db()
    db = SessionLocal()

    basarili = 0
    basarisiz = 0
    toplam = 8

    try:
        # Test kullanıcısı oluştur
        kullanici_id = ensure_test_user(db)

        # Test 1: API bağlantısı
        model = test_api_connection()
        if model is None:
            print("\n❌ API bağlantısı kurulamadı. Testler iptal edildi.")
            print("💡 .env dosyasında GEMINI_API_KEY değerini ayarlayın.")
            return

        basarili += 1

        # Testler arası bekleme (rate limit)
        test_functions = [
            (test_basic_chat, "Basit Selamlama"),
            (test_menu_query, "Menü Sorgusu"),
            (test_meal_logging, "Yemek Loglama"),
            (test_daily_report, "Günlük Rapor"),
            (test_nutrition_query, "Besin Değeri"),
            (test_health_advice, "Beslenme Tavsiyesi"),
            (test_meal_recommendation, "Yemek Önerisi"),
        ]

        for test_func, test_name in test_functions:
            try:
                if test_func == test_meal_recommendation:
                    test_func(model, kullanici_id, db)
                else:
                    test_func(model, kullanici_id, db)
                basarili += 1
            except Exception as e:
                print(f"  ❌ HATA: {e}")
                basarisiz += 1

            # Rate limit koruması — testler arası bekleme
            time.sleep(2)

    finally:
        db.close()

    # Sonuç özeti
    print_header("TEST SONUÇLARI")
    print(f"  ✅ Başarılı: {basarili}/{toplam}")
    print(f"  ❌ Başarısız: {basarisiz}/{toplam}")
    print(f"  📊 Başarı Oranı: {(basarili / toplam) * 100:.0f}%")

    if basarisiz == 0:
        print("\n🎉 Tüm testler başarılı! Chatbot modülü çalışıyor.")
    else:
        print(f"\n⚠️ {basarisiz} test başarısız oldu. Logları kontrol edin.")


if __name__ == "__main__":
    main()
