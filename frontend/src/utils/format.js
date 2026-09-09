export const money = (value) =>
  new Intl.NumberFormat('en-IN', {
    style: 'currency',
    currency: 'INR',
    maximumFractionDigits: 2,
  }).format(Number(value || 0));
export const dateLabel = (value) =>
  value
    ? new Date(value).toLocaleDateString('en-IN', {
        day: '2-digit',
        month: 'short',
        year: 'numeric',
        timeZone: 'Asia/Kolkata',
      })
    : '—';
export const managementRoles = ['admin', 'treasurer', 'secretary', 'coordinator'];
export const financeRoles = ['admin', 'treasurer'];
export const categories = [
  'Decoration',
  'Pooja & rituals',
  'Food & prasadam',
  'Cultural programs',
  'Sound & lighting',
  'Procession',
  'Safety & sanitation',
  'Operations',
  'Other',
];
export const today = () => new Date().toLocaleDateString('en-CA', { timeZone: 'Asia/Kolkata' });
