// Saved sentences for every screen (spec review-practice 5): one store for the app, asked once at start and again
// when a review screen opens.
import { createContext, useContext, useEffect, useMemo, useReducer, type ReactNode } from "react";
import { Platform, ToastAndroid } from "react-native";

import { api } from "../api";
import { createSavedStore, type SavedStore } from "../flow/savedStore";

const FAILED = "모아 두지 못했어요. 맥 연결을 확인해 주세요.";
const Saved = createContext<SavedStore | null>(null);

export function SavedProvider({ children }: { children: ReactNode }) {
  const [version, bump] = useReducer((n: number) => n + 1, 0);
  const store = useMemo(
    () =>
      createSavedStore({
        list: api.saved,
        set: api.setSaved,
        onFail: () => {
          if (Platform.OS === "android") ToastAndroid.show(FAILED, ToastAndroid.SHORT);
        },
        changed: bump,
      }),
    [],
  );
  useEffect(() => {
    store.refresh();
  }, [store]);
  // a new object each change, so the screens that read it draw again
  const value = useMemo(() => ({ ...store }), [store, version]); // eslint-disable-line react-hooks/exhaustive-deps
  return <Saved.Provider value={value}>{children}</Saved.Provider>;
}

export function useSaved(): SavedStore {
  const s = useContext(Saved);
  if (!s) throw new Error("useSaved outside SavedProvider");
  return s;
}
