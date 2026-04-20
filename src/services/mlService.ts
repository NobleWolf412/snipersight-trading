const BASE = typeof import.meta !== 'undefined' && (import.meta as any).env?.VITE_API_BASE
  ? (import.meta as any).env.VITE_API_BASE
  : '/api';

export interface MLStatus {
  trained: boolean;
  model_type: string;
  n_samples: number;
  accuracy: number;
  trained_at: string | null;
  min_samples_required: number;
}

export interface MLTrainResult {
  success: boolean;
  message: string;
  model_type?: string;
  n_samples?: number;
  n_trades?: number;
  n_signals?: number;
  accuracy?: number;
  trained_at?: string | null;
}

export interface FeatureImportanceItem {
  name: string;
  importance: number;
  direction: number; // mean SHAP: positive = pushes toward win, negative = toward loss
}

class MLService {
  private base = BASE;

  async getStatus(): Promise<MLStatus> {
    const res = await fetch(`${this.base}/ml/status`);
    if (!res.ok) throw new Error(`ML status error: ${res.status}`);
    return res.json();
  }

  async train(): Promise<MLTrainResult> {
    const res = await fetch(`${this.base}/ml/train`, { method: 'POST' });
    if (!res.ok) throw new Error(`ML train error: ${res.status}`);
    return res.json();
  }

  async getFeatureImportance(): Promise<FeatureImportanceItem[]> {
    const res = await fetch(`${this.base}/ml/feature-importance`);
    if (!res.ok) throw new Error(`ML feature importance error: ${res.status}`);
    const data = await res.json();
    return data.features ?? [];
  }

  async getGateRecommendations(): Promise<GateRecommendation[]> {
    const res = await fetch(`${this.base}/ml/gate-recommendations`);
    if (!res.ok) throw new Error(`ML gate recommendations error: ${res.status}`);
    const data = await res.json();
    return data.recommendations ?? [];
  }

  async clearSessionLogs(): Promise<{ success: boolean; message: string; deleted_sessions: number; deleted_signals: number }> {
    const res = await fetch(`${this.base}/ml/session-logs`, { method: 'DELETE' });
    if (!res.ok) throw new Error(`Clear session logs error: ${res.status}`);
    return res.json();
  }

  async resetModel(): Promise<{ success: boolean; message: string; deleted_file: boolean }> {
    const res = await fetch(`${this.base}/ml/model`, { method: 'DELETE' });
    if (!res.ok) throw new Error(`Reset model error: ${res.status}`);
    return res.json();
  }

  async predict(params: {
    confidence_score?: number;
    risk_reward_ratio?: number;
    direction?: string;
    trade_type?: string;
    regime?: string;
  }): Promise<{ win_probability: number | null }> {
    const qs = new URLSearchParams();
    if (params.confidence_score != null) qs.set('confidence_score', String(params.confidence_score));
    if (params.risk_reward_ratio != null) qs.set('risk_reward_ratio', String(params.risk_reward_ratio));
    if (params.direction) qs.set('direction', params.direction);
    if (params.trade_type) qs.set('trade_type', params.trade_type);
    if (params.regime) qs.set('regime', params.regime);
    const res = await fetch(`${this.base}/ml/predict?${qs.toString()}`);
    if (!res.ok) throw new Error(`ML predict error: ${res.status}`);
    return res.json();
  }
}

export interface GateRecommendation {
  gate: string;
  description: string;
  feature: string;
  shap_importance: number;
  shap_direction: number;
  recommendation: string;
}

export const mlService = new MLService();
