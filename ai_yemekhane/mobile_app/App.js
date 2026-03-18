import React, { useEffect, useMemo, useState } from "react";
import { StatusBar } from "expo-status-bar";
import * as ImagePicker from "expo-image-picker";
import { LinearGradient } from "expo-linear-gradient";
import { MaterialCommunityIcons } from "@expo/vector-icons";
import {
  ActivityIndicator,
  Alert,
  Image,
  Platform,
  Pressable,
  SafeAreaView,
  ScrollView,
  StyleSheet,
  Text,
  TextInput,
  View,
} from "react-native";
import { API_BASE_URL, apiGet, apiPostJson, apiUploadFile } from "./src/api";

const TABS = {
  menu: "menu",
  recognize: "recognize",
  rate: "rate",
  chat: "chat",
};

const TAB_LABELS = [
  { key: TABS.menu, label: "Menü", icon: "silverware-fork-knife" },
  { key: TABS.recognize, label: "Tanı", icon: "camera-outline" },
  { key: TABS.rate, label: "Puan", icon: "star-outline" },
  { key: TABS.chat, label: "Chat", icon: "chat-processing-outline" },
];

const MENU_FIELDS = [
  { key: "corba", label: "Çorba" },
  { key: "ana_yemek", label: "Ana Yemek" },
  { key: "pilav", label: "Pilav" },
  { key: "tatli", label: "Tatlı" },
  { key: "salata", label: "Salata/İçecek" },
];

const DRINK_KEYWORDS = [
  "ayran",
  "su",
  "meyve suyu",
  "komposto",
  "hoşaf",
  "limonata",
  "çay",
  "kahve",
  "kola",
  "gazoz",
  "soda",
  "ice tea",
];

function isDrinkLikeItem(name) {
  const normalized = (name || "").toLocaleLowerCase("tr-TR").trim();
  if (!normalized || normalized === "-" || normalized === "yok") {
    return false;
  }
  return DRINK_KEYWORDS.some((keyword) => normalized.includes(keyword));
}

const COLORS = {
  bg: "#edf3fb",
  card: "#ffffff",
  border: "#d6e2ef",
  text: "#112034",
  muted: "#637792",
  accent: "#0f766e",
  accentSoft: "#d8f2ee",
  danger: "#c62828",
  success: "#0d8a6f",
  darkHeader: "#083547",
  darkHeader2: "#0c4e5f",
  tealGlow: "#1f9f9f",
  cyanGlow: "#5aaed0",
};

const TEXT_INPUT_KEYBOARD_TYPE = Platform.OS === "android" ? "visible-password" : "default";

function TabButton({ label, icon, isActive, onPress }) {
  return (
    <Pressable
      style={({ pressed }) => [
        styles.tabButton,
        isActive && styles.tabButtonActive,
        pressed && styles.tabButtonPressed,
      ]}
      onPress={onPress}
    >
      <MaterialCommunityIcons
        name={icon}
        size={18}
        color={isActive ? "#ffffff" : "#d6e4ee"}
        style={styles.tabIcon}
      />
      <Text style={[styles.tabButtonText, isActive && styles.tabButtonTextActive]}>
        {label}
      </Text>
    </Pressable>
  );
}

function SectionCard({ title, subtitle, children }) {
  return (
    <View style={styles.cardFrame}>
      <LinearGradient colors={["#ffffff", "#f7fbff"]} style={styles.card}>
        <View style={styles.cardTitleWrap}>
          <Text style={styles.cardTitle}>{title}</Text>
          {subtitle ? <Text style={styles.cardSubtitle}>{subtitle}</Text> : null}
        </View>
        {children}
      </LinearGradient>
    </View>
  );
}

function DataRow({ label, value }) {
  return (
    <View style={styles.dataRow}>
      <Text style={styles.dataRowLabel}>{label}</Text>
      <Text style={styles.dataRowValue} numberOfLines={1}>
        {value || "-"}
      </Text>
    </View>
  );
}

function HeroBadge({ text }) {
  return (
    <View style={styles.heroBadge}>
      <Text style={styles.heroBadgeText}>{text}</Text>
    </View>
  );
}

