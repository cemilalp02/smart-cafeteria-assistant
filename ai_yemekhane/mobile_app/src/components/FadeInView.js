import React, { useEffect, useRef } from "react";
import { Animated } from "react-native";

export default function FadeInView({ delay = 0, duration = 500, style, children }) {
  const fadeAnim = useRef(new Animated.Value(0)).current;
  const slideAnim = useRef(new Animated.Value(24)).current;

  useEffect(() => {
    Animated.parallel([
      Animated.timing(fadeAnim, {
        toValue: 1, duration, delay,
        useNativeDriver: true,
      }),
      Animated.timing(slideAnim, {
        toValue: 0, duration, delay,
        useNativeDriver: true,
      }),
    ]).start();
  }, []);

  return (
    <Animated.View style={[style, { opacity: fadeAnim, transform: [{ translateY: slideAnim }] }]}>
      {children}
    </Animated.View>
  );
}
