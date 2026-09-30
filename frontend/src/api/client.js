/**
 * API Client for connecting to the FastAPI backend.
 * Uses window.APP_CONFIG.API_BASE_URL injected via public/config.js.
 */

const getBaseUrl = () => {
  return window?.APP_CONFIG?.API_BASE_URL || 'http://localhost:8080';
};

class ApiClient {
  constructor() {
    this.baseUrl = getBaseUrl();
  }

  async _fetch(endpoint, options = {}) {
    const url = `${this.baseUrl}/api/v1${endpoint}`;
    const headers = {
      'Content-Type': 'application/json',
      ...options.headers,
    };

    try {
      const response = await fetch(url, { ...options, headers });
      const data = await response.json();
      
      if (!response.ok || !data.success) {
        throw new Error(data.error || `HTTP error ${response.status}`);
      }
      
      return data.data;
    } catch (error) {
      console.error(`API Error on ${endpoint}:`, error);
      throw error;
    }
  }

  // Apps
  async getApps() {
    return this._fetch('/apps');
  }

  async createApp(name, description) {
    return this._fetch('/apps', {
      method: 'POST',
      body: JSON.stringify({ name, description }),
    });
  }

  // Incidents
  async getIncidents(page = 1, status = null) {
    const query = new URLSearchParams({ page });
    if (status) query.append('status', status);
    return this._fetch(`/incidents?${query.toString()}`);
  }

  async getIncident(id) {
    return this._fetch(`/incidents/${id}`);
  }

  async getCorrelatedIncidents(id) {
    return this._fetch(`/incidents/${id}/correlated`);
  }

  async resolveIncident(id) {
    return this._fetch(`/incidents/${id}/resolve`, {
      method: 'PATCH',
      body: JSON.stringify({}),
    });
  }

  async markFalsePositive(id) {
    return this._fetch(`/incidents/${id}/status`, {
      method: 'PATCH',
      body: JSON.stringify({ status: 'false_positive' }),
    });
  }

  async rateFix(id, rating) {
    return this._fetch(`/incidents/${id}/rate`, {
      method: 'PATCH',
      body: JSON.stringify({ rating }),
    });
  }

  // Analytics
  async getAnalyticsOverview() {
    return this._fetch('/analytics/overview');
  }

  async getMttrTrend() {
    return this._fetch('/analytics/mttr');
  }

  async getSeverityBreakdown() {
    return this._fetch('/analytics/severity');
  }

  async getErrorRanking() {
    return this._fetch('/analytics/errors');
  }
}

export const api = new ApiClient();
