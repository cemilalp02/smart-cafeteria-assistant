import React, { useEffect, useState } from "react";
import {
  ActivityIndicator,
  Pressable,
  RefreshControl,
  ScrollView,
  StyleSheet,
  Text,
  View,
} from "react-native";
import { LinearGradient } from "expo-linear-gradient";
import { MaterialCommunityIcons } from "@expo/vector-icons";
import { C, TABS, categoryLabelFor } from "../theme";
import { apiGet } from "../api";
import { FadeInView } from "../components";

// ─── Yardımcı: Dosyanın geneli için sabitler ────────────────────
const FLOW_STEPS = [
  {
    num: "01",
    icon: "star-outline",
    color: "#f59e0b",
    title: "Puanla & Yorum Yaz",
    desc: "Öğrenciler yemekleri anonim olarak puanlar ve detaylı yorum bırakır",
  },
  {
    num: "02",
    icon: "robot-outline",
    color: "#6366f1",
    title: "AI Analiz Eder",
    desc: "Makine öğrenmesi puanları, trendleri ve israf oranlarını analiz eder",
  },
  {
    num: "03",
    icon: "clipboard-text-outline",
    color: "#a855f7",
    title: "Menü Optimize Edilir",
    desc: "Düşük puanlı yemekler azaltılır, popüler yemekler sıklaştırılır",
  },
  {
    num: "04",
    icon: "leaf",
    color: "#22c55e",
    title: "İsraf Azalır",
    desc: "Daha az yiyecek çöpe gider, kaynak tasarrufu sağlanır",
  },
];

// Etiket dinamik olarak categoryLabelFor() ile hesaplanır
// (komposto/şalgam → İçecek, meyve → Meyve gibi)
const MENU_KEYS = ["corba", "ana_yemek", "yan_yemek", "tatli", "salata"];

// ─── Yıldız stringi (web index.html ile aynı) ───────────────────
function starsFor(rating) {
  const r = Math.round(rating || 0);
  return "★".repeat(r) + "☆".repeat(Math.max(0, 5 - r));
}

// ═══════════════════════════════════════════════════════════════
// HomeScreen — Eski web "index.html" sayfasının mobil portu
// ═══════════════════════════════════════════════════════════════

