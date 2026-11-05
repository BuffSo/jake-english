// Server address and token come from app/.env at build time (git ignores it; ADR-0007).
export const SERVER_URL = (process.env.EXPO_PUBLIC_SERVER_URL ?? "").replace(/\/+$/, "");
export const SERVER_TOKEN = process.env.EXPO_PUBLIC_SERVER_TOKEN ?? "";
export const CONFIGURED = SERVER_URL !== "" && SERVER_TOKEN.length >= 32;
