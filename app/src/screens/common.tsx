import { StyleSheet, Text, View } from "react-native";

import { ApiError, type ErrorCode } from "../api/client";
import { OFFLINE } from "../flow/state";
import { Dots, ThinkingFace } from "../ui/ThinkingFace";
import { colors } from "../ui/theme";
import type { Who } from "../ui/thinking";

export function codeOf(e: unknown): ErrorCode {
  return e instanceof ApiError ? e.code : "unknown";
}

export function messageOf(e: unknown): string {
  if (e instanceof ApiError && e.say?.text) return e.say.text;
  if (codeOf(e) === "offline") return OFFLINE;
  if (codeOf(e) === "claude_unavailable") return "지금은 라이언이 대답할 수 없어요. 맥의 인터넷 연결을 확인해 주세요.";
  return "문제가 생겼어요. 다시 해 볼까요?";
}

// The thinking face of `who` (no face when left out, as on the situation screen, whose big circle at the top
// thinks instead), the waiting text and three blinking dots. It replaced the spinner (2026-11-06 user).
export function Waiting({ text, who }: { text: string; who?: Who }) {
  return (
    <View style={styles.wait}>
      {who && <ThinkingFace who={who} size={96} />}
      <Text style={styles.waitText}>{text}</Text>
      <Dots />
    </View>
  );
}

export const styles = StyleSheet.create({
  wait: { alignItems: "center", padding: 24 },
  waitText: { marginTop: 12, fontSize: 17, color: colors.sub, textAlign: "center" },
  error: { color: colors.danger, fontSize: 16, marginVertical: 8 },
  title: { fontSize: 22, fontWeight: "700", color: colors.text },
  body: { fontSize: 18, color: colors.text, lineHeight: 26 },
  sub: { fontSize: 15, color: colors.sub },
});
