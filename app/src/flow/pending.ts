// What the roleplay screen sent and left running when the learner went back: an evaluation and a skip move the
// conversation's place on the Mac, and the evaluation records the line and moves the place only when it has finished,
// a few seconds later. The situation screen asks where to resume after them, or it would offer the line just said
// again (spec docs/superpowers/specs/2026-11-08-resume-roleplay-design.md 4, found by the builder check; a line counts
// as recorded once that try is kept, spec 2026-11-08-resume-unrecorded-design.md 1).

// as long as a request may run before the app gives it up (`TIMEOUT` in api/client.ts)
export const RESUME_WAIT_MS = 30_000;

export function createPending() {
  const running = new Set<Promise<unknown>>();
  return {
    // `p` itself, failures included, for the caller; counted until it settles either way
    track<T>(p: Promise<T>): Promise<T> {
      const counted = p.then(
        () => undefined,
        () => undefined,
      );
      running.add(counted);
      counted.finally(() => running.delete(counted));
      return p;
    },
    // what was running when asked has settled, or `maxMs` went by
    settled(maxMs: number): Promise<void> {
      if (running.size === 0) return Promise.resolve();
      let timer: ReturnType<typeof setTimeout> | undefined;
      const giveUp = new Promise<void>((r) => (timer = setTimeout(r, maxMs)));
      return Promise.race([Promise.all([...running]).then(() => undefined), giveUp]).finally(() => clearTimeout(timer));
    },
  };
}

// `ask` once what was running has settled, or `maxMs` went by: where to resume is asked after the evaluation the
// learner left, so the line just said is not offered again. Not asked (null) when `wanted` says the answer is no
// longer wanted by then: the screen that waited is gone (todo 20261108_32 3).
export function askAfter<T>(
  p: Pick<Pending, "settled">,
  ask: () => Promise<T>,
  wanted: () => boolean = () => true,
  maxMs = RESUME_WAIT_MS,
): Promise<T | null> {
  return p.settled(maxMs).then(() => (wanted() ? ask() : null));
}

type Pending = ReturnType<typeof createPending>;

// one for the app: the roleplay screen tracks, the situation screen waits
export const pending = createPending();
