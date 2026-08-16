import { apiClient } from './client';
import type { QueryRequest, QueryResponse } from './types';

export const queryApi = {
  submitQuery: async (request: QueryRequest): Promise<QueryResponse> => {
    return apiClient<QueryResponse>('/query', {
      method: 'POST',
      body: JSON.stringify(request),
    });
  },
};
