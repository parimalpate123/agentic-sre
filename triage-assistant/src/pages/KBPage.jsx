/**
 * KBPage - Full-page Knowledge Base management UI
 * Accessible at /knowledge-base route
 */

import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import KBUploadForm from '../components/KBUploadForm';
import KBDocumentList from '../components/KBDocumentList';

const TABS = [
  { id: 'upload', label: 'Upload' },
  { id: 'manage', label: 'Manage' },
];

export default function KBPage() {
  const navigate = useNavigate();
  const [activeTab, setActiveTab] = useState('upload');
  const [refreshTrigger, setRefreshTrigger] = useState(0);

  const handleUploadSuccess = () => {
    setRefreshTrigger((n) => n + 1);
    setActiveTab('manage');
  };

  return (
    <div className="min-h-screen bg-gray-50 flex flex-col">
      {/* Header */}
      <div className="bg-white border-b border-gray-200 px-6 py-4">
        <div className="max-w-4xl mx-auto flex items-center gap-4">
          <button
            type="button"
            onClick={() => navigate('/chat')}
            className="flex items-center gap-1.5 text-sm text-gray-500 hover:text-gray-800 transition-colors"
          >
            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" />
            </svg>
            Back to TARS
          </button>
          <div className="w-px h-5 bg-gray-200" />
          <div className="flex items-center gap-2">
            <svg className="w-5 h-5 text-violet-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 6.253v13m0-13C10.832 5.477 9.246 5 7.5 5S4.168 5.477 3 6.253v13C4.168 18.477 5.754 18 7.5 18s3.332.477 4.5 1.253m0-13C13.168 5.477 14.754 5 16.5 5c1.747 0 3.332.477 4.5 1.253v13C19.832 18.477 18.247 18 16.5 18c-1.746 0-3.332.477-4.5 1.253" />
            </svg>
            <h1 className="text-lg font-semibold text-gray-900">Knowledge Base</h1>
          </div>
        </div>
      </div>

      {/* Main content */}
      <div className="flex-1 px-6 py-8">
        <div className="max-w-4xl mx-auto">
          {/* Description */}
          <p className="text-sm text-gray-500 mb-6">
            Upload TARS operational documentation — runbooks, standard operating procedures, and
            guidelines for how TARS triages, handles incidents, and performs remediation. TARS will
            automatically reference relevant KB content when answering questions.
          </p>

          {/* Tabs */}
          <div className="flex gap-1 mb-6 border-b border-gray-200">
            {TABS.map((tab) => (
              <button
                key={tab.id}
                type="button"
                onClick={() => setActiveTab(tab.id)}
                className={`px-4 py-2 text-sm font-medium transition-colors border-b-2 -mb-px ${
                  activeTab === tab.id
                    ? 'border-violet-600 text-violet-600'
                    : 'border-transparent text-gray-500 hover:text-gray-700'
                }`}
              >
                {tab.label}
              </button>
            ))}
          </div>

          {/* Tab content */}
          <div className="bg-white border border-gray-200 rounded-xl p-6 shadow-sm">
            {activeTab === 'upload' ? (
              <>
                <h2 className="text-base font-semibold text-gray-800 mb-4">Upload Document</h2>
                <KBUploadForm onUploadSuccess={handleUploadSuccess} />
              </>
            ) : (
              <>
                <div className="flex items-center justify-between mb-4">
                  <h2 className="text-base font-semibold text-gray-800">Documents</h2>
                  <button
                    type="button"
                    onClick={() => setRefreshTrigger((n) => n + 1)}
                    className="text-xs text-gray-500 hover:text-gray-700 flex items-center gap-1"
                  >
                    <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
                    </svg>
                    Refresh
                  </button>
                </div>
                <KBDocumentList refreshTrigger={refreshTrigger} />
              </>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
