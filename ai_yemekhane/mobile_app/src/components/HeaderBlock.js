import React, { useEffect, useRef } from "react";
import { Animated, Dimensions, Platform, Pressable, StyleSheet, Text, View } from "react-native";
import { LinearGradient } from "expo-linear-gradient";
import { MaterialCommunityIcons } from "@expo/vector-icons";
import { C, TAB_LABELS } from "../theme";
import FadeInView from "./FadeInView";

const { width: SCREEN_WIDTH } = Dimensions.get("window");

function HeroBadge({ text, icon }) {
  return (
    <View style={styles.heroBadge}>
      {icon ? <MaterialCommunityIcons name={icon} size={12} color="#9df0d4" /> : null}
      <Text style={styles.heroBadgeText}>{text}</Text>
    </View>
  );
}

export function HeaderBlock() {
  const pulseAnim = useRef(new Animated.Value(0.4)).current;

  useEffect(() => {
    Animated.loop(
      Animated.sequence([
        Animated.timing(pulseAnim, { toValue: 0.7, duration: 2000, useNativeDriver: true }),
        Animated.timing(pulseAnim, { toValue: 0.4, duration: 2000, useNativeDriver: true }),
      ])
    ).start();
  }, []);

  return (
    <LinearGradient
      colors={["#050e18", "#0b1a30", "#0f2540"]}
      start={{ x: 0, y: 0 }}
      end={{ x: 1, y: 1 }}
      style={styles.headerGradient}
    >
      <Animated.View style={[styles.headerGlowLeft, { opacity: pulseAnim }]} />
      <Animated.View style={[styles.headerGlowRight, { opacity: pulseAnim }]} />
      <Animated.View style={[styles.headerGlowViolet, { opacity: pulseAnim }]} />

      <FadeInView delay={100}>
        <View style={styles.headerTopRow}>
          <View>
            <View style={styles.headerTitleRow}>
              <View style={styles.logoMark}>
                <MaterialCommunityIcons name="silverware-variant" size={18} color="#fff" />
              </View>
              <Text style={styles.headerTitle}>Akıllı Yemekhane</Text>
            </View>
            <Text style={styles.headerSubtitle}>Dijital Menü ve Geri Bildirim Platformu</Text>
          </View>
          <View style={styles.headerIconChip}>
            <MaterialCommunityIcons name="food-fork-drink" size={22} color="#ffffff" />
          </View>
        </View>
      </FadeInView>

      <FadeInView delay={300}>
        <View style={styles.heroBadgesRow}>
          <HeroBadge text="Anlık Menü" icon="clock-fast" />
          <HeroBadge text="Hızlı Puan" icon="star-shooting" />
          <HeroBadge text="AI Destekli" icon="robot-outline" />
        </View>
      </FadeInView>
    </LinearGradient>
  );
}

function TabButton({ label, icon, isActive, onPress }) {
  const scaleAnim = useRef(new Animated.Value(1)).current;
  const rotateAnim = useRef(new Animated.Value(0)).current;

  useEffect(() => {
    if (isActive) {
      Animated.parallel([
        Animated.sequence([
          Animated.timing(scaleAnim, { toValue: 1.18, duration: 150, useNativeDriver: true }),
          Animated.spring(scaleAnim, { toValue: 1, useNativeDriver: true, speed: 16, bounciness: 12 }),
        ]),
        Animated.sequence([
          Animated.timing(rotateAnim, { toValue: 1, duration: 200, useNativeDriver: true }),
          Animated.timing(rotateAnim, { toValue: 0, duration: 200, useNativeDriver: true }),
        ]),
      ]).start();
    }
  }, [isActive]);

  const iconRotate = rotateAnim.interpolate({
    inputRange: [0, 1],
    outputRange: ['0deg', '15deg'],
  });

  return (
    <Pressable onPress={onPress} style={styles.tabButton}>
      <Animated.View
        style={[
          styles.tabButtonInner,
          isActive && styles.tabButtonActive,
          { transform: [{ scale: scaleAnim }] },
        ]}
      >
        <Animated.View style={{ transform: [{ rotate: iconRotate }] }}>
          <MaterialCommunityIcons
            name={icon}
            size={20}
            color={isActive ? "#ffffff" : C.muted}
            style={styles.tabIcon}
          />
        </Animated.View>
        <Text style={[styles.tabButtonText, isActive && styles.tabButtonTextActive]}>
          {label}
        </Text>
        {isActive ? <View style={styles.tabActiveDot} /> : null}
      </Animated.View>
    </Pressable>
  );
}

