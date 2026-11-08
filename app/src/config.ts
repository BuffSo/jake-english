// Server address and token come from app/.env at build time (git ignores it; ADR-0007).
export const SERVER_URL = (process.env.EXPO_PUBLIC_SERVER_URL ?? "").replace(/\/+$/, "");
export const SERVER_TOKEN = process.env.EXPO_PUBLIC_SERVER_TOKEN ?? "";
export const CONFIGURED = SERVER_URL !== "" && SERVER_TOKEN.length >= 32;

// The server refuses recordings over 60s. Stopping at exactly 60s produced files a little over it (PR #12
// review), so the phone stops a few seconds earlier.
export const SERVER_RECORD_LIMIT_MS = 60_000;
export const RECORD_LIMIT_MS = 55_000;
// 「녹음이 곧 끝나요」 from here until the phone stops (spec record-feedback 2)
export const SOON_ENDS_MS = 50_000;
