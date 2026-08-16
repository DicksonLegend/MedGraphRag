import { apiClient } from './client';
import type { CareGapResult, CoverageMap, CoverageRequest, TrendResult } from './types';

export const featuresApi = {
  getTrends: async (): Promise<TrendResult> => {
    return apiClient<TrendResult>('/features/trend', {
      method: 'POST',
    });
  },

  getCareGaps: async (): Promise<CareGapResult> => {
    return apiClient<CareGapResult>('/features/caregap', {
      method: 'POST',
    });
  },

  getCoverageMap: async (request: CoverageRequest): Promise<CoverageMap> => {
    return apiClient<CoverageMap>('/features/coverage', {
      method: 'POST',
      body: JSON.stringify(request),
    });
  },
};
