import React, { useEffect, useMemo, useRef, useState } from "react";
import { StatusBar } from "expo-status-bar";
import { LinearGradient } from "expo-linear-gradient";
import { MaterialCommunityIcons } from "@expo/vector-icons";
import { Animated, Platform, SafeAreaView, StyleSheet, Text, View } from "react-native";
import * as Notifications from "expo-notifications";
import { C, TABS } from "./src/theme";
import { apiPostJson } from "./src/api";
import { HeaderBlock, HeaderTabs } from "./src/components";
import { MenuScreen, RateScreen, ChatScreen, StatsScreen } from "./src/screens";

// ─── PUSH NOTIFICATION SETUP ───────────────────────────────────
try {
  Notifications.setNotificationHandler({
    handleNotification: async () => ({
      shouldShowAlert: true,
      shouldPlaySound: true,
      shouldSetBadge: false,
    }),
  });
} catch (_e) {
  // Silently ignore – Expo Go limitation
}

async function registerForPushNotifications() {
  try {
    const { status: existingStatus } = await Notifications.getPermissionsAsync();
    let finalStatus = existingStatus;

    if (existingStatus !== "granted") {
      const { status } = await Notifications.requestPermissionsAsync();
      finalStatus = status;
    }

    if (finalStatus !== "granted") {
      console.log("Push notification izni verilmedi.");
      return null;
    }

    if (Platform.OS === "android") {
      try {
        await Notifications.setNotificationChannelAsync("menu-notifications", {
          name: "Menü Bildirimleri",
          importance: Notifications.AndroidImportance.HIGH,
          vibrationPattern: [0, 250, 250, 250],
          lightColor: "#20c997",
          sound: "default",
        });
      } catch (_channelErr) {
        console.log("ℹ️ Notification channel oluşturulamadı (Expo Go sınırlaması).");
        return null;
      }
    }

    let token = null;
    try {
      const tokenData = await Notifications.getExpoPushTokenAsync();
      token = tokenData.data;
      console.log("📱 Push Token:", token);
    } catch (_tokenErr) {
      console.log("ℹ️ Push token alınamadı (Expo Go sınırlaması).");
      return null;
    }

    try {
      await apiPostJson("/api/notifications/register", { token });
      console.log("✅ Push token backend'e kaydedildi.");
    } catch (e) {
      console.log("⚠️ Token kayıt hatası:", e.message);
    }

    return token;
  } catch (error) {
    console.log("ℹ️ Push notification desteği yok (Expo Go).");
    return null;
  }
}

// ═══════════════════════════════════════════════════════════════
// MAIN APP
// ═══════════════════════════════════════════════════════════════

export default function App() {
  const [activeTab, setActiveTab] = useState(TABS.menu);
  const [notification, setNotification] = useState(null);
  const notifAnim = useRef(new Animated.Value(-80)).current;

  useEffect(() => {
    registerForPushNotifications();

    let subscription = null;
    try {
      subscription = Notifications.addNotificationReceivedListener((notif) => {
        const { title, body } = notif.request.content;
        setNotification({ title, body });

        Animated.sequence([
          Animated.timing(notifAnim, { toValue: 0, duration: 400, useNativeDriver: true }),
          Animated.delay(4000),
          Animated.timing(notifAnim, { toValue: -80, duration: 300, useNativeDriver: true }),
        ]).start(() => setNotification(null));
      });
    } catch (_e) {
      // Expo Go limitation
    }

    let responseSubscription = null;
    try {
      responseSubscription = Notifications.addNotificationResponseReceivedListener((response) => {
        const data = response.notification.request.content.data;
        if (data?.type === "daily_menu") {
          setActiveTab(TABS.menu);
        }
      });
    } catch (_e) {
      // Expo Go limitation
    }

    return () => {
      if (subscription) subscription.remove();
      if (responseSubscription) responseSubscription.remove();
    };
  }, []);

  const content = useMemo(() => {
    if (activeTab === TABS.menu) return <MenuScreen />;
    if (activeTab === TABS.rate) return <RateScreen />;
    if (activeTab === TABS.stats) return <StatsScreen />;
    return <ChatScreen />;
  }, [activeTab]);

  return (
    <SafeAreaView style={styles.safeArea}>
      <StatusBar style="light" />

      {notification ? (
        <Animated.View style={[styles.notifBanner, { transform: [{ translateY: notifAnim }] }]}>
          <LinearGradient
            colors={[C.accent, C.accentDark]}
            start={{ x: 0, y: 0 }}
            end={{ x: 1, y: 1 }}
            style={styles.notifBannerInner}
          >
            <MaterialCommunityIcons name="bell-ring-outline" size={20} color="#fff" />
            <View style={{ flex: 1 }}>
              <Text style={styles.notifBannerTitle}>{notification.title}</Text>
              <Text style={styles.notifBannerBody} numberOfLines={2}>{notification.body}</Text>
            </View>
          </LinearGradient>
        </Animated.View>
      ) : null}

      <HeaderBlock />
      <HeaderTabs activeTab={activeTab} setActiveTab={setActiveTab} />
      <View style={styles.content}>{content}</View>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  safeArea: { flex: 1, backgroundColor: C.bg },
  content: { flex: 1 },
  notifBanner: {
    position: "absolute", top: 0, left: 0, right: 0, zIndex: 999,
    paddingHorizontal: 14, paddingTop: Platform.OS === "android" ? 30 : 50,
  },
  notifBannerInner: {
    flexDirection: "row", alignItems: "center", gap: 12, padding: 14, borderRadius: 16,
    shadowColor: C.accent, shadowOpacity: 0.4, shadowRadius: 12,
    shadowOffset: { width: 0, height: 6 }, elevation: 8,
  },
  notifBannerTitle: { color: "#fff", fontWeight: "800", fontSize: 14 },
  notifBannerBody: { color: "rgba(255,255,255,0.85)", fontSize: 12, fontWeight: "600", marginTop: 2 },
});
