import React, { useEffect, useMemo, useRef, useState } from "react";
import {
  ActivityIndicator, Animated, Dimensions, Platform, Pressable,
  ScrollView, StyleSheet, Text, TextInput, View,
} from "react-native";
import { MaterialCommunityIcons } from "@expo/vector-icons";
import { C, MENU_FIELDS, isDrinkLikeItem } from "../theme";
import { apiGet, apiPostJson } from "../api";
import { FadeInView, ScaleOnPress, SectionCard, PrimaryButton } from "../components";

const { width: SCREEN_WIDTH } = Dimensions.get("window");
const TEXT_INPUT_KEYBOARD_TYPE = Platform.OS === "android" ? "visible-password" : "default";

function AnimatedStar({ filled, onPress }) {
  const scaleAnim = useRef(new Animated.Value(1)).current;

  useEffect(() => {
    if (filled) {
      Animated.sequence([
        Animated.timing(scaleAnim, { toValue: 1.5, duration: 100, useNativeDriver: true }),
        Animated.spring(scaleAnim, { toValue: 1, useNativeDriver: true, speed: 14, bounciness: 14 }),
      ]).start();
    }
  }, [filled]);

  return (
    <Pressable onPress={onPress}>
      <Animated.View style={{ transform: [{ scale: scaleAnim }] }}>
        <MaterialCommunityIcons
          name={filled ? "star" : "star-outline"}
          size={40}
          color={filled ? C.gold : C.muted}
        />
      </Animated.View>
    </Pressable>
  );
}

