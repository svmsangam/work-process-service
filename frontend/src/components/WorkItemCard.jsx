import React, { useState } from 'react';
import clsx from 'clsx';
import { RefreshCw, Sparkles, CheckCircle2, AlertCircle } from 'lucide-react';
import { analyzeWorkItemAI, retryWorkItemAI, updateWorkItemStatus } from '../api/client';
import { getStatusMeta } from '../lib/workItemStatus';

function ActionButton({ onClick, loading, icon: Icon, label, className }) {
  return (
    <button
      type="button"
      onClick={onClick}
      disabled={loading}
      className={clsx(
        'inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium rounded-lg shadow-sm transition-colors disabled:opacity-50 disabled:cursor-not-allowed',
        className
      )}
    >
      {loading ? (
        <span className="w-3.5 h-3.5 border-2 border-current border-t-transparent rounded-full animate-spin" />
      ) : (
        <Icon className="w-3.5 h-3.5" />
      )}
      {loading ? 'Working...' : label}
    </button>
  );
}

export default function WorkItemCard({ item, onChanged }) {
  const [actionLoading, setActionLoading] = useState(null); // 'analyze' | 'retry' | 'complete' | null
  const [actionError, setActionError] = useState(null);

  const statusMeta = getStatusMeta(item.status);

  const runAction = async (action, fn) => {
    setActionLoading(action);
    setActionError(null);
    try {
      await fn();
      await onChanged?.();
    } catch (err) {
      setActionError(err.response?.data?.detail || 'Action failed. Please try again.');
    } finally {
      setActionLoading(null);
    }
  };

  const handleAnalyze = () => runAction('analyze', () => analyzeWorkItemAI(item.id));
  const handleRetry = () => runAction('retry', () => retryWorkItemAI(item.id));
  const handleComplete = () => runAction('complete', () => updateWorkItemStatus(item.id, 'COMPLETED'));

  return (
    <div className="bg-white p-5 rounded-xl border border-slate-200 shadow-sm hover:border-slate-300 transition-all">
      <div className="flex items-center justify-between mb-2 gap-2 flex-wrap">
        <div className="flex items-center gap-2 flex-wrap">
          <span className="text-xs font-mono font-semibold px-2.5 py-1 bg-slate-100 text-slate-700 rounded-md">
            {item.external_id}
          </span>
          <span className={clsx('text-xs font-medium px-2.5 py-1 rounded-full border', statusMeta.badgeClass)}>
            {statusMeta.label}
          </span>
        </div>
        {item.created_at && (
          <span className="text-xs text-slate-400 shrink-0">
            {new Date(item.created_at).toLocaleDateString()}
          </span>
        )}
      </div>

      <h3 className="text-base font-medium text-slate-900 mb-1">{item.title}</h3>
      {item.description && (
        <p className="text-sm text-slate-600 line-clamp-2 mb-3">{item.description}</p>
      )}

      {item.ai_analysis && (
        <div className="mb-3 p-3 bg-indigo-50 border border-indigo-100 rounded-lg">
          <p className="text-xs font-semibold text-indigo-700 uppercase mb-1">AI Analysis</p>
          <p className="text-sm text-indigo-900 mb-1.5">{item.ai_analysis.summary}</p>
          <div className="flex flex-wrap gap-x-4 gap-y-1 text-xs text-indigo-700">
            <span>
              <span className="font-medium">Category:</span> {item.ai_analysis.category}
            </span>
            <span>
              <span className="font-medium">Priority:</span> {item.ai_analysis.priority}
            </span>
          </div>
          {item.ai_analysis.recommendedAction && (
            <p className="text-xs text-indigo-700 mt-1.5">
              <span className="font-medium">Recommended action:</span> {item.ai_analysis.recommendedAction}
            </p>
          )}
        </div>
      )}

      {item.status === 'FAILED' && item.ai_error && (
        <div className="mb-3 p-3 bg-red-50 border border-red-100 rounded-lg text-sm text-red-700">
          <span className="font-medium">AI analysis failed:</span> {item.ai_error}
        </div>
      )}

      {actionError && (
        <div className="mb-3 p-2.5 bg-red-50 border border-red-200 text-red-700 text-xs rounded-lg flex items-center gap-1.5">
          <AlertCircle className="w-3.5 h-3.5 shrink-0" />
          {actionError}
        </div>
      )}

      <div className="flex flex-wrap gap-2">
        {item.status === 'RECEIVED' && (
          <ActionButton
            onClick={handleAnalyze}
            loading={actionLoading === 'analyze'}
            icon={Sparkles}
            label="Analyze with AI"
            className="bg-blue-600 hover:bg-blue-700 text-white"
          />
        )}
        {item.status === 'FAILED' && (
          <ActionButton
            onClick={handleRetry}
            loading={actionLoading === 'retry'}
            icon={RefreshCw}
            label="Retry AI"
            className="bg-red-600 hover:bg-red-700 text-white"
          />
        )}
        {item.status === 'READY_FOR_REVIEW' && (
          <ActionButton
            onClick={handleComplete}
            loading={actionLoading === 'complete'}
            icon={CheckCircle2}
            label="Mark Complete"
            className="bg-green-600 hover:bg-green-700 text-white"
          />
        )}
      </div>
    </div>
  );
}
