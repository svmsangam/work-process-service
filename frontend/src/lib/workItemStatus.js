// Mirrors backend WorkItemStatus (app/models.py). READY_FOR_REVIEW sits between
// ANALYSING and COMPLETED: it's when ai_analysis is populated and the item is
// awaiting a human to mark it COMPLETED.
export const WORK_ITEM_STATUSES = [
  {
    value: 'RECEIVED',
    label: 'Pending',
    badgeClass: 'bg-yellow-100 text-yellow-800 border-yellow-200',
  },
  {
    value: 'ANALYSING',
    label: 'Analyzing',
    badgeClass: 'bg-blue-100 text-blue-800 border-blue-200 animate-pulse',
  },
  {
    value: 'READY_FOR_REVIEW',
    label: 'Ready for Review',
    badgeClass: 'bg-purple-100 text-purple-800 border-purple-200',
  },
  {
    value: 'COMPLETED',
    label: 'Completed',
    badgeClass: 'bg-green-100 text-green-800 border-green-200',
  },
  {
    value: 'FAILED',
    label: 'Failed',
    badgeClass: 'bg-red-100 text-red-800 border-red-200',
  },
];

export const FILTER_OPTIONS = [
  { value: '', label: 'All' },
  ...WORK_ITEM_STATUSES.map(({ value, label }) => ({ value, label })),
];

const FALLBACK_STATUS_META = {
  label: 'Unknown',
  badgeClass: 'bg-slate-100 text-slate-700 border-slate-200',
};

export function getStatusMeta(status) {
  return WORK_ITEM_STATUSES.find((s) => s.value === status) ?? { value: status, ...FALLBACK_STATUS_META };
}
