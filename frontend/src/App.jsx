import React, { useCallback, useEffect, useState } from 'react';
import Navbar from './components/Navbar';
import WorkItemForm from './components/WorkItemForm';
import WorkItemList from './components/WorkItemList';
import { getWorkItems, createWorkItem } from './api/client';

// How often to re-poll while items are actively being processed by the AI
// background job, so the UI reflects completion without a manual refresh.
const POLL_INTERVAL_MS = 4000;
const ACTIVE_STATUSES = new Set(['RECEIVED', 'ANALYSING']);

export default function App() {
  const [items, setItems] = useState([]);
  const [loading, setLoading] = useState(true);
  const [fetchError, setFetchError] = useState(null);
  const [statusFilter, setStatusFilter] = useState('');

  // `silent` skips the loading-skeleton toggle, for background polls and
  // post-action refreshes where flashing the whole list would be jarring.
  const fetchItems = useCallback(async (filter, { silent = false } = {}) => {
    if (!silent) setLoading(true);
    try {
      const response = await getWorkItems(filter || undefined);
      setItems(response.data);
      setFetchError(null);
    } catch (error) {
      console.error('Failed to fetch work items:', error);
      setFetchError('Failed to load work items. Please try again.');
    } finally {
      if (!silent) setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchItems(statusFilter);
  }, [statusFilter, fetchItems]);

  useEffect(() => {
    const hasActiveItem = items.some((item) => ACTIVE_STATUSES.has(item.status));
    if (!hasActiveItem) return undefined;

    const interval = setInterval(() => fetchItems(statusFilter, { silent: true }), POLL_INTERVAL_MS);
    return () => clearInterval(interval);
  }, [items, statusFilter, fetchItems]);

  const handleCreateItem = async (data) => {
    await createWorkItem(data);
    await fetchItems(statusFilter, { silent: true });
  };

  return (
    <div className="min-h-screen bg-slate-50 font-sans text-slate-900">
      <Navbar />
      <main className="max-w-4xl mx-auto px-4 py-8">
        <WorkItemForm onItemCreated={handleCreateItem} />
        <div>
          <h2 className="text-lg font-semibold text-slate-800 mb-4">Work Items</h2>
          {fetchError && (
            <div className="mb-4 p-3 bg-red-50 border border-red-200 text-red-700 text-sm rounded-lg">
              {fetchError}
            </div>
          )}
          <WorkItemList
            items={items}
            loading={loading}
            statusFilter={statusFilter}
            onStatusFilterChange={setStatusFilter}
            onItemChanged={() => fetchItems(statusFilter, { silent: true })}
          />
        </div>
      </main>
    </div>
  );
}