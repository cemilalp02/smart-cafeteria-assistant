import React, { useEffect, useRef, useState } from "react";
import {
  Animated, Platform, Pressable, ScrollView, StyleSheet, Text, TextInput, View,
} from "react-native";
import { LinearGradient } from "expo-linear-gradient";
import { MaterialCommunityIcons } from "@expo/vector-icons";
import { C } from "../theme";
import { apiPostJson } from "../api";
import { FadeInView, ScaleOnPress } from "../components";

const TEXT_INPUT_KEYBOARD_TYPE = Platform.OS === "android" ? "visible-password" : "default";

function TypingDot({ delay }) {
  const anim = useRef(new Animated.Value(0.3)).current;
  useEffect(() => {
    Animated.loop(
      Animated.sequence([
        Animated.timing(anim, { toValue: 1, duration: 400, delay, useNativeDriver: true }),
        Animated.timing(anim, { toValue: 0.3, duration: 400, useNativeDriver: true }),
      ])
    ).start();
  }, []);
  return (
    <Animated.View style={[styles.typingDot, { opacity: anim }]} />
  );
}

export default function ChatScreen() {
  const [messages, setMessages] = useState([
    {
      role: "assistant",
      text: "Merhaba! 👋 Yemekhane asistanı hazır. Menü, puan ve besin değeri sorabilirsin.",
    },
  ]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const scrollRef = useRef(null);

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
      setMessages((prev) => [...prev, { role: "assistant", text: replyText, suggestions }]);
    } catch (e) {
      setMessages((prev) => [...prev, { role: "assistant", text: `Hata: ${e.message}` }]);
    } finally {
      setLoading(false);
    }
  };

  return (
    <View style={styles.chatContainer}>
      <ScrollView
        ref={scrollRef}
        contentContainerStyle={styles.chatList}
        onContentSizeChange={() => scrollRef.current?.scrollToEnd({ animated: true })}
      >
        {messages.map((item, index) => (
          <FadeInView key={`${item.role}-${index}`} delay={0} duration={300}>
            <View style={[
              styles.chatBubble,
              item.role === "user" ? styles.chatBubbleUser : styles.chatBubbleBot,
            ]}>
              <View style={styles.chatBubbleTop}>
                <View style={[
                  styles.chatAvatar,
                  item.role === "user" ? styles.chatAvatarUser : styles.chatAvatarBot,
                ]}>
                  <MaterialCommunityIcons
                    name={item.role === "user" ? "account" : "robot-outline"}
                    size={14}
                    color="#fff"
                  />
                </View>
                <Text style={styles.chatRoleName}>
                  {item.role === "user" ? "Sen" : "Asistan"}
                </Text>
              </View>
              <Text style={[
                styles.chatBubbleText,
                item.role === "user" ? styles.chatBubbleTextUser : styles.chatBubbleTextBot,
              ]}>
                {item.text}
              </Text>
              {item.suggestions && item.suggestions.length > 0 ? (
                <View style={styles.suggestionWrap}>
                  {item.suggestions.map((suggestion) => (
                    <ScaleOnPress key={suggestion} onPress={() => setInput(suggestion)}>
                      <View style={styles.suggestionButton}>
                        <Text style={styles.suggestionButtonText}>{suggestion}</Text>
                      </View>
                    </ScaleOnPress>
                  ))}
                </View>
              ) : null}
            </View>
          </FadeInView>
        ))}
        {loading ? (
          <View style={[styles.chatBubble, styles.chatBubbleBot]}>
            <View style={styles.typingDots}>
              <TypingDot delay={0} />
              <TypingDot delay={200} />
              <TypingDot delay={400} />
            </View>
          </View>
        ) : null}
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
          placeholderTextColor={C.muted}
          onSubmitEditing={sendMessage}
        />
        <ScaleOnPress onPress={sendMessage}>
          <LinearGradient
            colors={[C.primary, C.primaryDark]}
            style={styles.sendButton}
          >
            <MaterialCommunityIcons name="send" size={20} color="#fff" />
          </LinearGradient>
        </ScaleOnPress>
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  chatContainer: { flex: 1, paddingHorizontal: 14, paddingBottom: 12, gap: 10 },
  chatList: { gap: 10, paddingBottom: 12, paddingTop: 8 },
  chatBubble: { borderRadius: 20, padding: 14, maxWidth: "88%" },
  chatBubbleUser: {
    alignSelf: "flex-end", backgroundColor: C.primary, borderBottomRightRadius: 6,
    shadowColor: C.primary, shadowOpacity: 0.3, shadowRadius: 12,
    shadowOffset: { width: 0, height: 6 }, elevation: 4,
  },
  chatBubbleBot: {
    alignSelf: "flex-start", backgroundColor: C.bgCard2,
    borderWidth: 1, borderColor: C.border, borderBottomLeftRadius: 6,
  },
  chatBubbleTop: { flexDirection: "row", alignItems: "center", gap: 6, marginBottom: 6 },
  chatAvatar: { width: 22, height: 22, borderRadius: 11, alignItems: "center", justifyContent: "center" },
  chatAvatarUser: { backgroundColor: "rgba(255,255,255,0.2)" },
  chatAvatarBot: { backgroundColor: C.accentSoft },
  chatRoleName: { fontSize: 11, fontWeight: "800", color: C.muted, textTransform: "uppercase", letterSpacing: 0.5 },
  chatBubbleText: { lineHeight: 22, fontSize: 14 },
  chatBubbleTextUser: { color: "#ffffff" },
  chatBubbleTextBot: { color: C.text },
  suggestionWrap: { marginTop: 10, flexDirection: "row", flexWrap: "wrap", gap: 6 },
  suggestionButton: {
    backgroundColor: C.primarySoft, borderRadius: 999, paddingVertical: 7, paddingHorizontal: 12,
    borderWidth: 1, borderColor: "rgba(47,128,237,.18)",
  },
  suggestionButtonText: { color: "#84beff", fontSize: 12, fontWeight: "700" },
  chatInputRow: { flexDirection: "row", gap: 8, alignItems: "center" },
  chatInput: {
    flex: 1, borderWidth: 1, borderColor: C.border, borderRadius: 20,
    paddingHorizontal: 16, paddingVertical: 12, backgroundColor: C.bgCard, color: C.text, fontSize: 15,
  },
  sendButton: {
    width: 50, height: 50, borderRadius: 25, alignItems: "center", justifyContent: "center",
    shadowColor: C.primary, shadowOpacity: 0.45, shadowRadius: 14,
    shadowOffset: { width: 0, height: 5 }, elevation: 5,
  },
  typingDots: { flexDirection: "row", gap: 6, paddingVertical: 4, paddingHorizontal: 8 },
  typingDot: { width: 8, height: 8, borderRadius: 4, backgroundColor: C.muted },
});
