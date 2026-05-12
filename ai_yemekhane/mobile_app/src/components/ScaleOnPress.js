import React, { useRef } from "react";
import { Animated, Pressable } from "react-native";

export default function ScaleOnPress({ style, children, onPress, disabled }) {
  const scaleAnim = useRef(new Animated.Value(1)).current;
  const glowAnim = useRef(new Animated.Value(0)).current;

  const handlePressIn = () => {
    Animated.parallel([
      Animated.spring(scaleAnim, {
        toValue: 0.93, useNativeDriver: true, speed: 50, bounciness: 4,
      }),
      Animated.timing(glowAnim, {
        toValue: 1, duration: 150, useNativeDriver: true,
      }),
    ]).start();
  };

  const handlePressOut = () => {
    Animated.parallel([
      Animated.spring(scaleAnim, {
        toValue: 1, useNativeDriver: true, speed: 18, bounciness: 10,
      }),
      Animated.timing(glowAnim, {
        toValue: 0, duration: 300, useNativeDriver: true,
      }),
    ]).start();
  };

  return (
    <Pressable
      onPress={onPress}
      onPressIn={handlePressIn}
      onPressOut={handlePressOut}
      disabled={disabled}
    >
      <Animated.View style={[style, { transform: [{ scale: scaleAnim }], opacity: Animated.add(glowAnim.interpolate({ inputRange: [0, 1], outputRange: [1, 0.88] }), glowAnim.interpolate({ inputRange: [0, 1], outputRange: [0, 0.12] })) }]}>
        {children}
      </Animated.View>
    </Pressable>
  );
}