function HeaderBlock() {
  return (
    <LinearGradient colors={[COLORS.darkHeader, COLORS.darkHeader2]} style={styles.headerGradient}>
      <View style={styles.headerGlowLeft} />
      <View style={styles.headerGlowRight} />
      <View style={styles.headerTopRow}>
        <View>
          <Text style={styles.headerTitle}>Akıllı Yemekhane</Text>
          <Text style={styles.headerSubtitle}>Dijital Menü ve Geri Bildirim</Text>
        </View>
        <View style={styles.headerIconChip}>
          <MaterialCommunityIcons name="food-fork-drink" size={20} color="#ffffff" />
        </View>
      </View>

      <View style={styles.heroBadgesRow}>
        <HeroBadge text="Anlık Menü" />
        <HeroBadge text="Hızlı Puan" />
        <HeroBadge text="AI Destekli" />
      </View>
    </LinearGradient>
  );
}

function HeaderTabs({ activeTab, setActiveTab }) {
  return (
    <View style={styles.tabWrap}>
      <View style={styles.tabRow}>
        {TAB_LABELS.map((tab) => (
          <TabButton
            key={tab.key}
            label={tab.label}
            icon={tab.icon}
            isActive={activeTab === tab.key}
            onPress={() => setActiveTab(tab.key)}
          />
        ))}
      </View>
    </View>
  );
}

function MenuScreen() {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [menu, setMenu] = useState(null);

  const fetchMenu = async () => {
    setLoading(true);
    setError("");
    try {
      const response = await apiGet("/api/menu/today");
      if (!response.success || !response.data) {
        setError(response.message || "Menü verisi alınamadı.");
        setMenu(null);
      } else {
        setMenu(response.data);
      }
    } catch (e) {
      setError(e.message);
      setMenu(null);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchMenu();
  }, []);

  return (
    <ScrollView contentContainerStyle={styles.screenContent}>
      <SectionCard title="Bugünün Menüsü" subtitle="Yemekhane günlük plan">
        <View style={styles.metaPill}>
          <MaterialCommunityIcons name="lan-connect" size={14} color="#4f6785" />
          <Text style={styles.metaText}>API: {API_BASE_URL}</Text>
        </View>
        <Pressable style={styles.primaryButton} onPress={fetchMenu}>
          <Text style={styles.primaryButtonText}>Menüyü Yenile</Text>
        </Pressable>

        {loading ? <ActivityIndicator style={styles.loader} color={COLORS.accent} /> : null}
        {error ? <Text style={styles.errorText}>{error}</Text> : null}

        {menu ? (
          <View style={styles.resultBox}>
            <View style={styles.dayBadge}>
              <MaterialCommunityIcons name="calendar-week" size={14} color="#0c4f5b" />
              <Text style={styles.dayBadgeText}>{menu.gun || "-"}</Text>
            </View>
            {MENU_FIELDS.map((field) => {
              const value = menu[field.key] || "-";
              const label =
                field.key === "salata"
                  ? isDrinkLikeItem(value)
                    ? "İçecek"
                    : "Salata"
                  : field.label;
              return <DataRow key={field.key} label={label} value={value} />;
            })}
          </View>
        ) : null}
      </SectionCard>
    </ScrollView>
  );
}

