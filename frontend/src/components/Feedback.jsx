export function Loading({ label = 'Loading records…' }) {
  return (
    <div className="feedback" role="status">
      <span className="spinner" />
      {label}
    </div>
  );
}
export function ErrorNotice({ message, onRetry }) {
  return (
    <div className="notice error" role="alert">
      <span>{message}</span>
      {onRetry && (
        <button className="button secondary" onClick={onRetry}>
          Try again
        </button>
      )}
    </div>
  );
}
export function EmptyState({
  title = 'No records yet',
  description = 'Entries will appear here once they are added.',
}) {
  return (
    <div className="empty-state">
      <span className="empty-icon">✦</span>
      <h3>{title}</h3>
      <p>{description}</p>
    </div>
  );
}
export function StatusBadge({ value }) {
  const label = value === 'Dummy verified' ? 'Legacy demo' : value?.replaceAll('_', ' ');
  return (
    <span className={`badge ${String(value).toLowerCase().replaceAll(' ', '-')}`}>{label}</span>
  );
}
