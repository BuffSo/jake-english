// What was heard, one line until opened (`heardView`). Inside a bubble or row that opens on a tap it takes no tap of
// its own: it opens with that bubble, so one bubble never has two places that open different things, and a short
// line never swallows a tap meant for the bubble (spec heard-line-collapsed 2). Given `onPress`, it is a tap of its
// own: what was just heard, under the line to say, has no bubble around it.
import { Pressable, Text, type StyleProp, type TextStyle, type ViewStyle } from "react-native";

import { heardView } from "./heardView";

type Props = { text: string; open: boolean; style?: StyleProp<TextStyle>; onPress?: () => void; wrapStyle?: StyleProp<ViewStyle> };

export function HeardLine({ text, open, style, onPress, wrapStyle }: Props) {
  const v = heardView(text, open);
  const line = (
    <Text style={style} numberOfLines={v.lines} ellipsizeMode="tail">
      {v.text}
    </Text>
  );
  if (!onPress) return line;
  return (
    <Pressable onPress={onPress} hitSlop={8} style={wrapStyle} accessibilityRole="button" accessibilityState={{ expanded: open }}>
      {line}
    </Pressable>
  );
}
