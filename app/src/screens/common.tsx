import { useEffect } from "react";
import { StyleSheet, Text, View } from "react-native";

import { ApiError, type ErrorCode } from "../api/client";
import { OFFLINE } from "../flow/state";
import { Dots, SHOW_AFTER, ThinkingFace, useLate } from "../ui/ThinkingFace";
import { keepWords } from "../ui/keepWords";
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
// With a face, all of it shows only once the wait has lasted SHOW_AFTER, so a short wait shows nothing; the face
// alone coming later would push the text down. Without one the text shows at once, in place of the buttons the tap
// took away. `onShow`: called when it appears (the roleplay screen scrolls to it).
export function Waiting({ text, who, onShow }: { text: string; who?: Who; onShow?: () => void }) {
  const late = useLate(who ? SHOW_AFTER : 0);
  useEffect(() => {
    if (late) onShow?.();
  }, [late]); // eslint-disable-line react-hooks/exhaustive-deps
  if (!late) return null;
  return (
    <View style={styles.wait}>
      {who && <ThinkingFace who={who} size={96} after={0} />}
      <Text style={styles.waitText}>{text}</Text>
      <Dots />
    </View>
  );
}

// Every error on screen, so each goes through `keepWords` (todo 12-2): the Mac's own words (`say.text`) and the
// connection errors are long Korean. The red style is not exported, so an error drawn without this does not compile.
export function ErrorText({ text }: { text: string }) {
  return <Text style={own.error}>{keepWords(text)}</Text>;
}

const own = StyleSheet.create({
  error: { color: colors.danger, fontSize: 16, marginVertical: 8 },
});

export const styles = StyleSheet.create({
  wait: { alignItems: "center", padding: 24 },
  waitText: { marginTop: 12, fontSize: 17, color: colors.sub, textAlign: "center" },
  title: { fontSize: 22, fontWeight: "700", color: colors.text },
  body: { fontSize: 18, color: colors.text, lineHeight: 26 },
  sub: { fontSize: 15, color: colors.sub },
});
