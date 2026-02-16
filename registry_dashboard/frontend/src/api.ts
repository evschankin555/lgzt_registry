import axios from 'axios';

const API_BASE = '/api';

const api = axios.create({
  baseURL: API_BASE,
});

// Добавляем токен к каждому запросу
api.interceptors.request.use((config) => {
  const token = localStorage.getItem('token');
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

export const login = async (password: string) => {
  const response = await api.post('/login', { password });
  return response.data;
};

export const getStats = async () => {
  const response = await api.get('/stats');
  return response.data;
};

export const getUsers = async (page = 0, limit = 20, status?: string, search?: string) => {
  const response = await api.get('/users', { params: { page, limit, status, search } });
  return response.data;
};

export const getUser = async (userId: number) => {
  const response = await api.get(`/users/${userId}`);
  return response.data;
};

export const updateUser = async (userId: number, data: any) => {
  const response = await api.patch(`/users/${userId}`, data);
  return response.data;
};

export const deleteUser = async (userId: number) => {
  const response = await api.delete(`/users/${userId}`);
  return response.data;
};

export const getCompanies = async () => {
  const response = await api.get('/companies');
  return response.data;
};

export const getVolunteers = async () => {
  const response = await api.get('/volunteers');
  return response.data;
};

export const updateVolunteer = async (volunteerId: number, name: string) => {
  const response = await api.patch(`/volunteers/${volunteerId}`, { name });
  return response.data;
};

export const deleteVolunteer = async (volunteerId: number) => {
  const response = await api.delete(`/volunteers/${volunteerId}`);
  return response.data;
};

export const exportExcel = async () => {
  const response = await api.get('/export/excel', { responseType: 'blob' });
  const url = window.URL.createObjectURL(new Blob([response.data]));
  const link = document.createElement('a');
  link.href = url;
  link.setAttribute('download', 'registry_export.xlsx');
  document.body.appendChild(link);
  link.click();
  link.remove();
};

export default api;
