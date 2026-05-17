import React, { useEffect, useMemo, useState } from "react";
import {
  ActivityIndicator,
  Pressable,
  ScrollView,
  StyleSheet,
  Text,
  View,
} from "react-native";
import { MaterialCommunityIcons } from "@expo/vector-icons";
import { LinearGradient } from "expo-linear-gradient";
import { C } from "../theme";
import { apiGet, apiPostJson } from "../api";
import { FadeInView, SectionCard } from "../components";

// ─── Sabitler (vote.html ile birebir aynı) ─────────────────────
const GUNLER = ["Pazartesi", "Salı", "Çarşamba", "Perşembe", "Cuma"];
const ALT_COLORS = { A: "#6366f1", B: "#f59e0b", C: "#10b981" };
const ALT_ICONS = {
  A: "scale-balance",
  B: "star-shooting",
  C: "currency-try",
};
const ALT_LABELS_FALLBACK = {
  A: "Dengeli",
  B: "Popüler",
  C: "Ekonomik",
};

// Anonim ID — her oturumda yeni üretilir
const ANON_ID =
  "anon_" + Date.now() + "_" + Math.random().toString(36).slice(2, 10);

// ─── Yardımcı: Format fiyat / yüzde / sayı ─────────────────────
function fmtPercent(v) {
  if (v == null) return "—";
  return `${(v * 100).toFixed(0)}%`;
}
function fmtCost(v) {
  if (v == null) return "—";
  return `${Math.round(v)} ₺/gün`;
}
function fmtPop(v) {
  if (v == null) return "—";
  return `${(v * 10).toFixed(1)}/10`;
}
function fmtCal(v) {
  if (v == null) return "—";
  return `${Math.round(v)} kcal/gün`;
}

