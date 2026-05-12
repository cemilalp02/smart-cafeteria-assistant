# AI Yemekhane Mobile

Expo tabanli mobil istemci. Mevcut FastAPI backend endpointlerine baglanir.

## Kurulum

```bash
npm install
```

## API Ayari

1. `.env.example` dosyasini `.env` olarak kopyala.
2. `EXPO_PUBLIC_API_BASE_URL` degerini backend adresine gore guncelle.

Ornek:

```env
EXPO_PUBLIC_API_BASE_URL=http://10.0.2.2:8001
```

Notlar:
- Android emulator icin localhost yerine `10.0.2.2` kullan.
- Fiziksel cihaz icin backend makinesinin LAN IP'sini kullan (ornek: `http://192.168.1.20:8001`).

## Calistirma

```bash
npm run start
```

Istersen:

```bash
npm run android
npm run ios
```

## Ilk Surum Ekranlari

- `Menu`: `/api/menu/today`
- `Puan`: `/api/rate-meal`
- `Chat`: `/api/chat`
