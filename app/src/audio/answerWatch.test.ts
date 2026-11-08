import { createAnswerWatch } from "./answerWatch";

// a sound queue that the test drives: `set(p)` is the queue starting or running dry
function fakeQueue(playing = false) {
  const subs = new Set<(p: boolean) => void>();
  return {
    playing,
    subscribe(cb: (p: boolean) => void) {
      subs.add(cb);
      return () => {
        subs.delete(cb);
      };
    },
    isPlaying() {
      return this.playing;
    },
    set(p: boolean) {
      this.playing = p;
      subs.forEach((cb) => cb(p));
    },
  };
}

test("mark while playing turns answering on", () => {
  const q = fakeQueue(true);
  const seen: boolean[] = [];
  const w = createAnswerWatch(q, (a) => seen.push(a));
  w.mark();
  w.mark(); // the next sentence of the same answer
  expect(seen).toEqual([true]);
});

test("clears when the queue stops for any reason", () => {
  // the answer played out, or 「🔊 다시 듣기」 cleared the queue: either way Ryan is no longer speaking
  const q = fakeQueue(true);
  const seen: boolean[] = [];
  const w = createAnswerWatch(q, (a) => seen.push(a));
  w.mark();
  q.set(false);
  expect(seen).toEqual([true, false]);
  q.set(true); // a model sound the learner asked for is not an answer
  expect(seen).toEqual([true, false]);
});

test("mark while nothing plays stays off", () => {
  const q = fakeQueue(false);
  const seen: boolean[] = [];
  createAnswerWatch(q, (a) => seen.push(a)).mark();
  expect(seen).toEqual([]);
});

test("stop unsubscribes", () => {
  const q = fakeQueue(true);
  const seen: boolean[] = [];
  const w = createAnswerWatch(q, (a) => seen.push(a));
  w.mark();
  w.stop();
  q.set(false);
  w.mark();
  expect(seen).toEqual([true]);
});