// ─── Alternatif Kart ───────────────────────────────────────────
function AlternativeCard({ alt, hafta, isVoted, hasVoted, onVote, voting }) {
  const key = alt.alternatif;
  const color = ALT_COLORS[key] || C.muted;
  const icon = ALT_ICONS[key] || "food-fork-drink";
  const menu = alt.menu || [];

  return (
    <View
      style={[
        styles.altCard,
        {
          borderColor: isVoted ? color : C.border,
          shadowColor: isVoted ? color : "#000",
          shadowOpacity: isVoted ? 0.35 : 0.15,
        },
      ]}
    >
      {isVoted ? (
        <View style={[styles.votedBadge, { backgroundColor: color }]}>
          <MaterialCommunityIcons name="check" size={14} color="#fff" />
          <Text style={styles.votedBadgeText}>Oyunuz</Text>
        </View>
      ) : null}

      {/* Header */}
      <View style={styles.altHeader}>
        <View style={[styles.altIconCircle, { backgroundColor: color + "33" }]}>
          <MaterialCommunityIcons name={icon} size={22} color={color} />
        </View>
        <View style={{ flex: 1 }}>
          <Text style={[styles.altTitle, { color }]}>
            Menü {key}: {alt.etiket || ALT_LABELS_FALLBACK[key] || ""}
          </Text>
          <Text style={styles.altVoteCount}>{alt.oy_sayisi || 0} oy</Text>
        </View>
      </View>

      {/* Skor chip'leri */}
      <View style={styles.scoreRow}>
        <View
          style={[styles.scoreChip, { backgroundColor: "rgba(239,68,68,.12)" }]}
        >
          <MaterialCommunityIcons
            name="trending-down"
            size={11}
            color="#ef4444"
          />
          <Text style={[styles.scoreChipText, { color: "#ef4444" }]}>
            İsraf {fmtPercent(alt.skor_israf)}
          </Text>
        </View>
        <View
          style={[styles.scoreChip, { backgroundColor: "rgba(245,158,11,.12)" }]}
        >
          <MaterialCommunityIcons name="cash" size={11} color="#f59e0b" />
          <Text style={[styles.scoreChipText, { color: "#f59e0b" }]}>
            {fmtCost(alt.skor_maliyet)}
          </Text>
        </View>
        <View
          style={[styles.scoreChip, { backgroundColor: "rgba(16,185,129,.12)" }]}
        >
          <MaterialCommunityIcons name="star" size={11} color="#10b981" />
          <Text style={[styles.scoreChipText, { color: "#10b981" }]}>
            Pop {fmtPop(alt.skor_populerlik)}
          </Text>
        </View>
        <View
          style={[styles.scoreChip, { backgroundColor: "rgba(99,102,241,.12)" }]}
        >
          <MaterialCommunityIcons name="fire" size={11} color="#6366f1" />
          <Text style={[styles.scoreChipText, { color: "#6366f1" }]}>
            {fmtCal(alt.skor_beslenme)}
          </Text>
        </View>
      </View>

      {/* Menü tablosu */}
      <View style={styles.menuTable}>
        <View style={styles.menuTableHeader}>
          <Text style={[styles.menuTableHeaderCell, { flex: 0.9 }]}>Gün</Text>
          <Text style={[styles.menuTableHeaderCell, { flex: 1.1 }]}>Çorba</Text>
          <Text style={[styles.menuTableHeaderCell, { flex: 1.4 }]}>Ana</Text>
          <Text style={[styles.menuTableHeaderCell, { flex: 1.2 }]}>Yan</Text>
          <Text style={[styles.menuTableHeaderCell, { flex: 1.1 }]}>Tatlı</Text>
        </View>
        {menu.map((gun, i) => (
          <View key={i} style={styles.menuTableRow}>
            <Text
              style={[styles.menuTableCell, styles.menuTableDayCell, { flex: 0.9 }]}
            >
              {GUNLER[i] || gun.gun || `G${i + 1}`}
            </Text>
            <Text style={[styles.menuTableCell, { flex: 1.1 }]} numberOfLines={2}>
              {gun.corba || "—"}
            </Text>
            <Text style={[styles.menuTableCell, { flex: 1.4 }]} numberOfLines={2}>
              {gun.ana_yemek || "—"}
            </Text>
            <Text style={[styles.menuTableCell, { flex: 1.2 }]} numberOfLines={2}>
              {gun.yan_yemek || "—"}
            </Text>
            <Text style={[styles.menuTableCell, { flex: 1.1 }]} numberOfLines={2}>
              {gun.tatli || "—"}
            </Text>
          </View>
        ))}
      </View>

      {/* Oy butonu */}
      <Pressable
        onPress={() => !hasVoted && !voting && onVote(hafta, key)}
        disabled={hasVoted || voting}
        style={[
          styles.voteButton,
          {
            backgroundColor: hasVoted ? C.bgCard3 : color,
            opacity: voting ? 0.6 : 1,
          },
        ]}
      >
        {voting ? (
          <ActivityIndicator size="small" color="#fff" />
        ) : (
          <>
            <MaterialCommunityIcons
              name={
                hasVoted
                  ? isVoted
                    ? "check-circle"
                    : "lock"
                  : "vote-outline"
              }
              size={16}
              color={hasVoted ? C.muted : "#fff"}
            />
            <Text
              style={[
                styles.voteButtonText,
                { color: hasVoted ? C.muted : "#fff" },
              ]}
            >
              {hasVoted
                ? isVoted
                  ? "Bu menüye oy verdiniz"
                  : "Oy kullandınız"
                : "Bu Menüye Oy Ver"}
            </Text>
          </>
        )}
      </Pressable>
    </View>
  );
}

// ─── Sonuç Özet Kartı ──────────────────────────────────────────
function ResultSummaryCard({ s, isWinner }) {
  const color = ALT_COLORS[s.alternatif] || C.muted;
  const icon = ALT_ICONS[s.alternatif] || "food-fork-drink";
  return (
    <View
      style={[
        styles.resultCard,
        {
          borderColor: isWinner ? color : C.border,
          shadowOpacity: isWinner ? 0.35 : 0,
          shadowColor: color,
        },
      ]}
    >
      <View style={[styles.altIconCircle, { backgroundColor: color + "33" }]}>
        <MaterialCommunityIcons name={icon} size={18} color={color} />
      </View>
      <View style={{ flex: 1 }}>
        <View style={{ flexDirection: "row", alignItems: "center", gap: 6 }}>
          <Text style={[styles.resultTitle, { color }]}>
            Menü {s.alternatif}: {s.etiket}
          </Text>
          {isWinner ? (
            <MaterialCommunityIcons name="trophy" size={14} color={C.gold} />
          ) : null}
        </View>
        <Text style={styles.resultMeta}>
          {s.oy_sayisi} oy — %{s.oy_yuzdesi}
        </Text>
      </View>
      <View style={styles.resultBarTrack}>
        <View
          style={[
            styles.resultBarFill,
            { width: `${s.oy_yuzdesi || 0}%`, backgroundColor: color },
          ]}
        />
      </View>
    </View>
  );
}

