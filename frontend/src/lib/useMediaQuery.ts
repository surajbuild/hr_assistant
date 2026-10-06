import { useSyncExternalStore } from "react";

/** Subscribes to a CSS media query: const wide = useMediaQuery("(min-width: 1280px)"). */
export function useMediaQuery(query: string): boolean {
  return useSyncExternalStore(
    (cb) => {
      const mq = window.matchMedia(query);
      mq.addEventListener("change", cb);
      return () => mq.removeEventListener("change", cb);
    },
    () => window.matchMedia(query).matches,
    () => false,
  );
}
