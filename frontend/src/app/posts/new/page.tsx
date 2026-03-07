'use client';

import Link from 'next/link';

// Placeholder — the full post creation form will be built in Prompt 4
// when the AI labeling pipeline is wired in.
export default function NewPostPage() {
  return (
    <main className="min-h-screen bg-gray-950 text-white flex items-center justify-center p-4">
      <div className="text-center">
        <h1 className="text-3xl font-bold mb-4">New Post</h1>
        <p className="text-gray-400 mb-6">
          Post creation is coming soon. The AI labeling pipeline needs to be
          connected before this form is live.
        </p>
        <Link href="/feed" className="text-blue-400 underline">
          Back to feed
        </Link>
      </div>
    </main>
  );
}
