// A small text button inside a tappable row or bubble. It never disables its Pressable: a disabled Pressable hands
// the tap to the row around it (the same as `PractiseLink`, final review of review-practice). While it cannot be
// used it only dims, and what it calls ignores the tap.
import { Pressable, Text, type StyleProp, type TextStyle } from "react-native";

type Props = { label: string; onPress: () => void; dim?: boolean; textStyle?: StyleProp<TextStyle> };

export function InRowButton({ label, onPress, dim, textStyle }: Props) {
  return (
    <Pressable onPress={onPress} hitSlop={8} accessibilityRole="button">
      <Text style={[textStyle, dim && { opacity: 0.4 }]}>{label}</Text>
    </Pressable>
  );
}
