'use client';

import { useState, useEffect, useCallback } from 'react';
import { useRouter } from 'next/navigation';
import Link from 'next/link';
import axios from 'axios';
import { getToken, getMe, createPost, UserProfile } from '@/lib/api';

// Maps a governance level to its display label and subtitle.
// The subtitle for city/county is filled in dynamically from the user profile.
const LEVELS = [
  { key: 'city', label: 'City' },
  { key: 'county', label: 'County' },
  { key: 'state', label: 'State', subtitle: 'California' },
  { key: 'federal', label: 'Federal', subtitle: 'U.S. Government' },
] as const;

type GovernanceLevel = (typeof LEVELS)[number]['key'];

// Derive the post's location entries from selected governance levels and the
// user's profile. City/county levels use the user's stored IDs; state uses
// California (state_id=1); federal has no location_id (null = nationwide).
function buildLocations(
  levels: GovernanceLevel[],
  user: UserProfile,
): Array<{ location_type: string; location_id?: number | null }> {
  return levels.map((level) => {
    if (level === 'city') return { location_type: 'city', location_id: user.city_id };
    if (level === 'county') return { location_type: 'county', location_id: user.county_id };
    if (level === 'state') return { location_type: 'state', location_id: 1 };
    return { location_type: 'federal', location_id: null };
  });
}

const textareaClass =
  'w-full bg-gray-800 border border-transparent rounded-lg px-4 py-3 text-white placeholder-gray-500 focus:outline-none focus:border-blue-500 resize-none';

