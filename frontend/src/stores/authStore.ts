import { create } from 'zustand';
import { authApi } from '../api/auth';
import type { LoginRequest, UserClaims } from '../api/types';
import { useSessionStore } from './sessionStore';

interface AuthState {
  token: string | null;
  user_id: string | null;
  role: string | null;
  ephemeral: boolean;
  expires_in_minutes: number;
  isAuthenticated: boolean;
  isLoading: boolean;
  isInitialized: boolean;

  login: (credentials: LoginRequest) => Promise<void>;
  guestLogin: () => Promise<void>;
  restoreSession: () => Promise<boolean>;
  logout: () => Promise<boolean>; // returns guest_store_purged flag
  clearAuth: () => void;
}

export const useAuthStore = create<AuthState>((set, get) => ({
  token: sessionStorage.getItem('medgraph_token'),
  user_id: null,
  role: null,
  ephemeral: false,
  expires_in_minutes: 0,
  isAuthenticated: !!sessionStorage.getItem('medgraph_token'),
  isLoading: false,
  isInitialized: false,

  login: async (credentials: LoginRequest) => {
    set({ isLoading: true });
    try {
      const tokenRes = await authApi.login(credentials);
      sessionStorage.setItem('medgraph_token', tokenRes.token);
      
      // Fetch user claims via /auth/me
      const claims = await authApi.getMe();
      set({
        token: tokenRes.token,
        user_id: claims.user_id,
        role: claims.role,
        ephemeral: claims.ephemeral,
        expires_in_minutes: claims.expires_in_minutes,
        isAuthenticated: true,
        isLoading: false,
        isInitialized: true,
      });
    } catch (error) {
      set({ isLoading: false });
      throw error;
    }
  },

  guestLogin: async () => {
    set({ isLoading: true });
    try {
      const tokenRes = await authApi.guestLogin();
      sessionStorage.setItem('medgraph_token', tokenRes.token);

      const claims = await authApi.getMe();
      set({
        token: tokenRes.token,
        user_id: claims.user_id,
        role: claims.role,
        ephemeral: true,
        expires_in_minutes: claims.expires_in_minutes,
        isAuthenticated: true,
        isLoading: false,
        isInitialized: true,
      });
    } catch (error) {
      set({ isLoading: false });
      throw error;
    }
  },

  restoreSession: async () => {
    const existingToken = sessionStorage.getItem('medgraph_token');
    if (!existingToken) {
      set({ isInitialized: true, isAuthenticated: false, isLoading: false });
      return false;
    }

    set({ isLoading: true });
    try {
      const claims = await authApi.getMe();
      set({
        token: existingToken,
        user_id: claims.user_id,
        role: claims.role,
        ephemeral: claims.ephemeral,
        expires_in_minutes: claims.expires_in_minutes,
        isAuthenticated: true,
        isLoading: false,
        isInitialized: true,
      });
      return true;
    } catch {
      sessionStorage.removeItem('medgraph_token');
      useSessionStore.getState().clearSession();
      set({
        token: null,
        user_id: null,
        role: null,
        ephemeral: false,
        expires_in_minutes: 0,
        isAuthenticated: false,
        isLoading: false,
        isInitialized: true,
      });
      return false;
    }
  },

  logout: async () => {
    set({ isLoading: true });
    let guestPurged = false;
    try {
      const res = await authApi.logout();
      guestPurged = res.guest_store_purged;
    } catch {
      // Proceed with client cleanup regardless
    } finally {
      sessionStorage.removeItem('medgraph_token');
      useSessionStore.getState().clearSession();

      set({
        token: null,
        user_id: null,
        role: null,
        ephemeral: false,
        expires_in_minutes: 0,
        isAuthenticated: false,
        isLoading: false,
      });
    }
    return guestPurged;
  },

  clearAuth: () => {
    sessionStorage.removeItem('medgraph_token');
    useSessionStore.getState().clearSession();

    set({
      token: null,
      user_id: null,
      role: null,
      ephemeral: false,
      expires_in_minutes: 0,
      isAuthenticated: false,
      isLoading: false,
    });
  },
}));

// Listen for 401 unauthorized events globally to clear store
if (typeof window !== 'undefined') {
  window.addEventListener('auth:unauthorized', () => {
    useAuthStore.getState().clearAuth();
  });
}
