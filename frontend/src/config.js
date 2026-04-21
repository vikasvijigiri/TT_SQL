/**
 * API Configuration
 * Reads from environment variables, with intelligent fallbacks
 */

export const getApiBaseUrl = () => {
  // 1. Check Vite environment variable (set via .env.local or build process)
  if (import.meta.env.VITE_API_BASE_URL) {
    return import.meta.env.VITE_API_BASE_URL;
  }

  // 2. Check if API_BASE_URL is set globally (for legacy support)
  if (typeof window !== 'undefined' && window.API_BASE_URL) {
    return window.API_BASE_URL;
  }

  // 3. Dynamic fallback: same hostname as frontend, with configurable API port
  const hostname = window.location.hostname;
  const apiPort = import.meta.env.VITE_API_PORT || 8001;
  
  // If running on localhost, use explicit port; otherwise use same port
  if (hostname === 'localhost' || hostname === '127.0.0.1') {
    return `http://${hostname}:${apiPort}`;
  }
  
  // For production, assume API is on same origin but different path or same port
  return `${window.location.protocol}//${hostname}:${apiPort}`;
};

export const API_BASE_URL = getApiBaseUrl();
