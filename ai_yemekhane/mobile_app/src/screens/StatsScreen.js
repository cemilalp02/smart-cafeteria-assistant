import React, { useEffect, useState } from "react";
import {
  ActivityIndicator, RefreshControl, ScrollView, StyleSheet, Text, View,
} from "react-native";
import { LinearGradient } from "expo-linear-gradient";
import { MaterialCommunityIcons } from "@expo/vector-icons";
import { C } from "../theme";
import { apiGet } from "../api";
import { cacheSet, cacheGet, CACHE_KEYS, formatAge } from "../cache";

function StatCard({ icon, title, value, subtitle, color }) {
  return (
    <View style={styles.card}>
      <LinearGradient
        colors={[color + "20", color + "08"]}
        style={styles.cardGradient}
      >
        <View style={[styles.cardIcon, { backgroundColor: color + "25" }]}>
          <MaterialCommunityIcons name={icon} size={22} color={color} />
        </View>
        <Text style={styles.cardTitle}>{title}</Text>
        <Text style={[styles.cardValue, { color }]}>{value}</Text>
        {subtitle ? <Text style={styles.cardSubtitle}>{subtitle}</Text> : null}
      </LinearGradient>
    </View>
  );
}

export default function StatsScreen() {
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [maliyet, setMaliyet] = useState(null);
  const [maliyetDetay, setMaliyetDetay] = useState(null);
  const [haftalik, setHaftalik] = useState(null);
  const [lastUpdated, setLastUpdated] = useState(null);
  const [isOffline, setIsOffline] = useState(false);
  const [selfReport, setSelfReport] = useState(null);
  const [iotStatus, setIotStatus] = useState(null);
  const [maliyetAnaliz, setMaliyetAnaliz] = useState(null);

  useEffect(() => { loadStats(); }, []);

  async function loadStats(isRefresh = false) {
    if (isRefresh) setRefreshing(true);
    else setLoading(true);
    setIsOffline(false);
    try {
      const [m, md, h, sr, iot, ma] = await Promise.all([
        apiGet("/api/analytics/maliyet?gun=30"),
        apiGet("/api/analytics/maliyet-detay?gun=30"),
        apiGet("/api/analytics/haftalik-israf"),
        apiGet("/api/analytics/self-report?gun=30"),
        apiGet("/api/v1/iot/status"),
        apiGet("/api/v1/maliyet/analiz"),
      ]);
      if (m?.success) setMaliyet(m);
      if (md?.success) setMaliyetDetay(md);
      if (h?.success) setHaftalik(h);
      if (sr?.success) setSelfReport(sr);
      if (iot?.success) setIotStatus(iot);
      if (ma?.success) setMaliyetAnaliz(ma);
      setLastUpdated(new Date());
      await cacheSet(CACHE_KEYS.STATS_MALIYET, m);
      await cacheSet(CACHE_KEYS.STATS_DETAY, md);
      await cacheSet(CACHE_KEYS.STATS_HAFTALIK, h);
    } catch (e) {
      const [cm, cmd, ch] = await Promise.all([
        cacheGet(CACHE_KEYS.STATS_MALIYET, 24 * 3600000),
        cacheGet(CACHE_KEYS.STATS_DETAY, 24 * 3600000),
        cacheGet(CACHE_KEYS.STATS_HAFTALIK, 24 * 3600000),
      ]);
      if (cm?.data?.success) { setMaliyet(cm.data); setIsOffline(true); }
      if (cmd?.data?.success) setMaliyetDetay(cmd.data);
      if (ch?.data?.success) setHaftalik(ch.data);
      if (cm?.timestamp) setLastUpdated(new Date(cm.timestamp));
    }
    setLoading(false);
    setRefreshing(false);
  }

  if (loading) {
    return (
      <View style={styles.center}>
        <ActivityIndicator size="large" color="#6366f1" />
        <Text style={styles.loadingText}>İstatistikler yükleniyor...</Text>
      </View>
    );
  }

  return (
    <ScrollView
      style={styles.container}
      contentContainerStyle={styles.content}
      showsVerticalScrollIndicator={false}
      refreshControl={
        <RefreshControl
          refreshing={refreshing}
          onRefresh={() => loadStats(true)}
          colors={["#6366f1"]}
          tintColor="#6366f1"
        />
      }
    >
      <View style={styles.header}>
        <MaterialCommunityIcons name="chart-areaspline" size={28} color="#6366f1" />
        <View style={{ flex: 1 }}>
          <Text style={styles.headerTitle}>İstatistik Paneli</Text>
          {lastUpdated ? (
            <Text style={{ fontSize: 11, color: isOffline ? "#f59e0b" : "#94a3b8", marginTop: 2 }}>
              {isOffline ? "📴 Çevrimdışı" : "🟢 Canlı"} • {formatAge(Math.round((Date.now() - lastUpdated.getTime()) / 60000))}
            </Text>
          ) : null}
        </View>
      </View>

      <View style={styles.cardRow}>
        <StatCard
          icon="cash-multiple" title="İsraf Maliyeti"
          value={maliyet ? `${(maliyet.israf_maliyeti_tl || 0).toLocaleString("tr-TR")} ₺` : "-"}
          subtitle="Son 30 gün" color="#ef4444"
        />
        <StatCard
          icon="leaf" title="AI Tasarruf"
          value={maliyet ? `${(maliyet.ai_tasarruf_potansiyeli_tl || 0).toLocaleString("tr-TR")} ₺` : "-"}
          subtitle="%30 azaltma" color="#22c55e"
        />
      </View>

      <View style={styles.cardRow}>
        <StatCard
          icon="percent" title="İsraf Oranı"
          value={maliyet ? `%${maliyet.israf_orani_yuzde || 0}` : "-"}
          subtitle={maliyet ? `${maliyet.toplam_israf_porsiyon || 0} porsiyon` : ""}
          color="#f59e0b"
        />
        <StatCard
          icon="food" title="Üretim"
          value={maliyet ? `${(maliyet.toplam_uretilen_porsiyon || 0).toLocaleString("tr-TR")}` : "-"}
          subtitle="Toplam porsiyon" color="#6366f1"
        />
      </View>

      {haftalik ? (
        <View style={styles.section}>
          <Text style={styles.sectionTitle}>📊 Haftalık Karşılaştırma</Text>
          <View style={styles.compareRow}>
            <View style={styles.compareCard}>
              <Text style={styles.compareLabel}>Bu Hafta</Text>
              <Text style={[styles.compareValue, { color: C.accent }]}>
                %{(haftalik.bu_hafta?.ort_israf || 0).toFixed(1)}
              </Text>
              <Text style={styles.compareSmall}>Ort. İsraf</Text>
            </View>
            <View style={styles.compareDivider} />
            <View style={styles.compareCard}>
              <Text style={styles.compareLabel}>Geçen Hafta</Text>
              <Text style={[styles.compareValue, { color: C.muted }]}>
                %{(haftalik.gecen_hafta?.ort_israf || 0).toFixed(1)}
              </Text>
              <Text style={styles.compareSmall}>Ort. İsraf</Text>
            </View>
          </View>
          {haftalik.degisim !== null && haftalik.degisim !== undefined ? (
            <View style={[styles.badge, { backgroundColor: haftalik.iyilesti_mi ? C.successSoft : C.dangerSoft }]}>
              <MaterialCommunityIcons
                name={haftalik.iyilesti_mi ? "trending-down" : "trending-up"}
                size={16}
                color={haftalik.iyilesti_mi ? C.success : C.danger}
              />
              <Text style={[styles.badgeText, { color: haftalik.iyilesti_mi ? C.success : C.danger }]}>
                {Math.abs(haftalik.degisim).toFixed(1)} puan {haftalik.iyilesti_mi ? "iyileşme ✓" : "kötüleşme"}
              </Text>
            </View>
          ) : null}
        </View>
      ) : null}

      {maliyetDetay?.yemek_detaylari?.length > 0 ? (
        <View style={styles.section}>
          <Text style={styles.sectionTitle}>💸 En Pahalı İsraf Yemekleri</Text>
          {maliyetDetay.yemek_detaylari.slice(0, 5).map((y, i) => (
            <View key={i} style={styles.listItem}>
              <View style={[styles.rankBadge, {
                backgroundColor: i === 0 ? C.dangerSoft : i === 1 ? C.goldSoft : C.white08
              }]}>
                <Text style={[styles.rankText, {
                  color: i === 0 ? C.danger : i === 1 ? C.gold : C.muted
                }]}>#{i + 1}</Text>
              </View>
              <View style={styles.listItemContent}>
                <Text style={styles.listItemName} numberOfLines={1}>{y.yemek_adi}</Text>
                <Text style={styles.listItemMeta}>
                  {y.israf_porsiyon} porsiyon • %{y.israf_orani.toFixed(0)} israf
                </Text>
              </View>
              <Text style={styles.listItemCost}>
                {y.israf_maliyeti_tl.toLocaleString("tr-TR")} ₺
              </Text>
            </View>
          ))}
        </View>
      ) : null}

      {maliyetDetay?.haftalik_trend?.length > 0 ? (
        <View style={styles.section}>
          <Text style={styles.sectionTitle}>📈 Haftalık Maliyet Trendi</Text>
          {maliyetDetay.haftalik_trend.map((h, i) => (
            <View key={i} style={styles.trendRow}>
              <Text style={styles.trendLabel}>{h.hafta}</Text>
              <View style={styles.trendBarWrap}>
                <View style={[
                  styles.trendBar,
                  {
                    width: `${Math.min(100, (h.israf_orani / 50) * 100)}%`,
                    backgroundColor: h.israf_orani >= 40 ? "#ef4444" : h.israf_orani >= 25 ? "#f59e0b" : "#22c55e",
                  }
                ]} />
              </View>
              <Text style={styles.trendValue}>%{h.israf_orani.toFixed(0)}</Text>
            </View>
          ))}
        </View>
      ) : null}

      {selfReport && selfReport.toplam_bildirim > 0 ? (
        <View style={styles.section}>
          <Text style={styles.sectionTitle}>🗑️ Öğrenci İsraf Bildirimi</Text>
          <View style={styles.compareRow}>
            <View style={styles.compareCard}>
              <Text style={styles.compareLabel}>Toplam</Text>
              <Text style={[styles.compareValue, { color: C.primary }]}>{selfReport.toplam_bildirim}</Text>
              <Text style={styles.compareSmall}>bildirim</Text>
            </View>
            <View style={styles.compareDivider} />
            <View style={styles.compareCard}>
              <Text style={styles.compareLabel}>Dağılım</Text>
              {Object.entries(selfReport.dagilim || {}).map(([label, count]) => (
                <Text key={label} style={[styles.compareSmall, { marginTop: 2 }]}>
                  {label}: {count}
                </Text>
              ))}
            </View>
          </View>
          {selfReport.en_cok_israfa_maruz?.length > 0 ? (
            <View style={{ marginTop: 12 }}>
              <Text style={[styles.compareSmall, { fontWeight: "700", marginBottom: 6, color: C.textSoft }]}>En Çok İsraf Bildirilen:</Text>
              {selfReport.en_cok_israfa_maruz.slice(0, 3).map((y, i) => (
                <View key={i} style={[styles.listItem, { borderBottomWidth: 0, paddingVertical: 4 }]}>
                  <View style={[styles.rankBadge, { backgroundColor: C.dangerSoft, marginRight: 8, width: 26, height: 26 }]}>
                    <Text style={[styles.rankText, { color: C.danger, fontSize: 11 }]}>#{i + 1}</Text>
                  </View>
                  <Text style={[styles.listItemName, { fontSize: 13 }]} numberOfLines={1}>{y.yemek_adi}</Text>
                  <Text style={{ fontSize: 11, color: C.danger, fontWeight: "700", marginLeft: 8 }}>{y.self_report_label}</Text>
                </View>
              ))}
            </View>
          ) : null}
        </View>
      ) : null}

      {iotStatus ? (
        <View style={styles.section}>
          <Text style={styles.sectionTitle}>⚖️ IoT Tartı Verileri</Text>
          <View style={styles.compareRow}>
            <View style={styles.compareCard}>
              <Text style={styles.compareLabel}>Bugün</Text>
              <Text style={[styles.compareValue, { color: C.danger }]}>
                {iotStatus.bugun?.toplam_israf_kg || 0} kg
              </Text>
              <Text style={styles.compareSmall}>{iotStatus.bugun?.olcum_sayisi || 0} ölçüm</Text>
            </View>
            <View style={styles.compareDivider} />
            <View style={styles.compareCard}>
              <Text style={styles.compareLabel}>Aylık</Text>
              <Text style={[styles.compareValue, { color: C.gold }]}>
                {iotStatus.son_30_gun?.toplam_israf_kg || 0} kg
              </Text>
              <Text style={styles.compareSmall}>Günlük ort: {iotStatus.son_30_gun?.ort_gunluk_kg || 0} kg</Text>
            </View>
          </View>
          {iotStatus.kaynak_dagilim && Object.keys(iotStatus.kaynak_dagilim).length > 0 ? (
            <View style={[styles.badge, { backgroundColor: C.primarySoft, marginTop: 10 }]}>
              <MaterialCommunityIcons name="access-point" size={14} color={C.primary} />
              <Text style={[styles.badgeText, { color: C.primary }]}>
                {Object.entries(iotStatus.kaynak_dagilim).map(([k, v]) => `${k}: ${v}`).join(" • ")}
              </Text>
            </View>
          ) : null}
        </View>
      ) : null}

      {maliyetAnaliz ? (
        <View style={styles.section}>
          <Text style={styles.sectionTitle}>💰 İsraf Maliyet Analizi</Text>
          <View style={styles.compareRow}>
            <View style={styles.compareCard}>
              <Text style={styles.compareLabel}>Bugün</Text>
              <Text style={[styles.compareValue, { color: "#f59e0b" }]}>
                {(maliyetAnaliz.gunluk?.toplam_tl || 0).toLocaleString("tr-TR")} ₺
              </Text>
            </View>
            <View style={styles.compareDivider} />
            <View style={styles.compareCard}>
              <Text style={styles.compareLabel}>Bu Hafta</Text>
              <Text style={[styles.compareValue, { color: "#f59e0b" }]}>
                {(maliyetAnaliz.haftalik?.toplam_tl || 0).toLocaleString("tr-TR")} ₺
              </Text>
            </View>
            <View style={styles.compareDivider} />
            <View style={styles.compareCard}>
              <Text style={styles.compareLabel}>Bu Ay</Text>
              <Text style={[styles.compareValue, { color: "#f59e0b" }]}>
                {(maliyetAnaliz.aylik?.toplam_tl || 0).toLocaleString("tr-TR")} ₺
              </Text>
            </View>
          </View>
          {maliyetAnaliz.degisim_pct !== 0 ? (
            <View style={[styles.badge, { backgroundColor: maliyetAnaliz.degisim_pct < 0 ? C.successSoft || "#dcfce7" : C.dangerSoft || "#fee2e2", marginTop: 10 }]}>
              <Text style={{ fontSize: 12, color: maliyetAnaliz.degisim_pct < 0 ? C.success : C.danger, fontWeight: "700" }}>
                {maliyetAnaliz.degisim_pct < 0 ? "↓" : "↑"} %{Math.abs(maliyetAnaliz.degisim_pct)} geçen aya göre
              </Text>
            </View>
          ) : null}
        </View>
      ) : null}

      <View style={{ height: 40 }} />
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: C.bg },
  content: { padding: 16, paddingBottom: 30 },
  center: { flex: 1, justifyContent: "center", alignItems: "center", backgroundColor: C.bg },
  loadingText: { marginTop: 12, color: C.muted, fontSize: 14 },
  header: { flexDirection: "row", alignItems: "center", marginBottom: 20, gap: 12 },
  headerTitle: { fontSize: 22, fontWeight: "800", color: C.text },
  cardRow: { flexDirection: "row", gap: 12, marginBottom: 12 },
  card: { flex: 1, borderRadius: 16, overflow: "hidden", borderWidth: 1, borderColor: C.border },
  cardGradient: { padding: 16, borderRadius: 16, backgroundColor: C.bgCard },
  cardIcon: { width: 40, height: 40, borderRadius: 12, justifyContent: "center", alignItems: "center", marginBottom: 10 },
  cardTitle: { fontSize: 11, color: C.muted, fontWeight: "600", marginBottom: 4, textTransform: "uppercase", letterSpacing: 0.5 },
  cardValue: { fontSize: 20, fontWeight: "800" },
  cardSubtitle: { fontSize: 11, color: C.muted, marginTop: 4 },
  section: { backgroundColor: C.bgCard, borderRadius: 16, padding: 16, marginBottom: 12, borderWidth: 1, borderColor: C.border },
  sectionTitle: { fontSize: 16, fontWeight: "700", color: C.text, marginBottom: 14 },
  compareRow: { flexDirection: "row", alignItems: "center" },
  compareCard: { flex: 1, alignItems: "center", paddingVertical: 12 },
  compareDivider: { width: 1, height: 50, backgroundColor: C.border },
  compareLabel: { fontSize: 12, color: C.muted, fontWeight: "600", marginBottom: 4 },
  compareValue: { fontSize: 28, fontWeight: "800" },
  compareSmall: { fontSize: 11, color: C.muted, marginTop: 2 },
  badge: {
    flexDirection: "row", alignItems: "center", alignSelf: "center",
    paddingHorizontal: 14, paddingVertical: 6, borderRadius: 20, marginTop: 12, gap: 6,
  },
  badgeText: { fontSize: 13, fontWeight: "700" },
  listItem: { flexDirection: "row", alignItems: "center", paddingVertical: 10, borderBottomWidth: 1, borderBottomColor: C.borderLight },
  rankBadge: { width: 32, height: 32, borderRadius: 10, justifyContent: "center", alignItems: "center", marginRight: 12 },
  rankText: { fontSize: 13, fontWeight: "800" },
  listItemContent: { flex: 1 },
  listItemName: { fontSize: 14, fontWeight: "600", color: C.text },
  listItemMeta: { fontSize: 11, color: C.muted, marginTop: 2 },
  listItemCost: { fontSize: 15, fontWeight: "800", color: C.danger },
  trendRow: { flexDirection: "row", alignItems: "center", marginBottom: 10 },
  trendLabel: { width: 90, fontSize: 11, color: C.muted, fontWeight: "600" },
  trendBarWrap: { flex: 1, height: 12, backgroundColor: C.white08, borderRadius: 6, overflow: "hidden", marginHorizontal: 8 },
  trendBar: { height: "100%", borderRadius: 6 },
  trendValue: { width: 36, fontSize: 12, fontWeight: "700", color: C.textSoft, textAlign: "right" },
});