export default function NewPostPage() {
  const router = useRouter();

  const [authChecked, setAuthChecked] = useState(false);
  const [user, setUser] = useState<UserProfile | null>(null);

  // Panel 1 — problem
  const [problem, setProblem] = useState('');

  // Panel 2 — solutions (start with one empty entry)
  const [solutions, setSolutions] = useState<string[]>(['']);

  // Panel 3 — governance level toggles (multi-select)
  const [selectedLevels, setSelectedLevels] = useState<GovernanceLevel[]>([]);

  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState('');

  // Auth guard — redirect to login if no valid token.
  // On success, store the user profile so Panel 3 can show real place names.
  const checkAuth = useCallback(() => {
    const token = getToken();
    if (!token) {
      router.replace('/login?message=Please+log+in+to+post.');
      return;
    }
    getMe()
      .then((me) => {
        setUser(me);
        setAuthChecked(true);
      })
      .catch(() => router.replace('/login?message=Please+log+in+to+post.'));
  }, [router]);

  useEffect(() => {
    checkAuth();
  }, [checkAuth]);

  function toggleLevel(level: GovernanceLevel) {
    setSelectedLevels((prev) =>
      prev.includes(level) ? prev.filter((l) => l !== level) : [...prev, level],
    );
  }

  function addSolution() {
    setSolutions((prev) => [...prev, '']);
  }

  function updateSolution(index: number, value: string) {
    setSolutions((prev) => prev.map((s, i) => (i === index ? value : s)));
  }

  function removeSolution(index: number) {
    setSolutions((prev) => prev.filter((_, i) => i !== index));
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError('');

    if (!problem.trim()) {
      setError('Please describe the problem before submitting.');
      return;
    }

    const filledSolutions = solutions.filter((s) => s.trim());
    if (filledSolutions.length === 0) {
      setError('Please add at least one proposed solution.');
      return;
    }

    if (selectedLevels.length === 0) {
      setError('Please choose at least one level of government that should act.');
      return;
    }

    // Validate that the user has the IDs needed for the selected governance levels.
    if (selectedLevels.includes('city') && !user?.city_id) {
      setError(
        'You selected "City" but your profile has no city set. Add your city in your profile or choose a different level.',
      );
      return;
    }
    if (selectedLevels.includes('county') && !user?.county_id) {
      setError(
        'You selected "County" but your profile has no county set. Add your county in your profile or choose a different level.',
      );
      return;
    }

    // Auto-generate the title from the first 97 characters of the problem text.
    // The backend requires a title but the civic conversation UI hides it.
    const title =
      problem.trim().length > 97
        ? problem.trim().slice(0, 97) + '…'
        : problem.trim();

    setSubmitting(true);
    try {
      await createPost({
        title,
        content: problem.trim(),
        solutions: filledSolutions.map((content) => ({
          content,
          governance_levels: [...selectedLevels],
        })),
        locations: buildLocations(selectedLevels, user!),
      });
      router.push('/feed');
    } catch (err) {
      if (axios.isAxiosError(err) && err.response?.data?.detail) {
        const detail = err.response.data.detail;
        if (Array.isArray(detail)) {
          setError(detail[0]?.msg ?? 'Submission failed. Please check your inputs.');
        } else {
          setError(typeof detail === 'string' ? detail : 'Submission failed. Please check your inputs.');
        }
      } else {
        setError('Something went wrong. Please try again.');
      }
    } finally {
      setSubmitting(false);
    }
  }

  // Render nothing until auth check resolves — avoids a flash of the form
  // before the redirect fires on unauthenticated visits.
  if (!authChecked) return null;

  return (
    <main className="min-h-screen bg-gray-950 text-white">
      {/* Header */}
      <header className="border-b border-gray-800 px-4 py-3 flex items-center justify-between">
        <Link href="/feed" className="text-xl font-bold text-white">
          Direct Democracy Cali
        </Link>
        <Link href="/feed" className="text-gray-400 hover:text-white text-sm underline">
          Back to feed
        </Link>
      </header>

      <div className="max-w-2xl mx-auto px-4 py-10">
        <h1 className="text-3xl font-bold mb-1">What&apos;s on your mind?</h1>
        <p className="text-gray-400 mb-8">
          Tell your community about a problem you&apos;ve seen — and what you think should be
          done about it.
        </p>

        {error && (
          <div
            role="alert"
            className="bg-red-900 border border-red-700 text-red-200 px-4 py-3 rounded-lg mb-6"
          >
            {error}
          </div>
        )}

        <form onSubmit={handleSubmit} noValidate className="space-y-4">

          {/* ============================================================
              PANEL 1 — The problem
          ============================================================ */}
          <div className="bg-gray-900 border border-gray-700 rounded-2xl p-6">
            <textarea
              id="problem"
              rows={6}
              value={problem}
              onChange={(e) => setProblem(e.target.value)}
              placeholder="What's the problem you've seen?"
              maxLength={5000}
              aria-label="Describe the problem"
              className={textareaClass}
            />
            <p className="text-gray-600 text-xs mt-2 text-right">
              {problem.length} / 5000
            </p>
          </div>

          {/* ============================================================
              PANEL 2 — Proposed solutions
          ============================================================ */}
          <div className="bg-gray-900 border border-gray-700 rounded-2xl p-6 space-y-4">
            {solutions.map((sol, i) => (
              <div key={i}>
                {solutions.length > 1 && (
                  <div className="flex items-center justify-between mb-2">
                    <span className="text-xs text-gray-500 font-medium uppercase tracking-wide">
                      Solution {i + 1}
                    </span>
                    <button
                      type="button"
                      onClick={() => removeSolution(i)}
                      aria-label={`Remove solution ${i + 1}`}
                      className="text-gray-500 hover:text-red-400 text-sm transition-colors"
                    >
                      Remove
                    </button>
                  </div>
                )}
                <textarea
                  rows={3}
                  value={sol}
                  onChange={(e) => updateSolution(i, e.target.value)}
                  placeholder="What do you think should be done about it?"
                  maxLength={5000}
                  aria-label={`Solution ${i + 1}`}
                  className={textareaClass}
                />
              </div>
            ))}

            <button
              type="button"
              onClick={addSolution}
              className="text-blue-400 hover:text-blue-300 text-sm font-medium transition-colors"
            >
              + Add another solution
            </button>
          </div>

          {/* ============================================================
              PANEL 3 — Governance level (who needs to act?)
          ============================================================ */}
          <div className="bg-gray-900 border border-gray-700 rounded-2xl p-6">
            <p className="text-gray-200 font-medium mb-1">Who needs to act on this?</p>
            <p className="text-gray-400 text-sm mb-4">
              Select all that apply. This controls where your post appears and who your
              solutions are directed at.
            </p>

            <div className="grid grid-cols-2 gap-3" role="group" aria-label="Governance level">
              {LEVELS.map(({ key, label }) => {
                // Show the user's real place name under the relevant card.
                let subtitle: string | undefined;
                if (key === 'city') subtitle = user?.city_name ?? undefined;
                else if (key === 'county')
                  subtitle = user?.county_name ? `${user.county_name} County` : undefined;
                else if (key === 'state') subtitle = 'California';
                else subtitle = 'U.S. Government';

                const selected = selectedLevels.includes(key);

                return (
                  <button
                    key={key}
                    type="button"
                    onClick={() => toggleLevel(key)}
                    aria-pressed={selected}
                    className={`rounded-xl p-4 text-left transition-all border-2 ${
                      selected
                        ? 'bg-blue-700 border-blue-400 text-white'
                        : 'bg-gray-800 border-gray-600 text-gray-300 hover:border-gray-400'
                    }`}
                  >
                    <div className="font-semibold">{label}</div>
                    {subtitle && (
                      <div
                        className={`text-sm mt-0.5 ${selected ? 'text-blue-200' : 'text-gray-500'}`}
                      >
                        {subtitle}
                      </div>
                    )}
                  </button>
                );
              })}
            </div>
          </div>

          {/* ============================================================
              SUBMIT
          ============================================================ */}
          <button
            type="submit"
            disabled={submitting}
            className="w-full bg-blue-600 hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed text-white font-semibold py-3 px-4 rounded-xl transition-colors text-base"
          >
            {submitting ? 'Submitting…' : 'Submit to your community'}
          </button>

          <p className="text-gray-600 text-xs text-center pb-4">
            Your post is visible immediately. The AI category label appears within seconds.
          </p>
        </form>
      </div>
    </main>
  );
}