export default function RateScreen() {
  const [dateValue] = useState(new Date().toISOString().slice(0, 10));
  const [todayMenu, setTodayMenu] = useState(null);
  const [selectedMealId, setSelectedMealId] = useState("");
  const [menuLoading, setMenuLoading] = useState(false);
  const [menuError, setMenuError] = useState("");
  const [rating, setRating] = useState(0);
  const [comment, setComment] = useState("");
  const [loading, setLoading] = useState(false);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  const [selfReport, setSelfReport] = useState(null);

  const menuOptions = useMemo(() => {
    if (!todayMenu) return [];
    return MENU_FIELDS.map((field) => {
      const rawValue = todayMenu[field.key];
      const yemekAdi = typeof rawValue === "string" ? rawValue.trim() : "";
      if (!yemekAdi || yemekAdi === "-" || yemekAdi.toLowerCase() === "yok") return null;
      const isDrink = field.key === "salata" && isDrinkLikeItem(yemekAdi);
      const kategori = isDrink ? "icecek" : field.key;
      const kategoriLabel = isDrink ? "İçecek" : field.key === "salata" ? "Salata" : field.label;
      return { id: `${kategori}:${yemekAdi}`, kategori, kategoriLabel, yemekAdi, icon: field.icon, color: field.color };
    }).filter(Boolean);
  }, [todayMenu]);

  const selectedMeal = useMemo(
    () => menuOptions.find((item) => item.id === selectedMealId) || null,
    [menuOptions, selectedMealId]
  );

  const fetchTodayMenu = async () => {
    setMenuLoading(true); setMenuError("");
    try {
      const response = await apiGet("/api/menu/today");
      if (!response.success || !response.data) {
        setTodayMenu(null);
        setMenuError(response.message || "Bugünün menü verisi alınamadı.");
      } else {
        setTodayMenu(response.data);
      }
    } catch (e) { setTodayMenu(null); setMenuError(e.message); }
    finally { setMenuLoading(false); }
  };

  useEffect(() => { fetchTodayMenu(); }, []);

  useEffect(() => {
    if (menuOptions.length === 0) { setSelectedMealId(""); return; }
    const selectedStillExists = menuOptions.some((item) => item.id === selectedMealId);
    if (!selectedStillExists) setSelectedMealId(menuOptions[0].id);
  }, [menuOptions, selectedMealId]);

  const sendRating = async () => {
    if (!selectedMeal) { setError("Önce bugünün menüsünden bir yemek seç."); return; }
    if (!rating) { setError("Lütfen bir puan seçin."); return; }
    setLoading(true); setError(""); setMessage("");
    try {
      const payload = {
        tarih: dateValue, yemek_adi: selectedMeal.yemekAdi,
        kategori: selectedMeal.kategori, puan: rating, yorum: comment.trim() || null,
        israf_self_report: selfReport,
      };
      const response = await apiPostJson("/api/rate-meal", payload);
      if (!response.success) setError(response.message || "Puan kaydedilemedi.");
      else setMessage(response.message || "Puan kaydedildi.");
    } catch (e) { setError(e.message); }
    finally { setLoading(false); }
  };

  const PUAN_LABELS = ["", "Çok Kötü", "Kötü", "Orta", "İyi", "Mükemmel"];

  return (
    <ScrollView contentContainerStyle={styles.screenContent}>
      <SectionCard title="Yemek Puanla" subtitle="Menüden seç, puanla, yorum bırak" icon="star-shooting" delay={100} accentColor={C.gold}>

        <View style={styles.inlineHeader}>
          <Text style={styles.label}>Günün Menüsü</Text>
          <ScaleOnPress onPress={fetchTodayMenu}>
            <View style={styles.refreshChip}>
              <MaterialCommunityIcons name="refresh" size={14} color={C.accent} />
              <Text style={styles.refreshChipText}>Yenile</Text>
            </View>
          </ScaleOnPress>
        </View>

        {menuLoading ? <ActivityIndicator style={styles.loader} color={C.accent} size="small" /> : null}
        {menuError ? (
          <View style={styles.errorBox}>
            <MaterialCommunityIcons name="alert-circle-outline" size={16} color={C.danger} />
            <Text style={styles.errorText}>{menuError}</Text>
          </View>
        ) : null}

        <View style={styles.mealChoiceGrid}>
          {menuOptions.map((item, index) => (
            <FadeInView key={item.id} delay={index * 60}>
              <ScaleOnPress onPress={() => setSelectedMealId(item.id)}>
                <View style={[
                  styles.mealChoiceCard,
                  selectedMealId === item.id && styles.mealChoiceCardActive,
                ]}>
                  <View style={[styles.mealChoiceIcon, { backgroundColor: (item.color || C.primary) + "18" }]}>
                    <MaterialCommunityIcons name={item.icon} size={20} color={item.color || C.primary} />
                  </View>
                  <Text style={[styles.mealChoiceLabel, selectedMealId === item.id && { color: C.text }]}>
                    {item.kategoriLabel}
                  </Text>
                  <Text style={[styles.mealChoiceName, selectedMealId === item.id && { color: C.accent }]} numberOfLines={1}>
                    {item.yemekAdi}
                  </Text>
                </View>
              </ScaleOnPress>
            </FadeInView>
          ))}
        </View>

        {!menuLoading && !menuError && menuOptions.length === 0 ? (
          <Text style={styles.metaText}>Bugünün menüsünde seçilebilir yemek bulunamadı.</Text>
        ) : null}

        <Text style={styles.label}>Puanınız</Text>
        <View style={styles.starRow}>
          {[1, 2, 3, 4, 5].map((value) => (
            <AnimatedStar
              key={value}
              filled={value <= rating}
              onPress={() => setRating(value)}
            />
          ))}
        </View>
        {rating > 0 ? (
          <FadeInView>
            <Text style={styles.ratingLabel}>{rating}/5 — {PUAN_LABELS[rating]}</Text>
          </FadeInView>
        ) : null}

        <Text style={styles.label}>Ne kadar yemek artırdınız?</Text>
        <View style={styles.selfReportRow}>
          {[
            { value: 0, icon: "check-circle", label: "Hiç", color: C.success },
            { value: 1, icon: "circle-slice-2", label: "Az\n<%25", color: C.accent },
            { value: 2, icon: "circle-slice-4", label: "Orta\n%25-50", color: C.gold },
            { value: 3, icon: "circle-slice-8", label: "Çok\n>%50", color: C.danger },
          ].map((opt) => (
            <ScaleOnPress key={opt.value} onPress={() => setSelfReport(opt.value)}>
              <View style={[
                styles.srOption,
                selfReport === opt.value && { borderColor: opt.color, backgroundColor: opt.color + "18" },
              ]}>
                <MaterialCommunityIcons
                  name={opt.icon}
                  size={24}
                  color={selfReport === opt.value ? opt.color : C.muted}
                />
                <Text style={[
                  styles.srLabel,
                  selfReport === opt.value && { color: opt.color },
                ]}>{opt.label}</Text>
              </View>
            </ScaleOnPress>
          ))}
        </View>

        <Text style={styles.label}>Yorum (opsiyonel)</Text>
        <TextInput
          style={styles.commentInput}
          value={comment}
          onChangeText={setComment}
          placeholder="Düşüncelerinizi paylaşın..."
          autoCapitalize="sentences"
          keyboardType={TEXT_INPUT_KEYBOARD_TYPE}
          inputMode="text"
          autoComplete="off"
          showSoftInputOnFocus
          autoCorrect={false}
          spellCheck={false}
          importantForAutofill="no"
          multiline
          placeholderTextColor={C.muted}
        />

        <PrimaryButton onPress={sendRating} icon="star-check-outline">
          Puanı Gönder
        </PrimaryButton>

        {loading ? <ActivityIndicator style={styles.loader} color={C.accent} size="small" /> : null}
        {error ? (
          <View style={styles.errorBox}>
            <MaterialCommunityIcons name="alert-circle-outline" size={16} color={C.danger} />
            <Text style={styles.errorText}>{error}</Text>
          </View>
        ) : null}
        {message ? (
          <FadeInView>
            <View style={styles.successBox}>
              <MaterialCommunityIcons name="check-circle" size={18} color={C.success} />
              <Text style={styles.successText}>{message}</Text>
            </View>
          </FadeInView>
        ) : null}
      </SectionCard>
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  screenContent: { paddingHorizontal: 14, paddingTop: 6, paddingBottom: 24, gap: 16 },
  inlineHeader: { flexDirection: "row", justifyContent: "space-between", alignItems: "center" },
  label: { fontSize: 13, fontWeight: "800", color: C.textSoft, textTransform: "uppercase", letterSpacing: 0.8 },
  refreshChip: {
    flexDirection: "row", alignItems: "center", gap: 4, paddingVertical: 5, paddingHorizontal: 10,
    borderRadius: 999, backgroundColor: C.accentSoft, borderWidth: 1, borderColor: "rgba(32,201,151,.18)",
  },
  refreshChipText: { color: C.accent, fontWeight: "700", fontSize: 12 },
  metaText: { color: C.muted, fontSize: 11, fontWeight: "600" },
  loader: { marginVertical: 8 },
  errorBox: {
    flexDirection: "row", alignItems: "center", gap: 8,
    backgroundColor: C.dangerSoft, borderRadius: 12, paddingVertical: 10, paddingHorizontal: 14,
    borderWidth: 1, borderColor: "rgba(255,107,107,.18)",
  },
  errorText: { color: C.danger, fontWeight: "700", fontSize: 13, flex: 1 },
  successBox: {
    flexDirection: "row", alignItems: "center", gap: 8,
    backgroundColor: C.successSoft, borderRadius: 12, paddingVertical: 10, paddingHorizontal: 14,
    borderWidth: 1, borderColor: "rgba(58,196,125,.18)",
  },
  successText: { color: C.success, fontWeight: "700", fontSize: 13, flex: 1 },
  mealChoiceGrid: { flexDirection: "row", flexWrap: "wrap", gap: 8 },
  mealChoiceCard: {
    width: (SCREEN_WIDTH - 28 - 24 - 8) / 2, padding: 12, borderRadius: 16,
    backgroundColor: C.white04, borderWidth: 1, borderColor: C.borderLight, gap: 6,
  },
  mealChoiceCardActive: {
    borderColor: C.accent, backgroundColor: C.accentSoft,
    shadowColor: C.accent, shadowOpacity: 0.2, shadowRadius: 8,
    shadowOffset: { width: 0, height: 4 }, elevation: 3,
  },
  mealChoiceIcon: { width: 36, height: 36, borderRadius: 12, alignItems: "center", justifyContent: "center" },
  mealChoiceLabel: { fontSize: 10, fontWeight: "800", color: C.muted, textTransform: "uppercase", letterSpacing: 0.5 },
  mealChoiceName: { fontSize: 13, fontWeight: "700", color: C.textSoft },
  starRow: { flexDirection: "row", gap: 6, justifyContent: "center", paddingVertical: 8 },
  ratingLabel: { textAlign: "center", color: C.gold, fontWeight: "800", fontSize: 14 },
  selfReportRow: { flexDirection: "row", gap: 8, marginBottom: 12 },
  srOption: {
    flex: 1, alignItems: "center", gap: 4, paddingVertical: 10, paddingHorizontal: 4,
    borderRadius: 14, borderWidth: 2, borderColor: C.border, backgroundColor: C.white04,
  },
  srLabel: { fontSize: 10, fontWeight: "700", color: C.muted, textAlign: "center", lineHeight: 13 },
  commentInput: {
    minHeight: 80, textAlignVertical: "top", borderWidth: 1, borderColor: C.border,
    borderRadius: 16, paddingHorizontal: 14, paddingVertical: 12,
    backgroundColor: C.white04, color: C.text, fontSize: 14,
  },
});
