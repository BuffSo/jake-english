// While Claude makes a suggestion, a script or an evaluation, a thinking face replaces the spinner. The user found the
// spinner off-putting on the phone and asked for Jake's thinking face instead (2026-11-06). Two pictures per person
// cross-fade in a circle and three dots blink under the waiting text, with React Native's own Animated and nothing
// new installed (docs/superpowers/specs/2026-11-06-waiting-animation-design.md).
import { createContext, useContext, useEffect, useRef, type ReactNode } from "react";
import { Animated, StyleSheet, View } from "react-native";

import { api } from "../api";
import type { Thinking } from "../api/types";
import { colors } from "./theme";
import { framesFor, type Who } from "./thinking";

const HOLD = 1800; // ms a picture stays before the next comes in
const FADE = 600; // ms the cross-fade takes
const DOT = 400; // ms per dot; three make one 1.2 s round

// /home `images.thinking`, null until /home has come back
export const ThinkingFaces = createContext<Thinking | null>(null);

const fade = (v: Animated.Value, toValue: number, duration: number) =>
  Animated.timing(v, { toValue, duration, useNativeDriver: true });

// The pictures are square face crops, so the whole picture fills the circle. With no pictures the caller's fallback
// shows instead (nothing by default): a picture that fails to load leaves only the circle's background.
export function ThinkingFace({ who, size, fallback = null }: { who: Who; size: number; fallback?: ReactNode }) {
  const frames = framesFor(useContext(ThinkingFaces), who);
  if (!frames.length) return fallback;
  // keyed so that another person (Jake's pick turning into Ryan's script) starts from their first picture
  return <Faces key={`${who}:${frames.join("|")}`} frames={frames} size={size} />;
}

function Faces({ frames, size }: { frames: string[]; size: number }) {
  const opacity = useRef(frames.map((_, i) => new Animated.Value(i === 0 ? 1 : 0))).current;

  useEffect(() => {
    if (opacity.length < 2) return; // one picture just stays
    const steps = opacity.map((now, i) =>
      Animated.sequence([
        Animated.delay(HOLD),
        Animated.parallel([fade(now, 0, FADE), fade(opacity[(i + 1) % opacity.length], 1, FADE)]),
      ]),
    );
    const loop = Animated.loop(Animated.sequence(steps));
    loop.start();
    return () => loop.stop(); // leaving the wait (or the screen) stops it
  }, [opacity]);

  return (
    <View style={[styles.circle, { width: size, height: size, borderRadius: size / 2 }]}>
      {frames.map((path, i) => (
        // all pictures load at once and stay mounted, so a cross-fade never waits for a download
        <Animated.Image key={path} source={api.imageSource(path)} style={[StyleSheet.absoluteFill, { opacity: opacity[i] }]} />
      ))}
    </View>
  );
}

export function Dots() {
  const dots = useRef([0, 1, 2].map(() => new Animated.Value(0.3))).current;

  useEffect(() => {
    const loop = Animated.loop(
      Animated.sequence(dots.map((d) => Animated.sequence([fade(d, 1, DOT / 2), fade(d, 0.3, DOT / 2)]))),
    );
    loop.start();
    return () => loop.stop();
  }, [dots]);

  return (
    <View style={styles.dots}>
      {dots.map((d, i) => (
        <Animated.View key={i} style={[styles.dot, { opacity: d }]} />
      ))}
    </View>
  );
}

const styles = StyleSheet.create({
  circle: { alignSelf: "center", overflow: "hidden", backgroundColor: colors.ryan },
  dots: { flexDirection: "row", justifyContent: "center", marginTop: 10, gap: 6 },
  dot: { width: 8, height: 8, borderRadius: 4, backgroundColor: colors.sub },
});
