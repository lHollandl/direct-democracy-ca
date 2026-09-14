"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { ApiError, get, post } from "@/lib/api";
import { Notice, PageHeader } from "@/components/ui";
import { useDocumentTitle } from "@/components/useDocumentTitle";

type County = { id: number; name: string };
type City = { id: number; name: string };

const GENDERS = [
  ["woman", "Woman"],
  ["man", "Man"],
  ["nonbinary", "Non-binary"],
  ["other", "Other"],
  ["prefer_not_to_say", "Prefer not to say"],
];

const PARTIES = [
  ["democratic", "Democratic"],
  ["republican", "Republican"],
  ["green", "Green"],
  ["libertarian", "Libertarian"],
  ["american_independent", "American Independent"],
  ["peace_and_freedom", "Peace and Freedom"],
  ["no_party_preference", "No party preference"],
  ["other", "Other"],
  ["prefer_not_to_say", "Prefer not to say"],
];

export default function SignupPage() {
  useDocumentTitle("Join your community");
  const [counties, setCounties] = useState<County[]>([]);
  const [cities, setCities] = useState<City[]>([]);
  const [countyId, setCountyId] = useState("");
  const [termsVersion, setTermsVersion] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [done, setDone] = useState(false);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    void get<County[]>("/geo/counties").then(setCounties).catch(() => setCounties([]));
    void get<{ version: string }>("/legal/current-version")
      .then((v) => setTermsVersion(v.version))
      .catch(() => setTermsVersion(""));
  }, []);

  useEffect(() => {
    if (!countyId) {
      setCities([]);
      return;
    }
    void get<City[]>(`/geo/counties/${countyId}/cities`).then(setCities).catch(() => setCities([]));
  }, [countyId]);

  async function onSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError(null);
    setBusy(true);
    const form = new FormData(event.currentTarget);
    try {
      await post("/auth/signup", {
        email: form.get("email"),
        password: form.get("password"),
        real_name: form.get("real_name"),
        display_name: form.get("display_name"),
        date_of_birth: form.get("date_of_birth"),
        gender: form.get("gender"),
        political_party: form.get("political_party"),
        county_id: Number(form.get("county_id")),
        city_id: Number(form.get("city_id")),
        terms_version: termsVersion,
        agreed_to_terms: form.get("agreed") === "on",
      });
      setDone(true);
    } catch (problem) {
      setError(
        problem instanceof ApiError ? problem.message : "Something went wrong.",
      );
    } finally {
      setBusy(false);
    }
  }

  if (done) {
    return (
      <>
        <PageHeader title="Check your email" />
        <div className="mx-auto max-w-2xl px-4 py-8">
          <Notice kind="good">
            Your account is created. We sent a confirmation link to the address
            you gave. Use it before posting, voting or commenting.
          </Notice>
          <p className="mt-4 text-sm">
            <Link href="/login">Sign in</Link> once you have confirmed.
          </p>
        </div>
      </>
    );
  }

  return (
    <>
      <PageHeader
        title="Join your community"
        lead="One account per person, under your real name. What other people see is up to you — you can show your real name, a display name, or nothing at all."
      />
      <div className="mx-auto max-w-2xl px-4 py-8">
        {error ? <Notice kind="bad">{error}</Notice> : null}
        <form onSubmit={onSubmit} className="mt-4 space-y-4">
          <div>
            <label htmlFor="email" className="block font-medium">Email address</label>
            <input id="email" name="email" type="email" required autoComplete="email" className="field mt-1" />
            <p className="mt-1 text-sm text-[var(--muted)]">
              Used to confirm your account and reset your password. Never shown to anyone.
            </p>
          </div>
          <div>
            <label htmlFor="password" className="block font-medium">Password</label>
            <input id="password" name="password" type="password" required autoComplete="new-password" className="field mt-1" />
            <p className="mt-1 text-sm text-[var(--muted)]">
              At least 8 characters, with a capital letter and a number.
            </p>
          </div>
          <div className="grid gap-4 sm:grid-cols-2">
            <div>
              <label htmlFor="real_name" className="block font-medium">Your real name</label>
              <input id="real_name" name="real_name" required autoComplete="name" className="field mt-1" />
              <p className="mt-1 text-sm text-[var(--muted)]">
                So one person holds one account. Shown only if you choose to show it.
              </p>
            </div>
            <div>
              <label htmlFor="display_name" className="block font-medium">Display name</label>
              <input id="display_name" name="display_name" required className="field mt-1" />
              <p className="mt-1 text-sm text-[var(--muted)]">The name most people will see.</p>
            </div>
          </div>
          <div>
            <label htmlFor="date_of_birth" className="block font-medium">Date of birth</label>
            <input id="date_of_birth" name="date_of_birth" type="date" required className="field mt-1" />
            <p className="mt-1 text-sm text-[var(--muted)]">
              Checked once, to confirm you are old enough. The minimum age is on the{" "}
              <Link href="/settings">settings page</Link>.
            </p>
          </div>
          <div className="grid gap-4 sm:grid-cols-2">
            <div>
              <label htmlFor="county_id" className="block font-medium">County you live in</label>
              <select
                id="county_id"
                name="county_id"
                required
                className="field mt-1"
                value={countyId}
                onChange={(e) => setCountyId(e.target.value)}
              >
                <option value="">Choose a county</option>
                {counties.map((county) => (
                  <option key={county.id} value={county.id}>{county.name}</option>
                ))}
              </select>
            </div>
            <div>
              <label htmlFor="city_id" className="block font-medium">City you live in</label>
              <select id="city_id" name="city_id" required className="field mt-1" disabled={!cities.length}>
                <option value="">
                  {countyId ? "Choose a city" : "Choose a county first"}
                </option>
                {cities.map((city) => (
                  <option key={city.id} value={city.id}>{city.name}</option>
                ))}
              </select>
            </div>
          </div>
          <p className="text-sm text-[var(--muted)]">
            Your city and county decide which three communities you belong to:
            your city, your county, and California. You can read anywhere, and
            post and vote in those three.
          </p>
          <div className="grid gap-4 sm:grid-cols-2">
            <div>
              <label htmlFor="gender" className="block font-medium">Gender</label>
              <select id="gender" name="gender" required defaultValue="prefer_not_to_say" className="field mt-1">
                {GENDERS.map(([value, label]) => (
                  <option key={value} value={value}>{label}</option>
                ))}
              </select>
            </div>
            <div>
              <label htmlFor="political_party" className="block font-medium">Political party</label>
              <select id="political_party" name="political_party" required defaultValue="no_party_preference" className="field mt-1">
                {PARTIES.map(([value, label]) => (
                  <option key={value} value={value}>{label}</option>
                ))}
              </select>
            </div>
          </div>
          <p className="text-sm text-[var(--muted)]">
            Gender and political party are used for public totals only. They
            never change what you see, and they never change what your vote is
            worth.
          </p>
          <div className="rounded-lg border border-[var(--line)] p-3">
            <label htmlFor="agreed" className="flex items-start gap-2">
              <input id="agreed" name="agreed" type="checkbox" required className="mt-1" />
              <span className="text-sm">
                I have read the <Link href="/legal/terms">terms</Link> and the{" "}
                <Link href="/legal/privacy">privacy policy</Link>, and I understand
                that the cryptographic fingerprints of what I post are permanent
                and are never deleted, even if I delete my account.
              </span>
            </label>
          </div>
          <button type="submit" className="btn btn-primary" disabled={busy || !termsVersion}>
            {busy ? "Creating your account…" : "Create my account"}
          </button>
        </form>
      </div>
    </>
  );
}
