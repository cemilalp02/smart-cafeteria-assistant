import React from "react";
import { View, Text, StyleSheet } from "react-native";
import { MaterialCommunityIcons } from "@expo/vector-icons";
import { C } from "../theme";
import FadeInView from "./FadeInView";

export default function DataRow({ label, value, icon, color, delay = 0 }) {
  return (
    <FadeInView delay={delay}>
      <View style={styles.dataRow}>
        <View style={styles.dataRowLeft}>
          {icon ? (
            <View style={[styles.dataRowIcon, { backgroundColor: (color || C.primary) + "18" }]}>
              <MaterialCommunityIcons name={icon} size={16} color={color || C.primary} />
            </View>
          ) : null}
          <Text style={styles.dataRowLabel}>{label}</Text>
        </View>
        <Text style={styles.dataRowValue} numberOfLines={1}>
          {value || "-"}
        </Text>
      </View>
    </FadeInView>
  );
}

const styles = StyleSheet.create({
  dataRow: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    borderBottomWidth: 1,
    borderBottomColor: C.borderLight,
    paddingVertical: 10,
  },
  dataRowLeft: {
    flexDirection: "row",
    alignItems: "center",
    gap: 10,
  },
  dataRowIcon: {
    width: 30,
    height: 30,
    borderRadius: 10,
    alignItems: "center",
    justifyContent: "center",
  },
  dataRowLabel: {
    color: C.muted,
    fontSize: 13,
    fontWeight: "700",
    textTransform: "uppercase",
    letterSpacing: 0.5,
  },
  dataRowValue: {
    color: C.text,
    fontSize: 15,
    fontWeight: "700",
    marginLeft: 8,
    flexShrink: 1,
    textAlign: "right",
  },
});
