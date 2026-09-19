"use client";

/** Who is signed in, for the whole app. The token itself stays in api.ts. */

import { createContext, useContext, useEffect, useState } from "react";
import { get, onAuthChange, restoreSession, signOut as apiSignOut } from "@/lib/api";

export type Me = {
  id: number;
  email: string;
  real_name: string;
  display_name: string;
  public_name_mode: string;
  verification_level: string;
  verification_explanation: string;
  email_verified: boolean;
  is_admin: boolean;
  home_communities: { level: string; entity_id: number; name: string; label: string }[];
};

type SessionValue = {
  me: Me | null;
  loading: boolean;
  reload: () => Promise<void>;
  signOut: () => Promise<void>;
};

const SessionContext = createContext<SessionValue>({
  me: null,
  loading: true,
  reload: async () => {},
  signOut: async () => {},
});

export function SessionProvider({ children }: { children: React.ReactNode }) {
  const [me, setMe] = useState<Me | null>(null);
  const [loading, setLoading] = useState(true);

  const reload = async () => {
    try {
      setMe(await get<Me>("/auth/me"));
    } catch {
      setMe(null);
    }
  };

  useEffect(() => {
    let cancelled = false;
    (async () => {
      await restoreSession();
      if (!cancelled) {
        await reload();
        setLoading(false);
      }
    })();
    const stop = onAuthChange(() => {
      void reload();
    });
    return () => {
      cancelled = true;
      stop();
    };
  }, []);

  const signOut = async () => {
    await apiSignOut();
    setMe(null);
  };

  return (
    <SessionContext.Provider value={{ me, loading, reload, signOut }}>
      {children}
    </SessionContext.Provider>
  );
}

export function useSession() {
  return useContext(SessionContext);
}
