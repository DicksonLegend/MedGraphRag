import { apiClient } from './client';
import type { LoginRequest, LogoutResponse, TokenResponse, UserClaims } from './types';

export const authApi = {
  login: async (credentials: LoginRequest): Promise<TokenResponse> => {
    return apiClient<TokenResponse>('/auth/login', {
      method: 'POST',
      body: JSON.stringify(credentials),
    });
  },

  guestLogin: async (): Promise<TokenResponse> => {
    return apiClient<TokenResponse>('/auth/guest', {
      method: 'POST',
    });
  },

  getMe: async (): Promise<UserClaims> => {
    return apiClient<UserClaims>('/auth/me', {
      method: 'GET',
    });
  },

  logout: async (): Promise<LogoutResponse> => {
    return apiClient<LogoutResponse>('/auth/logout', {
      method: 'POST',
    });
  },
};
