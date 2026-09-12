'use client';

import { useEffect, useState } from 'react';
import Link from 'next/link';
import { getPosts, getMe, getCities, logout, Post, City, UserProfile } from '@/lib/api';
import { useRouter } from 'next/navigation';

// Resolves a post's locations to a human-readable string using a pre-loaded
// city name map. Falls back to "City #N" for any city not yet in the map.
function formatLocations(
  locations: Post['locations'],
  cityMap: Map<number, string>,
): string {
  if (!locations || locations.length === 0) return 'Unspecified location';
  return locations
    .map((loc) => {
      if (loc.location_type === 'city' && loc.location_id !== null) {
        return cityMap.get(loc.location_id ?? -1) ?? `City #${loc.location_id}`;
      }
      const type = loc.location_type.charAt(0).toUpperCase() + loc.location_type.slice(1);
      return loc.location_id ? `${type} #${loc.location_id}` : type;
    })
    .join(', ');
}

export default function FeedPage() {
  const router = useRouter();
  const [posts, setPosts] = useState<Post[]>([]);
  const [currentUser, setCurrentUser] = useState<UserProfile | null>(null);
  // Map of city_id → city name, populated on mount from GET /cities
  const [cityMap, setCityMap] = useState<Map<number, string>>(new Map());
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  useEffect(() => {
    async function load() {
      try {
        const [fetchedPosts, me, cities] = await Promise.allSettled([
          getPosts(),
          getMe(),
          getCities(),
        ]);

        if (fetchedPosts.status === 'fulfilled') {
          setPosts(fetchedPosts.value);
        } else {
          setError('Could not load posts. Is the backend running?');
        }

        if (me.status === 'fulfilled') {
          setCurrentUser(me.value);
        }
        // Silently ignore auth failure — anonymous browsing is allowed

        if (cities.status === 'fulfilled') {
          setCityMap(new Map(cities.value.map((c: City) => [c.id, c.name])));
        }
        // Silently ignore city lookup failure — feed still works, just shows "City #N"
      } finally {
        setLoading(false);
      }
    }
    load();
  }, []);

  function handleLogout() {
    logout();
    setCurrentUser(null);
    router.refresh();
  }

  return (
    <main className="min-h-screen bg-gray-950 text-white">
      {/* Header */}
      <header className="border-b border-gray-800 px-4 py-3 flex items-center justify-between">
        <Link href="/feed" className="text-xl font-bold text-white">
          Direct Democracy Cali
        </Link>
        <div className="flex items-center gap-4">
          {currentUser ? (
            <>
              <span className="text-gray-300 text-sm">{currentUser.username}</span>
              <button
                onClick={handleLogout}
                className="text-gray-400 hover:text-white text-sm underline"
              >
                Log out
              </button>
            </>
          ) : (
            <Link href="/login" className="text-blue-400 text-sm underline">
              Log in
            </Link>
          )}
          <Link
            href="/posts/new"
            className="bg-blue-600 hover:bg-blue-700 text-white text-sm font-semibold px-3 py-1.5 rounded transition-colors"
          >
            New Post
          </Link>
        </div>
      </header>

      {/* Guest banner */}
      {!currentUser && !loading && (
        <div className="bg-gray-800 border-b border-gray-700 px-4 py-3 text-center text-sm text-gray-300">
          You are browsing as a guest.{' '}
          <Link href="/login" className="text-blue-400 underline">
            Log in
          </Link>{' '}
          to vote or post.
        </div>
      )}

      {/* Feed */}
      <div className="max-w-2xl mx-auto px-4 py-8">
        <h2 className="text-2xl font-semibold mb-6">Community Posts</h2>

        {loading && <p className="text-gray-400">Loading posts...</p>}

        {error && (
          <div className="bg-red-900 border border-red-700 text-red-200 px-4 py-3 rounded mb-6">
            {error}
          </div>
        )}

        {!loading && posts.length === 0 && !error && (
          <p className="text-gray-400">
            No posts yet.{' '}
            <Link href="/posts/new" className="text-blue-400 underline">
              Be the first to post.
            </Link>
          </p>
        )}

        <ul className="space-y-4">
          {posts.map((post) => (
            <li
              key={post.id}
              className="bg-gray-800 border border-gray-700 rounded-lg p-5"
            >
              <h3 className="text-lg font-semibold mb-1">{post.title}</h3>
              <p className="text-gray-300 text-sm mb-3 leading-relaxed">
                {post.content.length > 150
                  ? post.content.slice(0, 150) + '…'
                  : post.content}
              </p>

              {post.solutions.length > 0 && (
                <div className="bg-gray-700 rounded px-3 py-2 mb-3 text-sm">
                  <span className="text-gray-400">Proposed solution: </span>
                  <span className="text-gray-200">{post.solutions[0].content.slice(0, 100)}{post.solutions[0].content.length > 100 ? '…' : ''}</span>
                </div>
              )}

              <div className="flex items-center gap-4 text-xs text-gray-500">
                <span>Posted by {post.username}</span>
                <span>{formatLocations(post.locations, cityMap)}</span>
                <span>{post.vote_count} vote{post.vote_count !== 1 ? 's' : ''}</span>
                <span>
                  {new Date(post.created_at).toLocaleDateString('en-US', {
                    year: 'numeric',
                    month: 'short',
                    day: 'numeric',
                  })}
                </span>
              </div>
            </li>
          ))}
        </ul>
      </div>
    </main>
  );
}
