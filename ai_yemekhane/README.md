# 🖥️ AI Yemekhane — Backend Uygulaması

Bu dizin, AI Akıllı Yemekhane Asistan Sistemi'nin ana backend uygulamasını içerir.

## 📁 Dizin Yapısı

```
ai_yemekhane/
├── main.py                     # FastAPI ana uygulama (40+ endpoint)
├── models.py                   # SQLAlchemy veritabanı modelleri
├── config.py                   # Konfigürasyon ayarları
├── requirements.txt            # Python bağımlılıkları
├── .env / .env.example         # Ortam değişkenleri
│
├── modules/                    # İş mantığı modülleri
│   ├── chatbot.py              #   Gemini 2.0 Flash chatbot
│   ├── menu_optimizer.py       #   ML menü optimizasyonu
│   ├── waste_analyzer.py       #   İsraf tahmin & analiz
│   ├── sentiment_analyzer.py   #   Türkçe duygu analizi
│   ├── feedback_analyzer.py    #   Geri bildirim analizi
│   ├── predictive_analyzer.py  #   Tahminsel analiz
│   ├── production_planner.py   #   Üretim planlama
│   ├── trend_analyzer.py       #   Trend analizi
│   ├── alert_system.py         #   Uyarı sistemi
│   ├── notification_service.py #   Push bildirim
│   ├── consumption_tracker.py  #   Tüketim takibi
│   └── pdf_report.py           #   PDF rapor üretimi
│
├── templates/                  # Jinja2 HTML şablonları (14 sayfa)
│   ├── base.html               #   Öğrenci layout
│   ├── base_admin.html         #   Admin layout
│   ├── index.html              #   Ana sayfa
│   ├── admin.html              #   Admin dashboard
│   ├── chat.html               #   Chatbot arayüzü
│   ├── rate.html               #   Puanlama
│   ├── menu.html               #   Menü takvimi
│   ├── today_menu.html         #   Günün menüsü
│   ├── report.html             #   Raporlama
│   ├── production_entry.html   #   Veri girişi
│   ├── production_plan.html    #   Üretim planı
│   └── feedback_analysis.html  #   Geri bildirim analizi
│
├── static/                     # CSS & JavaScript
│   ├── css/
│   │   ├── style.css           #   Ana stil dosyası
│   │   └── redesign.css        #   Ek tasarım kuralları
│   └── js/
│       └── app.js              #   Ortak JavaScript fonksiyonları
│
├── scripts/                    # Yardımcı scriptler
│   ├── data/                   #   Veri yükleme & düzeltme
│   │   ├── load_menu_data.py   #     CSV → DB veri yükleme
│   │   ├── seed_data.py        #     Örnek veri oluşturma
│   │   ├── generate_production_logs.py  # Üretim logu oluşturma
│   │   ├── fix_all_data.py     #     Veri temizleme
│   │   └── ...
│   ├── training/               #   Model eğitim scriptleri
│   │   ├── train_menu_model.py #     Menü modeli eğitimi
│   │   ├── train_waste_model.py #    İsraf modeli eğitimi
│   │   └── ...
│   └── tests/                  #   Test scriptleri
│       ├── test_chatbot.py
│       └── test_db.py
│
├── models_data/                # Eğitilmiş ML model dosyaları
│   ├── waste_predictor.joblib  #   İsraf tahmin modeli
│   └── menu_popularity_model.joblib  # Menü popülerlik modeli
│
├── data/                       # Uygulama verileri
│   ├── menu_data.csv           #   60+ günlük menü verileri
│   └── nutrition_data.csv      #   Besin değerleri tablosu
│
└── mobile_app/                 # React Native mobil uygulama
```

## 🚀 Hızlı Başlangıç

```bash
# 1. Bağımlılıkları yükle
pip install -r requirements.txt

# 2. Ortam değişkenlerini ayarla
copy .env.example .env
# .env içinde GEMINI_API_KEY'i ayarla

# 3. Veritabanını hazırla
python scripts/data/load_menu_data.py
python scripts/data/seed_data.py

# 4. Sunucuyu başlat
python main.py
```

## 🔗 API Endpoint'leri

Sunucu çalışırken: `http://localhost:8000/docs` (Swagger UI)

| Metot | Endpoint | Açıklama |
|---|---|---|
| `GET` | `/` | Ana sayfa |
| `GET` | `/today-menu` | Günün menüsü |
| `GET` | `/menu` | Menü takvimi |
| `GET` | `/rate` | Puanlama |
| `GET` | `/chat` | Chatbot |
| `GET` | `/admin` | Admin dashboard |
| `GET` | `/report` | Raporlar |
| `POST` | `/api/predict-menu` | Menü önerisi |
| `POST` | `/api/chat` | Chatbot API |
| `POST` | `/api/rate-meal` | Puanlama API |
| `GET` | `/api/menu/today` | Bugünün menüsü API |
| `GET` | `/api/waste/analysis` | İsraf analizi API |

## 🛠️ Teknoloji Stack

- **Backend:** Python 3.10+ / FastAPI / Uvicorn
- **Veritabanı:** SQLite + SQLAlchemy
- **ML:** scikit-learn, pandas, numpy
- **Chatbot:** Google Gemini 2.0 Flash API
- **Frontend:** HTML5, CSS3, JavaScript, Chart.js
- **Template Engine:** Jinja2
- **Mobil:** React Native (Expo)

## 📱 Mobil Uygulama

```bash
cd mobile_app
npm install
npm run start
```

API adresi için `mobile_app/.env` dosyasında `EXPO_PUBLIC_API_BASE_URL` değerini güncelleyin.
