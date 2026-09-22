import React, { useState } from 'react';
import { PlusCircle } from 'lucide-react';

const LABEL_CLASSES = 'block text-xs font-medium text-slate-700 uppercase mb-1';
const INPUT_CLASSES =
  'w-full px-3 py-2 bg-white text-slate-900 border border-slate-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500 text-sm';

export default function WorkItemForm({ onItemCreated }) {
  const [formData, setFormData] = useState({
    external_id: '',
    title: '',
    description: '',
  });
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setLoading(true);
    setError(null);

    try {
      await onItemCreated(formData);
      setFormData({ external_id: '', title: '', description: '' });
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to create work item');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="bg-white p-6 rounded-xl border border-slate-200 shadow-sm mb-8">
      <h2 className="text-lg font-semibold text-slate-800 mb-4 flex items-center gap-2">
        <PlusCircle className="w-5 h-5 text-blue-600" /> Create Work Item
      </h2>
      
      {error && (
        <div className="mb-4 p-3 bg-red-50 border border-red-200 text-red-700 text-sm rounded-lg">
          {error}
        </div>
      )}

      <form onSubmit={handleSubmit} className="space-y-4">
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div>
            <label className={LABEL_CLASSES}>External ID</label>
            <input
              type="text"
              required
              placeholder="e.g. CRM-12345"
              value={formData.external_id}
              onChange={(e) => setFormData({ ...formData, external_id: e.target.value })}
              className={INPUT_CLASSES}
            />
          </div>
          <div>
            <label className={LABEL_CLASSES}>Title</label>
            <input
              type="text"
              required
              placeholder="Brief summary..."
              value={formData.title}
              onChange={(e) => setFormData({ ...formData, title: e.target.value })}
              className={INPUT_CLASSES}
            />
          </div>
        </div>

        <div>
          <label className={LABEL_CLASSES}>Description</label>
          <textarea
            rows="3"
            placeholder="Detailed descriptions or context..."
            value={formData.description}
            onChange={(e) => setFormData({ ...formData, description: e.target.value })}
            className={`${INPUT_CLASSES} resize-none`}
          />
        </div>

        <button
          type="submit"
          disabled={loading}
          className="w-full md:w-auto px-5 py-2.5 bg-blue-600 hover:bg-blue-700 text-white font-medium text-sm rounded-lg shadow-sm transition-colors disabled:opacity-50"
        >
          {loading ? 'Submitting...' : 'Submit Work Item'}
        </button>
      </form>
    </div>
  );
}