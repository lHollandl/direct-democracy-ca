"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useRef, useState, type ReactNode } from "react";
import { apiBase, del, get, patch, post } from "@/lib/api";
import { useSession } from "@/components/Session";
import { Loading, Notice, PageHeader, Section } from "@/components/ui";
import { FieldError, useFormError } from "@/components/useFormError";
import { useDocumentTitle } from "@/components/useDocumentTitle";

const MODES = [
  ["display_name", "My display name", "Most people show this."],
  ["real_name", "My real name", "Everything you write is signed with your real name."],
  ["anonymous", "Anonymous Community Member", "Your name is never shown beside anything you write. Your vote still counts the same."],
];

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

const UNINCORPORATED = "unincorporated";

type County = { id: number; name: string };
type City = { id: number; name: string };
type HomeStatus = {
  county: { id: number; name: string } | null;
  city: { id: number; name: string } | null;
  next_change_allowed_at: string | null;
  refused_now_reason: string | null;
};

type MyPostCommunity = {
  community: { level: string; entity_id: number; name: string; label: string };
  umbrella_id: number | null;
  label_status: string;
  link: string;
};

type MyPost = {
  id: number;
  title: string;
  created_at: string;
  label_status: string;
  communities: MyPostCommunity[];
};

export default function MePage() {
  useDocumentTitle("Your account");
  const router = useRouter();
  const { me, loading, reload, signOut } = useSession();
  const [message, setMessage] = useState<string | null>(null);
  const { error, fieldErrors, alertRef, clear, fail, fieldProps } = useFormError();
  const [exportId, setExportId] = useState<number | null>(null);
  const [confirming, setConfirming] = useState(false);
  const deleteFormRef = useRef<HTMLFormElement>(null);

  const profileForm = useFormError();
  const [profileMessage, setProfileMessage] = useState<string | null>(null);
  const profileFormRef = useRef<HTMLFormElement>(null);

  const emailForm = useFormError();
  const [emailMessage, setEmailMessage] = useState<string | null>(null);
  const emailFormRef = useRef<HTMLFormElement>(null);

  const homeForm = useFormError();
  const [homeStatus, setHomeStatus] = useState<HomeStatus | null>(null);
  const [homeMessage, setHomeMessage] = useState<string | null>(null);
  const [counties, setCounties] = useState<County[]>([]);
  const [cities, setCities] = useState<City[]>([]);
  const [homeCountyId, setHomeCountyId] = useState("");
  const homeFormRef = useRef<HTMLFormElement>(null);

  const [myPosts, setMyPosts] = useState<MyPost[]>([]);
  const [myPostsCursor, setMyPostsCursor] = useState<number | null>(null);
  const [myPostsLoaded, setMyPostsLoaded] = useState(false);
  const [myPostsLoading, setMyPostsLoading] = useState(false);

  async function loadMyPosts(cursor: number | null, replace: boolean) {
    setMyPostsLoading(true);
    try {
      const body = await get<{ items: MyPost[]; next_cursor: number | null }>(
        `/posts/mine${cursor ? `?cursor=${cursor}` : ""}`,
      );
      setMyPosts((previous) => (replace ? body.items : [...previous, ...body.items]));
      setMyPostsCursor(body.next_cursor);
    } catch {
      // The rest of the account page still works even if this section can't load.
    } finally {
      setMyPostsLoading(false);
      setMyPostsLoaded(true);
    }
  }

  useEffect(() => {
    if (!me) return;
    void loadMyPosts(null, true);
  }, [me]);

  useEffect(() => {
    if (!me) return;
    void get<HomeStatus>("/me/home")
      .then((status) => {
        setHomeStatus(status);
        setHomeCountyId(status.county ? String(status.county.id) : "");
      })
      .catch(() => setHomeStatus(null));
    void get<County[]>("/geo/counties").then(setCounties).catch(() => setCounties([]));
  }, [me]);

  useEffect(() => {
    if (!homeCountyId) {
      setCities([]);
      return;
    }
    void get<City[]>(`/geo/counties/${homeCountyId}/cities`).then(setCities).catch(() => setCities([]));
  }, [homeCountyId]);

  async function updateProfile(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    profileForm.clear();
    setProfileMessage(null);
    const form = new FormData(event.currentTarget);
    try {
      await patch("/me/profile", {
        real_name: form.get("real_name"),
        display_name: form.get("display_name"),
        gender: form.get("gender"),
        political_party: form.get("political_party"),
      });
      setProfileMessage("Saved.");
      await reload();
    } catch (problem) {
      profileForm.fail(problem, profileFormRef.current);
    }
  }

  async function requestEmailChange(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    emailForm.clear();
    setEmailMessage(null);
    const form = new FormData(event.currentTarget);
    try {
      const body = await post<{ message: string }>("/me/email", {
        new_email: form.get("new_email"),
        password: form.get("password"),
      });
      setEmailMessage(body.message);
      emailFormRef.current?.reset();
    } catch (problem) {
      emailForm.fail(problem, emailFormRef.current);
    }
  }

  async function changeHome(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    homeForm.clear();
    setHomeMessage(null);
    const form = new FormData(event.currentTarget);
    const cityValue = form.get("city_id");
    try {
      const body = await post<{ message: string }>("/me/home", {
        county_id: Number(form.get("county_id")),
        city_id: cityValue === UNINCORPORATED ? null : Number(cityValue),
      });
      setHomeMessage(body.message);
      const status = await get<HomeStatus>("/me/home");
      setHomeStatus(status);
      await reload();
    } catch (problem) {
      homeForm.fail(problem, homeFormRef.current);
    }
  }

  async function changeMode(mode: string) {
    clear();
    try {
      const body = await patch<{ shown_as: string }>("/me/display", {
        public_name_mode: mode,
      });
      setMessage(`Everything you write now shows as “${body.shown_as}”.`);
      await reload();
    } catch (problem) {
      fail(problem);
    }
  }

  async function requestExport() {
    clear();
    const body = await post<{ id: number; message: string }>("/me/export");
    setExportId(body.id);
    setMessage(body.message);
  }

  async function deleteAccount(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    clear();
    const form = new FormData(event.currentTarget);
    try {
      await del("/me", {
        password: form.get("password"),
        understand_this_cannot_be_undone: true,
      });
      await signOut();
      router.push("/");
    } catch (problem) {
      fail(problem, deleteFormRef.current);
    }
  }

  let body: ReactNode;
  if (loading) {
    body = <Loading what="your account" />;
  } else if (!me) {
    body = <Notice>You need to <Link href="/login">sign in</Link> to see this page.</Notice>;
  } else {
    body = (
      <>
        {message ? <Notice kind="good">{message}</Notice> : null}
        {error ? (
          <Notice kind="bad" alertRef={alertRef}>
            {error}
          </Notice>
        ) : null}

        <Section
          title="Your communities"
          description={
            me.home_communities.length === 2
              ? "You live in an unincorporated area, so you have no city community. You can read anywhere. You post and vote in these two."
              : "You can read anywhere. You post and vote in these three."
          }
        >
          <ul className="flex flex-wrap gap-2">
            {me.home_communities.map((community) => (
              <li key={`${community.level}:${community.entity_id}`} className="badge">
                {community.label}
              </li>
            ))}
          </ul>
        </Section>

        <Section
          title="Your posts"
          description="Every problem you have written down, newest first, and where each one has been filed."
        >
          {!myPostsLoaded ? (
            <Loading what="your posts" />
          ) : myPosts.length === 0 ? (
            <p className="text-sm text-[var(--muted)]">
              You have not written down a problem yet.{" "}
              <Link href="/posts/new">Write your first one</Link>.
            </p>
          ) : (
            <ul className="space-y-3">
              {myPosts.map((item) => (
                <li key={item.id} className="rounded-lg border border-[var(--line)] p-3">
                  <Link href={`/posts/${item.id}`} className="font-medium">
                    {item.title}
                  </Link>
                  <ul className="mt-1 space-y-1 text-sm text-[var(--muted)]">
                    {item.communities.map((c) => (
                      <li key={`${c.community.level}:${c.community.entity_id}`}>
                        {c.community.label}: {c.label_status}
                        {c.umbrella_id !== null ? (
                          <>
                            {" — "}
                            <Link href={c.link}>View in the workshop</Link>
                          </>
                        ) : null}
                      </li>
                    ))}
                  </ul>
                </li>
              ))}
            </ul>
          )}
          {myPostsCursor !== null ? (
            <button
              type="button"
              className="btn mt-3"
              onClick={() => void loadMyPosts(myPostsCursor, false)}
              disabled={myPostsLoading}
            >
              {myPostsLoading ? "Loading…" : "Load more"}
            </button>
          ) : null}
        </Section>

        <Section
          title="Your profile"
          description="Real name, display name, gender and political party. Date of birth is never editable."
        >
          {profileMessage ? <Notice kind="good">{profileMessage}</Notice> : null}
          {profileForm.error ? (
            <Notice kind="bad" alertRef={profileForm.alertRef}>
              {profileForm.error}
            </Notice>
          ) : null}
          <form ref={profileFormRef} onSubmit={updateProfile} className="space-y-4" noValidate>
            <div className="grid gap-4 sm:grid-cols-2">
              <div>
                <label htmlFor="real_name" className="block font-medium">Your real name</label>
                <input
                  id="real_name"
                  name="real_name"
                  defaultValue={me.real_name}
                  required
                  autoComplete="name"
                  className="field mt-1"
                  {...profileForm.fieldProps("real_name")}
                />
                <FieldError name="real_name" fieldErrors={profileForm.fieldErrors} />
              </div>
              <div>
                <label htmlFor="display_name" className="block font-medium">Display name</label>
                <input
                  id="display_name"
                  name="display_name"
                  defaultValue={me.display_name}
                  required
                  className="field mt-1"
                  {...profileForm.fieldProps("display_name")}
                />
                <FieldError name="display_name" fieldErrors={profileForm.fieldErrors} />
              </div>
            </div>
            <div className="grid gap-4 sm:grid-cols-2">
              <div>
                <label htmlFor="gender" className="block font-medium">Gender</label>
                <select
                  id="gender"
                  name="gender"
                  defaultValue={me.gender}
                  required
                  className="field mt-1"
                  {...profileForm.fieldProps("gender")}
                >
                  {GENDERS.map(([value, label]) => (
                    <option key={value} value={value}>{label}</option>
                  ))}
                </select>
                <FieldError name="gender" fieldErrors={profileForm.fieldErrors} />
              </div>
              <div>
                <label htmlFor="political_party" className="block font-medium">Political party</label>
                <select
                  id="political_party"
                  name="political_party"
                  defaultValue={me.political_party}
                  required
                  className="field mt-1"
                  {...profileForm.fieldProps("political_party")}
                >
                  {PARTIES.map(([value, label]) => (
                    <option key={value} value={value}>{label}</option>
                  ))}
                </select>
                <FieldError name="political_party" fieldErrors={profileForm.fieldErrors} />
              </div>
            </div>
            <p className="text-sm text-[var(--muted)]">
              Gender and political party are used for public totals only. They
              never change what you see or what your vote is worth.
            </p>
            <button type="submit" className="btn btn-primary">Save profile</button>
          </form>
        </Section>

        <Section
          title="Change your email"
          description="We send a confirmation link to the new address and a notice to your current one. Nothing changes until you use the link."
        >
          {emailMessage ? <Notice kind="good">{emailMessage}</Notice> : null}
          {emailForm.error ? (
            <Notice kind="bad" alertRef={emailForm.alertRef}>
              {emailForm.error}
            </Notice>
          ) : null}
          <form ref={emailFormRef} onSubmit={requestEmailChange} className="space-y-4" noValidate>
            <div>
              <label htmlFor="new_email" className="block font-medium">New email address</label>
              <input
                id="new_email"
                name="new_email"
                type="email"
                required
                autoComplete="email"
                className="field mt-1"
                {...emailForm.fieldProps("new_email")}
              />
              <FieldError name="new_email" fieldErrors={emailForm.fieldErrors} />
            </div>
            <div>
              <label htmlFor="email_password" className="block font-medium">Confirm with your password</label>
              <input
                id="email_password"
                name="password"
                type="password"
                required
                autoComplete="current-password"
                className="field mt-1"
                {...emailForm.fieldProps("password")}
              />
              <FieldError name="password" fieldErrors={emailForm.fieldErrors} />
            </div>
            <button type="submit" className="btn btn-primary">Send confirmation link</button>
          </form>
        </Section>

        <Section
          title="Change your home community"
          description="Where you live decides what you can post, comment and vote on."
        >
          {homeMessage ? <Notice kind="good">{homeMessage}</Notice> : null}
          {homeForm.error ? (
            <Notice kind="bad" alertRef={homeForm.alertRef}>
              {homeForm.error}
            </Notice>
          ) : null}
          <p className="text-sm">
            Currently: {homeStatus?.city ? `${homeStatus.city.name}, ` : ""}
            {homeStatus?.county ? `${homeStatus.county.name} County` : "…"}
            {!homeStatus?.city ? " (unincorporated — no city)" : ""}
          </p>
          <div className="mt-2 rounded-lg border border-[var(--line)] p-3 text-sm text-[var(--muted)]">
            <p className="font-medium text-[var(--fg)]">Before you change it, know this:</p>
            <ul className="mt-1 list-disc space-y-1 pl-5">
              <li>
                You can change your home again{" "}
                {homeStatus?.next_change_allowed_at
                  ? `on ${new Date(homeStatus.next_change_allowed_at).toLocaleDateString()}`
                  : "any time, since your last change"}
                {" "}— the first change after signup is always free.
              </li>
              <li>
                If you are drawn or seated on a jury whose cycle is not yet
                published, you finish that service first.
              </li>
              <li>
                A move never carries a vote into a ballot already under way: you
                sit out any ballot in your old or new community that was
                already prepared before you moved. Everything you already
                posted, said or voted stays exactly where it was made.
              </li>
            </ul>
          </div>
          {homeStatus?.refused_now_reason ? (
            <div className="mt-3">
              <Notice kind="bad">{homeStatus.refused_now_reason}</Notice>
            </div>
          ) : (
            <form ref={homeFormRef} onSubmit={changeHome} className="mt-3 space-y-4" noValidate>
              <div className="grid gap-4 sm:grid-cols-2">
                <div>
                  <label htmlFor="home_county_id" className="block font-medium">County</label>
                  <select
                    id="home_county_id"
                    name="county_id"
                    required
                    className="field mt-1"
                    value={homeCountyId}
                    onChange={(e) => setHomeCountyId(e.target.value)}
                    {...homeForm.fieldProps("county_id")}
                  >
                    <option value="">Choose a county</option>
                    {counties.map((county) => (
                      <option key={county.id} value={county.id}>{county.name}</option>
                    ))}
                  </select>
                  <FieldError name="county_id" fieldErrors={homeForm.fieldErrors} />
                </div>
                <div>
                  <label htmlFor="home_city_id" className="block font-medium">City</label>
                  <select
                    id="home_city_id"
                    name="city_id"
                    required
                    className="field mt-1"
                    disabled={!cities.length}
                    defaultValue={homeStatus?.city ? String(homeStatus.city.id) : UNINCORPORATED}
                    {...homeForm.fieldProps("city_id")}
                  >
                    <option value="">
                      {homeCountyId ? "Choose a city" : "Choose a county first"}
                    </option>
                    {cities.length ? (
                      <option value={UNINCORPORATED}>Unincorporated — no city</option>
                    ) : null}
                    {cities.map((city) => (
                      <option key={city.id} value={city.id}>{city.name}</option>
                    ))}
                  </select>
                  <FieldError name="city_id" fieldErrors={homeForm.fieldErrors} />
                </div>
              </div>
              <button type="submit" className="btn btn-primary">Confirm home change</button>
            </form>
          )}
        </Section>

        <Section
          title="Your verification level"
          description={me.verification_level}
        >
          <p className="text-sm text-[var(--muted)]">{me.verification_explanation}</p>
        </Section>

        <Section title="How your name appears" description="This is a setting, not an account type. You can change it whenever you like.">
          <fieldset className="space-y-2">
            <legend className="sr-only">How your name appears</legend>
            {MODES.map(([value, label, explanation]) => (
              <label key={value} className="flex items-start gap-2 rounded-lg border border-[var(--line)] p-3">
                <input
                  type="radio"
                  name="public_name_mode"
                  value={value}
                  className="mt-1"
                  defaultChecked={me.public_name_mode === value}
                  onChange={() => void changeMode(value)}
                />
                <span>
                  <span className="font-medium">{label}</span>
                  <span className="block text-sm text-[var(--muted)]">{explanation}</span>
                </span>
              </label>
            ))}
          </fieldset>
        </Section>

        <Section
          title="Take your data with you"
          description="Everything the platform holds about you, as a JSON file. Your ballot votes are in it, and they are shown to nobody else."
        >
          <button type="button" className="btn" onClick={() => void requestExport()}>
            Prepare my data
          </button>
          {exportId ? (
            <p className="mt-2 text-sm">
              <a href={`${apiBase()}/me/export/${exportId}`}>Download it</a> — give
              it a moment if it is not ready yet.
            </p>
          ) : null}
        </Section>

        <Section
          title="Delete your account"
          description="Your name, email, password, date of birth, gender and political party are erased permanently."
        >
          <p className="text-sm text-[var(--muted)]">
            What you wrote stays in the civic record, attributed to “Former
            Community Member”, because other people built on it. Your home city
            and county are kept so that record stays in the right community;
            neither identifies you on its own. Cryptographic fingerprints are
            never deleted — they are public proofs, not personal data.
          </p>
          {confirming ? (
            <form
              ref={deleteFormRef}
              onSubmit={deleteAccount}
              className="mt-3 space-y-3"
              noValidate
            >
              <div>
                <label htmlFor="password" className="block font-medium">
                  Confirm with your password
                </label>
                <input
                  id="password"
                  name="password"
                  type="password"
                  required
                  className="field mt-1"
                  {...fieldProps("password")}
                />
                <FieldError name="password" fieldErrors={fieldErrors} />
              </div>
              <div className="flex gap-2">
                <button type="submit" className="btn" style={{ borderColor: "var(--bad)", color: "var(--bad)" }}>
                  Delete my account permanently
                </button>
                <button type="button" className="btn" onClick={() => setConfirming(false)}>
                  Keep my account
                </button>
              </div>
            </form>
          ) : (
            <button type="button" className="btn mt-3" onClick={() => setConfirming(true)}>
              I want to delete my account
            </button>
          )}
        </Section>
      </>
    );
  }

  return (
    <>
      <PageHeader title="Your account" lead={me?.display_name} />
      <div className={`mx-auto px-4 py-8 ${me ? "max-w-2xl" : "max-w-md"}`}>{body}</div>
    </>
  );
}
