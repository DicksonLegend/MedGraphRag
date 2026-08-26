import { apiClient, API_BASE_URL } from './client';
import { useAuthStore } from '../stores/authStore';
import type { ImageAnalysisResult, MultimodalStatusResponse } from './types';

export const multimodalApi = {
  /**
   * Get service status and capabilities.
   */
  getStatus: async (): Promise<MultimodalStatusResponse> => {
    return apiClient<MultimodalStatusResponse>('/multimodal/status', {
      method: 'GET',
    });
  },

  /**
   * Upload and analyze a medical image (PNG, JPG, DICOM).
   * @param file Medical image file
   * @param mode 'triage' (fast zero-shot ~200ms) or 'full' (generative VLM on CPU)
   * @param customPrompt Optional prompt for generative interpretation
   */
  analyzeImage: async (
    file: File,
    mode: 'triage' | 'full' = 'triage',
    customPrompt?: string
  ): Promise<ImageAnalysisResult> => {
    const formData = new FormData();
    formData.append('file', file, file.name);
    formData.append('mode', mode);
    if (customPrompt) {
      formData.append('custom_prompt', customPrompt);
    }

    return apiClient<ImageAnalysisResult>('/multimodal/analyze-image', {
      method: 'POST',
      body: formData,
    });
  },

  /**
   * List all stored scans for the authenticated user.
   */
  listScans: async (): Promise<ImageAnalysisResult[]> => {
    return apiClient<ImageAnalysisResult[]>('/multimodal/scans', {
      method: 'GET',
    });
  },

  /**
   * Delete a scan and its encrypted metadata from private storage.
   */
  deleteScan: async (imageId: string): Promise<{ status: string; image_id: string }> => {
    return apiClient<{ status: string; image_id: string }>(`/multimodal/scans/${imageId}`, {
      method: 'DELETE',
    });
  },

  /**
   * Fetch authenticated preview image blob.
   */
  getPreviewBlob: async (imageId: string): Promise<Blob> => {
    const token = useAuthStore.getState().token;
    const headers: Record<string, string> = {};
    if (token) {
      headers['Authorization'] = `Bearer ${token}`;
    }

    const res = await fetch(`${API_BASE_URL}/multimodal/preview/${imageId}`, {
      method: 'GET',
      headers,
    });

    if (!res.ok) {
      throw new Error(`Failed to load scan preview (${res.status})`);
    }

    return res.blob();
  },
};
