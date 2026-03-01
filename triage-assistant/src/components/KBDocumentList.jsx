/**
 * KBDocumentList - Table view of all uploaded KB documents with management actions
 */

import { useState, useEffect, useCallback } from 'react';
import { kbListDocuments, kbDeleteDocument, kbUpdateDocument, kbGetChunks } from '../services/api';

const DOC_TYPE_LABELS = {
  runbook: 'Runbook',
  sop: 'SOP',
  guideline: 'Guideline',
  architecture: 'Architecture',
  troubleshooting: 'Troubleshooting',
  other: 'Other',
};

const STATUS_STYLES = {
  active: 'bg-green-100 text-green-700',
  processing: 'bg-blue-100 text-blue-700',
  disabled: 'bg-gray-100 text-gray-500',
  failed: 'bg-red-100 text-red-700',
  pending: 'bg-yellow-100 text-yellow-700',
};

// ─── Document viewer modal ────────────────────────────────────────────────────
function DocumentViewer({ doc, onClose }) {
  const [chunks, setChunks] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [search, setSearch] = useState('');

  useEffect(() => {
    (async () => {
      try {
        const result = await kbGetChunks(doc.document_id);
        setChunks(result.chunks || []);
      } catch (err) {
        setError('Failed to load chunks: ' + err.message);
      } finally {
        setLoading(false);
      }
    })();
  }, [doc.document_id]);

  const filtered = search.trim()
    ? chunks.filter((c) => c.content?.toLowerCase().includes(search.toLowerCase()) ||
        c.section_title?.toLowerCase().includes(search.toLowerCase()))
    : chunks;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40">
      <div className="bg-white rounded-xl shadow-2xl w-full max-w-3xl max-h-[85vh] flex flex-col mx-4">
        {/* Header */}
        <div className="flex items-start justify-between px-6 py-4 border-b border-gray-200">
          <div>
            <h2 className="text-base font-semibold text-gray-900">{doc.file_name}</h2>
            <div className="flex items-center gap-3 mt-1">
              <span className="text-xs text-gray-500">
                {chunks.length} chunk{chunks.length !== 1 ? 's' : ''}
              </span>
              {doc.feature_name && (
                <span className="px-2 py-0.5 bg-violet-100 text-violet-700 rounded-full text-xs font-medium">
                  {doc.feature_name}
                </span>
              )}
              <span className="px-2 py-0.5 bg-gray-100 text-gray-600 rounded-full text-xs">
                {DOC_TYPE_LABELS[doc.doc_type] || doc.doc_type}
              </span>
            </div>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="text-gray-400 hover:text-gray-700 transition-colors ml-4 shrink-0"
          >
            <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>

        {/* Search */}
        <div className="px-6 py-3 border-b border-gray-100">
          <input
            type="text"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Search within document..."
            className="w-full px-3 py-1.5 text-sm border border-gray-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-violet-400"
          />
        </div>

        {/* Chunks */}
        <div className="flex-1 overflow-y-auto px-6 py-4 space-y-4">
          {loading && (
            <div className="flex items-center gap-2 text-sm text-gray-500 py-8 justify-center">
              <svg className="animate-spin w-4 h-4" viewBox="0 0 24 24">
                <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" fill="none" />
                <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
              </svg>
              Loading chunks...
            </div>
          )}

          {error && (
            <div className="bg-red-50 border border-red-200 rounded-lg px-4 py-3 text-sm text-red-700">
              {error}
            </div>
          )}

          {!loading && !error && filtered.length === 0 && (
            <p className="text-sm text-gray-400 text-center py-8">
              {search ? 'No chunks match your search.' : 'No chunks found for this document.'}
            </p>
          )}

          {filtered.map((chunk, idx) => (
            <div key={chunk.chunk_id || idx} className="border border-gray-200 rounded-lg overflow-hidden">
              {/* Chunk header */}
              <div className="flex items-center justify-between bg-gray-50 px-4 py-2 border-b border-gray-200">
                <div className="flex items-center gap-2">
                  <span className="text-xs font-mono text-gray-400">
                    Chunk {chunk.chunk_index + 1}/{chunk.total_chunks}
                  </span>
                  {chunk.section_title && (
                    <>
                      <span className="text-gray-300">·</span>
                      <span className="text-xs font-medium text-violet-600">{chunk.section_title}</span>
                    </>
                  )}
                </div>
                <span className="text-xs text-gray-400">
                  {chunk.content?.length || 0} chars
                </span>
              </div>
              {/* Chunk content */}
              <pre className="px-4 py-3 text-xs text-gray-700 whitespace-pre-wrap font-sans leading-relaxed">
                {chunk.content}
              </pre>
            </div>
          ))}
        </div>

        {/* Footer */}
        <div className="px-6 py-3 border-t border-gray-200 flex justify-between items-center">
          <p className="text-xs text-gray-400">
            {search && filtered.length !== chunks.length
              ? `Showing ${filtered.length} of ${chunks.length} chunks`
              : `${chunks.length} chunks total`}
          </p>
          <button
            type="button"
            onClick={onClose}
            className="px-4 py-1.5 text-sm text-gray-600 border border-gray-300 rounded-lg hover:bg-gray-50 transition-colors"
          >
            Close
          </button>
        </div>
      </div>
    </div>
  );
}