export function HeaderTabs({ activeTab, setActiveTab }) {
  return (
    <FadeInView delay={200}>
      <View style={styles.tabWrap}>
        <LinearGradient
          colors={[C.bgCard, C.bgCard2]}
          style={styles.tabRow}
        >
          {TAB_LABELS.map((tab) => (
            <TabButton
              key={tab.key}
              label={tab.label}
              icon={tab.icon}
              isActive={activeTab === tab.key}
              onPress={() => setActiveTab(tab.key)}
            />
          ))}
        </LinearGradient>
      </View>
    </FadeInView>
  );
}

const styles = StyleSheet.create({
  headerGradient: {
    paddingHorizontal: 20,
    paddingTop: 16,
    paddingBottom: 18,
    overflow: "hidden",
    position: "relative",
  },
  headerGlowLeft: {
    position: "absolute", width: 200, height: 200, borderRadius: 100,
    backgroundColor: C.glow2, top: -80, left: -60,
  },
  headerGlowRight: {
    position: "absolute", width: 240, height: 240, borderRadius: 120,
    backgroundColor: C.glow1, top: -130, right: -80,
  },
  headerGlowViolet: {
    position: "absolute", width: 180, height: 180, borderRadius: 90,
    backgroundColor: C.glowViolet, bottom: -100, left: SCREEN_WIDTH / 3,
  },
  headerTopRow: { flexDirection: "row", justifyContent: "space-between", alignItems: "center" },
  headerTitleRow: { flexDirection: "row", alignItems: "center", gap: 10 },
  logoMark: {
    width: 36, height: 36, borderRadius: 12,
    backgroundColor: C.white15, borderWidth: 1, borderColor: C.white08,
    alignItems: "center", justifyContent: "center",
  },
  headerIconChip: {
    width: 44, height: 44, borderRadius: 22,
    backgroundColor: C.white15, borderWidth: 1, borderColor: C.white08,
    alignItems: "center", justifyContent: "center",
  },
  headerTitle: { fontSize: 22, fontWeight: "900", color: "#f7fbff", letterSpacing: -0.5 },
  headerSubtitle: { marginTop: 4, fontSize: 12, color: C.textSoft, letterSpacing: 0.2 },
  heroBadgesRow: { marginTop: 14, flexDirection: "row", gap: 8, flexWrap: "wrap" },
  heroBadge: {
    flexDirection: "row", alignItems: "center", gap: 5,
    backgroundColor: C.accentSoft, borderWidth: 1,
    borderColor: "rgba(32, 201, 151, 0.18)",
    paddingVertical: 6, paddingHorizontal: 12, borderRadius: 999,
  },
  heroBadgeText: { color: "#9df0d4", fontSize: 11, fontWeight: "800", letterSpacing: 0.3 },
  tabWrap: { marginHorizontal: 14, marginTop: -8, marginBottom: 8 },
  tabRow: {
    flexDirection: "row", padding: 5, borderRadius: 20,
    borderWidth: 1, borderColor: C.border,
    shadowColor: "#000", shadowOpacity: 0.3, shadowRadius: 16,
    shadowOffset: { width: 0, height: 8 }, elevation: 6,
  },
  tabButton: { flex: 1 },
  tabButtonInner: { borderRadius: 16, paddingVertical: 10, alignItems: "center", justifyContent: "center" },
  tabButtonActive: {
    backgroundColor: C.accent,
    shadowColor: C.accent, shadowOpacity: 0.45, shadowRadius: 10,
    shadowOffset: { width: 0, height: 5 }, elevation: 6,
  },
  tabIcon: { marginBottom: 2 },
  tabButtonText: { color: C.muted, fontWeight: "700", fontSize: 11, letterSpacing: 0.3 },
  tabButtonTextActive: { color: "#ffffff" },
  tabActiveDot: {
    width: 4, height: 4, borderRadius: 2, backgroundColor: "#ffffff", marginTop: 2,
    shadowColor: "#fff", shadowOpacity: 0.6, shadowRadius: 4, shadowOffset: { width: 0, height: 0 },
  },
});
