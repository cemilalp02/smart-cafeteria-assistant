/**
 * Premium Color Palette & Theme Constants
 * ════════════════════════════════════════
 * Tüm ekranlar tarafından paylaşılan renk paleti ve sabitler.
 */

export const C = {
  bg: "#060f1a",
  bgCard: "#0e1a2d",
  bgCard2: "#152439",
  bgCard3: "#1b2e4a",
  surface: "#213753",
  border: "rgba(100, 160, 240, 0.14)",
  borderLight: "rgba(100, 160, 240, 0.08)",
  text: "#edf5fc",
  textSoft: "#c0d4e8",
  muted: "#7a94b0",
  accent: "#22d4a0",
  accentDark: "#0fa07f",
  accentSoft: "rgba(34, 212, 160, 0.12)",
  primary: "#3b8bf2",
  primaryDark: "#1a5bb5",
  primarySoft: "rgba(59, 139, 242, 0.12)",
  violet: "#a855f7",
  violetSoft: "rgba(168, 85, 247, 0.12)",
  magenta: "#ec4899",
  magentaSoft: "rgba(236, 72, 153, 0.10)",
  teal: "#14b8a6",
  tealSoft: "rgba(20, 184, 166, 0.12)",
  cyan: "#06b6d4",
  danger: "#ff6b6b",
  dangerSoft: "rgba(255, 107, 107, 0.12)",
  success: "#3ac47d",
  successSoft: "rgba(58, 196, 125, 0.12)",
  gold: "#f5b731",
  goldSoft: "rgba(245, 183, 49, 0.15)",
  white08: "rgba(255,255,255,0.08)",
  white04: "rgba(255,255,255,0.04)",
  white15: "rgba(255,255,255,0.15)",
  glow1: "rgba(59, 139, 242, 0.35)",
  glow2: "rgba(34, 212, 160, 0.25)",
  glowViolet: "rgba(168, 85, 247, 0.20)",
};

export const TABS = {
  home: "home",
  menu: "menu",
  rate: "rate",
  vote: "vote",
  chat: "chat",
};

export const TAB_LABELS = [
  { key: TABS.home, label: "Ana Sayfa", icon: "home-variant-outline" },
  { key: TABS.menu, label: "Menü", icon: "silverware-fork-knife" },
  { key: TABS.rate, label: "Puan", icon: "star-outline" },
  { key: TABS.vote, label: "Oylama", icon: "vote-outline" },
  { key: TABS.chat, label: "Chat", icon: "chat-processing-outline" },
];

export const MENU_FIELDS = [
  { key: "corba", label: "Çorba", icon: "bowl-mix-outline", color: "#f59e0b" },
  { key: "ana_yemek", label: "Ana Yemek", icon: "food-steak", color: "#ef4444" },
  { key: "yan_yemek", label: "Yan Yemek", icon: "rice", color: "#8b5cf6" },
  { key: "tatli", label: "Tatlı", icon: "cupcake", color: "#ec4899" },
  { key: "salata", label: "Salata/İçecek", icon: "food-apple-outline", color: "#10b981" },
];

export const DRINK_KEYWORDS = [
  "ayran", "su", "meyve suyu", "komposto", "kompoto", "hoşaf", "hosaf",
  "şalgam", "salgam", "limonata", "çay", "kahve", "kola", "gazoz",
  "soda", "ice tea",
];

export const FRUIT_KEYWORDS = [
  "meyve", "elma", "portakal", "muz", "armut", "kiraz", "üzüm", "uzum",
  "şeftali", "seftali", "kayısı", "kayisi", "çilek", "cilek", "karpuz",
  "kavun", "nar", "incir", "mandalina", "limon", "erik", "ananas",
];

function _norm(name) {
  return (name || "").toLocaleLowerCase("tr-TR").trim();
}

export function isDrinkLikeItem(name) {
  const normalized = _norm(name);
  if (!normalized || normalized === "-" || normalized === "yok") return false;
  return DRINK_KEYWORDS.some((keyword) => normalized.includes(keyword));
}

export function isFruitLikeItem(name) {
  const normalized = _norm(name);
  if (!normalized || normalized === "-" || normalized === "yok") return false;
  return FRUIT_KEYWORDS.some((keyword) => normalized.includes(keyword));
}

/**
 * Bir menü alanı için doğru gösterim etiketini döndürür.
 * - "salata" alanı: içerik içecek-benzeri ise "İçecek", aksi halde "Salata"
 * - "tatli"  alanı: içerik içecek (komposto/şalgam/hoşaf...) ise "İçecek",
 *                   meyve ise "Meyve", aksi halde "Tatlı"
 * - Diğer alanlar: MENU_FIELDS'taki sabit etiket
 */
export function categoryLabelFor(fieldKey, value) {
  if (fieldKey === "salata") {
    return isDrinkLikeItem(value) ? "İçecek" : "Salata";
  }
  if (fieldKey === "tatli") {
    if (isDrinkLikeItem(value)) return "İçecek";
    if (isFruitLikeItem(value)) return "Meyve";
    return "Tatlı";
  }
  const field = MENU_FIELDS.find((f) => f.key === fieldKey);
  return field ? field.label : fieldKey;
}
