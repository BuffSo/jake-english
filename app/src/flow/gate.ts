// Lets one async action run at a time; calls that arrive while it runs are ignored (double taps, the 60s
// auto-stop landing on a tap). PR #12 review.
export function createGate() {
  let busy = false;
  return {
    get busy() {
      return busy;
    },
    async run<T>(fn: () => Promise<T>): Promise<T | undefined> {
      if (busy) return undefined;
      busy = true;
      try {
        return await fn();
      } finally {
        busy = false;
      }
    },
  };
}
