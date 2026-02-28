/**
 * Chat Session Dialog Component
 * Allows users to save, load, and resume chat sessions
 */

import { useState, useEffect } from 'react';
import { saveChatSession, loadChatSession, listChatSessions } from '../services/api';

export default function ChatSessionDialog({ 
  isOpen, 
  onClose, 
  onLoadSession,
  currentMessages,
  currentIncidentData,
  currentRemediationStatuses
}) {
  const [sessions, setSessions] = useState([]);
  const [isLoading, setIsLoading] = useState(false);
  const [isSaving, setIsSaving] = useState(false);
  const [sessionName, setSessionName] = useState('');
  const [error, setError] = useState(null);
  const [activeTab, setActiveTab] = useState('save'); // 'save' or 'load'

  // Load sessions list when dialog opens
  useEffect(() => {
    if (isOpen && activeTab === 'load') {
      loadSessionsList();
    }
  }, [isOpen, activeTab]);

  const loadSessionsList = async () => {
    setIsLoading(true);
    setError(null);
    try {
      const result = await listChatSessions(20);
      setSessions(result.sessions || []);
    } catch (err) {
      console.error('Error loading sessions:', err);
      setError('Failed to load sessions. Please try again.');
    } finally {
      setIsLoading(false);
    }
  };

  const handleSave = async () => {
    if (!sessionName.trim()) {
      setError('Please enter a session name');
      return;
    }

    setIsSaving(true);
    setError(null);
    
    try {
      // Extract incident data from messages
      const incidentData = currentIncidentData || 
        (currentMessages.find(m => m.incident)?.incident || null);

      const result = await saveChatSession(
        null, // Generate new session ID
        sessionName.trim(),
        currentMessages,
        incidentData,
        currentRemediationStatuses
      );

      console.log('✅ Chat session saved:', result);
      
      // Show success message and close
      alert(`Session saved successfully!\nSession ID: ${result.session_id}`);
      setSessionName('');
      onClose();
      
      // Refresh sessions list if on load tab
      if (activeTab === 'load') {
        loadSessionsList();
      }
    } catch (err) {
      console.error('Error saving session:', err);
      setError('Failed to save session. Please try again.');
    } finally {
      setIsSaving(false);
    }
  };

  const handleLoad = async (sessionId) => {
    setIsLoading(true);
    setError(null);
    
    try {
      const session = await loadChatSession(sessionId);
      console.log('📥 Loaded chat session:', session);
      
      // Call parent callback to restore session
      onLoadSession(session);
      
      // Close dialog
      onClose();
    } catch (err) {
      console.error('Error loading session:', err);
      setError('Failed to load session. Please try again.');
    } finally {
      setIsLoading(false);
    }
  };

  const formatDate = (dateString) => {
    if (!dateString) return 'Unknown date';
    try {
      const date = new Date(dateString);
      // Use toLocaleString with explicit options to ensure local timezone
      // Format: "1/26/2026, 3:56:25 AM" (local time)
      return date.toLocaleString(undefined, {
        year: 'numeric',
        month: 'numeric',
        day: 'numeric',
        hour: 'numeric',
        minute: '2-digit',
        second: '2-digit',
        hour12: true
      });
    } catch {
      return dateString;
    }
  };

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 bg-transparent flex items-center justify-center z-50">
      <div className="bg-white rounded-lg shadow-xl w-full max-w-2xl max-h-[80vh] flex flex-col">
        {/* Header */}
        <div className="bg-gradient-to-r from-blue-600 to-blue-700 text-white px-6 py-4 rounded-t-lg">
          <div className="flex items-center justify-between">
            <h2 className="text-lg font-semibold">💾 Chat Session Management</h2>
            <button
              onClick={onClose}
              className="text-white hover:text-gray-200 text-xl font-bold"
            >
              ×
            </button>
          </div>
        </div>

        {/* Tabs */}
        <div className="flex border-b border-gray-200">
          <button
            onClick={() => setActiveTab('save')}
            className={`flex-1 px-4 py-3 text-sm font-medium ${
              activeTab === 'save'
                ? 'text-blue-600 border-b-2 border-blue-600 bg-blue-50'
                : 'text-gray-600 hover:text-gray-800 hover:bg-gray-50'
            }`}
          >
            💾 Save Current Chat
          </button>
          <button
            onClick={() => setActiveTab('load')}
            className={`flex-1 px-4 py-3 text-sm font-medium ${
              activeTab === 'load'
                ? 'text-blue-600 border-b-2 border-blue-600 bg-blue-50'
                : 'text-gray-600 hover:text-gray-800 hover:bg-gray-50'
            }`}
          >
            📂 Load Saved Chat
          </button>
        </div>

        {/* Content */}
        <div className="flex-1 overflow-y-auto p-6">
          {error && (
            <div className="mb-4 p-3 bg-red-50 border border-red-200 rounded text-red-800 text-sm">
              {error}
            </div>
          )}

          {activeTab === 'save' ? (
            <div className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  Session Name
                </label>
                <input
                  type="text"
                  value={sessionName}
                  onChange={(e) => setSessionName(e.target.value)}
                  placeholder="e.g., Payment Service Investigation"
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
                  onKeyDown={(e) => {
                    if (e.key === 'Enter') {
                      handleSave();
                    }
                  }}
                />
              </div>

              <div className="bg-gray-50 rounded-lg p-3 text-sm text-gray-600">
                <p className="font-semibold mb-1">This will save:</p>
                <ul className="list-disc list-inside space-y-1">
                  <li>{currentMessages.length} chat messages</li>
                  {currentIncidentData && <li>Current incident data</li>}
                  {Object.keys(currentRemediationStatuses).length > 0 && (
                    <li>{Object.keys(currentRemediationStatuses).length} remediation status(es)</li>
                  )}
                </ul>
              </div>

              <button
                onClick={handleSave}
                disabled={isSaving || !sessionName.trim()}
                className="w-full px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors disabled:opacity-50 disabled:cursor-not-allowed font-medium"
              >
                {isSaving ? 'Saving...' : '💾 Save Session'}
              </button>
            </div>
          ) : (
            <div className="space-y-4">
              <div className="flex items-center justify-between mb-4">
                <h3 className="text-sm font-semibold text-gray-700">
                  Saved Sessions ({sessions.length})
                </h3>
                <button
                  onClick={loadSessionsList}
                  disabled={isLoading}
                  className="text-xs text-blue-600 hover:text-blue-800 font-medium disabled:opacity-50"
                >
                  🔄 Refresh
                </button>
              </div>

              {isLoading ? (
                <div className="flex items-center justify-center py-8">
                  <svg className="animate-spin h-6 w-6 text-blue-600" viewBox="0 0 24 24">
                    <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" fill="none" />
                    <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
                  </svg>
                </div>
              ) : sessions.length === 0 ? (
                <div className="text-center py-8 text-gray-500">
                  <p className="text-sm">No saved sessions found.</p>
                  <p className="text-xs mt-2">Save a chat session to resume it later.</p>
                </div>
              ) : (
                <div className="space-y-2">
                  {sessions.map((session) => (
                    <div
                      key={session.session_id}
                      className="border border-gray-200 rounded-lg p-4 hover:border-blue-300 hover:bg-blue-50 transition-colors cursor-pointer"
                      onClick={() => handleLoad(session.session_id)}
                    >
                      <div className="flex items-start justify-between">
                        <div className="flex-1">
                          <h4 className="font-semibold text-gray-800 mb-1">
                            {session.session_name || 'Unnamed Session'}
                          </h4>
                          <div className="text-xs text-gray-600 space-y-1">
                            <p>Created: {formatDate(session.created_at)}</p>
                            <p>Updated: {formatDate(session.updated_at)}</p>
                            <p>
                              {session.message_count || 0} messages
                              {session.has_incident && ' • Has incident'}
                            </p>
                          </div>
                        </div>
                        <button
                          onClick={(e) => {
                            e.stopPropagation();
                            handleLoad(session.session_id);
                          }}
                          className="ml-4 px-3 py-1.5 bg-blue-600 text-white text-xs rounded hover:bg-blue-700 transition-colors"
                        >
                          Load
                        </button>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
