import React from 'react';
import { PackageOpen } from 'lucide-react';
import clsx from 'clsx';
import WorkItemCard from './WorkItemCard';
import { FILTER_OPTIONS } from '../lib/workItemStatus';

function ListSkeleton() {
  return (
    <div className="space-y-3">
      {[0, 1, 2].map((i) => (
        <div key={i} className="bg-white p-5 rounded-xl border border-slate-200 shadow-sm animate-pulse">
          <div className="h-4 w-24 bg-slate-200 rounded mb-3" />
          <div className="h-4 w-2/3 bg-slate-200 rounded mb-2" />
          <div className="h-3 w-full bg-slate-100 rounded" />
        </div>
      ))}
    </div>
  );
}

export default function WorkItemList({ items, loading, statusFilter, onStatusFilterChange, onItemChanged }) {
  return (
    <div>
      <div className="flex flex-wrap gap-2 mb-4">
        {FILTER_OPTIONS.map((option) => (
          <button
            key={option.value || 'ALL'}
            type="button"
            onClick={() => onStatusFilterChange(option.value)}
            className={clsx(
              'px-3 py-1.5 text-xs font-medium rounded-full border transition-colors',
              statusFilter === option.value
                ? 'bg-slate-900 text-white border-slate-900'
                : 'bg-white text-slate-600 border-slate-200 hover:border-slate-300'
            )}
          >
            {option.label}
          </button>
        ))}
      </div>

      {loading ? (
        <ListSkeleton />
      ) : !items || items.length === 0 ? (
        <div className="text-center py-12 border-2 border-dashed border-slate-200 rounded-xl bg-slate-50/50">
          <PackageOpen className="w-10 h-10 text-slate-400 mx-auto mb-2" />
          <p className="text-slate-600 font-medium">No work items found</p>
          <p className="text-slate-400 text-xs">Create your first item above to populate the list.</p>
        </div>
      ) : (
        <div className="space-y-3">
          {items.map((item) => (
            <WorkItemCard key={item.id} item={item} onChanged={onItemChanged} />
          ))}
        </div>
      )}
    </div>
  );
}
