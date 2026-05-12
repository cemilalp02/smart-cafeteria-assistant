import React from "react";
import { View, Text, StyleSheet } from "react-native";
import { LinearGradient } from "expo-linear-gradient";
import { MaterialCommunityIcons } from "@expo/vector-icons";
import { C } from "../theme";
import FadeInView from "./FadeInView";

export default function SectionCard({ title, subtitle, icon, children, delay = 0, accentColor }) {
  const borderColor = accentColor || C.accent;
  return (
    <FadeInView delay={delay}>
      <View style={styles.cardFrame}>
        <LinearGradient
          colors={[C.bgCard, C.bgCard2]}
          start={{ x: 0, y: 0 }}
          end={{ x: 1, y: 1 }}
          style={styles.card}
        >
          <View style={[styles.cardGlowTop, { backgroundColor: borderColor + "08" }]} />
          <View style={[styles.cardTopAccent, { backgroundColor: borderColor }]} />
          <View style={styles.cardTitleWrap}>
            <View style={styles.cardTitleRow}>
              {icon ? (
                <View style={[styles.cardIconWrap, { backgroundColor: borderColor + "18", borderColor: borderColor + "28" }]}>
                  <MaterialCommunityIcons name={icon} size={20} color={borderColor} />
                </View>
              ) : null}
              <View style={{ flex: 1 }}>
                <Text style={styles.cardTitle}>{title}</Text>
                {subtitle ? <Text style={styles.cardSubtitle}>{subtitle}</Text> : null}
              </View>
            </View>
          </View>
          {children}
        </LinearGradient>
      </View>
    </FadeInView>
  );
}

const styles = StyleSheet.create({
  cardFrame: {
    borderRadius: 22,
    overflow: "hidden",
    shadowColor: "#000",
    shadowOpacity: 0.35,
    shadowRadius: 20,
    shadowOffset: { width: 0, height: 10 },
    elevation: 8,
  },
  card: {
    borderRadius: 22,
    padding: 18,
    borderWidth: 1,
    borderColor: C.border,
    gap: 14,
    overflow: "hidden",
  },
  cardGlowTop: {
    position: "absolute",
    top: -40,
    right: -40,
    width: 140,
    height: 140,
    borderRadius: 70,
  },
  cardTopAccent: {
    position: "absolute",
    top: 0,
    left: 0,
    right: 0,
    height: 3,
    borderTopLeftRadius: 22,
    borderTopRightRadius: 22,
  },
  cardTitleWrap: {
    gap: 2,
  },
  cardTitleRow: {
    flexDirection: "row",
    alignItems: "center",
    gap: 12,
  },
  cardIconWrap: {
    width: 42,
    height: 42,
    borderRadius: 14,
    borderWidth: 1,
    alignItems: "center",
    justifyContent: "center",
  },
  cardTitle: {
    fontSize: 20,
    fontWeight: "900",
    color: C.text,
    letterSpacing: -0.3,
  },
  cardSubtitle: {
    color: C.muted,
    fontSize: 12,
    fontWeight: "600",
    marginTop: 2,
  },
});
