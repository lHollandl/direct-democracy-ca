import axios from 'axios';

const BASE_URL = 'http://localhost:8000';

export function getToken(): string | null {
  if (typeof window === 'undefined') return null;
  return localStorage.getItem('token');
}

// Axios instance that automatically attaches the Bearer token when present
const apiClient = axios.create({
  baseURL: BASE_URL,
});

apiClient.interceptors.request.use((config) => {
  const token = getToken();
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

export default apiClient;

// --- Types ---

export interface UserProfile {
  id: number;
  username: string;
  email: string;
  created_at: string;
  influence_score: number;
  political_party: string | null;
}

export interface PostLocation {
  id: number;
  location_type: string;
  location_id: number | null;
}

export interface SolutionSummary {
  id: number;
  title: string;
  content: string;
  upvote_count: number;
  ai_contribution_percentage: number;
  content_hash: string | null;
}

export interface Post {
  id: number;
  user_id: number;
  title: string;
  content: string;
  created_at: string;
  ai_contribution_percentage: number;
  ai_model_used: string | null;
  content_hash: string | null;
  label_count: number;
  vote_count: number;
  locations: PostLocation[];
  solution: SolutionSummary | null;
}

// --- API functions ---

export async function signup(
  username: string,
  email: string,
  password: string,
  dateOfBirth: string,
): Promise<void> {
  await apiClient.post('/users', {
    username,
    email,
    password,
    date_of_birth: dateOfBirth,
    agreed_to_terms: true,
    agreed_to_terms_version: '1.0',
  });
}

export async function login(username: string, password: string): Promise<void> {
  const response = await apiClient.post('/auth/login', { username, password });
  localStorage.setItem('token', response.data.access_token);
}

export function logout(): void {
  localStorage.removeItem('token');
}

export async function getMe(): Promise<UserProfile> {
  const response = await apiClient.get('/auth/me');
  return response.data;
}

export async function getPosts(locationFilter?: {
  location_type?: string;
  location_id?: number;
}): Promise<Post[]> {
  const response = await apiClient.get('/posts', { params: locationFilter });
  return response.data;
}

export async function createPost(data: {
  title: string;
  content: string;
  solution_title: string;
  solution_content: string;
  locations: Array<{ location_type: string; location_id?: number | null }>;
  ai_contribution_percentage?: number;
  ai_model_used?: string | null;
}): Promise<Post> {
  const response = await apiClient.post('/posts', data);
  return response.data;
}
