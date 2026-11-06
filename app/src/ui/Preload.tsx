// Loads pictures before a screen needs them (2026-11-06, after the phone test: a face could first show as an empty
// circle while its picture came from the Mac). `Image.prefetch` cannot send the token the Mac asks for, so the
// pictures are drawn here instead, invisibly and as long as the app runs, and the image cache keeps them.
import { Image, StyleSheet, View } from "react-native";

import { api } from "../api";

export function Preload({ paths }: { paths: string[] }) {
  return (
    <View style={styles.hidden} pointerEvents="none">
      {paths.map((p) => (
        <Image key={p} source={api.imageSource(p)} style={styles.dot} />
      ))}
    </View>
  );
}

const styles = StyleSheet.create({
  hidden: { position: "absolute", left: 0, top: 0, width: 1, height: 1, opacity: 0, overflow: "hidden" },
  dot: { position: "absolute", width: 1, height: 1 },
});
