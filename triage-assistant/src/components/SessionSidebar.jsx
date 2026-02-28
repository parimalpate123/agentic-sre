/**
 * SessionSidebar – Left pane: New chat, Sample questions (demo), and session list
 */

import { useState, useEffect, useRef } from 'react';
import { createPortal } from 'react-dom';
import { useNavigate, useParams } from 'react-router-dom';
import { PREDEFINED_QUESTIONS } from './SuggestedQuestions';
import { listChatSessions } from '../services/api';

export default function SessionSidebar({ onRefreshTrigger, onSampleQuestionClick, onOpenIncidents, onOpenSessionDialog, onShowAdmin, untriagedCount = 0 }) {
  const navigate = useNavigate();
  const { sessionId: routeSessionId } = useParams();
  const [sessions, setSessions] = useState([]);
  const [showSamplePopover, setShowSamplePopover] = useState(false);
  const [selectedCategory, setSelectedCategory] = useState('');
  const samplePopoverRef = useRef(null);

  // Load session list when sidebar mounts or refresh is triggered
  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const result = await listChatSessions(30);
        if (!cancelled && result?.sessions) setSessions(result.sessions);
      } catch (err) {
        if (!cancelled) console.error('Failed to list sessions:', err);
      }
    })();
    return () => { cancelled = true; };
  }, [onRefreshTrigger]);

  const handleNewChat = () => {
    navigate('/chat');
  };

  const handleSessionClick = (sessionId) => {
    navigate(`/chat/${sessionId}`);
  };

  const exampleQuestions = [
    'What errors occurred in payment-service?',
    'Show me policy-service errors with policy_number',
    'What rating calculations failed in rating-service?',
  ];

  const totalQuestions = Object.values(PREDEFINED_QUESTIONS).flat().length;
  const selectedQuestions = selectedCategory ? PREDEFINED_QUESTIONS[selectedCategory] || [] : [];

  const formatSessionDate = (dateStr) => {
    if (!dateStr) return '';
    const d = new Date(dateStr);
    return d.toLocaleDateString(undefined, { month: 'numeric', day: 'numeric', year: 'numeric', hour: '2-digit', minute: '2-digit' });
  };

  const truncate = (str, maxLen = 42) => {
    if (!str || str.length <= maxLen) return str || '';
    return str.slice(0, maxLen).trim() + '...';
  };

  return (
    <aside className="w-64 shrink-0 flex flex-col bg-white overflow-hidden border-r border-gray-200">
      {/* Logo / brand at top – click to go Home */}
      <button
        type="button"
        onClick={() => navigate('/chat')}
        className="w-full text-left px-4 pt-5 pb-3 border-b border-gray-100 hover:bg-gray-50 transition-colors rounded-none"
        title="Go to Home"
      >
        <div className="text-base font-semibold text-violet-800">TARS</div>
        <div className="text-[11px] text-gray-500 mt-1 leading-tight">Telemetry Analysis & Resolution System</div>
      </button>

      {/* Primary actions – stacked, left-aligned with icons */}
      <div className="px-3 py-3 space-y-0.5 border-b border-gray-100">
        <button
          type="button"
          onClick={handleNewChat}
          className="w-full flex items-center gap-3 px-3 py-2 rounded-lg text-sm font-medium text-gray-700 hover:bg-gray-100 transition-colors"
        >
          <span className="text-lg leading-none text-violet-600">+</span>
          New chat
        </button>
        <button
          type="button"
          onClick={() => onOpenIncidents?.()}
          className="w-full flex items-center gap-3 px-3 py-2 rounded-lg text-sm text-gray-700 hover:bg-gray-100 transition-colors"
          title={`${untriagedCount} alarm-triggered incident(s) not triaged`}
        >
          <span className="relative shrink-0">
            <svg className="w-4 h-4 text-gray-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 17h5l-1.405-1.405A2.032 2.032 0 0118 14.158V11a6.002 6.002 0 00-4-5.659V5a2 2 0 10-4 0v.341C7.67 6.165 6 8.388 6 11v3.159c0 .538-.214 1.055-.595 1.436L4 17h5m6 0v1a3 3 0 11-6 0v-1m6 0H9" />
            </svg>
            {untriagedCount > 0 && (
              <span className="absolute -top-1.5 -right-1.5 min-w-[14px] h-[14px] flex items-center justify-center rounded-full bg-red-500 text-white text-[9px] font-bold">
                {untriagedCount > 99 ? '99+' : untriagedCount}
              </span>
            )}
          </span>
          <span className="flex-1 text-left">Auto trigger incidents</span>
        </button>
        <button
          type="button"
          onClick={() => onOpenIncidents?.()}
          className="w-full flex items-center gap-3 px-3 py-2 rounded-lg text-sm text-violet-600 hover:bg-violet-50 transition-colors font-medium"
        >
          <svg className="w-4 h-4 text-violet-600 shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2m-3 7h3m-3 4h3m-6-4h.01M9 16h.01" />
          </svg>
          All Incidents
        </button>
        {onOpenSessionDialog && (
          <button
            type="button"
            onClick={onOpenSessionDialog}
            className="w-full flex items-center gap-3 px-3 py-2 rounded-lg text-sm text-gray-700 hover:bg-gray-100 transition-colors"
            title="Save or load a chat session"
          >
            <svg className="w-4 h-4 text-gray-500 shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 7H5a2 2 0 00-2 2v9a2 2 0 002 2h14a2 2 0 002-2V9a2 2 0 00-2-2h-3m-1 4l-3 3m0 0l-3-3m3 3V4" />
            </svg>
            Saved sessions
          </button>
        )}
        {onShowAdmin && (
          <button
            type="button"
            onClick={onShowAdmin}
            className="w-full flex items-center gap-3 px-3 py-2 rounded-lg text-sm text-gray-700 hover:bg-gray-100 transition-colors"
          >
            <svg className="w-4 h-4 text-gray-500 shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.065 2.572c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.572 1.065c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.065-2.572c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z" />
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
            </svg>
            Admin
          </button>
        )}
        <button
          type="button"
          disabled
          className="w-full flex items-center gap-3 px-3 py-2 rounded-lg text-sm text-gray-400 cursor-not-allowed"
          title="Coming soon"
        >
          <svg className="w-4 h-4 shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 6.253v13m0-13C10.832 5.477 9.246 5 7.5 5S4.168 5.477 3 6.253v13C4.168 18.477 5.754 18 7.5 18s3.332.477 4.5 1.253m0-13C13.168 5.477 14.754 5 16.5 5c1.747 0 3.332.477 4.5 1.253v13C19.832 18.477 18.247 18 16.5 18c-1.746 0-3.332.477-4.5 1.253" />
          </svg>
          Knowledge base
        </button>
        {/* Empty space for 3 future options (keeps Recents pushed down) */}
        <div className="flex flex-col gap-0.5" aria-hidden>
          {[1, 2, 3].map((i) => (
            <div key={i} className="h-9" />
          ))}
        </div>
      </div>

      {/* Sample questions – small link, before Recents */}
      <div className="px-3 py-2 border-b border-gray-100" ref={samplePopoverRef}>
        <button
          type="button"
          onClick={() => setShowSamplePopover((v) => !v)}
          className="text-xs text-gray-500 hover:text-violet-600 hover:underline"
        >
          Sample questions
        </button>
      </div>

      {/* Recents section (Claude-style) */}
      <div className="flex-1 overflow-y-auto min-h-0 py-2">
        <div className="flex items-center gap-2 px-4 py-1.5">
          <svg className="w-4 h-4 text-gray-400 shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z" />
          </svg>
          <span className="text-[11px] font-medium text-gray-500 uppercase tracking-wide">Recents</span>
        </div>
        <div className="px-2 space-y-0.5">
          {sessions.length === 0 ? (
            <p className="text-xs text-gray-400 px-3 py-2">No chats yet</p>
          ) : (
            sessions.map((session) => {
              const isActive = routeSessionId === session.session_id;
              const label = session.session_name || `Chat Session ${formatSessionDate(session.updated_at || session.created_at)}`;
              return (
                <button
                  key={session.session_id}
                  type="button"
                  onClick={() => handleSessionClick(session.session_id)}
                  className={`w-full text-left text-xs px-3 py-2 rounded-md transition-colors overflow-hidden min-w-0 flex items-center gap-2 ${
                    isActive
                      ? 'bg-violet-50 text-violet-800 font-medium'
                      : 'text-gray-700 hover:bg-gray-100'
                  }`}
                  title={label}
                >
                  <span className="block truncate flex-1 min-w-0">{truncate(label)}</span>
                </button>
              );
            })
          )}
        </div>
      </div>

      {/* Sample questions popover – rendered in portal so it uses full main area */}
      {showSamplePopover && createPortal(
        <div
          className="fixed inset-0 z-50 flex items-start justify-center pt-4 pb-4 bg-black/20"
          style={{ left: '16rem' }}
          onClick={(e) => e.target === e.currentTarget && setShowSamplePopover(false)}
          role="dialog"
          aria-label="Sample questions"
        >
          <div
            className="bg-white rounded-xl shadow-xl border border-gray-200 w-full max-w-2xl max-h-[calc(100vh-2rem)] overflow-y-auto mx-4 p-5"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="flex items-center justify-between mb-4">
              <h2 className="text-sm font-semibold text-gray-800">Sample questions</h2>
              <button
                type="button"
                onClick={() => setShowSamplePopover(false)}
                className="p-1 rounded text-gray-400 hover:text-gray-600"
                aria-label="Close"
              >
                <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" /></svg>
              </button>
            </div>
            <div className="flex flex-col gap-4">
              <div>
                <p className="text-xs text-gray-500 mb-2 font-medium">Example Questions:</p>
                <div className="flex flex-wrap gap-2">
                  {exampleQuestions.map((q, i) => (
                    <button
                      key={i}
                      type="button"
                      onClick={() => { onSampleQuestionClick?.(q); setShowSamplePopover(false); }}
                      className="text-left text-sm px-3 py-2 rounded-lg border border-violet-200 bg-white text-violet-600 hover:bg-violet-50 hover:border-violet-300"
                    >
                      {q}
                    </button>
                  ))}
                </div>
              </div>
              <div>
                <p className="text-xs text-gray-500 mb-2 font-medium">More Questions:</p>
                <select
                  value={selectedCategory}
                  onChange={(e) => setSelectedCategory(e.target.value)}
                  className="w-full text-sm border border-gray-300 rounded-lg px-3 py-2 focus:ring-2 focus:ring-violet-400 focus:border-violet-400 mb-2"
                >
                  <option value="">Select category ({totalQuestions} questions)</option>
                  {Object.entries(PREDEFINED_QUESTIONS).map(([cat, questions]) => (
                    <option key={cat} value={cat}>{cat} ({questions.length})</option>
                  ))}
                </select>
                {selectedCategory && selectedQuestions.length > 0 && (
                  <div className="flex flex-col gap-1">
                    {selectedQuestions.map((q, i) => (
                      <button
                        key={i}
                        type="button"
                        onClick={() => { onSampleQuestionClick?.(q); setShowSamplePopover(false); }}
                        className="w-full text-left text-sm px-3 py-2 rounded-lg border border-violet-200 bg-white text-violet-600 hover:bg-violet-50 hover:border-violet-300"
                      >
                        {q}
                      </button>
                    ))}
                  </div>
                )}
              </div>
            </div>
          </div>
        </div>,
        document.body
      )}
    </aside>
  );
}
