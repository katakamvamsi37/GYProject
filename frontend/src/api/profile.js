import apiClient from './client';

export const getProfile = (userId) => apiClient.get(`/profiles/${userId}/`);
export const updateProfile = (userId, payload) => apiClient.patch(`/profiles/${userId}/`, payload);
