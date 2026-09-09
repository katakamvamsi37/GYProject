import api from './client';
export const getDashboard = (year, signal) => api.get('/dashboard/', { params: { year }, signal });
