import { useEffect, useState } from 'react';
import Modal from '../../components/Modal';
import { ErrorNotice } from '../../components/Feedback';
import { errorMessage } from '../../api/client';
import { createRecord, updateRecord, listRecords } from '../../api/records';

export default function RecordForm({ resource, config, year, record, onClose, onSaved }) {
  const [submissionKey] = useState(() => crypto.randomUUID());
  const [form, setForm] = useState(() =>
    record
      ? Object.fromEntries(config.fields.map((field) => [field.name, record[field.name] ?? '']))
      : config.defaults(year),
  );
  const [plans, setPlans] = useState([]);
  const [planSearch, setPlanSearch] = useState('');
  const [planError, setPlanError] = useState('');
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  useEffect(() => {
    if (resource !== 'expenses') return;
    const controller = new AbortController();
    const timer = setTimeout(() => {
      listRecords('plans', { year, search: planSearch, page_size: 100 }, controller.signal)
        .then(({ data }) => {
          setPlans(data.results);
          setPlanError(data.count > 100 ? 'More than 100 budgets match. Refine the search.' : '');
        })
        .catch((error) => {
          if (!controller.signal.aborted) setPlanError(errorMessage(error));
        });
    }, 200);
    return () => {
      clearTimeout(timer);
      controller.abort();
    };
  }, [resource, year, planSearch]);
  const submit = async (event) => {
    event.preventDefault();
    setBusy(true);
    setError('');
    const payload = { ...form };
    if ('plan' in payload) payload.plan = payload.plan ? Number(payload.plan) : null;
    if (resource === 'payments') payload.paid_on = new Date(payload.paid_on).toISOString();
    try {
      if (record) await updateRecord(resource, record.id, payload, year);
      else await createRecord(resource, payload, submissionKey);
      onSaved();
    } catch (error) {
      setError(errorMessage(error));
    } finally {
      setBusy(false);
    }
  };
  return (
    <Modal title={`${record ? 'Edit' : 'Add'} ${config.singular}`} onClose={onClose} busy={busy}>
      <form onSubmit={submit} className="record-form">
        {config.review && (
          <p className="notice info">
            This entry will be pending until another administrator or treasurer reviews it.
            Submitted financial entries cannot be overwritten.
          </p>
        )}
        <div className="form-grid">
          {config.fields.map((field) => (
            <label
              className={field.type === 'textarea' || field.type === 'plan' ? 'span-two' : ''}
              key={field.name}
            >
              {field.label}
              {field.optional && <span className="optional">Optional</span>}
              {field.type === 'select' ? (
                <select
                  value={form[field.name]}
                  onChange={(e) => setForm({ ...form, [field.name]: e.target.value })}
                >
                  {field.options.map((option) => (
                    <option key={option}>{option}</option>
                  ))}
                </select>
              ) : field.type === 'textarea' ? (
                <textarea
                  rows={3}
                  value={form[field.name]}
                  onChange={(e) => setForm({ ...form, [field.name]: e.target.value })}
                />
              ) : field.type === 'plan' ? (
                <>
                  <input
                    aria-label="Search linked budgets"
                    placeholder="Search budgets…"
                    value={planSearch}
                    onChange={(e) => setPlanSearch(e.target.value)}
                  />
                  <select
                    value={form.plan}
                    onChange={(e) => setForm({ ...form, plan: e.target.value })}
                  >
                    <option value="">No linked budget</option>
                    {plans.map((plan) => (
                      <option value={plan.id} key={plan.id}>
                        {plan.title}
                      </option>
                    ))}
                  </select>
                  {planError && <small className="field-error">{planError}</small>}
                </>
              ) : field.type === 'checkbox' ? (
                <input
                  type="checkbox"
                  checked={form[field.name]}
                  onChange={(e) => setForm({ ...form, [field.name]: e.target.checked })}
                />
              ) : (
                <input
                  type={field.type}
                  value={form[field.name]}
                  onChange={(e) => setForm({ ...form, [field.name]: e.target.value })}
                  required={!field.optional}
                  min={field.min}
                  step={field.step}
                  maxLength={field.type === 'url' ? 200 : undefined}
                />
              )}
              {field.help && <small>{field.help}</small>}
            </label>
          ))}
        </div>
        {error && <ErrorNotice message={error} />}
        <div className="form-actions">
          <button type="button" className="button secondary" disabled={busy} onClick={onClose}>
            Cancel
          </button>
          <button className="button primary" disabled={busy}>
            {busy ? 'Saving…' : config.review ? 'Submit for review' : 'Save record'}
          </button>
        </div>
      </form>
    </Modal>
  );
}
