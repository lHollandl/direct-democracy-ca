'use client';

import { useEffect, useState } from 'react';
import Link from 'next/link';
import { getPosts, getMe, logout, Post, UserProfile } from '@/lib/api';
import { useRouter } from 'next/navigation';

function formatLocations(locations: Post['locations']): string {
  if (!locations || locations.length === 0) return 'Unspecified location';
  return locations
    .map((loc) => {
      const type = loc.location_type.charAt(0).toUpperCase() + loc.location_type.slice(1);
      return loc.location_id ? `${type} #${loc.location_id}` : type;
    })
    .join(', ');
}

export default function FeedPage() {
  const router = useRouter();
  const [posts, setPosts] = useState<Post[]>([]);
  const [currentUser, setCurrentUser] = useState<UserProfile | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  useEffect(() => {
    async function load() {
      try {
        const [fetchedPosts, me] = await Promise.allSettled([getPosts(), getMe()]);

        if (fetchedPosts.status === 'fulfilled') {
          setPosts(fetchedPosts.value);
        } else {
          setError('Could not load posts. Is the backend running?');
        }

        if (me.status === 'fulfilled') {
          setCurrentUser(me.value);
        }
        // Silently ignore auth failure — anonymous browsing is allowed
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

              {post.solution && (
                <div className="bg-gray-700 rounded px-3 py-2 mb-3 text-sm">
                  <span className="text-gray-400">Proposed solution: </span>
                  <span className="text-gray-200">{post.solution.title}</span>
                </div>
              )}

              <div className="flex items-center gap-4 text-xs text-gray-500">
                <span>{formatLocations(post.locations)}</span>
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
