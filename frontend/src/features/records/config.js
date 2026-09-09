import { categories, dateLabel, money, today } from '../../utils/format';

const field = (name, label, type = 'text', extra = {}) => ({ name, label, type, ...extra });
const category = field('category', 'Category', 'select', { options: categories });
const amount = field('amount', 'Amount (₹)', 'number', { min: '0.01', step: '0.01' });
const evidence = [
  field('evidence_url', 'Receipt / evidence URL', 'url', {
    optional: true,
    help: 'Link to a receipt in your committee’s shared storage.',
  }),
  field('notes', 'Notes', 'textarea', { optional: true }),
];
export const recordConfig = {
  plans: {
    title: 'Festival budgets',
    description: 'Give every part of the celebration a clear spending plan.',
    singular: 'budget',
    writeRoles: ['admin', 'treasurer'],
    defaults: (year) => ({
      title: '',
      category: categories[0],
      budget: '',
      target_date: `${year}-09-01`,
      status: 'Planning',
    }),
    fields: [
      field('title', 'Budget title'),
      category,
      field('budget', 'Planned budget (₹)', 'number', { min: '0.01', step: '0.01' }),
      field('target_date', 'Target date', 'date'),
      field('status', 'Progress', 'select', {
        options: ['Planning', 'In progress', 'Completed', 'Cancelled'],
      }),
    ],
    columns: [
      ['title', 'Budget / activity'],
      ['category', 'Category'],
      ['budget', 'Budget', money],
      ['spent', 'Approved spending', money],
      ['target_date', 'Target date', dateLabel],
      ['status', 'Progress'],
    ],
  },
  expenses: {
    title: 'Expense ledger',
    description: 'Record festival spending, attach evidence, and keep every approval traceable.',
    singular: 'expense',
    writeRoles: ['admin', 'treasurer', 'secretary', 'coordinator'],
    review: true,
    defaults: (year) => ({
      description: '',
      category: categories[0],
      amount: '',
      spent_on: year === new Date().getFullYear() ? today() : `${year}-09-01`,
      plan: '',
      vendor: '',
      receipt_reference: '',
      evidence_url: '',
      notes: '',
    }),
    fields: [
      field('description', 'What was the expense for?'),
      category,
      amount,
      field('spent_on', 'Expense date', 'date'),
      field('vendor', 'Vendor / paid to'),
      field('receipt_reference', 'Receipt / voucher number'),
      field('plan', 'Linked budget', 'plan', { optional: true }),
      ...evidence,
    ],
    columns: [
      ['description', 'Description'],
      ['category', 'Category'],
      ['vendor', 'Paid to'],
      ['amount', 'Amount', money],
      ['spent_on', 'Date', dateLabel],
      ['status', 'Review status'],
    ],
  },
  payments: {
    title: 'Collections',
    description: 'Record actual contributions received. A second reviewer confirms each entry.',
    singular: 'collection',
    writeRoles: ['admin', 'treasurer', 'secretary', 'coordinator'],
    review: true,
    defaults: (year) => ({
      donor_name: '',
      amount: '',
      method: 'Cash',
      paid_on: `${year === new Date().getFullYear() ? today() : year + '-09-01'}T12:00`,
      transaction_reference: '',
      evidence_url: '',
      notes: '',
    }),
    fields: [
      field('donor_name', 'Contributor name'),
      amount,
      field('method', 'Payment method', 'select', {
        options: ['Cash', 'UPI', 'Bank transfer', 'Cheque'],
      }),
      field('paid_on', 'Received on', 'datetime-local'),
      field('transaction_reference', 'Bank / UPI / cheque reference', 'text', {
        optional: true,
        help: 'Required for every non-cash contribution.',
      }),
      ...evidence,
    ],
    columns: [
      ['donor_name', 'Contributor'],
      ['reference', 'Receipt ID'],
      ['method', 'Method'],
      ['amount', 'Amount', money],
      ['paid_on', 'Received', dateLabel],
      ['status', 'Review status'],
    ],
  },
  members: {
    title: 'Committee & volunteers',
    description:
      'Keep responsibilities and contact details in one place. Login access is managed separately.',
    singular: 'member',
    writeRoles: ['admin', 'secretary'],
    defaults: () => ({
      name: '',
      email: '',
      phone: '',
      position: 'Volunteer',
      authority: 'Festival volunteer',
      active: true,
    }),
    fields: [
      field('name', 'Full name'),
      field('email', 'Email address', 'email'),
      field('phone', 'Mobile number', 'tel', { optional: true }),
      field('position', 'Position / responsibility'),
      field('authority', 'Scope of responsibility'),
      field('active', 'Active volunteer', 'checkbox'),
    ],
    columns: [
      ['name', 'Name'],
      ['position', 'Responsibility'],
      ['email', 'Email'],
      ['phone', 'Phone'],
      ['authority', 'Authority'],
      ['active', 'Status', (value) => (value ? 'Active' : 'Inactive')],
    ],
  },
  audit: {
    title: 'Audit trail',
    description:
      'A chronological record of submissions, reviews, account changes, and budget updates.',
    singular: 'event',
    writeRoles: [],
    columns: [
      ['created_at', 'When', dateLabel],
      ['actor_name', 'Who'],
      ['action', 'Action'],
      ['resource', 'Record type'],
      ['object_id', 'Record ID'],
      ['summary', 'Details'],
    ],
  },
};
