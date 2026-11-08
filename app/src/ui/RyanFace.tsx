// Ryan's pictures are tall portraits with room above the head. `resizeMode="cover"` crops around the centre, and
// on the phone it cut off the top of his head (2026-11-05, user). So each picture is drawn at its own ratio inside
// a clipping box and placed by hand: from the top for the portrait, on the face for the circle. Jake's front
// picture has the same size and goes in the same circle (2026-11-06).
import { Image, StyleSheet, View, type ImageSourcePropType, type StyleProp, type ViewStyle } from "react-native";

import { FACE_BOX, type Face } from "./faces";
import { colors } from "./theme";

const W = 572; // the pictures' size in pixels (private assets folder, served by the Mac)
const H = 1024;

type Source = ImageSourcePropType;

// From the top of the head to the chest, as wide as the screen allows. `style`: the screen's own place for it, such
// as a margin, or letting it shrink (the first screen).
export function RyanPortrait({ source, style }: { source: Source; style?: StyleProp<ViewStyle> }) {
  return (
    <View style={[styles.portrait, style]}>
      <Image source={source} style={styles.fullWidth} />
    </View>
  );
}

// A circle filled by the face of `face`'s picture. `onError`: the picture could not be loaded.
type CircleProps = { source: Source; size: number; face: Face; onError?: () => void };
export function FaceCircle({ source, size, face, onError }: CircleProps) {
  const box = FACE_BOX[face];
  const scale = size / box.size;
  return (
    <View style={[styles.circle, { width: size, height: size, borderRadius: size / 2 }]}>
      <Image
        source={source}
        onError={onError}
        style={{ position: "absolute", width: W * scale, height: H * scale, left: -box.x * scale, top: -box.y * scale }}
      />
    </View>
  );
}

const styles = StyleSheet.create({
  portrait: { width: "100%", aspectRatio: 4 / 5, borderRadius: 20, overflow: "hidden", backgroundColor: colors.ryan },
  fullWidth: { width: "100%", aspectRatio: W / H },
  circle: { alignSelf: "center", overflow: "hidden", backgroundColor: colors.ryan },
});
