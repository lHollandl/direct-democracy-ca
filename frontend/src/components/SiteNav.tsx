"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useSession } from "@/components/Session";

const LINKS = [
  { href: "/feed", label: "Feed" },
  { href: "/posts/new", label: "Post a problem" },
  { href: "/ballot", label: "Ballot" },
  { href: "/jury", label: "Jury" },
  { href: "/results", label: "Results" },
];

export default function SiteNav() {
  const { me, signOut } = useSession();
  const pathname = usePathname();

  return (
    <nav
      aria-label="Main"
      className="border-b border-[var(--line)] bg-[var(--surface)]"
    >
      <div className="mx-auto flex max-w-4xl flex-wrap items-center gap-x-4 gap-y-2 px-4 py-3">
        <Link href="/" className="font-bold text-[var(--foreground)] no-underline">
          Direct Democracy Cali
        </Link>
        <ul className="flex flex-wrap items-center gap-x-4 gap-y-1 text-sm">
          {LINKS.map((link) => (
            <li key={link.href}>
              <Link
                href={link.href}
                aria-current={pathname === link.href ? "page" : undefined}
                className={pathname === link.href ? "font-semibold" : ""}
              >
                {link.label}
              </Link>
            </li>
          ))}
          {me?.is_admin ? (
            <li>
              <Link href="/admin" className={pathname === "/admin" ? "font-semibold" : ""}>
                Admin
              </Link>
            </li>
          ) : null}
        </ul>
        <div className="ml-auto flex items-center gap-3 text-sm">
          {me ? (
            <>
              <Link href="/me">{me.display_name}</Link>
              <button type="button" className="btn px-3 py-1" onClick={() => void signOut()}>
                Sign out
              </button>
            </>
          ) : (
            <>
              <Link href="/login">Sign in</Link>
              <Link href="/signup" className="btn btn-primary px-3 py-1 no-underline">
                Join
              </Link>
            </>
          )}
        </div>
      </div>
      {me && !me.email_verified ? (
        <p className="bg-[var(--accent-soft)] px-4 py-2 text-center text-sm">
          Confirm your email address before posting, voting or commenting. The
          link is in the message we sent when you signed up.
        </p>
      ) : null}
    </nav>
  );
}
