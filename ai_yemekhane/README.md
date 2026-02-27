# 🍽️ AI Tabanlı Akıllı Yemekhane Asistan Sistemi

Üniversite bitirme projesi kapsamında geliştirilen, yapay zeka destekli akıllı yemekhane asistan sistemi.

## 📋 Proje Hakkında

Bu sistem 3 temel AI modülünden oluşmaktadır:

| Modül | Açıklama | Teknoloji |
|-------|----------|-----------|
| **Menü Optimizasyonu** | ML ile yemek popülerlik tahmini ve haftalık menü önerisi | scikit-learn, pandas |
| **Yemek Tanıma** | Fotoğraftan yemek tanıma ve besin analizi | YOLO, Food-101, Pillow |
| **Chatbot Asistan** | LLM tabanlı yemekhane soru-cevap asistanı | Google Gemini API |

## 🗂️ Proje Yapısı

```
ai_yemekhane/
├── main.py                  # FastAPI ana uygulama
├── config.py                # Konfigürasyon ayarları
├── models.py                # SQLAlchemy veritabanı modelleri
├── seed_data.py             # Örnek veri yükleyici
├── requirements.txt         # Python bağımlılıkları
├── .env.example             # Ortam değişkenleri şablonu
├── README.md                # Bu dosya
│
├── modules/                 # AI Modülleri
│   ├── __init__.py
│   ├── menu_optimizer.py    # Modül 1: Menü Optimizasyonu
│   ├── food_recognizer.py   # Modül 2: Yemek Tanıma
│   └── chatbot.py           # Modül 3: Chatbot Asistan
│
├── templates/               # HTML Şablonları
│   └── index.html           # Ana sayfa
│
├── static/                  # Statik dosyalar
│   └── css/
│       └── style.css        # Stil dosyası
│
├── uploads/                 # Yüklenen fotoğraflar
│   └── .gitkeep
│
└── models_data/             # ML model dosyaları
    └── .gitkeep
```

## 🚀 Kurulum

### 1. Gereksinimleri yükleyin

```bash
cd ai_yemekhane
pip install -r requirements.txt
```

### 2. Ortam değişkenlerini ayarlayın

```bash
# .env.example dosyasını kopyalayın
copy .env.example .env

# .env dosyasını açıp API anahtarlarınızı girin
# Özellikle GEMINI_API_KEY alanını doldurun
```

### 3. Veritabanını oluşturun ve örnek veri yükleyin

```bash
python seed_data.py
```

### 4. Sunucuyu başlatın

```bash
python main.py
```

Sunucu varsayılan olarak `http://localhost:8000` adresinde çalışır.

## 🔗 API Endpoint'leri

| Metot | Endpoint | Açıklama |
|-------|----------|----------|
| `GET` | `/` | Ana sayfa (Web arayüzü) |
| `POST` | `/api/predict-menu` | Haftalık menü önerisi |
| `POST` | `/api/recognize-food` | Fotoğraftan yemek tanıma |
| `POST` | `/api/chat` | Chatbot mesajı gönder |
| `GET` | `/api/nutrition/{yemek_adi}` | Besin değeri sorgula |
| `GET` | `/api/report/{kullanici_id}` | Kullanıcı raporu |
| `GET` | `/api/menu/today` | Bugünün menüsü |

### Swagger API Dokümantasyonu

Sunucu çalışırken `http://localhost:8000/docs` adresinden interaktif API dokümantasyonuna erişebilirsiniz.

## 🗄️ Veritabanı Tabloları

- **Yemekler**: Yemek bilgileri ve besin değerleri (kalori, protein, karbonhidrat, yağ)
- **Menüler**: Günlük menü planları (çorba, ana yemek, pilav, tatlı, salata)
- **Kullanıcılar**: Kullanıcı profilleri ve kalori hedefleri
- **KullanıcıYemekLog**: Yemek tüketim kayıtları (foto/chatbot/manuel)

## 🛠️ Teknoloji Stack

- **Backend**: Python 3.10+ / FastAPI
- **Veritabanı**: SQLite + SQLAlchemy
- **ML**: scikit-learn, pandas, numpy
- **Görüntü İşleme**: YOLO (ultralytics), Pillow
- **Chatbot**: Google Gemini API
- **Frontend**: HTML5, CSS3, JavaScript (Vanilla)
- **Template Engine**: Jinja2

## 📝 Geliştirme Notları

- Modüller şu an **placeholder** fonksiyonlar ile oluşturulmuştur
- İlerleyen aşamalarda her modüldeki `TODO` işaretli kısımlar gerçek implementasyon ile değiştirilecektir
- Kamera sistemi projeden kaldırılmıştır; fotoğraf yükleme manuel olarak yapılır
