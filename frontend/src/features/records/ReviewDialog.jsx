import { useState } from 'react';
import Modal from '../../components/Modal';
import { ErrorNotice, StatusBadge } from '../../components/Feedback';
import { reviewRecord } from '../../api/records';
import { errorMessage } from '../../api/client';
import { dateLabel, money, financeRoles } from '../../utils/format';
import { useAuth } from '../../context/AuthContext';

export default function ReviewDialog({ resource, record, year, onClose, onSaved }) {
  const { user } = useAuth();
  const [action, setAction] = useState(record.status === 'pending' ? 'approve' : 'void');
  const [note, setNote] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const allowed =
    financeRoles.includes(user.role) &&
    record.created_by !== user.id &&
    ['pending', 'approved', 'confirmed', 'Dummy verified'].includes(record.status);
  const submit = async (event) => {
    event.preventDefault();
    setBusy(true);
    setError('');
    try {
      await reviewRecord(resource, record.id, { action, note }, year);
      onSaved();
    } catch (error) {
      setError(errorMessage(error));
    } finally {
      setBusy(false);
    }
  };
  return (
    <Modal title="Entry details & review" onClose={onClose} busy={busy}>
      <div className="entry-detail">
        <div className="entry-detail-title">
          <h3>{record.description || record.donor_name}</h3>
          <StatusBadge value={record.status} />
        </div>
        <strong className="detail-amount">{money(record.amount)}</strong>
        <dl className="detail-grid">
          {[
            ['Date', dateLabel(record.spent_on || record.paid_on)],
            ['Recorded by', record.created_by_name],
            ['Vendor / method', record.vendor || record.method],
            [
              'Receipt / transaction',
              record.receipt_reference || record.transaction_reference || 'Not provided',
            ],
            ['Budget', record.plan_title || 'Not linked'],
            ['Notes', record.notes || '—'],
            ['Reviewed by', record.reviewed_by_name || 'Not reviewed'],
            ['Review note', record.review_note || '—'],
          ].map(([label, value]) => (
            <div key={label}>
              <dt>{label}</dt>
              <dd>{value}</dd>
            </div>
          ))}
        </dl>
        {record.evidence_url && /^https?:\/\//i.test(record.evidence_url) && (
          <a href={record.evidence_url} target="_blank" rel="noreferrer" className="text-link">
            Open receipt evidence ↗
          </a>
        )}
        {record.created_by === user.id && (
          <p className="notice info">Another administrator or treasurer must review your entry.</p>
        )}
        {allowed && (
          <form onSubmit={submit} className="review-form">
            <label>
              Decision
              <select value={action} onChange={(e) => setAction(e.target.value)}>
                {record.status === 'pending' ? (
                  <>
                    <option value="approve">Approve entry</option>
                    <option value="reject">Reject entry</option>
                  </>
                ) : (
                  <option value="void">Void this entry</option>
                )}
              </select>
            </label>
            <label>
              Review reason
              <textarea
                required
                rows={3}
                maxLength={500}
                placeholder="Describe the evidence checked or the reason for this decision."
                value={note}
                onChange={(e) => setNote(e.target.value)}
              />
            </label>
            {error && <ErrorNotice message={error} />}
            <button className="button primary" disabled={busy}>
              {busy ? 'Saving decision…' : 'Save review decision'}
            </button>
          </form>
        )}
      </div>
    </Modal>
  );
}
