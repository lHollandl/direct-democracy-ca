"use client";

/** Who is signed in, for the whole app. The token itself stays in api.ts. */

import { usePathname, useRouter } from "next/navigation";
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

export type RequireAuthResult =
  | { status: "loading"; me: null }
  | { status: "redirecting"; me: null }
  | { status: "expired"; me: null }
  | { status: "authed"; me: Me };

/**
 * A page that needs a session sends the visitor to `/login?next=<path>`
 * (ARCHITECTURE.md §9). A visitor who was signed in and whose session ends
 * while the page is open sees "expired" instead of a silent redirect, so the
 * page can say "You have been signed out. Sign in again." rather than ever
 * showing a signed-in page to a signed-out visitor.
 */
export function useRequireAuth(): RequireAuthResult {
  const { me, loading } = useSession();
  const router = useRouter();
  const pathname = usePathname();
  const [everAuthed, setEverAuthed] = useState(false);

  useEffect(() => {
    if (me) setEverAuthed(true);
  }, [me]);

  useEffect(() => {
    if (!loading && !me && !everAuthed) {
      router.replace(`/login?next=${encodeURIComponent(pathname)}`);
    }
  }, [loading, me, everAuthed, pathname, router]);

  if (loading) return { status: "loading", me: null };
  if (me) return { status: "authed", me };
  if (everAuthed) return { status: "expired", me: null };
  return { status: "redirecting", me: null };
}
