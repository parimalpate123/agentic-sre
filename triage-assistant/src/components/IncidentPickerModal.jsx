/**
 * IncidentPickerModal — modal that shows open incidents from Alerts, ServiceNow, or Jira.
 * ServiceNow and Jira use hardcoded demo data; Alerts uses live CloudWatch alarm incidents
 * passed in via the `alerts` prop.
 */

import { useState, useEffect } from 'react';

// ---------------------------------------------------------------------------
// Demo data for ServiceNow and Jira
// ---------------------------------------------------------------------------
const DEMO_INCIDENTS = {
  servicenow: [
    {
      id: 'SN-4821',
      source: 'ServiceNow',
      time: '2/19/2026, 1:10:00 PM EST',
      app: 'Policy Service',
      by: 'pagerduty-bot',
      title: 'Policy-service 5xx errors during peak load',
      service: 'policy-service',
      status: 'New',
      priority: 'Critical',
      description: '5xx error rate increased during 18:00–20:00 UTC. Correlated with high request volume. Possible DB connection exhaustion.',
      steps: '1. During next peak window, monitor 5xx rate for policy-service. 2. Correlate with RDS connection count.',
    },
    {
      id: 'SN-4819',
      source: 'ServiceNow',
      time: '2/19/2026, 9:05:00 AM EST',
      app: 'Checkout Service',
      by: 'monitoring-bot',
      title: 'Payment gateway timeout affecting checkout',
      service: 'payment-service',
      status: 'In Progress',
      priority: 'High',
      description: 'Customers report checkout failures when completing payment. Payment service times out after 30s. Started around 14:00 UTC.',
      steps: '1. Navigate to checkout with a cart containing 2+ items. 2. Select payment method and submit. 3. Wait for timeout.',
    },
    {
      id: 'SN-4815',
      source: 'ServiceNow',
      time: '2/19/2026, 6:30:00 AM EST',
      app: 'Payment API',
      by: 'alerting-sre',
      title: 'Card declined errors spike in production',
      service: 'payment-service',
      status: 'New',
      priority: 'Critical',
      description: 'Error rate for card declined responses increased from 0.1% to 2.5% over 2 hours. Logs show connection pool exhaustion.',
      steps: '1. Run load test against payment API with 500 concurrent users. 2. Monitor card-decline error rate.',
    },
    {
      id: 'SN-4811',
      source: 'ServiceNow',
      time: '2/19/2026, 3:45:00 AM EST',
      app: 'Policy Validation API',
      by: 'performance-monitor',
      title: 'Policy validation timeout on policy-service',
      service: 'policy-service',
      status: 'In Progress',
      priority: 'High',
      description: 'Policy validation endpoint times out under load. P99 latency > 10s. Redis cache hit rate dropped to 60% from 95%.',
      steps: '1. Send 200 concurrent requests to GET /policy/validate with varying policy IDs. 2. Observe latency degradation.',
    },
    {
      id: 'SN-4807',
      source: 'ServiceNow',
      time: '2/18/2026, 11:20:00 AM EST',
      app: 'Rating Engine',
      by: 'api-monitor',
      title: 'Rating calculation failure for bulk requests',
      service: 'rating-service',
      status: 'In Progress',
      priority: 'High',
      description: 'Bulk rating API returns 500 for requests with more than 50 items. Stack trace points to timeout in rating-engine.',
      steps: '1. Call POST /rating/quote with body containing 51+ items. 2. Observe 500 and timeout in rating-service logs.',
    },
  ],
  jira: [
    {
      id: 'PLAT-1234',
      source: 'Jira',
      time: '3/27/2026, 4:15:00 PM EST',
      app: 'Order Service',
      by: 'auto-triage',
      title: 'Order creation silently failing for premium users',
      service: 'order-service',
      status: 'Open',
      priority: 'High',
      description: 'Orders placed by premium-tier users are returning 200 but not persisting. Affects ~3% of orders since deploy at 14:00 UTC.',
      steps: '1. Create order as premium user. 2. Check order history — entry missing.',
    },
    {
      id: 'PLAT-1231',
      source: 'Jira',
      time: '3/27/2026, 1:00:00 PM EST',
      app: 'Notification Service',
      by: 'oncall-bot',
      title: 'Push notifications delayed by 15+ minutes',
      service: 'notification-service',
      status: 'In Progress',
      priority: 'Medium',
      description: 'Push notification delivery latency spiked after queue consumer restart. Messages queued but not dispatched promptly.',
      steps: '1. Trigger a notification event. 2. Observe delivery time in notification-service logs.',
    },
    {
      id: 'PLAT-1228',
      source: 'Jira',
      time: '3/26/2026, 9:30:00 AM EST',
      app: 'User Service',
      by: 'security-scanner',
      title: 'Auth token refresh returning 401 intermittently',
      service: 'user-service',
      status: 'Open',
      priority: 'Critical',
      description: 'Token refresh endpoint returns 401 for ~5% of requests. Pattern correlates with high DB query latency spikes.',
      steps: '1. Generate token. 2. Wait for near-expiry. 3. Call /auth/refresh repeatedly under load.',
    },
    {
      id: 'PLAT-1225',
      source: 'Jira',
      time: '3/26/2026, 6:00:00 AM EST',
      app: 'Inventory Service',
      by: 'load-monitor',
      title: 'Inventory sync lag causing oversell on flash sales',
      service: 'inventory-service',
      status: 'Open',
      priority: 'Critical',
      description: 'Inventory counts lag up to 90 seconds behind actual stock during high-traffic events, resulting in oversell.',
      steps: '1. Trigger a flash sale simulation. 2. Compare inventory API response vs DB count — observe delta.',
    },
  ],
};

