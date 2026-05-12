import React from "react";
import { View, Text, StyleSheet } from "react-native";
import { LinearGradient } from "expo-linear-gradient";
import { MaterialCommunityIcons } from "@expo/vector-icons";
import { C } from "../theme";
import ScaleOnPress from "./ScaleOnPress";

export function PrimaryButton({ children, onPress, icon, gradient, style: extraStyle, glowColor }) {
  return (
    <ScaleOnPress onPress={onPress} style={extraStyle}>
      <LinearGradient
        colors={gradient || [C.accent, C.accentDark]}
        start={{ x: 0, y: 0 }}
        end={{ x: 1, y: 1 }}
        style={[styles.primaryButton, glowColor && { shadowColor: glowColor }]}
      >
        {icon ? (
          <MaterialCommunityIcons name={icon} size={18} color="#fff" style={{ marginRight: 6 }} />
        ) : null}
        <Text style={styles.primaryButtonText}>{children}</Text>
      </LinearGradient>
    </ScaleOnPress>
  );
}

export function SecondaryButton({ children, onPress, icon }) {
  return (
    <ScaleOnPress onPress={onPress}>
      <View style={styles.secondaryButton}>
        {icon ? (
          <MaterialCommunityIcons name={icon} size={16} color={C.accent} style={{ marginRight: 6 }} />
        ) : null}
        <Text style={styles.secondaryButtonText}>{children}</Text>
      </View>
    </ScaleOnPress>
  );
}

const styles = StyleSheet.create({
  primaryButton: {
    borderRadius: 18,
    paddingVertical: 15,
    paddingHorizontal: 22,
    alignItems: "center",
    justifyContent: "center",
    flexDirection: "row",
    shadowColor: C.accent,
    shadowOpacity: 0.4,
    shadowRadius: 14,
    shadowOffset: { width: 0, height: 7 },
    elevation: 5,
  },
  primaryButtonText: {
    color: "#ffffff",
    fontWeight: "800",
    fontSize: 15,
    letterSpacing: 0.2,
  },
  secondaryButton: {
    backgroundColor: C.white08,
    borderColor: C.border,
    borderWidth: 1,
    borderRadius: 16,
    paddingVertical: 12,
    paddingHorizontal: 16,
    alignItems: "center",
    justifyContent: "center",
    flexDirection: "row",
  },
  secondaryButtonText: {
    color: C.accent,
    fontWeight: "700",
    fontSize: 15,
  },
});