// ─── Main list ────────────────────────────────────────────────────────────────
export default function KBDocumentList({ refreshTrigger }) {
  const [documents, setDocuments] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [actionInProgress, setActionInProgress] = useState(null);
  const [viewingDoc, setViewingDoc] = useState(null);

  const loadDocuments = useCallback(async () => {
    setLoading(true);
    setError('');
    try {
      const result = await kbListDocuments();
      setDocuments(result.documents || []);
    } catch (err) {
      setError('Failed to load documents: ' + err.message);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadDocuments();
  }, [loadDocuments, refreshTrigger]);

  const handleToggleStatus = async (doc) => {
    const newStatus = doc.status === 'active' ? 'disabled' : 'active';
    setActionInProgress(doc.document_id + ':toggle');
    try {
      await kbUpdateDocument(doc.document_id, newStatus);
      await loadDocuments();
    } catch (err) {
      alert('Failed to update status: ' + err.message);
    } finally {
      setActionInProgress(null);
    }
  };

  const handleDelete = async (doc) => {
    if (!window.confirm(`Delete "${doc.file_name}"? This will also remove all associated chunks.`)) return;
    setActionInProgress(doc.document_id + ':delete');
    try {
      await kbDeleteDocument(doc.document_id);
      await loadDocuments();
    } catch (err) {
      alert('Failed to delete document: ' + err.message);
    } finally {
      setActionInProgress(null);
    }
  };

  if (loading) {
    return (
      <div className="flex items-center gap-2 text-sm text-gray-500 py-8">
        <svg className="animate-spin w-4 h-4" viewBox="0 0 24 24">
          <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" fill="none" />
          <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
        </svg>
        Loading documents...
      </div>
    );
  }

  if (error) {
    return (
      <div className="bg-red-50 border border-red-200 rounded-lg px-4 py-3 text-sm text-red-700">
        {error}
        <button onClick={loadDocuments} className="ml-3 underline hover:no-underline">Retry</button>
      </div>
    );
  }

  if (documents.length === 0) {
    return (
      <div className="text-center py-12 text-gray-400">
        <svg className="w-12 h-12 mx-auto mb-3 opacity-40" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M12 6.253v13m0-13C10.832 5.477 9.246 5 7.5 5S4.168 5.477 3 6.253v13C4.168 18.477 5.754 18 7.5 18s3.332.477 4.5 1.253m0-13C13.168 5.477 14.754 5 16.5 5c1.747 0 3.332.477 4.5 1.253v13C19.832 18.477 18.247 18 16.5 18c-1.746 0-3.332.477-4.5 1.253" />
        </svg>
        <p className="text-sm">No documents yet. Upload your first document in the Upload tab.</p>
      </div>
    );
  }

  return (
    <>
      {viewingDoc && (
        <DocumentViewer doc={viewingDoc} onClose={() => setViewingDoc(null)} />
      )}

      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-gray-200 text-left">
              <th className="pb-2 pr-4 font-semibold text-gray-600 whitespace-nowrap">File</th>
              <th className="pb-2 pr-4 font-semibold text-gray-600 whitespace-nowrap">Functionality</th>
              <th className="pb-2 pr-4 font-semibold text-gray-600 whitespace-nowrap">Type</th>
              <th className="pb-2 pr-4 font-semibold text-gray-600 text-center whitespace-nowrap">Chunks</th>
              <th className="pb-2 pr-4 font-semibold text-gray-600 whitespace-nowrap">Status</th>
              <th className="pb-2 font-semibold text-gray-600 whitespace-nowrap">Actions</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-100">
            {documents.map((doc) => {
              const isActing = actionInProgress?.startsWith(doc.document_id);
              return (
                <tr key={doc.document_id} className="hover:bg-gray-50 transition-colors">
                  <td className="py-2.5 pr-4">
                    <p className="font-medium text-gray-800 truncate max-w-[180px]" title={doc.file_name}>
                      {doc.file_name}
                    </p>
                  </td>
                  <td className="py-2.5 pr-4">
                    <span className="px-2 py-0.5 bg-violet-100 text-violet-700 rounded-full text-xs font-medium">
                      {doc.feature_name || doc.service_name || '—'}
                    </span>
                  </td>
                  <td className="py-2.5 pr-4">
                    <span className="px-2 py-0.5 bg-gray-100 text-gray-600 rounded-full text-xs">
                      {DOC_TYPE_LABELS[doc.doc_type] || doc.doc_type}
                    </span>
                  </td>
                  <td className="py-2.5 pr-4 text-center text-gray-500">
                    {doc.chunk_count ?? '—'}
                  </td>
                  <td className="py-2.5 pr-4">
                    <span className={`px-2 py-0.5 rounded-full text-xs font-medium ${STATUS_STYLES[doc.status] || 'bg-gray-100 text-gray-600'}`}>
                      {doc.status}
                    </span>
                  </td>
                  <td className="py-2.5">
                    <div className="flex items-center gap-3">
                      {doc.status === 'active' && (
                        <button
                          type="button"
                          onClick={() => setViewingDoc(doc)}
                          className="text-xs text-gray-500 hover:text-gray-800 hover:underline"
                        >
                          View
                        </button>
                      )}
                      {(doc.status === 'active' || doc.status === 'disabled') && (
                        <button
                          type="button"
                          onClick={() => handleToggleStatus(doc)}
                          disabled={isActing}
                          className="text-xs text-violet-600 hover:text-violet-800 hover:underline disabled:opacity-50 disabled:cursor-not-allowed"
                        >
                          {doc.status === 'active' ? 'Disable' : 'Enable'}
                        </button>
                      )}
                      <button
                        type="button"
                        onClick={() => handleDelete(doc)}
                        disabled={isActing}
                        className="text-xs text-red-500 hover:text-red-700 hover:underline disabled:opacity-50 disabled:cursor-not-allowed"
                      >
                        Delete
                      </button>
                    </div>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </>
  );
}