function RecognizeScreen() {
  const [asset, setAsset] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [best, setBest] = useState(null);

  const pickImage = async () => {
    const permission = await ImagePicker.requestMediaLibraryPermissionsAsync();
    if (!permission.granted) {
      Alert.alert("İzin Gerekli", "Fotoğraf seçmek için izin vermelisin.");
      return;
    }

    const result = await ImagePicker.launchImageLibraryAsync({
      mediaTypes: ImagePicker.MediaTypeOptions.Images,
      allowsEditing: false,
      quality: 0.85,
    });

    if (!result.canceled && result.assets && result.assets.length > 0) {
      setAsset(result.assets[0]);
      setBest(null);
      setError("");
    }
  };

  const analyzeImage = async () => {
    if (!asset) {
      setError("Önce bir fotoğraf seç.");
      return;
    }

    setLoading(true);
    setError("");
    try {
      const response = await apiUploadFile("/api/recognize-food", asset);
      const bestGuess =
        response.en_olasi_yemek ||
        response.data?.en_olasi_yemek ||
        (response.taninan_yemekler && response.taninan_yemekler[0]) ||
        null;

      if (!bestGuess) {
        setError(response.message || "Yemek tanıma sonucu bulunamadı.");
        setBest(null);
      } else {
        setBest(bestGuess);
      }
    } catch (e) {
      setError(e.message);
      setBest(null);
    } finally {
      setLoading(false);
    }
  };

  return (
    <ScrollView contentContainerStyle={styles.screenContent}>
      <SectionCard title="Fotoğraftan Yemek Tanı" subtitle="Tepsiden hızlı analiz">
        <View style={styles.horizontalButtons}>
          <Pressable style={styles.primaryButton} onPress={pickImage}>
            <Text style={styles.primaryButtonText}>Fotoğraf Seç</Text>
          </Pressable>
          <Pressable style={styles.secondaryButton} onPress={analyzeImage}>
            <Text style={styles.secondaryButtonText}>Tanı</Text>
          </Pressable>
        </View>

        {asset ? (
          <Image source={{ uri: asset.uri }} style={styles.previewImage} />
        ) : (
          <View style={styles.emptyImageBox}>
            <MaterialCommunityIcons name="image-search-outline" size={28} color="#6f85a1" />
            <Text style={styles.metaText}>Henüz fotoğraf seçilmedi.</Text>
          </View>
        )}

        {loading ? <ActivityIndicator style={styles.loader} color={COLORS.accent} /> : null}
        {error ? <Text style={styles.errorText}>{error}</Text> : null}

        {best ? (
          <View style={styles.resultBox}>
            <DataRow label="Yemek" value={best.yemek || best.yemek_adi || "-"} />
            <DataRow
              label="Güven"
              value={`${Math.round((best.guven || best.guven_skoru || 0) * 100)}%`}
            />
            <DataRow label="Kalori" value={`${best.kalori ?? "-"}`} />
            <DataRow label="Protein" value={`${best.protein ?? "-"}`} />
            <DataRow label="Karbonhidrat" value={`${best.karbonhidrat ?? "-"}`} />
            <DataRow label="Yağ" value={`${best.yag ?? "-"}`} />
          </View>
        ) : null}
      </SectionCard>
    </ScrollView>
  );
}

