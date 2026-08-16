import { apiClient } from './client';
import type { ReportResponse, ReportSummaryItem } from './types';

export const reportsApi = {
  uploadReport: async (file: File): Promise<ReportResponse> => {
    const formData = new FormData();
    formData.append('file', file, file.name);

    return apiClient<ReportResponse>('/report', {
      method: 'POST',
      body: formData,
    });
  },

  listReports: async (): Promise<ReportSummaryItem[]> => {
    return apiClient<ReportSummaryItem[]>('/reports', {
      method: 'GET',
    });
  },
};
