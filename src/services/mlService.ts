import { api } from './api';

export interface MLStatus {
  trained: boolean;
  model_type: string;
  n_samples: number;
  accuracy: number;
  trained_at: string | null;
  min_samples_required: number;
}

export interface MLTrainResult extends MLStatus {
  success: boolean;
  message: string;
}

export interface FeatureImportanceItem {
  name: string;
  importance: number;
  direction: number; // mean SHAP: positive = pushes toward win, negative = toward loss
}

class MLService {
  private base = api.baseURL;

  async getStatus(): Promise<MLStatus> {
    const res = await fetch(`${this.base}/api/ml/status`);
    if (!res.ok) throw new Error(`ML status error: ${res.status}`);
    return res.json();
  }

  async train(): Promise<MLTrainResult> {
    const res = await fetch(`${this.base}/api/ml/train`, { method: 'POST' });
    if (!res.ok) throw new Error(`ML train error: ${res.status}`);
    return res.json();
  }

  async getFeatureImportance(): Promise<FeatureImportanceItem[]> {
    const res = await fetch(`${this.base}/api/ml/feature-importance`);
    if (!res.ok) throw new Error(`ML feature importance error: ${res.status}`);
    const data = await res.json();
    return data.features ?? [];
  }
}

export const mlService = new MLService();
