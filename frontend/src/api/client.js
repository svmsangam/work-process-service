import axios from 'axios';

const api = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000/',
  headers: {
    'Content-Type': 'application/json',
  },
});

export const getWorkItems = (statusFilter) =>
  api.get('/work-items', { params: statusFilter ? { status: statusFilter } : undefined });

export const createWorkItem = (data) => api.post('/work-items', data);

export const analyzeWorkItemAI = (id) => api.post(`/work-items/${id}/analyse`);

export const retryWorkItemAI = (id) => api.post(`/work-items/${id}/retry`);

export const updateWorkItemStatus = (id, status) =>
  api.patch(`/work-items/${id}/status`, { status });

export default api;