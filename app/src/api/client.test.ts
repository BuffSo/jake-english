import { ApiError, makeApi } from "./client";

const URL = "http://mac.test:8787";
const TOKEN = "t".repeat(32);

function json(status: number, body: unknown) {
  return { ok: status < 400, status, json: async () => body } as unknown as Response;
}

function streamOf(chunks: string[]) {
  const enc = new TextEncoder();
  let i = 0;
  return {
    ok: true,
    status: 200,
    body: {
      getReader: () => ({
        read: async () => (i < chunks.length ? { done: false, value: enc.encode(chunks[i++]) } : { done: true, value: undefined }),
        cancel: async () => {},
      }),
    },
  } as unknown as Response;
}

const noFile = async () => new Uint8Array([1, 2, 3]);

test("sends bearer token", async () => {
  const f = jest.fn(async () => json(200, { lines: {}, images: {} }));
  await makeApi(URL, TOKEN, f as never, noFile).getHome();
  const [url, init] = f.mock.calls[0] as unknown as [string, RequestInit];
  expect(url).toBe(`${URL}/home`);
  expect((init.headers as Record<string, string>).Authorization).toBe(`Bearer ${TOKEN}`);
});

test("503 becomes claude_unavailable with say", async () => {
  const say = { text: "지금은 대답할 수 없어요.", audio: "a".repeat(64) };
  const f = jest.fn(async () => json(503, { code: "claude_unavailable", say }));
  const err = await makeApi(URL, TOKEN, f as never, noFile).createRoleplay("길 묻기").catch((e) => e);
  expect(err).toBeInstanceOf(ApiError);
  expect(err.code).toBe("claude_unavailable");
  expect(err.say).toEqual(say);
});

test("network failure becomes offline", async () => {
  const f = jest.fn(async () => {
    throw new TypeError("Network request failed");
  });
  const err = await makeApi(URL, TOKEN, f as never, noFile).getHome().catch((e) => e);
  expect(err.code).toBe("offline");
});

test("timeout becomes offline", async () => {
  jest.useFakeTimers();
  const f = jest.fn(
    (_url: string, init: RequestInit) =>
      new Promise<Response>((_, reject) => init.signal?.addEventListener("abort", () => reject(new Error("aborted")))),
  );
  const p = makeApi(URL, TOKEN, f as never, noFile).getHome().catch((e) => e);
  jest.advanceTimersByTime(30_000);
  expect((await p).code).toBe("offline");
  jest.useRealTimers();
});

test("audioSource adds rate and token header", () => {
  const api = makeApi(URL, TOKEN, jest.fn() as never, noFile);
  expect(api.audioSource("a".repeat(64), 0.8)).toEqual({
    uri: `${URL}/audio/${"a".repeat(64)}?rate=0.8`,
    headers: { Authorization: `Bearer ${TOKEN}` },
  });
  expect(api.audioSource("a".repeat(64)).uri).toBe(`${URL}/audio/${"a".repeat(64)}?rate=1`);
});

test("attempt uploads bytes and passes events in order", async () => {
  const f = jest.fn(async () =>
    streamOf(['{"type":"heard","text":"hi","followed":true}\n{"type":"te', 'xt","delta":"좋아요."}\n', '{"type":"done","next":2,"issues":0}\n']),
  );
  const events: unknown[] = [];
  await makeApi(URL, TOKEN, f as never, noFile).attempt("0123456789ab", 1, "file:///rec.m4a", "turn", (e) => events.push(e));
  const [url, init] = f.mock.calls[0] as unknown as [string, RequestInit];
  expect(url).toBe(`${URL}/roleplays/0123456789ab/lines/1/attempts?mode=turn`);
  expect(init.method).toBe("POST");
  expect((init.headers as Record<string, string>)["Content-Type"]).toBe("audio/mp4");
  expect(events.map((e) => (e as { type: string }).type)).toEqual(["heard", "text", "done"]);
});
