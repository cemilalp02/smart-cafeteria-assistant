import React, { useEffect, useState } from "react";
import { ActivityIndicator, RefreshControl, ScrollView, StyleSheet, Text, View } from "react-native";
import { MaterialCommunityIcons } from "@expo/vector-icons";
import { C, MENU_FIELDS, categoryLabelFor } from "../theme";
import { apiGet } from "../api";
import { cacheSet, cacheGet, CACHE_KEYS, formatAge } from "../cache";
import { SectionCard, DataRow, PrimaryButton } from "../components";

export default function MenuScreen() {
  const [loading, setLoading] = useState(false);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState("");
  const [menu, setMenu] = useState(null);
  const [lastUpdated, setLastUpdated] = useState(null);
  const [isOffline, setIsOffline] = useState(false);

  const fetchMenu = async (isRefresh = false) => {
    if (isRefresh) setRefreshing(true);
    else setLoading(true);
    setError("");
    setIsOffline(false);
    try {
      const response = await apiGet("/api/menu/today");
      if (!response.success || !response.data) {
        setError(response.message || "Menü verisi alınamadı.");
        setMenu(null);
      } else {
        setMenu(response.data);
        setLastUpdated(new Date());
        await cacheSet(CACHE_KEYS.MENU, response.data);
      }
    } catch (e) {
      const cached = await cacheGet(CACHE_KEYS.MENU, 24 * 3600000);
      if (cached?.data) {
        setMenu(cached.data);
        setIsOffline(true);
        setLastUpdated(new Date(cached.timestamp));
        setError("");
      } else {
        setError(e.message);
        setMenu(null);
      }
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  };

  useEffect(() => { fetchMenu(); }, []);

  return (
    <ScrollView
      contentContainerStyle={styles.screenContent}
      refreshControl={
        <RefreshControl
          refreshing={refreshing}
          onRefresh={() => fetchMenu(true)}
          colors={["#6366f1"]}
          tintColor="#6366f1"
        />
      }
    >
      <SectionCard title="Bugünün Menüsü" subtitle="Yemekhane günlük plan" icon="calendar-today" delay={100} accentColor={C.primary}>
        <View style={styles.metaPill}>
          <View style={[styles.statusDot, isOffline && { backgroundColor: "#f59e0b" }]} />
          <Text style={styles.metaText}>
            {isOffline ? "Çevrimdışı mod" : "Canlı bağlantı"}
            {lastUpdated ? ` • ${formatAge(Math.round((Date.now() - lastUpdated.getTime()) / 60000))}` : ""}
          </Text>
        </View>

        <PrimaryButton onPress={() => fetchMenu(false)} icon="refresh">
          Menüyü Yenile
        </PrimaryButton>

        {loading ? <ActivityIndicator style={styles.loader} color={C.accent} size="small" /> : null}
        {error ? (
          <View style={styles.errorBox}>
            <MaterialCommunityIcons name="alert-circle-outline" size={16} color={C.danger} />
            <Text style={styles.errorText}>{error}</Text>
          </View>
        ) : null}

        {menu ? (
          <View style={styles.resultBox}>
            <View style={styles.dayBadge}>
              <MaterialCommunityIcons name="calendar-week" size={14} color={C.accent} />
              <Text style={styles.dayBadgeText}>{menu.gun || "-"}</Text>
            </View>
            {MENU_FIELDS.map((field, index) => {
              const value = menu[field.key] || "-";
              const label = categoryLabelFor(field.key, value);
              return (
                <DataRow
                  key={field.key}
                  label={label}
                  value={value}
                  icon={field.icon}
                  color={field.color}
                  delay={index * 80}
                />
              );
            })}
          </View>
        ) : null}
      </SectionCard>
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  screenContent: { paddingHorizontal: 14, paddingTop: 6, paddingBottom: 24, gap: 16 },
  metaPill: {
    alignSelf: "flex-start", flexDirection: "row", alignItems: "center", gap: 8,
    backgroundColor: C.white04, borderRadius: 999, paddingVertical: 5, paddingHorizontal: 12,
    borderWidth: 1, borderColor: C.borderLight,
  },
  statusDot: { width: 7, height: 7, borderRadius: 4, backgroundColor: C.accent },
  metaText: { color: C.muted, fontSize: 11, fontWeight: "600" },
  loader: { marginVertical: 8 },
  errorBox: {
    flexDirection: "row", alignItems: "center", gap: 8,
    backgroundColor: C.dangerSoft, borderRadius: 12, paddingVertical: 10, paddingHorizontal: 14,
    borderWidth: 1, borderColor: "rgba(255,107,107,.18)",
  },
  errorText: { color: C.danger, fontWeight: "700", fontSize: 13, flex: 1 },
  resultBox: {
    backgroundColor: C.white04, borderRadius: 16, borderWidth: 1,
    borderColor: C.border, padding: 14, gap: 6,
  },
  dayBadge: {
    alignSelf: "flex-start", flexDirection: "row", alignItems: "center", gap: 6,
    backgroundColor: C.accentSoft, borderRadius: 999, paddingVertical: 6, paddingHorizontal: 12,
    marginBottom: 4, borderWidth: 1, borderColor: "rgba(32,201,151,.18)",
  },
  dayBadgeText: { color: C.accent, fontWeight: "800", fontSize: 12, letterSpacing: 0.3 },
});