// ─── Geçmiş Oylama Satırı ──────────────────────────────────────
function HistoryRow({ g }) {
  const winnerColor = ALT_COLORS[g.kazanan_alternatif] || C.muted;
  return (
    <View style={styles.historyRow}>
      <View style={{ flexDirection: "row", alignItems: "center", gap: 8 }}>
        <MaterialCommunityIcons
          name="calendar-check"
          size={14}
          color={C.muted}
        />
        <Text style={styles.historyHafta}>{g.hafta}</Text>
        <Text style={styles.historyOy}>{g.toplam_oy} oy</Text>
      </View>
      <View style={{ flexDirection: "row", alignItems: "center", gap: 6, marginTop: 6 }}>
        <MaterialCommunityIcons name="trophy" size={13} color={winnerColor} />
        <Text style={[styles.historyKazanan, { color: winnerColor }]}>
          Menü {g.kazanan_alternatif} ({g.kazanan_etiket})
        </Text>
      </View>
      <View style={styles.historyDetayRow}>
        {(g.detay || []).map((d, i) => (
          <View
            key={i}
            style={[
              styles.historyDetayChip,
              {
                backgroundColor: (ALT_COLORS[d.alt] || C.muted) + "1f",
              },
            ]}
          >
            <Text
              style={[
                styles.historyDetayText,
                { color: ALT_COLORS[d.alt] || C.muted },
              ]}
            >
              {d.etiket}: {d.oy}
            </Text>
          </View>
        ))}
      </View>
    </View>
  );
}

// ═══════════════════════════════════════════════════════════════
// MAIN VOTE SCREEN
// ═══════════════════════════════════════════════════════════════

