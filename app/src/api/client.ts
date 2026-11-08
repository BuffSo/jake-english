// Talks to the Mac server. Every request carries the token. Fetch and file reading are passed in so the
// tests need no native modules; src/api/index.ts wires in expo/fetch and expo-file-system.
import { NdjsonSplitter } from "./ndjson";
import type {
  AttemptEvent,
  AttemptMode,
  Home,
  LineWithProgress,
  PastItem,
  PastRun,
  Roleplay,
  Said,
  SavedItem,
  Summary,
  ThreeLine,
} from "./types";

export type ErrorCode = "offline" | "claude_unavailable" | "no_speech" | "too_long" | "not_found" | "unknown";

export class ApiError extends Error {
  constructor(
    public code: ErrorCode,
    public say?: Said,
  ) {
    super(code);
  }
}

type FetchLike = (url: string, init: RequestInit) => Promise<Response>;
type ReadFile = (uri: string) => Promise<Uint8Array>;

const TIMEOUT = 30_000;
const LONG = 120_000; // writing a script and preparing a line can take a while
const KNOWN: ErrorCode[] = ["claude_unavailable", "no_speech", "too_long", "not_found"];

function toCode(status: number, code?: string): ErrorCode {
  if (code && (KNOWN as string[]).includes(code)) return code as ErrorCode;
  if (status === 404) return "not_found";
  if (status === 413) return "too_long";
  if (status === 503) return "claude_unavailable";
  return "unknown";
}

export function makeApi(base: string, token: string, f: FetchLike, readFile: ReadFile) {
  const auth = { Authorization: `Bearer ${token}` };

  async function request(path: string, init: RequestInit = {}, timeout = TIMEOUT): Promise<Response> {
    const ctrl = new AbortController();
    const timer = setTimeout(() => ctrl.abort(), timeout);
    let res: Response;
    try {
      res = await f(base + path, { ...init, headers: { ...(init.headers as object), ...auth }, signal: ctrl.signal });
    } catch {
      throw new ApiError("offline");
    } finally {
      clearTimeout(timer);
    }
    if (!res.ok) {
      let body: { code?: string; say?: Said | null } = {};
      try {
        body = await res.json();
      } catch {
        // not JSON: keep the status only
      }
      throw new ApiError(toCode(res.status, body.code), body.say ?? undefined);
    }
    return res;
  }

  const get = async <T>(path: string, timeout = TIMEOUT) => (await (await request(path, {}, timeout)).json()) as T;
  const post = async <T>(path: string, body?: unknown, timeout = TIMEOUT) =>
    (await (
      await request(
        path,
        { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body ?? {}) },
        timeout,
      )
    ).json()) as T;

  async function upload(path: string, fileUri: string, timeout = TIMEOUT): Promise<Response> {
    const bytes = await readFile(fileUri);
    return request(path, { method: "POST", headers: { "Content-Type": "audio/mp4" }, body: bytes as never }, timeout);
  }

  return {
    // asks for the day's shadowing tip: the Mac counts it said only when asked, so a plain `/home` check leaves it
    // (spec ryan-shadowing-tip 4)
    getHome: () => get<Home>("/home?tip=1"),
    // Jake's suggestion inside the topic (spec situation-topics 4)
    recommend: (skip: string[], topic: string) => post<Said>("/recommend", { skip, topic }),
    transcribe: async (fileUri: string) => ((await (await upload("/transcribe", fileUri)).json()) as { text: string }).text,
    // a described or suggested situation, or a list line by its id: the Mac looks up its description and who starts
    createRoleplay: (choice: { situation: string } | { pick: string }, topic: string) =>
      post<Roleplay>("/roleplays", { ...choice, topic }, LONG),
    getLine: (id: string, idx: number) => get<LineWithProgress>(`/roleplays/${id}/lines/${idx}`, LONG),
    getThree: (id: string, idx: number) => get<ThreeLine>(`/roleplays/${id}/lines/${idx}/three`, LONG),
    // Sohee's interpretation: the text first, then her sound of it (spec korean-translation 4)
    getKo: (id: string, idx: number) => get<{ text: string }>(`/roleplays/${id}/lines/${idx}/ko`),
    getKoAudio: (id: string, idx: number) => get<{ audio: string }>(`/roleplays/${id}/lines/${idx}/ko/audio`),
    summary: (id: string) => get<Summary>(`/roleplays/${id}/summary`),
    copyRoleplay: (id: string) => post<Roleplay>(`/roleplays/${id}/copy`, undefined, LONG),
    // 다시 연습 (spec review-practice): read from the Mac's records, no Claude call
    getRoleplay: (id: string) => get<Roleplay>(`/roleplays/${id}`),
    past: async () => (await get<{ items: PastItem[] }>("/past")).items,
    pastRun: (group: string) => get<PastRun>(`/groups/${group}/latest`),
    saved: async () => (await get<{ items: SavedItem[] }>("/saved")).items,
    setSaved: (rpId: string, idx: number, on: boolean) =>
      post<{ key: string; on: boolean }>("/saved", { rp_id: rpId, idx, on }),

    async attempt(
      id: string,
      idx: number,
      fileUri: string,
      mode: AttemptMode,
      onEvent: (e: AttemptEvent) => void,
    ): Promise<void> {
      const res = await upload(`/roleplays/${id}/lines/${idx}/attempts?mode=${mode}`, fileUri);
      const reader = res.body?.getReader();
      if (!reader) throw new ApiError("unknown");
      const decoder = new TextDecoder();
      const lines = new NdjsonSplitter();
      for (;;) {
        let timer: ReturnType<typeof setTimeout> | undefined;
        const idle = new Promise<never>((_, reject) => {
          timer = setTimeout(() => reject(new ApiError("offline")), TIMEOUT);
        });
        let chunk: ReadableStreamReadResult<Uint8Array>;
        try {
          chunk = await Promise.race([reader.read(), idle]);
        } catch (e) {
          reader.cancel().catch(() => {});
          throw e instanceof ApiError ? e : new ApiError("offline");
        } finally {
          clearTimeout(timer);
        }
        if (chunk.done) break;
        for (const e of lines.push(decoder.decode(chunk.value, { stream: true }))) onEvent(e as AttemptEvent);
      }
      for (const e of lines.flush()) onEvent(e as AttemptEvent);
    },

    audioSource: (key: string, rate: 0.6 | 0.8 | 1 = 1) => ({ uri: `${base}/audio/${key}?rate=${rate}`, headers: auth }),
    imageSource: (path: string) => ({ uri: base + path, headers: auth }),
    // the learner's own recording, streamed for replay and never saved on the phone
    recordingSource: (id: string, idx: number, n: number) => ({
      uri: `${base}/roleplays/${id}/lines/${idx}/attempts/${n}/recording`,
      headers: auth,
    }),
  };
}

export type Api = ReturnType<typeof makeApi>;
