/**
 * ChatWindow Component
 * Main chat interface that combines all components
 */

import { useState, useRef, useEffect } from 'react';
import MessageBubble from './MessageBubble';
import InputBox from './InputBox';
import SuggestedQuestions from './SuggestedQuestions';
import { askQuestion, fetchLogGroups } from '../services/api';

export default function ChatWindow({ isFullScreen = false, onToggleFullScreen }) {
  const [messages, setMessages] = useState([
    {
      id: 'welcome',
      text: "Hi! I'm your Triage Assistant. I can help you analyze CloudWatch logs and identify issues in your services.\n\nAsk me questions like:\n- \"What errors occurred in payment-service?\"\n- \"Show me policy-service errors with policy_number\"\n- \"What rating calculations failed in rating-service?\"\n\nCross-Service Tracing:\n- \"Trace CORR-ABBFE258-2314-494A-B9BB-ADB33142404F across services\"\n- \"Follow request CORR-... through the system\"\n- \"Show me the request flow for correlation_id ...\"\n\nThe trace feature will search across all services to show you the complete request flow!",
      isUser: false,
      timestamp: new Date().toISOString(),
    },
  ]);
  const [isLoading, setIsLoading] = useState(false);
  const [suggestions, setSuggestions] = useState([]);
  const [useMCP, setUseMCP] = useState(true); // Default to ON (true), user can toggle to OFF (false)
  const [searchMode, setSearchMode] = useState('quick'); // 'quick' = real-time, 'deep' = Logs Insights
  const [selectedService, setSelectedService] = useState(''); // Empty = auto-detect from question
  const [timeRange, setTimeRange] = useState('2h'); // Default 2 hours
  const messagesEndRef = useRef(null);
  
  // Log groups state
  const [logGroups, setLogGroups] = useState([]);
  const [isLoadingLogGroups, setIsLoadingLogGroups] = useState(false);
  const [logGroupSearch, setLogGroupSearch] = useState('');
  const [logGroupsCache, setLogGroupsCache] = useState(null);
  const [logGroupsCacheTime, setLogGroupsCacheTime] = useState(0);
  const CACHE_DURATION = 5 * 60 * 1000; // 5 minutes

  // Available services for dropdown (fallback if log groups not loaded)
  const defaultServices = [
    { value: '', label: 'Auto-detect' },
    { value: 'payment-service', label: 'Payment Service' },
    { value: 'order-service', label: 'Order Service' },
    { value: 'api-gateway', label: 'API Gateway' },
    { value: 'user-service', label: 'User Service' },
    { value: 'inventory-service', label: 'Inventory Service' },
    { value: 'policy-service', label: 'Policy Service' },
    { value: 'rating-service', label: 'Rating Service' },
    { value: 'notification-service', label: 'Notification Service' },
    { value: 'sre-poc-incident-handler', label: 'Incident Handler (Lambda)' },
  ];

  // Time range options
  const timeRanges = [
    { value: '15m', label: '15 min' },
    { value: '1h', label: '1 hour' },
    { value: '2h', label: '2 hours' },
    { value: '6h', label: '6 hours' },
    { value: '24h', label: '24 hours' },
  ];

  // Auto-scroll to bottom when new messages arrive
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  // Fetch log groups on mount (CloudWatch is always selected for now)
  useEffect(() => {
    const loadLogGroups = async () => {
      // Check cache
      const now = Date.now();
      if (logGroupsCache && (now - logGroupsCacheTime) < CACHE_DURATION) {
        setLogGroups(logGroupsCache);
        return;
      }

      setIsLoadingLogGroups(true);
      try {
        console.log('Fetching log groups...');
        const response = await fetchLogGroups('/aws/', 100);
        console.log('Log groups response:', response);
        
        const groups = response.logGroups || [];
        console.log(`Found ${groups.length} log groups`);
        
        // Add "Auto-detect" option at the beginning
        const groupsWithAuto = [
          { value: '', label: 'Auto-detect', fullName: '', category: 'Default' },
          ...groups
        ];
        
        console.log('Setting log groups:', groupsWithAuto.length);
        setLogGroups(groupsWithAuto);
        setLogGroupsCache(groupsWithAuto);
        setLogGroupsCacheTime(now);
      } catch (error) {
        console.error('Failed to fetch log groups:', error);
        console.error('Error details:', error.message, error.stack);
        // Fallback to default services on error
        setLogGroups(defaultServices);
      } finally {
        setIsLoadingLogGroups(false);
      }
    };

    loadLogGroups();
  }, []); // Run once on mount

  const handleSendMessage = async (question) => {
    // Add user message
    const userMessage = {
      id: `user-${Date.now()}`,
      text: question,
      isUser: true,
      timestamp: new Date().toISOString(),
    };
    setMessages((prev) => [...prev, userMessage]);
    setIsLoading(true);
    setSuggestions([]);

    try {
      // Call API with all options
      const response = await askQuestion(
        question,
        selectedService || null,  // null = auto-detect
        timeRange,
        useMCP,
        searchMode  // 'quick' or 'deep'
      );

      // Add assistant message
      const assistantMessage = {
        id: `assistant-${Date.now()}`,
        text: response.answer || 'I could not process your request. Please try again.',
        isUser: false,
        timestamp: response.timestamp || new Date().toISOString(),
        insights: response.insights || [],
        recommendations: response.recommendations || [],
        logEntries: response.log_entries || [],
        totalResults: response.total_results || 0,
        searchMode: response.search_mode || searchMode,  // Store search mode used for this query
        cloudwatchUrl: response.cloudwatch_url || null,  // CloudWatch Logs Console URL
        // Cross-service correlation data
        correlationData: response.correlation_data || null,
        requestFlow: response.request_flow || null,
        servicesFound: response.services_found || null,
        patternData: response.pattern_data || null,
      };
      setMessages((prev) => [...prev, assistantMessage]);

      // Update suggestions
      if (response.follow_up_questions && response.follow_up_questions.length > 0) {
        setSuggestions(response.follow_up_questions);
      }
    } catch (error) {
      console.error('Error:', error);
      const errorMessage = {
        id: `error-${Date.now()}`,
        text: `❌ Sorry, I encountered an error: ${error.message}\n\nPlease try again or rephrase your question.`,
        isUser: false,
        timestamp: new Date().toISOString(),
      };
      setMessages((prev) => [...prev, errorMessage]);
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="flex flex-col h-full bg-white rounded-lg shadow-lg overflow-hidden">
      {/* Header */}
      <div className="bg-gradient-to-r from-blue-600 to-blue-700 text-white px-6 py-4">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 bg-white/20 rounded-full flex items-center justify-center">
              <span className="text-xl">🔍</span>
            </div>
            <div>
              <h1 className="text-lg font-semibold">Triage Hub</h1>
              <p className="text-sm text-blue-100">AI-powered log analysis</p>
            </div>
          </div>
          <div className="flex items-center gap-2">
            {/* MCP Toggle - Always visible, default ON */}
            <div className="flex items-center gap-2 bg-white/10 rounded-lg px-3 py-1.5">
              <span className="text-xs text-blue-100">MCP:</span>
              <button
                onClick={() => setUseMCP(true)}
                className={`text-xs px-2 py-1 rounded transition-colors ${
                  useMCP === true
                    ? 'bg-white text-blue-700 font-semibold'
                    : 'bg-white/20 text-white hover:bg-white/30'
                }`}
                title="Use MCP server for log queries"
              >
                ON
              </button>
              <button
                onClick={() => setUseMCP(false)}
                className={`text-xs px-2 py-1 rounded transition-colors ${
                  useMCP === false
                    ? 'bg-white text-blue-700 font-semibold'
                    : 'bg-white/20 text-white hover:bg-white/30'
                }`}
                title="Use Direct API for log queries"
              >
                OFF
              </button>
            </div>
            <button
              onClick={onToggleFullScreen}
              className="bg-white/20 hover:bg-white/30 rounded-lg p-2 transition-colors"
              title={isFullScreen ? 'Exit full screen' : 'Enter full screen'}
            >
              {isFullScreen ? (
                <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                </svg>
              ) : (
                <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 8V4m0 0h4M4 4l5 5m11-1V4m0 0h-4m4 0l-5 5M4 16v4m0 0h4m-4 0l5-5m11 5l-5-5m5 5v-4m0 4h-4" />
                </svg>
              )}
            </button>
          </div>
        </div>
      </div>

      {/* Log Source Selector */}
      <div className="bg-gray-50 border-b border-gray-200 px-4 py-2.5">
        <div className="flex items-center gap-3">
          <span className="text-xs text-gray-500 font-medium">Log Source:</span>
          <div className="flex gap-2">
            {/* CloudWatch - Enabled */}
            <button
              disabled={false}
              className="text-xs px-3 py-1.5 rounded-md bg-blue-600 text-white font-medium cursor-default"
              title="CloudWatch Logs (Active)"
            >
              CloudWatch
            </button>
            {/* Elasticsearch - Disabled */}
            <button
              disabled={true}
              className="text-xs px-3 py-1.5 rounded-md bg-gray-200 text-gray-400 cursor-not-allowed opacity-60"
              title="Elasticsearch (Coming soon)"
            >
              Elasticsearch
            </button>
            {/* Datadog - Disabled */}
            <button
              disabled={true}
              className="text-xs px-3 py-1.5 rounded-md bg-gray-200 text-gray-400 cursor-not-allowed opacity-60"
              title="Datadog (Coming soon)"
            >
              Datadog
            </button>
            {/* Dynatrace - Disabled */}
            <button
              disabled={true}
              className="text-xs px-3 py-1.5 rounded-md bg-gray-200 text-gray-400 cursor-not-allowed opacity-60"
              title="Dynatrace (Coming soon)"
            >
              Dynatrace
            </button>
          </div>
          <span className="text-xs text-gray-400 italic ml-auto">Multi-source support coming soon</span>
        </div>
      </div>

      {/* Search Controls */}
      <div className="bg-white border-b border-gray-200 px-4 py-3">
        <div className="flex flex-wrap items-center gap-4">
          {/* Quick/Deep Search Toggle */}
          <div className="flex items-center gap-2">
            <span className="text-xs text-gray-500 font-medium">Search:</span>
            <div className="flex bg-gray-100 rounded-lg p-0.5">
              <button
                onClick={() => setSearchMode('quick')}
                className={`text-xs px-3 py-1.5 rounded-md transition-colors ${
                  searchMode === 'quick'
                    ? 'bg-white text-blue-700 font-semibold shadow-sm'
                    : 'text-gray-600 hover:text-gray-800'
                }`}
                title="Real-time search using filter_log_events (no indexing delay)"
              >
                Quick
              </button>
              <button
                onClick={() => setSearchMode('deep')}
                className={`text-xs px-3 py-1.5 rounded-md transition-colors ${
                  searchMode === 'deep'
                    ? 'bg-white text-blue-700 font-semibold shadow-sm'
                    : 'text-gray-600 hover:text-gray-800'
                }`}
                title="CloudWatch Logs Insights (may have 5-15 min indexing delay for new logs)"
              >
                Deep
              </button>
            </div>
          </div>

          {/* Service/Log Group Dropdown */}
          <div className="flex items-center gap-2">
            <span className="text-xs text-gray-500 font-medium">Service:</span>
            <select
              value={selectedService}
              onChange={(e) => setSelectedService(e.target.value)}
              disabled={isLoadingLogGroups}
              className="text-xs bg-gray-100 border-0 rounded-lg px-2 py-1.5 text-gray-700 focus:ring-2 focus:ring-blue-500 disabled:opacity-50 min-w-[180px]"
              title={selectedService || 'Auto-detect'}
            >
              {isLoadingLogGroups ? (
                <option>Loading log groups...</option>
              ) : logGroups.length > 0 ? (
                logGroups.map((group) => (
                  <option key={group.value || group.fullName} value={group.fullName || group.value} title={group.fullName}>
                    {group.label}
                  </option>
                ))
              ) : (
                defaultServices.map((service) => (
                  <option key={service.value} value={service.value}>
                    {service.label}
                  </option>
                ))
              )}
            </select>
          </div>

          {/* Time Range Dropdown */}
          <div className="flex items-center gap-2">
            <span className="text-xs text-gray-500 font-medium">Time:</span>
            <select
              value={timeRange}
              onChange={(e) => setTimeRange(e.target.value)}
              className="text-xs bg-gray-100 border-0 rounded-lg px-2 py-1.5 text-gray-700 focus:ring-2 focus:ring-blue-500"
            >
              {timeRanges.map((range) => (
                <option key={range.value} value={range.value}>
                  {range.label}
                </option>
              ))}
            </select>
          </div>
        </div>

        {/* Always Visible Disclaimer */}
        <div className="mt-2 text-xs text-gray-500 bg-gray-50 rounded-lg px-3 py-2">
          {searchMode === 'quick' ? (
            <span>
              <strong className="text-blue-600">Quick Search:</strong> Real-time results with no delay. Searches multiple log groups in parallel. Best for recent logs and immediate troubleshooting.
            </span>
          ) : (
            <span>
              <strong className="text-orange-600">Deep Search:</strong> Uses CloudWatch Logs Insights for complex queries and analytics. Note: New logs may take 5-15 minutes to be indexed.
            </span>
          )}
        </div>
      </div>

      {/* Main content area with sidebar */}
      <div className="flex-1 flex overflow-hidden">
        {/* Messages and Input area (main content) */}
        <div className="flex-1 flex flex-col min-w-0">
          {/* Messages area */}
          <div className="flex-1 overflow-y-auto p-4 bg-gray-50">
            {messages.map((message) => (
              <MessageBubble key={message.id} message={message} isUser={message.isUser} />
            ))}

            {/* Loading indicator */}
            {isLoading && (
              <div className="flex justify-start mb-4">
                <div className="bg-gray-100 rounded-2xl rounded-bl-md px-4 py-3">
                  <div className="flex items-center gap-2 text-gray-500">
                    <svg className="animate-spin h-4 w-4" viewBox="0 0 24 24">
                      <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" fill="none" />
                      <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
                    </svg>
                    <span className="text-sm">Analyzing logs...</span>
                  </div>
                </div>
              </div>
            )}

            <div ref={messagesEndRef} />
          </div>

          {/* Input box */}
          <InputBox onSend={handleSendMessage} disabled={isLoading} />
        </div>

        {/* Right sidebar - Suggested questions */}
        <div className="w-96 border-l border-gray-200 bg-white flex flex-col">
          <SuggestedQuestions
            suggestions={suggestions}
            onQuestionClick={handleSendMessage}
            disabled={isLoading}
          />
        </div>
      </div>
    </div>
  );
}
