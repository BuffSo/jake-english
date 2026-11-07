// Two or more tabs side by side on a gray bar; the chosen one stands out in white (spec review-screens 2).
import { Pressable, StyleSheet, Text, View } from "react-native";

import { colors } from "./theme";

type Props<K extends string> = { tabs: { key: K; label: string }[]; current: K; onChange: (key: K) => void };

export function Tabs<K extends string>({ tabs, current, onChange }: Props<K>) {
  return (
    <View style={styles.bar} accessibilityRole="tablist">
      {tabs.map((t) => {
        const on = t.key === current;
        return (
          <Pressable
            key={t.key}
            accessibilityRole="tab"
            accessibilityState={{ selected: on }}
            onPress={() => {
              if (!on) onChange(t.key);
            }}
            style={[styles.tab, on && styles.on]}
          >
            <Text style={[styles.label, on && styles.onLabel]}>{t.label}</Text>
          </Pressable>
        );
      })}
    </View>
  );
}

const styles = StyleSheet.create({
  bar: { flexDirection: "row", backgroundColor: colors.ryan, borderRadius: 12, padding: 3 },
  tab: { flex: 1, alignItems: "center", paddingVertical: 9, borderRadius: 10 },
  on: {
    backgroundColor: colors.bg,
    elevation: 1,
    shadowColor: "#000",
    shadowOpacity: 0.12,
    shadowRadius: 2,
    shadowOffset: { width: 0, height: 1 },
  },
  label: { fontSize: 16, color: colors.sub },
  onLabel: { color: colors.text, fontWeight: "600" },
});
