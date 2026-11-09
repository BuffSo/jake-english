import { pictureShown } from "./picture";

// spec free-talk-design 9 「그림」: a picture not received shows the words alone, not an empty ring (final review T8 m2)
test("a picture shows until it fails to load", () => {
  expect(pictureShown("sohee-face.png", null)).toBe("sohee-face.png");
  expect(pictureShown("sohee-face.png", "sohee-face.png")).toBeUndefined();
  expect(pictureShown(undefined, null)).toBeUndefined(); // a server from before the pictures
});

test("another picture in the same place is tried on its own", () => {
  // her bubble turns from the face to the whisper face in the same place
  expect(pictureShown("sohee-whisper.png", "sohee-face.png")).toBe("sohee-whisper.png");
});
