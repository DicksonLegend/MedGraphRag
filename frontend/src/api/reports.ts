import { apiClient } from './client';
import type { ReportDetailResponse, ReportResponse, ReportSummaryItem } from './types';

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

  getReportDetail: async (reportId: string): Promise<ReportDetailResponse> => {
    return apiClient<ReportDetailResponse>(`/reports/${reportId}`, {
      method: 'GET',
    });
  },

  purgeReport: async (reportId: string): Promise<{ status: string; report_id: string }> => {
    return apiClient<{ status: string; report_id: string }>(`/reports/${reportId}`, {
      method: 'DELETE',
    });
  },
};