const PRIORITY_COLOR = {
  Critical: 'text-red-600 bg-red-50 border-red-200',
  High:     'text-amber-600 bg-amber-50 border-amber-200',
  Medium:   'text-blue-600 bg-blue-50 border-blue-200',
  Low:      'text-gray-500 bg-gray-50 border-gray-200',
};

/** Format an ISO timestamp into a readable string like "3/28/2026, 1:10:00 AM EST" */
function formatTime(ts) {
  if (!ts) return '';
  try {
    return new Date(ts).toLocaleString('en-US', { timeZone: 'America/New_York', timeZoneName: 'short' });
  } catch {
    return ts;
  }
}

/** Return true if the text looks like an internal pydantic/validation error — not meaningful to show */
function isInternalError(text) {
  if (!text) return false;
  return text.includes('validation error') || text.includes('pydantic') || text.includes('NoneType');
}

export default function IncidentPickerModal({ isOpen, initialSource = 'alerts', alerts = [], onLoad, onClose }) {
  const [source, setSource] = useState(initialSource);
  const [timeframe, setTimeframe] = useState('all');

  // Reset to the source that was clicked when the modal reopens
  useEffect(() => {
    if (isOpen) setSource(initialSource);
  }, [isOpen, initialSource]);

  if (!isOpen) return null;

  // Map live alert incidents to display shape — use alarm_name/service as title, not internal errors
  const rawAlerts = alerts.map((inc, idx) => {
    const raw = inc.data ? (typeof inc.data === 'string' ? JSON.parse(inc.data) : inc.data) : inc;
    const service = raw?.service || inc.service || 'unknown';

    // Prefer alarm_name for the title; fall back to executive_summary only if it's not an internal error
    const alarmName = inc.alarm_name || raw?.alarm_name;
    const summary = !isInternalError(raw?.executive_summary) ? raw?.executive_summary : null;
    const title = alarmName
      ? alarmName.replace(/-/g, ' ').replace(/\b\w/g, c => c.toUpperCase())
      : summary || `Alert — ${service}`;

    const description = summary || (alarmName ? `CloudWatch alarm triggered on ${service}.` : '');

    return {
      id: inc.incident_id || `alert-${idx}`,
      source: 'Alert',
      time: formatTime(inc.created_at || inc.timestamp),
      app: service,
      by: 'CloudWatch',
      title,
      service,
      status: inc.status ? inc.status.charAt(0).toUpperCase() + inc.status.slice(1) : 'Open',
      priority: 'High',
      description,
      steps: '',
    };
  });

  const incidents = source === 'alerts' ? rawAlerts : (DEMO_INCIDENTS[source] || []);

  const handleLoad = (inc) => {
    const parts = [`Investigate ${inc.service}: ${inc.title}`];
    if (inc.description && !isInternalError(inc.description)) parts.push(inc.description);
    onLoad(parts.join(' — '));
    onClose();
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
      {/* Backdrop */}
      <div className="absolute inset-0 bg-black/40" onClick={onClose} />

      {/* Modal — wide, tall, matches Image #11 */}
      <div className="relative bg-white rounded-xl shadow-2xl w-full max-w-5xl max-h-[90vh] flex flex-col overflow-hidden">

        {/* Header */}
        <div className="px-8 pt-6 pb-4 border-b border-gray-100 shrink-0">
          <div className="flex items-start justify-between mb-4">
            <div>
              <h2 className="text-xl font-bold text-gray-800">Incidents</h2>
              <p className="text-sm text-gray-500 mt-0.5">Click an incident to load it into the chat for detailed analysis</p>
            </div>
            <button type="button" onClick={onClose} className="text-gray-400 hover:text-gray-600 transition-colors p-1 rounded mt-1">
              <svg className="w-5 h-5" fill="none" stroke="currentColor" strokeWidth={2} viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
              </svg>
            </button>
          </div>

          {/* Controls row */}
          <div className="flex items-center gap-4 flex-wrap">
            <span className="text-sm text-gray-600">
              Incidents <span className="font-semibold text-gray-800">({incidents.length})</span>
            </span>
            <div className="flex items-center gap-2">
              <span className="text-xs text-gray-500">Timeframe:</span>
              <select
                value={timeframe}
                onChange={e => setTimeframe(e.target.value)}
                className="border border-gray-300 rounded-md px-2.5 py-1.5 text-xs bg-white focus:border-violet-400 focus:outline-none"
              >
                <option value="all">All Time</option>
                <option value="24h">Last 24h</option>
                <option value="7d">Last 7 days</option>
                <option value="30d">Last 30 days</option>
              </select>
            </div>
            <div className="flex items-center gap-2">
              <span className="text-xs text-gray-500">Source:</span>
              <select
                value={source}
                onChange={e => setSource(e.target.value)}
                className="border border-gray-300 rounded-md px-2.5 py-1.5 text-xs bg-white focus:border-violet-400 focus:outline-none"
              >
                <option value="alerts">Alerts</option>
                <option value="servicenow">ServiceNow</option>
                <option value="jira">Jira</option>
              </select>
            </div>
            <button
              type="button"
              className="ml-auto flex items-center gap-1.5 text-xs text-violet-600 hover:text-violet-800 font-medium border border-violet-200 rounded-md px-3 py-1.5 hover:bg-violet-50 transition-colors"
            >
              <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" strokeWidth={2} viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
              </svg>
              Refresh
            </button>
          </div>
        </div>

        {/* Incident list — each item is a bordered card */}
        <div className="flex-1 overflow-y-auto px-8 py-4 space-y-3">
          {incidents.length === 0 ? (
            <div className="py-12 text-center text-sm text-gray-400">
              No open incidents found.
            </div>
          ) : (
            incidents.map((inc) => (
              <div
                key={inc.id}
                className="border border-gray-200 rounded-lg px-5 py-4 flex gap-5 hover:border-violet-200 hover:bg-violet-50/30 transition-colors"
              >
                {/* Left: incident details */}
                <div className="flex-1 min-w-0">
                  {/* Meta row */}
                  <div className="flex items-center gap-2 flex-wrap text-xs text-gray-500 mb-1.5">
                    <span className="px-2 py-0.5 border border-gray-300 rounded text-[11px] font-medium text-gray-600 bg-white shrink-0">
                      {inc.source}
                    </span>
                    {inc.time && <span>{inc.time}</span>}
                    {inc.app && <span>App: <span className="text-gray-700">{inc.app}</span></span>}
                    {inc.by && <span>By: <span className="text-gray-700">{inc.by}</span></span>}
                  </div>

                  {/* Title */}
                  <p className="text-sm font-semibold text-gray-800 mb-1.5 leading-snug">{inc.title}</p>

                  {/* Service / Status / Priority */}
                  <div className="flex items-center gap-2 flex-wrap mb-2 text-xs text-gray-600">
                    <span>Service: <span className="text-gray-800 font-medium">{inc.service}</span></span>
                    <span className="text-gray-300">·</span>
                    <span>Status: <span className="text-gray-800">{inc.status}</span></span>
                    <span className="text-gray-300">·</span>
                    <span>Priority:</span>
                    <span className={`px-1.5 py-0.5 rounded border text-[10px] font-bold ${PRIORITY_COLOR[inc.priority] || PRIORITY_COLOR.Low}`}>
                      {inc.priority}
                    </span>
                  </div>

                  {/* Description */}
                  {inc.description && (
                    <p className="text-xs text-gray-500 leading-relaxed line-clamp-2 mb-1">{inc.description}</p>
                  )}

                  {/* Steps */}
                  {inc.steps && (
                    <p className="text-xs text-gray-400 line-clamp-1">
                      <span className="font-medium text-gray-500">Steps to reproduce:</span> {inc.steps}
                    </p>
                  )}
                </div>

                {/* Right: load button */}
                <div className="shrink-0 flex items-start pt-1">
                  <button
                    type="button"
                    onClick={() => handleLoad(inc)}
                    className="px-4 py-1.5 bg-violet-50 text-violet-700 border border-violet-200 rounded-md text-sm font-semibold hover:bg-violet-100 hover:border-violet-300 transition-colors"
                  >
                    Load
                  </button>
                </div>
              </div>
            ))
          )}
        </div>
      </div>
    </div>
  );
}
