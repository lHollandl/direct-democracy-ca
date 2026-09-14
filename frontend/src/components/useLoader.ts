"use client";

import { useCallback, useEffect, useState } from "react";

/**
 * Fetch something when the page opens, and again whenever it is asked to.
 *
 * State is set from the promise's callback, never synchronously inside the
 * effect, and a result that arrives after the reader has left the page is
 * dropped rather than written into a component that is no longer there.
 */
export function useLoader<T>(
  fetcher: () => Promise<T>,
  deps: unknown[],
): { data: T | null; failed: boolean; reload: () => void } {
  const [data, setData] = useState<T | null>(null);
  const [failed, setFailed] = useState(false);
  const [nonce, setNonce] = useState(0);

  // eslint-disable-next-line react-hooks/exhaustive-deps
  const run = useCallback(fetcher, deps);

  useEffect(() => {
    let live = true;
    run().then(
      (value) => {
        if (live) {
          setData(value);
          setFailed(false);
        }
      },
      () => {
        if (live) setFailed(true);
      },
    );
    return () => {
      live = false;
    };
  }, [run, nonce]);

  const reload = useCallback(() => setNonce((n) => n + 1), []);
  return { data, failed, reload };
}
