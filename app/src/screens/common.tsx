import { ActivityIndicator, StyleSheet, Text, View } from "react-native";

import { ApiError, type ErrorCode } from "../api/client";
import { OFFLINE } from "../flow/state";
import { colors } from "../ui/theme";

export function codeOf(e: unknown): ErrorCode {
  return e instanceof ApiError ? e.code : "unknown";
}

export function messageOf(e: unknown): string {
  if (e instanceof ApiError && e.say?.text) return e.say.text;
  if (codeOf(e) === "offline") return OFFLINE;
  if (codeOf(e) === "claude_unavailable") return "지금은 라이언이 대답할 수 없어요. 맥의 인터넷 연결을 확인해 주세요.";
  return "문제가 생겼어요. 다시 해 볼까요?";
}

export function Waiting({ text }: { text: string }) {
  return (
    <View style={styles.wait}>
      <ActivityIndicator size="large" color={colors.primary} />
      <Text style={styles.waitText}>{text}</Text>
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
