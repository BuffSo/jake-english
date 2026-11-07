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

  // A sentence taken out leaves the list at once: if the list then cannot be loaded again, a row still showing it
  // would take its ★ for 「모아 두기」 (todo 12-1).
  async function change(rpId: string, idx: number, text: string, on: boolean): Promise<void> {
    const key = sentenceKey(text);
    busy.add(key);
    deps.changed();
    try {
      await deps.set(rpId, idx, on);
      keys = new Set(keys);
      if (on) keys.add(key);
      else {
        keys.delete(key);
        items = items?.filter((i) => i.key !== key) ?? null;
      }
      await refresh();
    } catch {
      deps.onFail();
    } finally {
      busy.delete(key);
      deps.changed();
    }
  }

  // ☆/★ on a line: whatever it is now, the other way
  async function toggle(rpId: string, idx: number, text: string): Promise<void> {
    if (busy.has(sentenceKey(text))) return;
    await change(rpId, idx, text, !keys.has(sentenceKey(text)));
  }

  // 「빼기」 in the saved list, which asked 「목록에서 뺄까요?」: only ever out, even if this store thinks it is out already
  async function remove(rpId: string, idx: number, text: string): Promise<void> {
    if (busy.has(sentenceKey(text))) return;
    await change(rpId, idx, text, false);
  }

  return {
    items: () => items,
    lastError: () => error,
    has: (text: string) => keys.has(sentenceKey(text)),
    pending: (text: string) => busy.has(sentenceKey(text)),
    refresh,
    toggle,
    remove,
  };
}
