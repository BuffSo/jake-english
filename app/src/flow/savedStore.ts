// Saved sentences as the app knows them (spec review-practice 5, 6): the list from the Mac and which sentences are
// saved, by sentence key. Kept free of React so it can be tested; `ui/useSaved.tsx` wires it to the screens.
import type { SavedItem } from "../api/types";
import { sentenceKey } from "./review";

type Deps = {
  list: () => Promise<SavedItem[]>;
  set: (rpId: string, idx: number, on: boolean) => Promise<unknown>;
  onFail: () => void; // the Mac did not take the change: say so, and show it as it was
  changed: () => void; // something on screen may have changed
};

export type SavedStore = ReturnType<typeof createSavedStore>;

export function createSavedStore(deps: Deps) {
  let items: SavedItem[] | null = null;
  let keys = new Set<string>();
  let error: unknown = null; // why the last list could not be loaded, shown when there is no list yet
  const busy = new Set<string>(); // sentences whose change is on its way: a second tap waits (double taps)

  async function refresh(): Promise<void> {
    try {
      items = await deps.list();
      keys = new Set(items.map((i) => i.key));
      error = null;
    } catch (e) {
      error = e; // keep what was shown; the next screen that opens asks again
    }
    deps.changed();
  }

  async function toggle(rpId: string, idx: number, text: string): Promise<void> {
    const key = sentenceKey(text);
    if (busy.has(key)) return;
    const on = !keys.has(key);
    busy.add(key);
    deps.changed();
    try {
      await deps.set(rpId, idx, on);
      keys = new Set(keys);
      if (on) keys.add(key);
      else keys.delete(key);
      await refresh();
    } catch {
      deps.onFail();
    } finally {
      busy.delete(key);
      deps.changed();
    }
  }

  return {
    items: () => items,
    lastError: () => error,
    has: (text: string) => keys.has(sentenceKey(text)),
    pending: (text: string) => busy.has(sentenceKey(text)),
    refresh,
    toggle,
  };
}
