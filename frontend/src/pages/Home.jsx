import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import {
  Wallet,
  ArrowDownLeft,
  ArrowUpRight,
  ShieldCheck,
  Plus,
  Flower2,
  ClipboardCheck,
} from 'lucide-react';
import { getDashboard } from '../api/dashboard';
import { errorMessage } from '../api/client';
import { useAuth } from '../context/AuthContext';
import { useFestival } from '../context/FestivalContext';
import { Loading, ErrorNotice, EmptyState, StatusBadge } from '../components/Feedback';
import { money, dateLabel, managementRoles } from '../utils/format';
import SpendingChart from '../features/dashboard/SpendingChart';

export default function Home() {
  const { year } = useFestival();
  const { user } = useAuth();
  const [data, setData] = useState(null);
  const [error, setError] = useState('');
  const [revision, setRevision] = useState(0);
  useEffect(() => {
    const controller = new AbortController();
    setData(null);
    setError('');
    getDashboard(year, controller.signal)
      .then(({ data }) => {
        if (!controller.signal.aborted) setData(data);
      })
      .catch((error) => {
        if (!controller.signal.aborted) setError(errorMessage(error));
      });
    return () => controller.abort();
  }, [year, revision]);
  const management = managementRoles.includes(user.role);
  return (
    <>
      <div className="page-heading">
        <div>
          <h1>
            Festival overview<span className="heading-dot">.</span>
          </h1>
          <p>
            Welcome, {user.name.split(' ')[0]}. Here’s where your {year} celebration stands.
          </p>
        </div>
        {management && (
          <Link className="button primary" to="/collections">
            <Plus size={16} />
            Record a collection
          </Link>
        )}
      </div>
      <section className="festival-banner">
        <div>
          <span className="eyebrow">CELEBRATE WITH PURPOSE</span>
          <h2>One community. A thousand contributions.</h2>
          <p>Keep the celebration joyful and the accounts clear.</p>
        </div>
        <div className="banner-seal" aria-hidden="true">
          <Flower2 size={65} />
          <span>GANESH UTSAV {year}</span>
        </div>
      </section>
      {error ? (
        <ErrorNotice message={error} onRetry={() => setRevision((x) => x + 1)} />
      ) : !data ? (
        <Loading />
      ) : (
        <>
          <section className="metrics" aria-label="Festival financial summary">
            {[
              [
                'Confirmed collections',
                data.collected,
                'Reviewed contributions received',
                ArrowDownLeft,
                'green',
              ],
              ['Approved expenses', data.spent, 'Reviewed spending only', ArrowUpRight, 'orange'],
              [
                'Recorded fund balance',
                data.cash_balance,
                'Collections minus approved expenses',
                Wallet,
                'dark',
              ],
              [
                'Festival budget',
                data.budget,
                `${money(data.remaining_budget)} budget remaining`,
                ClipboardCheck,
                'purple',
              ],
            ].map(([label, value, note, Icon, tone]) => (
              <article className={`metric ${tone}`} key={label}>
                <div className="metric-label">
                  {label}
                  <span className="metric-icon">
                    <Icon size={18} />
                  </span>
                </div>
                <strong>{money(value)}</strong>
                <small>{note}</small>
              </article>
            ))}
          </section>
          <div className="dashboard-grid">
            <section className="panel">
              <div className="panel-heading">
                <div>
                  <h2>Spending through the year</h2>
                  <p>Approved expenses · {year}</p>
                </div>
                <span className="chart-legend">
                  <i /> Expenses
                </span>
              </div>
              <SpendingChart data={data.monthly_spend} />
            </section>
            <section className="panel audit-health">
              <div className="panel-heading">
                <div>
                  <h2>Review desk</h2>
                  <p>A little attention, a clearer ledger.</p>
                </div>
                <ShieldCheck size={22} />
              </div>
              <div className="review-stat">
                <span>Expenses awaiting review</span>
                <b>{data.pending_expenses}</b>
              </div>
              <div className="review-stat">
                <span>Collections awaiting review</span>
                <b>{data.pending_collections}</b>
              </div>
              <div className="review-stat">
                <span>Expenses without receipt evidence</span>
                <b>{data.missing_receipts}</b>
              </div>
              <div className="review-stat">
                <span>Active committee & volunteers</span>
                <b>{data.members}</b>
              </div>
              {data.legacy_payments > 0 && (
                <p className="notice warning">
                  {data.legacy_payments} legacy demo collection(s) excluded from totals.
                </p>
              )}
              {management && (
                <Link className="button secondary full-width" to="/expenses?status=pending">
                  Review expense entries
                  <ArrowUpRight size={16} />
                </Link>
              )}
              <p className="fine-print">
                Pending entries are excluded from posted totals. Fund balance is not a bank
                reconciliation.
              </p>
            </section>
          </div>
          <div className="dashboard-grid bottom-grid">
            <section className="panel">
              <div className="panel-heading">
                <div>
                  <h2>Recent expense entries</h2>
                  <p>Latest records and their review status</p>
                </div>
                {management && (
                  <Link className="text-link" to="/expenses">
                    Full ledger
                    <ArrowUpRight size={15} />
                  </Link>
                )}
              </div>
              {!management ? (
                <EmptyState
                  title="Committee-managed records"
                  description="Your role has access to festival summary totals."
                />
              ) : !data.recent_expenses.length ? (
                <EmptyState
                  title="Your ledger starts here"
                  description="Add your first festival expense to begin the audit trail."
                />
              ) : (
                <div className="recent-list">
                  {data.recent_expenses.map((item) => (
                    <div className="recent-row" key={item.id}>
                      <span className="entry-symbol">
                        <ArrowUpRight size={18} />
                      </span>
                      <div>
                        <strong>{item.description}</strong>
                        <small>
                          {item.category} · {dateLabel(item.spent_on)}
                        </small>
                      </div>
                      <StatusBadge value={item.status} />
                      <b>{money(item.amount)}</b>
                    </div>
                  ))}
                </div>
              )}
            </section>
            <section className="panel">
              <div className="panel-heading">
                <div>
                  <h2>Where we’re spending</h2>
                  <p>Approved expenses by category</p>
                </div>
              </div>
              {!data.expenses_by_category.length ? (
                <EmptyState
                  title="No approved spending"
                  description="Categories appear after expense approval."
                />
              ) : (
                <div className="category-list">
                  {data.expenses_by_category.map((item, i) => (
                    <div key={item.category}>
                      <div>
                        <span>
                          <i
                            style={{
                              background: ['#c65c30', '#dfab52', '#568578', '#8582a3'][i % 4],
                            }}
                          />
                          {item.category}
                        </span>
                        <strong>{money(item.amount)}</strong>
                      </div>
                      <div className="progress-track">
                        <span
                          style={{
                            width: `${Math.min(100, (Number(item.amount) / Number(data.spent || 1)) * 100)}%`,
                          }}
                        />
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </section>
          </div>
        </>
      )}
    </>
  );
}