function RateScreen() {
  const [dateValue, setDateValue] = useState(new Date().toISOString().slice(0, 10));
  const [todayMenu, setTodayMenu] = useState(null);
  const [selectedMealId, setSelectedMealId] = useState("");
  const [menuLoading, setMenuLoading] = useState(false);
  const [menuError, setMenuError] = useState("");
  const [rating, setRating] = useState(5);
  const [comment, setComment] = useState("");
  const [loading, setLoading] = useState(false);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");

  const menuOptions = useMemo(() => {
    if (!todayMenu) return [];

    return MENU_FIELDS.map((field) => {
      const rawValue = todayMenu[field.key];
      const yemekAdi = typeof rawValue === "string" ? rawValue.trim() : "";
      if (!yemekAdi || yemekAdi === "-" || yemekAdi.toLowerCase() === "yok") {
        return null;
      }

      const isDrink = field.key === "salata" && isDrinkLikeItem(yemekAdi);
      const kategori = isDrink ? "icecek" : field.key;
      const kategoriLabel = isDrink
        ? "İçecek"
        : field.key === "salata"
          ? "Salata"
          : field.label;

      return {
        id: `${kategori}:${yemekAdi}`,
        kategori,
        kategoriLabel,
        yemekAdi,
      };
    }).filter(Boolean);
  }, [todayMenu]);

  const selectedMeal = useMemo(
    () => menuOptions.find((item) => item.id === selectedMealId) || null,
    [menuOptions, selectedMealId]
  );

  const fetchTodayMenu = async () => {
    setMenuLoading(true);
    setMenuError("");
    try {
      const response = await apiGet("/api/menu/today");
      if (!response.success || !response.data) {
        setTodayMenu(null);
        setMenuError(response.message || "Bugünün menü verisi alınamadı.");
      } else {
        setTodayMenu(response.data);
      }
    } catch (e) {
      setTodayMenu(null);
      setMenuError(e.message);
    } finally {
      setMenuLoading(false);
    }
  };

  useEffect(() => {
    fetchTodayMenu();
  }, []);

  useEffect(() => {
    if (menuOptions.length === 0) {
      setSelectedMealId("");
      return;
    }

    const selectedStillExists = menuOptions.some((item) => item.id === selectedMealId);
    if (!selectedStillExists) {
      setSelectedMealId(menuOptions[0].id);
    }
  }, [menuOptions, selectedMealId]);

  const sendRating = async () => {
    if (!selectedMeal) {
      setError("Önce bugünün menüsünden bir yemek seç.");
      return;
    }

    setLoading(true);
    setError("");
    setMessage("");
    try {
      const payload = {
        tarih: dateValue,
        yemek_adi: selectedMeal.yemekAdi,
        kategori: selectedMeal.kategori,
        puan: rating,
        yorum: comment.trim() || null,
      };
      const response = await apiPostJson("/api/rate-meal", payload);
      if (!response.success) {
        setError(response.message || "Puan kaydedilemedi.");
      } else {
        setMessage(response.message || "Puan kaydedildi.");
      }
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <ScrollView contentContainerStyle={styles.screenContent}>
      <SectionCard title="Yemek Puanla" subtitle="Menüden seç, puanla, yorum bırak">
        <Text style={styles.label}>Tarih (YYYY-MM-DD)</Text>
        <View style={styles.inputWithIcon}>
          <MaterialCommunityIcons name="calendar-month-outline" size={18} color="#547192" />
          <TextInput
            style={styles.iconInput}
            value={dateValue}
            onChangeText={setDateValue}
            autoCapitalize="none"
            keyboardType="default"
            placeholderTextColor={COLORS.muted}
          />
        </View>

        <View style={styles.inlineHeader}>
          <Text style={styles.label}>Günün Menüsünden Yemek Seç</Text>
          <Pressable style={styles.linkButton} onPress={fetchTodayMenu}>
            <Text style={styles.linkButtonText}>Yenile</Text>
          </Pressable>
        </View>

        {menuLoading ? <ActivityIndicator style={styles.loader} color={COLORS.accent} /> : null}
        {menuError ? <Text style={styles.errorText}>{menuError}</Text> : null}

        <View style={styles.choiceWrap}>
          {menuOptions.map((item) => (
            <Pressable
              key={item.id}
              style={[
                styles.choiceButton,
                styles.menuChoiceButton,
                selectedMealId === item.id && styles.choiceButtonActive,
              ]}
              onPress={() => setSelectedMealId(item.id)}
            >
              <Text
                style={[
                  styles.choiceButtonText,
                  selectedMealId === item.id && styles.choiceButtonTextActive,
                ]}
              >
                {item.kategoriLabel}: {item.yemekAdi}
              </Text>
            </Pressable>
          ))}
        </View>

        {!menuLoading && !menuError && menuOptions.length === 0 ? (
          <Text style={styles.metaText}>Bugünün menüsünde seçilebilir yemek bulunamadı.</Text>
        ) : null}

        {selectedMeal ? (
          <View style={styles.selectedMealBox}>
            <View style={styles.selectedMealTop}>
              <MaterialCommunityIcons name="check-decagram" size={16} color="#0c6a61" />
              <Text style={styles.selectedMealText}>Seçilen: {selectedMeal.yemekAdi}</Text>
            </View>
            <Text style={styles.selectedMealMeta}>{selectedMeal.kategoriLabel}</Text>
          </View>
        ) : null}

        <Text style={styles.label}>Puan</Text>
        <View style={styles.choiceWrap}>
          {[1, 2, 3, 4, 5].map((value) => (
            <Pressable
              key={value}
              style={[styles.ratingButton, rating === value && styles.choiceButtonActive]}
              onPress={() => setRating(value)}
            >
              <Text
                style={[
                  styles.choiceButtonText,
                  rating === value && styles.choiceButtonTextActive,
                ]}
              >
                {value}
              </Text>
            </Pressable>
          ))}
        </View>

        <Text style={styles.label}>Yorum (opsiyonel)</Text>
        <TextInput
          style={[styles.input, styles.multilineInput, styles.commentInput]}
          value={comment}
          onChangeText={setComment}
          placeholder="Yorumunu yaz..."
          autoCapitalize="sentences"
          keyboardType={TEXT_INPUT_KEYBOARD_TYPE}
          inputMode="text"
          autoComplete="off"
          showSoftInputOnFocus
          autoCorrect={false}
          spellCheck={false}
          importantForAutofill="no"
          multiline
          placeholderTextColor={COLORS.muted}
        />
        <Text style={styles.metaText}>
          Türkçe karakter için emülatörde Gboard dili Türkçe olmalı.
        </Text>

        <Pressable style={styles.primaryButton} onPress={sendRating}>
          <Text style={styles.primaryButtonText}>Puanı Gönder</Text>
        </Pressable>

        {loading ? <ActivityIndicator style={styles.loader} color={COLORS.accent} /> : null}
        {error ? <Text style={styles.errorText}>{error}</Text> : null}
        {message ? <Text style={styles.successText}>{message}</Text> : null}
      </SectionCard>
    </ScrollView>
  );
}

function ChatScreen() {
  const [messages, setMessages] = useState([
    {
      role: "assistant",
      text: "Yemekhane asistanı hazır. Menü, puan ve besin değeri sorabilirsin.",
    },
  ]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);

  const sendMessage = async () => {
    const text = input.trim();
    if (!text) return;

    setMessages((prev) => [...prev, { role: "user", text }]);
    setInput("");
    setLoading(true);
    try {
      const response = await apiPostJson("/api/chat", { message: text });
      const replyText = response.data?.response || response.response || "Yanıt alınamadı.";
      const suggestions = response.data?.suggestions || [];
      setMessages((prev) => [
        ...prev,
        { role: "assistant", text: replyText, suggestions },
      ]);
    } catch (e) {
      setMessages((prev) => [...prev, { role: "assistant", text: `Hata: ${e.message}` }]);
    } finally {
      setLoading(false);
    }
  };

  return (
    <View style={styles.chatContainer}>
      <ScrollView contentContainerStyle={styles.chatList}>
        {messages.map((item, index) => (
          <View
            key={`${item.role}-${index}`}
            style={[
              styles.chatBubble,
              item.role === "user" ? styles.chatBubbleUser : styles.chatBubbleBot,
            ]}
          >
            <Text
              style={[
                styles.chatBubbleText,
                item.role === "user" ? styles.chatBubbleTextUser : styles.chatBubbleTextBot,
              ]}
            >
              {item.text}
            </Text>
            {item.suggestions && item.suggestions.length > 0 ? (
              <View style={styles.suggestionWrap}>
                {item.suggestions.map((suggestion) => (
                  <Pressable
                    key={suggestion}
                    style={styles.suggestionButton}
                    onPress={() => setInput(suggestion)}
                  >
                    <Text style={styles.suggestionButtonText}>{suggestion}</Text>
                  </Pressable>
                ))}
              </View>
            ) : null}
          </View>
        ))}
      </ScrollView>

      <View style={styles.chatInputRow}>
        <TextInput
          style={styles.chatInput}
          value={input}
          onChangeText={setInput}
          placeholder="Mesaj yaz..."
          autoCapitalize="sentences"
          keyboardType={TEXT_INPUT_KEYBOARD_TYPE}
          inputMode="text"
          autoComplete="off"
          showSoftInputOnFocus
          autoCorrect={false}
          spellCheck={false}
          importantForAutofill="no"
          placeholderTextColor={COLORS.muted}
        />
        <Pressable style={styles.primaryButtonSmall} onPress={sendMessage}>
          <Text style={styles.primaryButtonText}>Gönder</Text>
        </Pressable>
      </View>
      {loading ? <ActivityIndicator style={styles.loader} color={COLORS.accent} /> : null}
    </View>
  );
}

export default function App() {
  const [activeTab, setActiveTab] = useState(TABS.menu);

  const content = useMemo(() => {
    if (activeTab === TABS.menu) return <MenuScreen />;
    if (activeTab === TABS.recognize) return <RecognizeScreen />;
    if (activeTab === TABS.rate) return <RateScreen />;
    return <ChatScreen />;
  }, [activeTab]);

  return (
    <SafeAreaView style={styles.safeArea}>
      <StatusBar style="light" />
      <HeaderBlock />
      <HeaderTabs activeTab={activeTab} setActiveTab={setActiveTab} />

      <View style={styles.content}>{content}</View>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  safeArea: {
    flex: 1,
    backgroundColor: COLORS.bg,
  },
  headerGradient: {
    paddingHorizontal: 18,
    paddingTop: 14,
    paddingBottom: 14,
    overflow: "hidden",
    position: "relative",
  },
  headerGlowLeft: {
    position: "absolute",
    width: 180,
    height: 180,
    borderRadius: 90,
    backgroundColor: COLORS.tealGlow,
    opacity: 0.18,
    top: -60,
    left: -40,
  },
  headerGlowRight: {
    position: "absolute",
    width: 210,
    height: 210,
    borderRadius: 105,
    backgroundColor: COLORS.cyanGlow,
    opacity: 0.2,
    top: -110,
    right: -70,
  },
  headerTopRow: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
  },
  headerIconChip: {
    width: 38,
    height: 38,
    borderRadius: 19,
    backgroundColor: "rgba(255,255,255,0.15)",
    borderWidth: 1,
    borderColor: "rgba(255,255,255,0.22)",
    alignItems: "center",
    justifyContent: "center",
  },
  headerTitle: {
    fontSize: 18,
    fontWeight: "800",
    color: "#f7fbff",
    letterSpacing: 0.2,
  },
  headerSubtitle: {
    marginTop: 3,
    fontSize: 12,
    color: "#d6e8f1",
  },
  heroBadgesRow: {
    marginTop: 12,
    flexDirection: "row",
    gap: 8,
    flexWrap: "wrap",
  },
  heroBadge: {
    backgroundColor: "rgba(255,255,255,0.18)",
    borderWidth: 1,
    borderColor: "rgba(255,255,255,0.2)",
    paddingVertical: 5,
    paddingHorizontal: 10,
    borderRadius: 999,
  },
  heroBadgeText: {
    color: "#e9f6fd",
    fontSize: 11,
    fontWeight: "700",
  },
  tabWrap: {
    marginHorizontal: 14,
    marginTop: -10,
    marginBottom: 6,
  },
  tabRow: {
    flexDirection: "row",
    gap: 8,
    backgroundColor: "#103f4f",
    padding: 7,
    borderRadius: 16,
    borderWidth: 1,
    borderColor: "#245769",
    shadowColor: "#0b2330",
    shadowOpacity: 0.22,
    shadowRadius: 12,
    shadowOffset: { width: 0, height: 6 },
    elevation: 4,
  },
  tabButton: {
    flex: 1,
    borderRadius: 10,
    paddingVertical: 9,
    alignItems: "center",
    justifyContent: "center",
    backgroundColor: "rgba(255,255,255,0.13)",
  },
  tabButtonActive: {
    backgroundColor: COLORS.accent,
  },
  tabButtonPressed: {
    opacity: 0.8,
  },
  tabIcon: {
    marginBottom: 2,
  },
  tabButtonText: {
    color: "#d6e4ee",
    fontWeight: "700",
    fontSize: 13,
  },
  tabButtonTextActive: {
    color: "#ffffff",
  },
  content: {
    flex: 1,
  },
  screenContent: {
    paddingHorizontal: 14,
    paddingTop: 8,
    paddingBottom: 18,
    gap: 14,
  },
  cardFrame: {
    borderRadius: 18,
    backgroundColor: "#e5edf7",
    padding: 1,
    shadowColor: "#23384f",
    shadowOpacity: 0.12,
    shadowRadius: 12,
    shadowOffset: { width: 0, height: 5 },
    elevation: 3,
  },
  card: {
    borderRadius: 17,
    padding: 15,
    borderWidth: 1,
    borderColor: "#f4f8fc",
    gap: 12,
  },
  cardTitleWrap: {
    gap: 1,
  },
  cardTitle: {
    fontSize: 20,
    fontWeight: "800",
    color: COLORS.text,
  },
  cardSubtitle: {
    color: COLORS.muted,
    fontSize: 11,
    fontWeight: "600",
  },
  label: {
    fontSize: 13,
    fontWeight: "700",
    color: "#2e4058",
  },
  input: {
    borderWidth: 1,
    borderColor: COLORS.border,
    borderRadius: 12,
    paddingHorizontal: 12,
    paddingVertical: 10,
    backgroundColor: "#f9fbff",
    color: COLORS.text,
    fontSize: 15,
  },
  inputWithIcon: {
    flexDirection: "row",
    alignItems: "center",
    gap: 8,
    borderWidth: 1,
    borderColor: COLORS.border,
    borderRadius: 12,
    paddingHorizontal: 12,
    backgroundColor: "#f9fbff",
  },
  iconInput: {
    flex: 1,
    color: COLORS.text,
    fontSize: 15,
    paddingVertical: 10,
  },
  multilineInput: {
    minHeight: 92,
    textAlignVertical: "top",
  },
  commentInput: {
    borderStyle: "dashed",
    borderColor: "#c7d7ea",
  },
  inlineHeader: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
  },
  linkButton: {
    paddingVertical: 4,
    paddingHorizontal: 8,
    borderRadius: 8,
    backgroundColor: COLORS.accentSoft,
  },
  linkButtonText: {
    color: COLORS.accent,
    fontWeight: "700",
    fontSize: 12,
  },
  primaryButton: {
    backgroundColor: "#117f76",
    borderRadius: 12,
    paddingVertical: 12,
    alignItems: "center",
    shadowColor: "#0f766e",
    shadowOpacity: 0.22,
    shadowRadius: 9,
    shadowOffset: { width: 0, height: 4 },
    elevation: 3,
  },
  primaryButtonSmall: {
    backgroundColor: "#117f76",
    borderRadius: 12,
    paddingVertical: 10,
    paddingHorizontal: 14,
    alignItems: "center",
    justifyContent: "center",
  },
  primaryButtonText: {
    color: "#ffffff",
    fontWeight: "800",
    fontSize: 15,
  },
  secondaryButton: {
    backgroundColor: "#f5faf9",
    borderColor: "#9bd5cd",
    borderWidth: 1,
    borderRadius: 12,
    paddingVertical: 10,
    paddingHorizontal: 14,
    alignItems: "center",
  },
  secondaryButtonText: {
    color: COLORS.accent,
    fontWeight: "700",
    fontSize: 15,
  },
  horizontalButtons: {
    flexDirection: "row",
    gap: 10,
  },
  resultBox: {
    backgroundColor: "#f4f8fe",
    borderRadius: 12,
    borderWidth: 1,
    borderColor: "#cad9ea",
    padding: 12,
    gap: 8,
  },
  dayBadge: {
    alignSelf: "flex-start",
    flexDirection: "row",
    alignItems: "center",
    gap: 6,
    backgroundColor: "#dff2f0",
    borderRadius: 999,
    paddingVertical: 5,
    paddingHorizontal: 10,
    marginBottom: 3,
  },
  dayBadgeText: {
    color: "#0c4f5b",
    fontWeight: "800",
    fontSize: 12,
  },
  dataRow: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    borderBottomWidth: 1,
    borderBottomColor: "#e6eef7",
    paddingBottom: 7,
  },
  dataRowLabel: {
    color: "#536a85",
    fontSize: 12,
    fontWeight: "700",
  },
  dataRowValue: {
    color: COLORS.text,
    fontSize: 14,
    fontWeight: "700",
    marginLeft: 8,
    flexShrink: 1,
    textAlign: "right",
  },
  selectedMealBox: {
    backgroundColor: COLORS.accentSoft,
    borderRadius: 12,
    borderWidth: 1,
    borderColor: "#a4ddd6",
    paddingHorizontal: 12,
    paddingVertical: 10,
    gap: 4,
  },
  selectedMealTop: {
    flexDirection: "row",
    alignItems: "center",
    gap: 6,
  },
  selectedMealText: {
    color: "#0a4b48",
    fontWeight: "800",
    fontSize: 15,
  },
  selectedMealMeta: {
    color: "#126a67",
    fontWeight: "600",
    fontSize: 12,
  },
  rowTitle: {
    color: COLORS.text,
    fontSize: 15,
    fontWeight: "800",
  },
  rowText: {
    color: COLORS.text,
    fontSize: 14,
  },
  metaText: {
    color: COLORS.muted,
    fontSize: 11,
  },
  metaPill: {
    alignSelf: "flex-start",
    flexDirection: "row",
    alignItems: "center",
    gap: 6,
    backgroundColor: "#e7eff9",
    borderRadius: 999,
    paddingVertical: 5,
    paddingHorizontal: 10,
  },
  errorText: {
    color: COLORS.danger,
    fontWeight: "700",
    fontSize: 12,
  },
  successText: {
    color: COLORS.success,
    fontWeight: "700",
    fontSize: 12,
  },
  loader: {
    marginVertical: 8,
  },
  choiceWrap: {
    flexDirection: "row",
    flexWrap: "wrap",
    gap: 8,
  },
  choiceButton: {
    backgroundColor: "#edf4fc",
    borderRadius: 20,
    paddingHorizontal: 12,
    paddingVertical: 8,
    borderWidth: 1,
    borderColor: "#cfdeee",
  },
  menuChoiceButton: {
    borderRadius: 12,
  },
  ratingButton: {
    minWidth: 52,
    alignItems: "center",
    backgroundColor: "#edf4fc",
    borderRadius: 24,
    paddingHorizontal: 12,
    paddingVertical: 10,
    borderWidth: 1,
    borderColor: "#cfdeee",
  },
  choiceButtonActive: {
    backgroundColor: COLORS.accent,
    borderColor: COLORS.accent,
  },
  choiceButtonText: {
    color: "#2d3b4f",
    fontWeight: "700",
  },
  choiceButtonTextActive: {
    color: "#ffffff",
  },
  previewImage: {
    width: "100%",
    height: 230,
    borderRadius: 12,
    backgroundColor: "#e5edf7",
  },
  emptyImageBox: {
    height: 145,
    borderRadius: 12,
    borderWidth: 1,
    borderColor: "#cdd9e8",
    borderStyle: "dashed",
    backgroundColor: "#f7fbff",
    alignItems: "center",
    justifyContent: "center",
    gap: 6,
  },
  chatContainer: {
    flex: 1,
    paddingHorizontal: 12,
    paddingBottom: 12,
    gap: 10,
  },
  chatList: {
    gap: 8,
    paddingBottom: 12,
    paddingTop: 8,
  },
  chatBubble: {
    borderRadius: 15,
    padding: 12,
    maxWidth: "90%",
  },
  chatBubbleUser: {
    alignSelf: "flex-end",
    backgroundColor: COLORS.accent,
  },
  chatBubbleBot: {
    alignSelf: "flex-start",
    backgroundColor: "#ffffff",
    borderWidth: 1,
    borderColor: COLORS.border,
  },
  chatBubbleText: {
    lineHeight: 20,
    fontSize: 14,
  },
  chatBubbleTextUser: {
    color: "#ffffff",
  },
  chatBubbleTextBot: {
    color: COLORS.text,
  },
  suggestionWrap: {
    marginTop: 8,
    flexDirection: "row",
    flexWrap: "wrap",
    gap: 6,
  },
  suggestionButton: {
    backgroundColor: "#edf4fc",
    borderRadius: 16,
    paddingVertical: 6,
    paddingHorizontal: 10,
  },
  suggestionButtonText: {
    color: "#2d3b4f",
    fontSize: 12,
    fontWeight: "600",
  },
  chatInputRow: {
    flexDirection: "row",
    gap: 8,
    alignItems: "center",
  },
  chatInput: {
    flex: 1,
    borderWidth: 1,
    borderColor: COLORS.border,
    borderRadius: 12,
    paddingHorizontal: 12,
    paddingVertical: 9,
    backgroundColor: "#ffffff",
    color: COLORS.text,
    fontSize: 15,
  },
});
