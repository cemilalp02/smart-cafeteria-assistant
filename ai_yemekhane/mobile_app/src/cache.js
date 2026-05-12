/**
 * Offline Cache Katmanı — AsyncStorage
 * ═════════════════════════════════════
 * Menü ve istatistik verilerini telefonun hafızasına kaydeder.
 * İnternet yokken son kaydedilen veriyi gösterir.
 */

import AsyncStorage from "@react-native-async-storage/async-storage";

const CACHE_KEYS = {
  MENU: "@yemekhane_menu",
  STATS_MALIYET: "@yemekhane_stats_maliyet",
  STATS_DETAY: "@yemekhane_stats_detay",
  STATS_HAFTALIK: "@yemekhane_stats_haftalik",
  LAST_UPDATED: "@yemekhane_last_updated",
};

/**
 * Veriyi cache'e kaydet
 */
export async function cacheSet(key, data) {
  try {
    const payload = JSON.stringify({
      data,
      timestamp: Date.now(),
    });
    await AsyncStorage.setItem(key, payload);
  } catch (e) {
    console.warn("Cache yazma hatası:", e);
  }
}

/**
 * Cache'den veri oku
 * @param {string} key
 * @param {number} maxAgeMs - Maksimum yaş (ms). Varsayılan 1 saat.
 * @returns {object|null} { data, timestamp, stale }
 */
export async function cacheGet(key, maxAgeMs = 3600000) {
  try {
    const raw = await AsyncStorage.getItem(key);
    if (!raw) return null;

    const { data, timestamp } = JSON.parse(raw);
    const age = Date.now() - timestamp;

    return {
      data,
      timestamp,
      stale: age > maxAgeMs,
      ageMinutes: Math.round(age / 60000),
    };
  } catch (e) {
    console.warn("Cache okuma hatası:", e);
    return null;
  }
}

/**
 * Tüm cache'i temizle
 */
export async function cacheClear() {
  try {
    const keys = Object.values(CACHE_KEYS);
    await AsyncStorage.multiRemove(keys);
  } catch (e) {
    console.warn("Cache temizleme hatası:", e);
  }
}

/**
 * Son güncelleme zamanını formatla (örn: "5 dk önce")
 */
export function formatAge(ageMinutes) {
  if (ageMinutes < 1) return "Az önce";
  if (ageMinutes < 60) return `${ageMinutes} dk önce`;
  const hours = Math.floor(ageMinutes / 60);
  if (hours < 24) return `${hours} saat önce`;
  const days = Math.floor(hours / 24);
  return `${days} gün önce`;
}

export { CACHE_KEYS };
