import api from './client';
export const listRecords = (resource, params, signal) =>
  api.get(`/${resource}/`, { params, signal });
export const createRecord = (resource, payload, submissionKey) =>
  api.post(`/${resource}/`, payload, { headers: { 'Idempotency-Key': submissionKey } });
export const updateRecord = (resource, id, payload, year) =>
  api.patch(`/${resource}/${id}/`, payload, { params: { year } });
export const reviewRecord = (resource, id, payload, year) =>
  api.post(`/${resource}/${id}/review/`, payload, { params: { year } });
export async function exportRecords(resource, params, format = 'csv') {
  const response = await api.get(`/export/${resource}/`, {
    params: { ...params, file_format: format },
    responseType: 'blob',
  });
  const url = URL.createObjectURL(response.data);
  const link = document.createElement('a');
  link.href = url;
  link.download = `ganesh-${resource}-${params.year}.${format}`;
  document.body.append(link);
  link.click();
  link.remove();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}