export default function HomeScreen({ setActiveTab }) {
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [menu, setMenu] = useState(null);
  const [waste, setWaste] = useState(null);
  const [ratings, setRatings] = useState(null);

  const loadAll = async () => {
    try {
      const [m, w, r] = await Promise.all([
        apiGet("/api/menu/today").catch(() => null),
        apiGet("/api/waste/daily").catch(() => null),
        apiGet("/api/ratings/today").catch(() => null),
      ]);
      if (m?.success) setMenu(m.data);
      if (w?.success) setWaste(w);
      if (r?.success) setRatings(r);
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  };

  useEffect(() => {
    loadAll();
    // index.html'deki gibi 30 saniyede bir canlı yenileme
    const id = setInterval(() => loadAll(), 30000);
    return () => clearInterval(id);
  }, []);

  // ─── Hesaplanan değerler (index.html'deki loadLiveStats / loadCafeteriaSummary) ──
  const ratingEntries = ratings?.data ? Object.entries(ratings.data) : [];
  const toplamOy = ratingEntries.reduce(
    (s, [, v]) => s + (v.toplam_oy || 0),
    0
  );
  const ortPuan =
    ratingEntries.length > 0
      ? ratingEntries.reduce((s, [, v]) => s + (v.ortalama || 0), 0) /
      ratingEntries.length
      : 0;
  const yemekSayisi = ratingEntries.length;
  const tahminiIsraf =
    waste?.genel_israf_skoru != null ? `%${waste.genel_israf_skoru}` : "—";

  // İsraf seviyesi badge'i
  let israfBadge = { text: "Yükleniyor…", bg: C.white08, fg: C.muted };
  if (waste?.genel_israf_seviye === "Dusuk" || waste?.genel_israf_seviye === "Düşük") {
    israfBadge = {
      text: "İsraf düşük",
      bg: "rgba(50, 185, 131, .16)",
      fg: "#79efc4",
      icon: "leaf",
    };
  } else if (waste?.genel_israf_seviye === "Yuksek" || waste?.genel_israf_seviye === "Yüksek") {
    israfBadge = {
      text: "İsraf yüksek",
      bg: "rgba(255, 107, 107, .16)",
      fg: "#ffb2a6",
      icon: "alert",
    };
  } else if (waste) {
    israfBadge = {
      text: "İsraf orta",
      bg: "rgba(255, 189, 89, .16)",
      fg: "#ffd792",
      icon: "chart-bar",
    };
  }

  if (loading) {
    return (
      <View style={styles.center}>
        <ActivityIndicator size="large" color={C.accent} />
        <Text style={styles.loadingText}>Yükleniyor…</Text>
      </View>
    );
  }

  return (
    <ScrollView
      style={styles.scroll}
      contentContainerStyle={styles.scrollContent}
      showsVerticalScrollIndicator={false}
      refreshControl={
        <RefreshControl
          refreshing={refreshing}
          onRefresh={() => {
            setRefreshing(true);
            loadAll();
          }}
          tintColor={C.accent}
          colors={[C.accent]}
        />
      }
    >
      {/* ═══ HERO ═══ */}
      <FadeInView delay={50}>
        <LinearGradient
          colors={[C.bgCard, C.bgCard2]}
          start={{ x: 0, y: 0 }}
          end={{ x: 1, y: 1 }}
          style={styles.heroCard}
        >
          <Text style={styles.eyebrow}>AI Tabanlı Akıllı Yemekhane Platformu</Text>
          <Text style={styles.heroTitle}>Yemek İsrafını</Text>
          <Text style={[styles.heroTitle, styles.heroTitleAccent]}>
            Yapay Zekâ ile Azaltıyoruz
          </Text>
          <Text style={styles.heroSubtitle}>
            Öğrenci geri bildirimleri, makine öğrenmesi ve gerçek zamanlı analiz ile
            yemekhane menülerini optimize ediyor, israfı minimuma indiriyoruz.
          </Text>

          <View style={styles.heroCtaRow}>
            <Pressable
              style={[styles.btn, styles.btnPrimary]}
              onPress={() => setActiveTab && setActiveTab(TABS.menu)}
            >
              <MaterialCommunityIcons
                name="silverware-fork-knife"
                size={14}
                color="#fff"
              />
              <Text style={styles.btnPrimaryText}>Günün Menüsü</Text>
            </Pressable>
            <Pressable
              style={[styles.btn, styles.btnAccent]}
              onPress={() => setActiveTab && setActiveTab(TABS.rate)}
            >
              <MaterialCommunityIcons name="star-outline" size={14} color="#fff" />
              <Text style={styles.btnPrimaryText}>Yemek Puanla</Text>
            </Pressable>
            <Pressable
              style={[styles.btn, styles.btnOutline]}
              onPress={() => setActiveTab && setActiveTab(TABS.chat)}
            >
              <MaterialCommunityIcons
                name="robot-outline"
                size={14}
                color={C.accent}
              />
              <Text style={styles.btnOutlineText}>AI Asistan</Text>
            </Pressable>
          </View>
        </LinearGradient>
      </FadeInView>

      {/* ═══ CANLI İSTATİSTİKLER ═══ */}
      <FadeInView delay={150}>
        <View style={styles.section}>
          <View style={styles.sectionHeaderRow}>
            <View style={styles.sectionIconChip}>
              <MaterialCommunityIcons
                name="chart-line-variant"
                size={16}
                color={C.accent}
              />
            </View>
            <View style={{ flex: 1 }}>
              <Text style={styles.sectionTitle}>Canlı İstatistikler</Text>
              <Text style={styles.sectionDesc}>
                Veriler gerçek zamanlı güncellenir
              </Text>
            </View>
            <View style={styles.pulseBadge}>
              <View style={styles.pulseDot} />
              <Text style={styles.pulseText}>Canlı</Text>
            </View>
          </View>

          <View style={styles.statsGrid}>
            <StatTile
              value={toplamOy.toString()}
              label="Toplam Puanlama"
              color={C.primary}
            />
            <StatTile
              value={ortPuan > 0 ? `${ortPuan.toFixed(1)}/5` : "—"}
              label="Ortalama Puan"
              color={C.gold}
            />
            <StatTile
              value={yemekSayisi.toString()}
              label="Puanlanan Yemek"
              color={C.violet}
            />
            <StatTile value={tahminiIsraf} label="Tahmini İsraf" color={C.accent} />
          </View>
        </View>
      </FadeInView>

      {/* ═══ NASIL ÇALIŞIR ═══ */}
      <FadeInView delay={250}>
        <View style={styles.section}>
          <View style={styles.sectionHeaderRow}>
            <View
              style={[
                styles.sectionIconChip,
                { backgroundColor: C.violetSoft, borderColor: "rgba(168,85,247,.25)" },
              ]}
            >
              <MaterialCommunityIcons
                name="cog-outline"
                size={16}
                color={C.violet}
              />
            </View>
            <View style={{ flex: 1 }}>
              <Text style={styles.sectionTitle}>Sistem Nasıl Çalışır?</Text>
              <Text style={styles.sectionDesc}>
                Yemek israfını azaltmak için 4 adımlık döngüsel süreç
              </Text>
            </View>
          </View>

          <View style={{ gap: 10 }}>
            {FLOW_STEPS.map((step, idx) => (
              <View key={step.num} style={styles.flowStep}>
                <View
                  style={[
                    styles.flowIcon,
                    { backgroundColor: step.color + "22", borderColor: step.color + "44" },
                  ]}
                >
                  <MaterialCommunityIcons
                    name={step.icon}
                    size={20}
                    color={step.color}
                  />
                </View>
                <View style={{ flex: 1 }}>
                  <View
                    style={{
                      flexDirection: "row",
                      alignItems: "center",
                      gap: 8,
                    }}
                  >
                    <Text style={[styles.flowNum, { color: step.color }]}>
                      {step.num}
                    </Text>
                    <Text style={styles.flowTitle}>{step.title}</Text>
                  </View>
                  <Text style={styles.flowDesc}>{step.desc}</Text>
                </View>
                {idx < FLOW_STEPS.length - 1 ? (
                  <View style={styles.flowConnector} />
                ) : null}
              </View>
            ))}
          </View>
        </View>
      </FadeInView>

      {/* ═══ BUGÜNÜN GÖRÜNÜMÜ — Bugünün Menüsü ═══ */}
      <FadeInView delay={350}>
        <View style={styles.section}>
          <View style={styles.sectionHeaderRow}>
            <View
              style={[
                styles.sectionIconChip,
                { backgroundColor: C.primarySoft, borderColor: "rgba(59,139,242,.25)" },
              ]}
            >
              <MaterialCommunityIcons
                name="calendar-today"
                size={16}
                color={C.primary}
              />
            </View>
            <View style={{ flex: 1 }}>
              <Text style={styles.sectionTitle}>Bugünün Menüsü</Text>
              <Text style={styles.sectionDesc}>
                {menu?.gun || "—"} · {menu?.tarih || ""}
              </Text>
            </View>
          </View>

          {menu ? (
            <View style={styles.menuList}>
              {MENU_KEYS.map((key) => {
                const value = menu[key] || "—";
                const label = categoryLabelFor(key, value);
                return (
                  <View key={key} style={styles.menuRow}>
                    <Text style={styles.menuRowCat}>{label}</Text>
                    <Text style={styles.menuRowName} numberOfLines={2}>
                      {value}
                    </Text>
                  </View>
                );
              })}
            </View>
          ) : (
            <View style={styles.emptyState}>
              <MaterialCommunityIcons name="silverware" size={28} color={C.muted} />
              <Text style={styles.emptyStateText}>
                Bugün için menü bulunamadı.
              </Text>
            </View>
          )}
        </View>
      </FadeInView>

      {/* ═══ BUGÜNÜN ÖZETİ ═══ */}
      <FadeInView delay={400}>
        <View style={styles.section}>
          <View style={styles.sectionHeaderRow}>
            <View
              style={[
                styles.sectionIconChip,
                { backgroundColor: C.accentSoft, borderColor: "rgba(34,212,160,.25)" },
              ]}
            >
              <MaterialCommunityIcons
                name="trending-down"
                size={16}
                color={C.accent}
              />
            </View>
            <View style={{ flex: 1 }}>
              <Text style={styles.sectionTitle}>Bugünün Özeti</Text>
              <Text style={styles.sectionDesc}>İsraf takibi · canlı veri</Text>
            </View>
          </View>

          <View style={styles.summaryRow}>
            <View style={styles.summaryStat}>
              <Text style={[styles.summaryValue, { color: C.danger }]}>
                {tahminiIsraf}
              </Text>
              <Text style={styles.summaryLabel}>İsraf</Text>
            </View>
            <View style={styles.summaryDivider} />
            <View style={styles.summaryStat}>
              <Text style={[styles.summaryValue, { color: C.gold }]}>
                {ortPuan > 0 ? `${ortPuan.toFixed(1)}/5` : "—"}
              </Text>
              <Text style={styles.summaryLabel}>Ortalama</Text>
            </View>
            <View style={styles.summaryDivider} />
            <View style={styles.summaryStat}>
              <Text style={[styles.summaryValue, { color: C.primary }]}>
                {toplamOy}
              </Text>
              <Text style={styles.summaryLabel}>Oy</Text>
            </View>
          </View>

          <View style={[styles.statusChip, { backgroundColor: israfBadge.bg }]}>
            {israfBadge.icon ? (
              <MaterialCommunityIcons
                name={israfBadge.icon}
                size={13}
                color={israfBadge.fg}
              />
            ) : null}
            <Text style={[styles.statusChipText, { color: israfBadge.fg }]}>
              {israfBadge.text}
            </Text>
          </View>
        </View>
      </FadeInView>

      {/* ═══ BUGÜNÜN PUANLARI ═══ */}
      {ratingEntries.length > 0 ? (
        <FadeInView delay={450}>
          <View style={styles.section}>
            <View style={styles.sectionHeaderRow}>
              <View
                style={[
                  styles.sectionIconChip,
                  { backgroundColor: C.goldSoft, borderColor: "rgba(245,183,49,.25)" },
                ]}
              >
                <MaterialCommunityIcons name="star" size={16} color={C.gold} />
              </View>
              <View style={{ flex: 1 }}>
                <Text style={styles.sectionTitle}>Bugünün Puanları</Text>
                <Text style={styles.sectionDesc}>Öğrenci geri bildirimi</Text>
              </View>
              <View style={styles.pulseBadge}>
                <View style={styles.pulseDot} />
                <Text style={styles.pulseText}>Canlı</Text>
              </View>
            </View>

            <View style={{ gap: 8 }}>
              {ratingEntries.map(([yemek, info]) => (
                <View key={yemek} style={styles.ratingRow}>
                  <Text style={styles.ratingName} numberOfLines={1}>
                    {yemek}
                  </Text>
                  <Text style={styles.ratingStars}>{starsFor(info.ortalama)}</Text>
                  <Text style={styles.ratingScore}>
                    {(info.ortalama || 0).toFixed(1)}
                  </Text>
                </View>
              ))}
            </View>

            <Pressable
              style={[styles.btn, styles.btnAccent, { marginTop: 14, alignSelf: "stretch" }]}
              onPress={() => setActiveTab && setActiveTab(TABS.rate)}
            >
              <MaterialCommunityIcons name="star-outline" size={14} color="#fff" />
              <Text style={styles.btnPrimaryText}>Puanlama Ekranı</Text>
            </Pressable>
          </View>
        </FadeInView>
      ) : null}

      {/* ═══ MODÜLLER ═══ */}
      <FadeInView delay={500}>
        <View style={styles.section}>
          <View style={styles.sectionHeaderRow}>
            <View
              style={[
                styles.sectionIconChip,
                { backgroundColor: C.tealSoft, borderColor: "rgba(20,184,166,.25)" },
              ]}
            >
              <MaterialCommunityIcons
                name="apps"
                size={16}
                color={C.teal}
              />
            </View>
            <View style={{ flex: 1 }}>
              <Text style={styles.sectionTitle}>Platform Modülleri</Text>
              <Text style={styles.sectionDesc}>
                Yapay zekâ destekli araçlar
              </Text>
            </View>
          </View>

          <View style={styles.featureGrid}>
            <FeatureCard
              icon="silverware-fork-knife"
              color={C.primary}
              title="Günün Menüsü"
              desc="Çorba, ana yemek, tatlı detayları"
              onPress={() => setActiveTab && setActiveTab(TABS.menu)}
            />
            <FeatureCard
              icon="star-outline"
              color={C.gold}
              title="Anonim Puanlama"
              desc="Yemekleri puanla, yorum bırak"
              onPress={() => setActiveTab && setActiveTab(TABS.rate)}
            />
            <FeatureCard
              icon="vote-outline"
              color={C.violet}
              title="Menü Oylama"
              desc="Gelecek hafta menüsünü sen seç"
              onPress={() => setActiveTab && setActiveTab(TABS.vote)}
            />
            <FeatureCard
              icon="robot-outline"
              color={C.accent}
              title="AI Asistan"
              desc="Menü ve besin değeri sorularına anında yanıt"
              onPress={() => setActiveTab && setActiveTab(TABS.chat)}
            />
          </View>
        </View>
      </FadeInView>

      {/* ═══ TEKNOLOJİ ═══ */}
      <FadeInView delay={550}>
        <View style={[styles.section, styles.techSection]}>
          <Text style={styles.techLabel}>Kullanılan Teknolojiler</Text>
          <View style={styles.techRow}>
            {[
              "FastAPI",
              "Python",
              "scikit-learn",
              "Gemini AI",
              "SQLite",
              "React Native",
            ].map((t) => (
              <View key={t} style={styles.techTag}>
                <Text style={styles.techTagText}>{t}</Text>
              </View>
            ))}
          </View>
        </View>
      </FadeInView>

      <View style={{ height: 24 }} />
    </ScrollView>
  );
}

// ─── Sub-components ─────────────────────────────────────────────

function StatTile({ value, label, color }) {
  return (
    <View style={styles.statTile}>
      <Text style={[styles.statTileValue, { color }]}>{value}</Text>
      <Text style={styles.statTileLabel}>{label}</Text>
    </View>
  );
}

function FeatureCard({ icon, color, title, desc, onPress }) {
  return (
    <Pressable onPress={onPress} style={styles.featureCard}>
      <View
        style={[
          styles.featureIconWrap,
          { backgroundColor: color + "22", borderColor: color + "44" },
        ]}
      >
        <MaterialCommunityIcons name={icon} size={22} color={color} />
      </View>
      <View style={{ flex: 1 }}>
        <Text style={styles.featureTitle}>{title}</Text>
        <Text style={styles.featureDesc}>{desc}</Text>
      </View>
      <MaterialCommunityIcons name="chevron-right" size={20} color={C.muted} />
    </Pressable>
  );
}

// ─── Styles ─────────────────────────────────────────────────────

const styles = StyleSheet.create({
  scroll: { flex: 1, backgroundColor: C.bg },
  scrollContent: { padding: 14, paddingBottom: 30 },

  center: {
    flex: 1,
    justifyContent: "center",
    alignItems: "center",
    backgroundColor: C.bg,
  },
  loadingText: { color: C.muted, marginTop: 12 },

  // Hero
  heroCard: {
    borderRadius: 20,
    padding: 18,
    borderWidth: 1,
    borderColor: C.border,
    marginBottom: 14,
  },
  eyebrow: {
    fontSize: 10,
    fontWeight: "800",
    color: C.accent,
    letterSpacing: 1.5,
    textTransform: "uppercase",
    marginBottom: 8,
  },
  heroTitle: {
    fontSize: 22,
    fontWeight: "900",
    color: C.text,
    letterSpacing: -0.5,
    lineHeight: 28,
  },
  heroTitleAccent: { color: C.accent },
  heroSubtitle: {
    fontSize: 12,
    color: C.textSoft,
    lineHeight: 18,
    marginTop: 10,
  },
  heroCtaRow: {
    flexDirection: "row",
    flexWrap: "wrap",
    gap: 8,
    marginTop: 16,
  },
  btn: {
    flexDirection: "row",
    alignItems: "center",
    gap: 6,
    paddingHorizontal: 14,
    paddingVertical: 10,
    borderRadius: 10,
    justifyContent: "center",
  },
  btnPrimary: { backgroundColor: C.primary },
  btnAccent: { backgroundColor: C.accent },
  btnOutline: { borderWidth: 1, borderColor: C.accent, backgroundColor: "transparent" },
  btnPrimaryText: { color: "#fff", fontWeight: "800", fontSize: 12 },
  btnOutlineText: { color: C.accent, fontWeight: "800", fontSize: 12 },

  // Section common
  section: {
    backgroundColor: C.bgCard,
    borderRadius: 18,
    padding: 16,
    borderWidth: 1,
    borderColor: C.border,
    marginBottom: 14,
  },
  sectionHeaderRow: {
    flexDirection: "row",
    alignItems: "center",
    gap: 12,
    marginBottom: 14,
  },
  sectionIconChip: {
    width: 34,
    height: 34,
    borderRadius: 11,
    backgroundColor: C.accentSoft,
    borderWidth: 1,
    borderColor: "rgba(34,212,160,.25)",
    alignItems: "center",
    justifyContent: "center",
  },
  sectionTitle: { color: C.text, fontWeight: "900", fontSize: 15, letterSpacing: -0.2 },
  sectionDesc: { color: C.muted, fontSize: 11, marginTop: 2 },

  pulseBadge: {
    flexDirection: "row",
    alignItems: "center",
    gap: 5,
    backgroundColor: "rgba(34,212,160,.12)",
    paddingHorizontal: 9,
    paddingVertical: 4,
    borderRadius: 999,
  },
  pulseDot: { width: 6, height: 6, borderRadius: 3, backgroundColor: C.accent },
  pulseText: { color: C.accent, fontSize: 10, fontWeight: "800" },

  // Stats grid
  statsGrid: {
    flexDirection: "row",
    flexWrap: "wrap",
    gap: 10,
  },
  statTile: {
    flexBasis: "47.5%",
    flexGrow: 1,
    backgroundColor: C.bgCard2,
    borderRadius: 12,
    borderWidth: 1,
    borderColor: C.borderLight,
    padding: 14,
    alignItems: "center",
  },
  statTileValue: { fontSize: 22, fontWeight: "900", letterSpacing: -0.5 },
  statTileLabel: {
    fontSize: 10,
    color: C.muted,
    fontWeight: "700",
    marginTop: 4,
    textTransform: "uppercase",
    letterSpacing: 0.5,
  },

  // Flow steps
  flowStep: {
    flexDirection: "row",
    alignItems: "center",
    gap: 12,
    backgroundColor: C.bgCard2,
    borderRadius: 12,
    padding: 12,
    borderWidth: 1,
    borderColor: C.borderLight,
    position: "relative",
  },
  flowIcon: {
    width: 40,
    height: 40,
    borderRadius: 12,
    borderWidth: 1,
    alignItems: "center",
    justifyContent: "center",
  },
  flowNum: { fontSize: 11, fontWeight: "900", letterSpacing: 1 },
  flowTitle: { color: C.text, fontWeight: "800", fontSize: 13 },
  flowDesc: { color: C.muted, fontSize: 11, marginTop: 3, lineHeight: 15 },
  flowConnector: {
    position: "absolute",
    bottom: -6,
    left: 32,
    width: 1,
    height: 6,
    backgroundColor: C.border,
  },

  // Menu list
  menuList: {
    backgroundColor: C.bgCard2,
    borderRadius: 12,
    borderWidth: 1,
    borderColor: C.borderLight,
    paddingHorizontal: 12,
  },
  menuRow: {
    flexDirection: "row",
    alignItems: "center",
    paddingVertical: 10,
    borderBottomWidth: 1,
    borderBottomColor: C.borderLight,
    gap: 12,
  },
  menuRowCat: {
    color: C.muted,
    fontSize: 11,
    fontWeight: "800",
    letterSpacing: 0.3,
    textTransform: "uppercase",
    width: 100,
  },
  menuRowName: { color: C.text, fontSize: 13, fontWeight: "700", flex: 1 },

  emptyState: {
    alignItems: "center",
    padding: 24,
    gap: 8,
  },
  emptyStateText: { color: C.muted, fontSize: 12 },

  // Summary
  summaryRow: {
    flexDirection: "row",
    alignItems: "center",
    backgroundColor: C.bgCard2,
    borderRadius: 12,
    borderWidth: 1,
    borderColor: C.borderLight,
    paddingVertical: 14,
  },
  summaryStat: { flex: 1, alignItems: "center" },
  summaryDivider: { width: 1, height: 36, backgroundColor: C.border },
  summaryValue: { fontSize: 22, fontWeight: "900", letterSpacing: -0.5 },
  summaryLabel: {
    fontSize: 10,
    color: C.muted,
    fontWeight: "700",
    marginTop: 4,
    textTransform: "uppercase",
    letterSpacing: 0.5,
  },

  statusChip: {
    flexDirection: "row",
    alignItems: "center",
    gap: 6,
    alignSelf: "center",
    paddingHorizontal: 14,
    paddingVertical: 6,
    borderRadius: 999,
    marginTop: 12,
  },
  statusChipText: { fontSize: 12, fontWeight: "800" },

  // Rating row
  ratingRow: {
    flexDirection: "row",
    alignItems: "center",
    backgroundColor: C.bgCard2,
    borderRadius: 10,
    borderWidth: 1,
    borderColor: C.borderLight,
    paddingHorizontal: 12,
    paddingVertical: 10,
    gap: 10,
  },
  ratingName: { color: C.text, fontWeight: "700", fontSize: 12, flex: 1 },
  ratingStars: { color: C.gold, fontSize: 13, letterSpacing: 1 },
  ratingScore: { color: C.text, fontWeight: "900", fontSize: 13, width: 30, textAlign: "right" },

  // Feature cards
  featureGrid: { gap: 8 },
  featureCard: {
    flexDirection: "row",
    alignItems: "center",
    gap: 12,
    backgroundColor: C.bgCard2,
    borderRadius: 12,
    borderWidth: 1,
    borderColor: C.borderLight,
    paddingHorizontal: 12,
    paddingVertical: 12,
  },
  featureIconWrap: {
    width: 38,
    height: 38,
    borderRadius: 11,
    borderWidth: 1,
    alignItems: "center",
    justifyContent: "center",
  },
  featureTitle: { color: C.text, fontWeight: "800", fontSize: 13 },
  featureDesc: { color: C.muted, fontSize: 11, marginTop: 2 },

  // Tech
  techSection: { alignItems: "center" },
  techLabel: {
    color: C.muted,
    fontSize: 10,
    fontWeight: "800",
    textTransform: "uppercase",
    letterSpacing: 1.2,
    marginBottom: 10,
  },
  techRow: {
    flexDirection: "row",
    flexWrap: "wrap",
    gap: 6,
    justifyContent: "center",
  },
  techTag: {
    backgroundColor: C.bgCard2,
    borderColor: C.borderLight,
    borderWidth: 1,
    paddingHorizontal: 10,
    paddingVertical: 5,
    borderRadius: 8,
  },
  techTagText: { color: C.textSoft, fontSize: 10, fontWeight: "700" },
});
