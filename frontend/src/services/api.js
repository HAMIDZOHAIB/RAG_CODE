// src/services/api.js
import axios from 'axios';

const API_BASE_URL = import.meta.env.VITE_API_URL

const api = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
  timeout: 30000,
});

export const chatAPI = {
  sendQuery: async (sessionId, query) => {
    const response = await api.post('/query', {
      session_id: sessionId,
      query,
    });
    return response.data;
  },

  getChatHistory: async (sessionId) => {
    const response = await api.get(`/history/${sessionId}`);
    return response.data;
  },

  clearHistory: async (sessionId) => {
    const response = await api.post('/clear-history', {
      session_id: sessionId,
    });
    return response.data;
  },
};

export default api;