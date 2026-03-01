/**
 * KBUploadForm - Upload form for knowledge base documents
 */

import { useState, useRef } from 'react';
import { kbUpload, kbUploadFile, kbUploadComplete } from '../services/api';

const FUNCTIONALITIES = [
  { value: 'triage',            label: 'Triage',             desc: 'Log analysis, error identification, initial investigation' },
  { value: 'incident-response', label: 'Incident Response',  desc: 'Incident handling, escalation, on-call procedures' },
  { value: 'remediation',       label: 'Remediation',        desc: 'Fix procedures, rollback steps, code change guidance' },
  { value: 'alerting',          label: 'Alerting',           desc: 'Alarm thresholds, notification rules, alert tuning' },
  { value: 'deployment',        label: 'Deployment',         desc: 'Deploy procedures, release runbooks, rollback guides' },
  { value: 'general',           label: 'General',            desc: 'General operational knowledge, team conventions' },
];

const DOC_TYPES = [
  { value: 'runbook',         label: 'Runbook',                       desc: 'What to do when a specific alert fires' },
  { value: 'sop',             label: 'SOP (Standard Operating Procedure)', desc: 'Step-by-step checklist for routine tasks' },
  { value: 'guideline',       label: 'Guideline',                     desc: 'Best practices and recommendations' },
  { value: 'architecture',    label: 'Architecture',                  desc: 'System design, component diagrams, data flows' },
  { value: 'troubleshooting', label: 'Troubleshooting Guide',         desc: 'Known issues and how to resolve them' },
  { value: 'other',           label: 'Other',                         desc: 'General operational documentation' },
];

const ALLOWED_TYPES = ['.txt', '.md', '.markdown', '.pdf'];

export default function KBUploadForm({ onUploadSuccess }) {
  const [functionality, setFunctionality] = useState('');
  const [docType, setDocType] = useState('runbook');
  const [file, setFile] = useState(null);
  const [status, setStatus] = useState(null); // null | 'uploading' | 'processing' | 'success' | 'error'
  const [progress, setProgress] = useState('');
  const [error, setError] = useState('');
  const fileRef = useRef(null);

  const handleFileChange = (e) => {
    const f = e.target.files[0];
    if (!f) return;
    const ext = '.' + f.name.split('.').pop().toLowerCase();
    if (!ALLOWED_TYPES.includes(ext)) {
      setError(`Unsupported file type: ${ext}. Allowed: ${ALLOWED_TYPES.join(', ')}`);
      return;
    }
    setFile(f);
    setError('');
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!functionality || !file) {
      setError('Functionality and file are required.');
      return;
    }

    setStatus('uploading');
    setError('');
    setProgress('Creating document record...');

    try {
      // Step 1: Create document record + get presigned URL
      const { document_id, upload_url } = await kbUpload({
        functionality,
        doc_type: docType,
        file_name: file.name,
      });

      setProgress('Uploading file to storage...');

      // Step 2: PUT file directly to S3
      await kbUploadFile(upload_url, file);

      setStatus('processing');
      setProgress('Processing document (parsing, chunking, embedding)...');

      // Step 3: Trigger backend processing
      await kbUploadComplete(document_id);

      setStatus('success');
      setProgress('');

      // Reset form
      setFunctionality('');
      setDocType('runbook');
      setFile(null);
      if (fileRef.current) fileRef.current.value = '';

      onUploadSuccess?.();
    } catch (err) {
      setStatus('error');
      setError(err.message || 'Upload failed. Please try again.');
      setProgress('');
    }
  };

  const selectedFunc = FUNCTIONALITIES.find((f) => f.value === functionality);
  const selectedDocType = DOC_TYPES.find((t) => t.value === docType);

  return (
    <form onSubmit={handleSubmit} className="space-y-5 max-w-lg">
      {/* Functionality */}
      <div>
        <label className="block text-sm font-medium text-gray-700 mb-1">
          Functionality <span className="text-red-500">*</span>
        </label>
        <select
          value={functionality}
          onChange={(e) => setFunctionality(e.target.value)}
          required
          className="w-full px-3 py-2 text-sm border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-violet-500"
        >
          <option value="">Select functionality...</option>
          {FUNCTIONALITIES.map(({ value, label }) => (
            <option key={value} value={value}>{label}</option>
          ))}
        </select>
        {selectedFunc && (
          <p className="text-xs text-gray-400 mt-1">{selectedFunc.desc}</p>
        )}
      </div>

      {/* Doc Type */}
      <div>
        <label className="block text-sm font-medium text-gray-700 mb-1">Document Type</label>
        <select
          value={docType}
          onChange={(e) => setDocType(e.target.value)}
          className="w-full px-3 py-2 text-sm border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-violet-500"
        >
          {DOC_TYPES.map(({ value, label }) => (
            <option key={value} value={value}>{label}</option>
          ))}
        </select>
        {selectedDocType && (
          <p className="text-xs text-gray-400 mt-1">{selectedDocType.desc}</p>
        )}
      </div>

      {/* File */}
      <div>
        <label className="block text-sm font-medium text-gray-700 mb-1">
          Document File <span className="text-red-500">*</span>
          <span className="text-gray-400 text-xs ml-2">({ALLOWED_TYPES.join(', ')})</span>
        </label>
        <input
          ref={fileRef}
          type="file"
          accept={ALLOWED_TYPES.join(',')}
          onChange={handleFileChange}
          required
          className="w-full text-sm text-gray-600 file:mr-3 file:py-1.5 file:px-3 file:rounded-lg file:border-0 file:text-sm file:font-medium file:bg-violet-50 file:text-violet-700 hover:file:bg-violet-100"
        />
        {file && (
          <p className="text-xs text-gray-500 mt-1">
            {file.name} ({(file.size / 1024).toFixed(1)} KB)
          </p>
        )}
      </div>

      {/* Status feedback */}
      {error && (
        <div className="bg-red-50 border border-red-200 rounded-lg px-3 py-2 text-sm text-red-700">
          {error}
        </div>
      )}
      {status === 'success' && (
        <div className="bg-green-50 border border-green-200 rounded-lg px-3 py-2 text-sm text-green-700">
          Document uploaded and processed successfully.
        </div>
      )}
      {(status === 'uploading' || status === 'processing') && progress && (
        <div className="flex items-center gap-2 text-sm text-violet-600">
          <svg className="animate-spin w-4 h-4 shrink-0" viewBox="0 0 24 24">
            <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" fill="none" />
            <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
          </svg>
          {progress}
        </div>
      )}

      <button
        type="submit"
        disabled={status === 'uploading' || status === 'processing'}
        className="px-5 py-2 bg-violet-600 hover:bg-violet-700 disabled:bg-gray-400 disabled:cursor-not-allowed text-white text-sm font-medium rounded-lg transition-colors"
      >
        {status === 'uploading' || status === 'processing' ? 'Processing...' : 'Upload Document'}
      </button>
    </form>
  );
}
