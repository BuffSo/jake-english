import { RECORD_LIMIT_MS, SERVER_RECORD_LIMIT_MS } from "./config";

test("the phone stops recording well before the server's limit", () => {
  // PR #12 review: stopping at exactly 60s made files a little over 60s, which the server rejects
  expect(RECORD_LIMIT_MS).toBeLessThanOrEqual(SERVER_RECORD_LIMIT_MS - 3000);
});
