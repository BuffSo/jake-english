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
  expect(url).toBe(`${URL}/home?tip=1`); // asks for the day's shadowing tip (spec ryan-shadowing-tip 4)
  expect((init.headers as Record<string, string>).Authorization).toBe(`Bearer ${TOKEN}`);
});

test("503 becomes claude_unavailable with say", async () => {
  const say = { text: "지금은 대답할 수 없어요.", audio: "a".repeat(64) };
  const f = jest.fn(async () => json(503, { code: "claude_unavailable", say }));
  const err = await makeApi(URL, TOKEN, f as never, noFile).createRoleplay({ situation: "길 묻기" }, "other").catch((e) => e);
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

test("copy posts to the roleplay's copy route", async () => {
  const f = jest.fn(async () => json(200, { id: "b".repeat(12) }));
  await makeApi(URL, TOKEN, f as never, noFile).copyRoleplay("a".repeat(12));
  const [url, init] = f.mock.calls[0] as unknown as [string, RequestInit];
  expect(url).toBe(`${URL}/roleplays/${"a".repeat(12)}/copy`);
  expect(init.method).toBe("POST");
});

test("recording source carries the token and the attempt number", () => {
  const src = makeApi(URL, TOKEN, jest.fn() as never, noFile).recordingSource("a".repeat(12), 3, 2);
  expect(src).toEqual({
    uri: `${URL}/roleplays/${"a".repeat(12)}/lines/3/attempts/2/recording`,
    headers: { Authorization: `Bearer ${TOKEN}` },
  });
});

test("attempt sends the shadow mode", async () => {
  const f = jest.fn(async () => streamOf(['{"type":"done","next":0,"issues":0}\n']));
  await makeApi(URL, TOKEN, f as never, noFile).attempt("a".repeat(12), 0, "file://x.m4a", "shadow", () => {});
  expect((f.mock.calls[0] as unknown as [string])[0]).toBe(`${URL}/roleplays/${"a".repeat(12)}/lines/0/attempts?mode=shadow`);
});

test("recommend sends the situations turned down on the screen", async () => {
  const f = jest.fn(async () => json(200, { text: "호텔에서 체크인하는 상황으로 연습해 보면 어때요?", audio: "a".repeat(64) }));
  await makeApi(URL, TOKEN, f as never, noFile).recommend(["카페에서 주문하는 상황으로 연습해 보면 어때요?"], "usa");
  const [url, init] = f.mock.calls[0] as unknown as [string, RequestInit];
  expect(url).toBe(`${URL}/recommend`);
  // Jake suggests inside the topic the learner picked (spec situation-topics 4)
  expect(JSON.parse(init.body as string)).toEqual({ skip: ["카페에서 주문하는 상황으로 연습해 보면 어때요?"], topic: "usa" });
});

test("a list pick goes by its id, not its text", async () => {
  // the Mac looks up the list line's description and who speaks first (spec situation-topics, builder notes)
  const f = jest.fn(async () => json(200, {}));
  await makeApi(URL, TOKEN, f as never, noFile).createRoleplay({ pick: "u-hotel-checkin" }, "usa");
  const [url, init] = f.mock.calls[0] as unknown as [string, RequestInit];
  expect(url).toBe(`${URL}/roleplays`);
  expect(JSON.parse(init.body as string)).toEqual({ pick: "u-hotel-checkin", topic: "usa" });
});

test("Sohee's interpretation: the text, then its sound", async () => {
  const f = jest.fn(async (url: string) => json(200, url.endsWith("/audio") ? { audio: "c".repeat(64) } : { text: "뭐 드릴까요?" }));
  const api = makeApi(URL, TOKEN, f as never, noFile);
  expect(await api.getKo("abcdef012345", 2)).toEqual({ text: "뭐 드릴까요?" });
  expect(await api.getKoAudio("abcdef012345", 2)).toEqual({ audio: "c".repeat(64) });
  const urls = f.mock.calls.map((c) => (c as unknown as [string])[0]);
  expect(urls).toEqual([`${URL}/roleplays/abcdef012345/lines/2/ko`, `${URL}/roleplays/abcdef012345/lines/2/ko/audio`]);
});

describe("다시 연습 calls", () => {
  const call = (f: jest.Mock, i = 0) => f.mock.calls[i] as unknown as [string, RequestInit];

  test("getRoleplay, pastRun and the lists ask the right paths", async () => {
    const f = jest.fn(async () => json(200, { items: [{ group: "a1b2c3d4e5f6" }] }));
    const api = makeApi(URL, TOKEN, f as never, noFile);
    await api.getRoleplay("a1b2c3d4e5f6");
    await api.pastRun("a1b2c3d4e5f6");
    expect(await api.past()).toEqual([{ group: "a1b2c3d4e5f6" }]);
    expect(await api.saved()).toEqual([{ group: "a1b2c3d4e5f6" }]);
    expect(f.mock.calls.map((c) => (c as unknown as [string])[0])).toEqual([
      `${URL}/roleplays/a1b2c3d4e5f6`,
      `${URL}/groups/a1b2c3d4e5f6/latest`,
      `${URL}/past`,
      `${URL}/saved`,
    ]);
  });

  test("setSaved posts the line and whether it is on", async () => {
    const f = jest.fn(async () => json(200, { key: "sure", on: true }));
    expect(await makeApi(URL, TOKEN, f as never, noFile).setSaved("a1b2c3d4e5f6", 2, true)).toEqual({ key: "sure", on: true });
    const [url, init] = call(f);
    expect(url).toBe(`${URL}/saved`);
    expect(init.method).toBe("POST");
    expect(JSON.parse(init.body as string)).toEqual({ rp_id: "a1b2c3d4e5f6", idx: 2, on: true });
  });
});

test("talkTurn posts the recording with how much of Ryan was heard", async () => {
  const f = jest.fn(async () =>
    streamOf(['{"type":"heard","text":"hi","n":1,"idx":1,"korean":false}\n{"type":"text","delta":"Nice"}\n', '{"type":"done","idx":2}\n']),
  );
  const events: unknown[] = [];
  await makeApi(URL, TOKEN, f as never, noFile).talkTurn("x", "file:///rec.m4a", 1, (e) => events.push(e));
  const [url, init] = f.mock.calls[0] as unknown as [string, RequestInit];
  expect(url).toBe(`${URL}/talks/x/turns?heard=1`);
  expect(init.method).toBe("POST");
  expect((init.headers as Record<string, string>)["Content-Type"]).toBe("audio/mp4");
  expect(events.map((e) => (e as { type: string }).type)).toEqual(["heard", "text", "done"]);
});

test("talkTurn without a cut has no query", async () => {
  const f = jest.fn(async () => streamOf([]));
  await makeApi(URL, TOKEN, f as never, noFile).talkTurn("x", "file:///rec.m4a", null, () => {});
  expect((f.mock.calls[0] as unknown as [string])[0]).toBe(`${URL}/talks/x/turns`);
});

test("endTalk posts and reads the fixes", async () => {
  const end = { items: [], say: null };
  const f = jest.fn(async () => json(200, end));
  expect(await makeApi(URL, TOKEN, f as never, noFile).endTalk("x", null)).toEqual(end);
  const [url, init] = f.mock.calls[0] as unknown as [string, RequestInit];
  expect(url).toBe(`${URL}/talks/x/end`);
  expect(init.method).toBe("POST");
  await makeApi(URL, TOKEN, f as never, noFile).endTalk("x", 2);
  expect((f.mock.calls[1] as unknown as [string])[0]).toBe(`${URL}/talks/x/end?heard=2`);
});

test("createTalk posts", async () => {
  const f = jest.fn(async () => json(200, { id: "x" }));
  expect(await makeApi(URL, TOKEN, f as never, noFile).createTalk()).toEqual({ id: "x" });
  const [url, init] = f.mock.calls[0] as unknown as [string, RequestInit];
  expect(url).toBe(`${URL}/talks`);
  expect(init.method).toBe("POST");
});

test("createTalk on an old server (404) rejects as not_found", async () => {
  const f = jest.fn(async () => json(404, {}));
  const err = await makeApi(URL, TOKEN, f as never, noFile).createTalk().catch((e) => e);
  expect(err).toBeInstanceOf(ApiError);
  expect(err.code).toBe("not_found");
});

test("endTalk surfaces a 409 and a 503", async () => {
  const busy = await makeApi(URL, TOKEN, (async () => json(409, {})) as never, noFile).endTalk("x", null).catch((e) => e);
  expect(busy).toBeInstanceOf(ApiError);
  expect(busy.code).toBe("unknown");
  const down = await makeApi(URL, TOKEN, (async () => json(503, { code: "claude_unavailable" })) as never, noFile)
    .endTalk("x", null)
    .catch((e) => e);
  expect(down.code).toBe("claude_unavailable");
});