export default function VoteScreen() {
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState("");
  const [data, setData] = useState(null);
  const [results, setResults] = useState(null);
  const [history, setHistory] = useState([]);
  const [votedThisSession, setVotedThisSession] = useState(null);
  const [voting, setVoting] = useState(null);

  const hasVoted = !!votedThisSession;

  // ─── Verileri çek ───────────────────────────────────────────
  const loadAll = async () => {
    setLoading(true);
    setError("");
    try {
      const altRes = await apiGet("/api/v1/voting/alternatifler");
      if (!altRes.success) {
        setData(null);
        setError(altRes.error || "Alternatifler yüklenemedi.");
        setResults(null);
        return;
      }
      setData(altRes);

      // Sonuçlar
      try {
        const sonucRes = await apiGet(
          "/api/v1/voting/sonuclar?hafta=" + altRes.hafta
        );
        if (sonucRes.success && sonucRes.toplam_oy > 0) {
          setResults(sonucRes);
        } else {
          setResults(null);
        }
      } catch {
        setResults(null);
      }

      // Geçmiş
      try {
        const gecRes = await apiGet("/api/v1/voting/gecmis");
        if (gecRes.success && gecRes.gecmis) {
          // İlk eleman aktif hafta — onu atla, sadece toplam_oy > 0 olanları göster
          setHistory(gecRes.gecmis.slice(1).filter((g) => g.toplam_oy > 0));
        } else {
          setHistory([]);
        }
      } catch {
        setHistory([]);
      }
    } catch (e) {
      setError(e.message || "Bilinmeyen hata.");
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  };

  useEffect(() => {
    loadAll();
  }, []);

  // ─── Oy ver ─────────────────────────────────────────────────
  const oyVer = async (hafta, alternatif) => {
    if (hasVoted || voting) return;
    setVoting(alternatif);
    try {
      const res = await apiPostJson("/api/v1/voting/oy-ver", {
        hafta,
        alternatif,
        anonim_id: ANON_ID,
      });
      if (res.success) {
        setVotedThisSession(alternatif);
        await loadAll();
      } else if (res.zaten_oylandi) {
        setVotedThisSession(alternatif);
        await loadAll();
      } else {
        setError(res.error || "Oy verilemedi.");
      }
    } catch (e) {
      setError(e.message || "Oy verirken hata.");
    } finally {
      setVoting(null);
    }
  };

  // ─── Render ─────────────────────────────────────────────────
  if (loading) {
    return (
      <View style={styles.centerWrap}>
        <ActivityIndicator size="large" color={C.accent} />
        <Text style={styles.centerText}>Alternatifler yükleniyor…</Text>
      </View>
    );
  }

  if (error && !data) {
    return (
      <View style={styles.centerWrap}>
        <MaterialCommunityIcons name="alert-circle" size={48} color={C.danger} />
        <Text style={[styles.centerText, { color: C.danger }]}>{error}</Text>
        <Pressable onPress={loadAll} style={styles.retryBtn}>
          <Text style={styles.retryBtnText}>Tekrar Dene</Text>
        </Pressable>
      </View>
    );
  }

  if (!data || !data.alternatifler || data.alternatifler.length === 0) {
    return (
      <View style={styles.centerWrap}>
        <MaterialCommunityIcons name="inbox" size={48} color={C.muted} />
        <Text style={styles.centerText}>
          Bu hafta için henüz menü alternatifi oluşturulmamış.
        </Text>
        <Text style={[styles.centerText, { fontSize: 12, marginTop: 4 }]}>
          Yönetici panelinden alternatifler oluşturulduğunda görünecek.
        </Text>
      </View>
    );
  }

  return (
    <ScrollView
      style={styles.scroll}
      contentContainerStyle={styles.scrollContent}
      showsVerticalScrollIndicator={false}
    >
      <FadeInView delay={50}>
        {/* Başlık */}
        <View style={styles.titleSection}>
          <View style={styles.titleIconCircle}>
            <MaterialCommunityIcons name="vote" size={20} color={C.accent} />
          </View>
          <View style={{ flex: 1 }}>
            <Text style={styles.titleText}>Gelecek Hafta Menüsünü Sen Seç!</Text>
            <Text style={styles.titleDesc}>
              AI tarafından oluşturulan 3 alternatiften birini oyla. En çok oy alan
              menü uygulanır.
            </Text>
          </View>
        </View>

        {/* Durum çubuğu */}
        <LinearGradient
          colors={[C.primarySoft, C.violetSoft]}
          start={{ x: 0, y: 0 }}
          end={{ x: 1, y: 1 }}
          style={styles.statusBar}
        >
          <View style={styles.statusItem}>
            <MaterialCommunityIcons
              name="calendar-week"
              size={13}
              color={C.text}
            />
            <Text style={styles.statusText}>Hafta {data.hafta}</Text>
          </View>
          <View style={styles.statusItem}>
            <MaterialCommunityIcons name="calendar" size={13} color={C.text} />
            <Text style={styles.statusText}>{data.baslangic_tarihi}</Text>
          </View>
          <View style={styles.statusItem}>
            <MaterialCommunityIcons name="counter" size={13} color={C.text} />
            <Text style={styles.statusText}>{data.toplam_oy || 0} oy</Text>
          </View>
          {hasVoted ? (
            <View style={styles.statusItem}>
              <MaterialCommunityIcons name="check-circle" size={13} color={C.success} />
              <Text style={[styles.statusText, { color: C.success }]}>
                Oyunuz kaydedildi
              </Text>
            </View>
          ) : null}
        </LinearGradient>

        {/* Hata mesajı (oy verme sırasında) */}
        {error ? (
          <View style={styles.errorBanner}>
            <MaterialCommunityIcons
              name="alert-circle"
              size={14}
              color={C.danger}
            />
            <Text style={styles.errorBannerText}>{error}</Text>
          </View>
        ) : null}

        {/* Alternatif kartlar */}
        {data.alternatifler.map((alt) => (
          <AlternativeCard
            key={alt.alternatif}
            alt={alt}
            hafta={data.hafta}
            isVoted={votedThisSession === alt.alternatif}
            hasVoted={hasVoted}
            voting={voting === alt.alternatif}
            onVote={oyVer}
          />
        ))}

        {/* Sonuç bölümü */}
        {results ? (
          <SectionCard
            icon="chart-donut"
            title="Oylama Sonuçları"
            subtitle={`Toplam ${results.toplam_oy} oy · Kazanan: Menü ${results.kazanan?.alternatif} (${results.kazanan?.etiket})`}
          >
            <View style={{ gap: 8 }}>
              {results.sonuclar.map((s) => (
                <ResultSummaryCard
                  key={s.alternatif}
                  s={s}
                  isWinner={s.alternatif === results.kazanan?.alternatif}
                />
              ))}
            </View>
          </SectionCard>
        ) : null}

        {/* Geçmiş */}
        {history.length > 0 ? (
          <SectionCard
            icon="history"
            title="Geçmiş Oylamalar"
            subtitle={`${history.length} hafta önceki sonuç`}
          >
            <View style={{ gap: 8 }}>
              {history.map((g, i) => (
                <HistoryRow key={i} g={g} />
              ))}
            </View>
          </SectionCard>
        ) : null}

        {/* Yenile butonu */}
        <Pressable
          onPress={() => {
            setRefreshing(true);
            loadAll();
          }}
          style={styles.refreshBtn}
          disabled={refreshing}
        >
          {refreshing ? (
            <ActivityIndicator size="small" color={C.accent} />
          ) : (
            <>
              <MaterialCommunityIcons
                name="refresh"
                size={16}
                color={C.accent}
              />
              <Text style={styles.refreshBtnText}>Yenile</Text>
            </>
          )}
        </Pressable>

        <View style={{ height: 20 }} />
      </FadeInView>
    </ScrollView>
  );
}

// ═══════════════════════════════════════════════════════════════
// STYLES
// ═══════════════════════════════════════════════════════════════
const styles = StyleSheet.create({
  scroll: { flex: 1, backgroundColor: C.bg },
  scrollContent: { padding: 14, paddingBottom: 40 },

  centerWrap: {
    flex: 1,
    justifyContent: "center",
    alignItems: "center",
    padding: 28,
    backgroundColor: C.bg,
  },
  centerText: {
    color: C.textSoft,
    marginTop: 14,
    fontSize: 14,
    textAlign: "center",
    lineHeight: 20,
  },
  retryBtn: {
    marginTop: 16,
    paddingHorizontal: 22,
    paddingVertical: 10,
    backgroundColor: C.accent,
    borderRadius: 12,
  },
  retryBtnText: { color: "#fff", fontWeight: "800", fontSize: 13 },

  // Title section
  titleSection: {
    flexDirection: "row",
    gap: 12,
    alignItems: "center",
    marginBottom: 12,
  },
  titleIconCircle: {
    width: 40,
    height: 40,
    borderRadius: 12,
    backgroundColor: C.accentSoft,
    alignItems: "center",
    justifyContent: "center",
    borderWidth: 1,
    borderColor: "rgba(34,212,160,0.2)",
  },
  titleText: {
    color: C.text,
    fontWeight: "900",
    fontSize: 17,
    letterSpacing: -0.3,
  },
  titleDesc: { color: C.muted, fontSize: 11, marginTop: 3, lineHeight: 15 },

  // Status bar
  statusBar: {
    flexDirection: "row",
    flexWrap: "wrap",
    gap: 12,
    paddingVertical: 10,
    paddingHorizontal: 14,
    borderRadius: 12,
    borderWidth: 1,
    borderColor: C.border,
    marginBottom: 14,
  },
  statusItem: { flexDirection: "row", alignItems: "center", gap: 5 },
  statusText: { color: C.text, fontSize: 11, fontWeight: "700" },

  errorBanner: {
    flexDirection: "row",
    alignItems: "center",
    gap: 8,
    padding: 10,
    backgroundColor: C.dangerSoft,
    borderRadius: 10,
    borderWidth: 1,
    borderColor: "rgba(255,107,107,0.3)",
    marginBottom: 12,
  },
  errorBannerText: { color: C.danger, fontSize: 12, fontWeight: "700", flex: 1 },

  // Alt card
  altCard: {
    backgroundColor: C.bgCard,
    borderRadius: 16,
    borderWidth: 2,
    padding: 14,
    marginBottom: 14,
    shadowOffset: { width: 0, height: 4 },
    shadowRadius: 12,
    elevation: 4,
    position: "relative",
  },
  votedBadge: {
    position: "absolute",
    top: 10,
    right: 10,
    flexDirection: "row",
    alignItems: "center",
    gap: 4,
    paddingHorizontal: 10,
    paddingVertical: 3,
    borderRadius: 99,
    zIndex: 2,
  },
  votedBadgeText: { color: "#fff", fontWeight: "800", fontSize: 10 },
  altHeader: { flexDirection: "row", alignItems: "center", gap: 12, marginBottom: 10 },
  altIconCircle: {
    width: 36,
    height: 36,
    borderRadius: 12,
    alignItems: "center",
    justifyContent: "center",
  },
  altTitle: { fontSize: 15, fontWeight: "900", letterSpacing: -0.2 },
  altVoteCount: { color: C.muted, fontSize: 11, fontWeight: "700", marginTop: 2 },

  scoreRow: { flexDirection: "row", flexWrap: "wrap", gap: 6, marginBottom: 12 },
  scoreChip: {
    flexDirection: "row",
    alignItems: "center",
    gap: 4,
    paddingHorizontal: 8,
    paddingVertical: 4,
    borderRadius: 8,
  },
  scoreChipText: { fontSize: 10, fontWeight: "800" },

  // Menü tablosu
  menuTable: {
    borderRadius: 10,
    borderWidth: 1,
    borderColor: C.borderLight,
    overflow: "hidden",
    marginBottom: 12,
    backgroundColor: C.bgCard2,
  },
  menuTableHeader: {
    flexDirection: "row",
    paddingVertical: 6,
    paddingHorizontal: 6,
    backgroundColor: C.bgCard3,
    borderBottomWidth: 1,
    borderBottomColor: C.borderLight,
  },
  menuTableHeaderCell: {
    fontSize: 10,
    fontWeight: "800",
    color: C.muted,
    paddingHorizontal: 4,
  },
  menuTableRow: {
    flexDirection: "row",
    paddingVertical: 6,
    paddingHorizontal: 6,
    borderBottomWidth: 1,
    borderBottomColor: C.borderLight,
  },
  menuTableCell: {
    fontSize: 10,
    color: C.textSoft,
    paddingHorizontal: 4,
    lineHeight: 14,
  },
  menuTableDayCell: { fontWeight: "800", color: C.text },

  // Vote button
  voteButton: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "center",
    gap: 6,
    paddingVertical: 12,
    borderRadius: 12,
  },
  voteButtonText: { fontWeight: "800", fontSize: 13 },

  // Result card
  resultCard: {
    flexDirection: "row",
    alignItems: "center",
    gap: 10,
    backgroundColor: C.bgCard2,
    borderRadius: 12,
    borderWidth: 1,
    padding: 12,
    shadowOffset: { width: 0, height: 4 },
    shadowRadius: 8,
    elevation: 2,
  },
  resultTitle: { fontWeight: "800", fontSize: 12 },
  resultMeta: { color: C.muted, fontSize: 10, marginTop: 2 },
  resultBarTrack: {
    width: 70,
    height: 6,
    borderRadius: 3,
    backgroundColor: C.bgCard3,
    overflow: "hidden",
  },
  resultBarFill: { height: "100%", borderRadius: 3 },

  // History
  historyRow: {
    backgroundColor: C.bgCard2,
    borderRadius: 12,
    borderWidth: 1,
    borderColor: C.border,
    padding: 12,
  },
  historyHafta: { color: C.text, fontWeight: "800", fontSize: 12 },
  historyOy: { color: C.muted, fontSize: 11, marginLeft: 4 },
  historyKazanan: { fontWeight: "800", fontSize: 12 },
  historyDetayRow: { flexDirection: "row", flexWrap: "wrap", gap: 5, marginTop: 8 },
  historyDetayChip: {
    paddingHorizontal: 7,
    paddingVertical: 3,
    borderRadius: 6,
  },
  historyDetayText: { fontSize: 10, fontWeight: "800" },

  refreshBtn: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "center",
    gap: 6,
    paddingVertical: 11,
    backgroundColor: C.bgCard,
    borderRadius: 12,
    borderWidth: 1,
    borderColor: C.border,
    marginTop: 6,
  },
  refreshBtnText: { color: C.accent, fontWeight: "800", fontSize: 13 },
});
