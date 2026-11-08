// A picture from the Mac that may not load: spec free-talk-design 9 「그림」 says a picture not received shows the
// words alone, but an Image that fails keeps its place, so Sohee's face was an empty green ring (final review). Like
// `FaceCircle`'s `onError` (ui/RyanFace.tsx), the failure is kept and the picture is left out after it. The failed
// path is kept rather than a flag: her bubble draws the face and then the whisper face in the same place.
import { useState } from "react";

export const pictureShown = (path: string | undefined, failed: string | null): string | undefined =>
  path && path !== failed ? path : undefined;

// [the picture to draw, or undefined to draw none; the Image's onError]
export function usePicture(path: string | undefined): [string | undefined, () => void] {
  const [failed, setFailed] = useState<string | null>(null);
  return [pictureShown(path, failed), () => setFailed(path ?? null)];
}
