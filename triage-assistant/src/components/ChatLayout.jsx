/**
 * ChatLayout – Claude-like shell: session sidebar + main chat pane
 */

import { useState, useCallback, useEffect } from 'react';
import SessionSidebar from './SessionSidebar';
import ChatWindow from './ChatWindow';

export default function ChatLayout({
  isFullScreen,
  onToggleFullScreen,
  onShowUtilityPanel,
  chatWindowRef,
}) {
  const [sessionListRefreshTrigger, setSessionListRefreshTrigger] = useState(0);
  const [untriagedCount, setUntriagedCount] = useState(0);
  const [activeMode, setActiveMode] = useState('ask'); // 'ask' | 'trace' | 'investigate'

  // Reflect incident count in browser tab title so it's visible across tabs
  useEffect(() => {
    document.title = untriagedCount > 0 ? `(${untriagedCount}) TARS` : 'TARS';
    return () => { document.title = 'TARS'; };
  }, [untriagedCount]);

  const handleSessionCreated = useCallback(() => {
    setSessionListRefreshTrigger((t) => t + 1);
  }, []);

  const handleSampleQuestionClick = useCallback((question) => {
    chatWindowRef.current?.sendMessage?.(question);
  }, []);

  const handleOpenIncidents = useCallback((source) => {
    chatWindowRef.current?.openIncidents?.(source);
  }, [chatWindowRef]);

  const handleOpenSessionDialog = useCallback(() => {
    chatWindowRef.current?.openSessionDialog?.();
  }, [chatWindowRef]);

  return (
    <div className="flex h-full bg-gray-50">
      <SessionSidebar
        onRefreshTrigger={sessionListRefreshTrigger}
        onSampleQuestionClick={handleSampleQuestionClick}
        onOpenIncidents={handleOpenIncidents}
        onOpenSessionDialog={handleOpenSessionDialog}
        onShowAdmin={onShowUtilityPanel}
        untriagedCount={untriagedCount}
        activeMode={activeMode}
        onModeChange={setActiveMode}
      />
      <div className="flex-1 flex flex-col min-w-0 bg-white overflow-hidden">
        <ChatWindow
          ref={chatWindowRef}
          isFullScreen={isFullScreen}
          onToggleFullScreen={onToggleFullScreen}
          onShowUtilityPanel={onShowUtilityPanel}
          onSessionCreated={handleSessionCreated}
          onUntriagedCountChange={setUntriagedCount}
          activeMode={activeMode}
          onModeChange={setActiveMode}
        />
      </div>
    </div>
  );
}
