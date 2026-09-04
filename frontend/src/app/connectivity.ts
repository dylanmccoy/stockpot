// Spec §11 O-5: a visible "reconnecting" hint for the store-walk case, with no
// offline machinery (no service worker, no persisted cache). `onlineManager` is
// TanStack Query's own connectivity signal — it already listens for the
// browser's `online`/`offline` events and, under the default `networkMode:
// "online"`, pauses every query's fetch while offline and resumes them the
// moment it flips back. `useIsOffline` just mirrors that signal into a boolean
// a component can render from.

import { useEffect, useState } from "react";
import { onlineManager } from "@tanstack/react-query";

export function useIsOffline(): boolean {
  const [offline, setOffline] = useState(() => !onlineManager.isOnline());

  useEffect(() => {
    return onlineManager.subscribe(() => {
      setOffline(!onlineManager.isOnline());
    });
  }, []);

  return offline;
}
