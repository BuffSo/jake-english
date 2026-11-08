import { RECORD_LIMIT_MS, SERVER_RECORD_LIMIT_MS, SOON_ENDS_MS } from "./config";

test("the phone stops recording well before the server's limit", () => {
  // PR #12 review: stopping at exactly 60s made files a little over 60s, which the server rejects
  expect(RECORD_LIMIT_MS).toBeLessThanOrEqual(SERVER_RECORD_LIMIT_MS - 3000);
});

test("「녹음이 곧 끝나요」 shows a few seconds before the phone stops", () => {
  expect(SOON_ENDS_MS).toBe(50_000);
  expect(SOON_ENDS_MS).toBeLessThan(RECORD_LIMIT_MS);
});
