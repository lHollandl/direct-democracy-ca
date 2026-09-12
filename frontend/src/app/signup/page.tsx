'use client';

import { useState, useEffect } from 'react';
import { useRouter } from 'next/navigation';
import Link from 'next/link';
import { signup, getCounties, getCities, County, City } from '@/lib/api';
import axios from 'axios';

export default function SignupPage() {
  const router = useRouter();

  // Account fields
  const [username, setUsername] = useState('');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [dateOfBirth, setDateOfBirth] = useState('');
  const [agreedToTerms, setAgreedToTerms] = useState(false);

  // Location fields — optional
  const [counties, setCounties] = useState<County[]>([]);
  const [cities, setCities] = useState<City[]>([]);
  const [selectedCountyId, setSelectedCountyId] = useState<number | ''>('');
  const [selectedCityId, setSelectedCityId] = useState<number | ''>('');
  const [loadingCounties, setLoadingCounties] = useState(false);
  const [loadingCities, setLoadingCities] = useState(false);

  const [error, setError] = useState('');
  const [submitting, setSubmitting] = useState(false);

  // Load all 58 California counties once on mount (state_id=1)
  useEffect(() => {
    setLoadingCounties(true);
    getCounties(1)
      .then(setCounties)
      .catch(() => {/* silently skip — location is optional */})
      .finally(() => setLoadingCounties(false));
  }, []);

  // Reload cities whenever the selected county changes
  useEffect(() => {
    if (!selectedCountyId) {
      setCities([]);
      setSelectedCityId('');
      return;
    }
    setLoadingCities(true);
    setSelectedCityId('');
    getCities(selectedCountyId)
      .then(setCities)
      .catch(() => {/* silently skip */})
      .finally(() => setLoadingCities(false));
  }, [selectedCountyId]);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError('');

    if (!agreedToTerms) {
      setError('You must agree to the terms of service to register.');
      return;
    }

    setSubmitting(true);
    try {
      await signup(
        username,
        email,
        password,
        dateOfBirth,
        selectedCountyId !== '' ? selectedCountyId : undefined,
        selectedCityId !== '' ? selectedCityId : undefined,
      );
      router.push('/login?message=Account+created!+Please+log+in.');
    } catch (err) {
      if (axios.isAxiosError(err) && err.response?.data?.detail) {
        setError(err.response.data.detail);
      } else {
        setError('Something went wrong. Please try again.');
      }
    } finally {
      setSubmitting(false);
    }
  }

  const inputClass = 'w-full bg-gray-800 border border-gray-600 rounded px-3 py-2 text-white focus:outline-none focus:border-blue-500';
  const selectClass = 'w-full bg-gray-800 border border-gray-600 rounded px-3 py-2 text-white focus:outline-none focus:border-blue-500 disabled:opacity-50 disabled:cursor-not-allowed';

  return (
    <main className="min-h-screen bg-gray-950 text-white flex items-center justify-center p-4">
      <div className="w-full max-w-md">
        <h1 className="text-3xl font-bold mb-2">Create an account</h1>
        <p className="text-gray-400 mb-8">Join the civic conversation in California.</p>

        {error && (
          <div role="alert" className="bg-red-900 border border-red-700 text-red-200 px-4 py-3 rounded mb-6">
            {error}
          </div>
        )}

        <form onSubmit={handleSubmit} className="space-y-5">
          <div>
            <label htmlFor="username" className="block text-sm font-medium text-gray-300 mb-1">
              Username
            </label>
            <input
              id="username"
              type="text"
              required
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              className={inputClass}
            />
          </div>

          <div>
            <label htmlFor="email" className="block text-sm font-medium text-gray-300 mb-1">
              Email
            </label>
            <input
              id="email"
              type="email"
              required
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              className={inputClass}
            />
          </div>

          <div>
            <label htmlFor="password" className="block text-sm font-medium text-gray-300 mb-1">
              Password
            </label>
            <input
              id="password"
              type="password"
              required
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              className={inputClass}
            />
            <p className="text-gray-500 text-xs mt-1">
              At least 8 characters, one uppercase letter, and one number.
            </p>
          </div>

          <div>
            <label htmlFor="dob" className="block text-sm font-medium text-gray-300 mb-1">
              Date of birth{' '}
              <span className="text-gray-500 font-normal">(required by law for users under 13)</span>
            </label>
            <input
              id="dob"
              type="date"
              required
              value={dateOfBirth}
              onChange={(e) => setDateOfBirth(e.target.value)}
              className={inputClass}
            />
          </div>

          {/* Location — optional, warm conversational copy per design intent */}
          <div className="pt-2 pb-1 border-t border-gray-800">
            <p className="text-gray-200 font-medium mb-1">Where do you live?</p>
            <p className="text-gray-400 text-sm mb-4">
              This helps us show you what&apos;s happening in your community. You can skip
              this and set it later.
            </p>

            <div className="space-y-3">
              <div>
                <label htmlFor="county" className="block text-sm font-medium text-gray-300 mb-1">
                  County <span className="text-gray-500 font-normal">(optional)</span>
                </label>
                <select
                  id="county"
                  value={selectedCountyId}
                  onChange={(e) => setSelectedCountyId(e.target.value ? Number(e.target.value) : '')}
                  disabled={loadingCounties}
                  aria-busy={loadingCounties}
                  className={selectClass}
                >
                  <option value="">
                    {loadingCounties ? 'Loading…' : 'Skip for now'}
                  </option>
                  {counties.map((c) => (
                    <option key={c.id} value={c.id}>
                      {c.name} County
                    </option>
                  ))}
                </select>
              </div>

              <div>
                <label htmlFor="city" className="block text-sm font-medium text-gray-300 mb-1">
                  City <span className="text-gray-500 font-normal">(optional)</span>
                </label>
                <select
                  id="city"
                  value={selectedCityId}
                  onChange={(e) => setSelectedCityId(e.target.value ? Number(e.target.value) : '')}
                  disabled={!selectedCountyId || loadingCities}
                  aria-busy={loadingCities}
                  className={selectClass}
                >
                  <option value="">
                    {!selectedCountyId
                      ? 'Choose a county first'
                      : loadingCities
                      ? 'Loading…'
                      : cities.length === 0
                      ? 'No cities listed for this county yet'
                      : 'Skip for now'}
                  </option>
                  {cities.map((c) => (
                    <option key={c.id} value={c.id}>
                      {c.name}
                    </option>
                  ))}
                </select>
              </div>
            </div>
          </div>

          <div className="flex items-start gap-3">
            <input
              id="terms"
              type="checkbox"
              checked={agreedToTerms}
              onChange={(e) => setAgreedToTerms(e.target.checked)}
              className="mt-1"
            />
            <label htmlFor="terms" className="text-sm text-gray-300">
              I agree to the{' '}
              <Link href="/terms" className="text-blue-400 underline">
                terms of service
              </Link>
            </label>
          </div>

          <button
            type="submit"
            disabled={submitting}
            className="w-full bg-blue-600 hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed text-white font-semibold py-2 px-4 rounded transition-colors"
          >
            {submitting ? 'Creating account...' : 'Create account'}
          </button>
        </form>

        <p className="text-gray-400 text-sm mt-6 text-center">
          Already have an account?{' '}
          <Link href="/login" className="text-blue-400 underline">
            Log in
          </Link>
        </p>
      </div>
    </main>
  );
}
