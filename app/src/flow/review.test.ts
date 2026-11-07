import keys from "../../../contract/sentence-keys.json";
import { sentenceKey } from "./review";

test("sentence keys match the contract", () => {
  for (const [text, key] of keys as [string, string][]) expect(sentenceKey(text)).toBe(key);
});
