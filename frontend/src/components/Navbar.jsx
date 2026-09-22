import React from 'react';
import { Layers } from 'lucide-react';

export default function Navbar() {
  return (
    <nav className="bg-slate-900 text-white shadow-md">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 h-16 flex items-center justify-between">
        <div className="flex items-center space-x-3">
          <Layers className="h-6 w-6 text-blue-400" />
          <span className="text-xl font-bold tracking-tight">WorkItem Tracker</span>
        </div>
        <span className="text-xs bg-slate-800 text-slate-300 px-3 py-1 rounded-full border border-slate-700">
          v1.0.0
        </span>
      </div>
    </nav>
  );
}