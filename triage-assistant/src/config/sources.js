/**
 * Log/incident source configuration for the source strip.
 * CloudWatch and Incident are selectable; others shown as coming soon.
 */
export const SOURCE_STRIP_SOURCES = [
  { id: 'cloudwatch', label: 'CloudWatch', type: 'log', enabled: true, comingSoon: false },
  { id: 'incident', label: 'Incident', type: 'incident', enabled: true, comingSoon: false },
  { id: 'dynatrace', label: 'Dynatrace', type: 'log', enabled: false, comingSoon: true },
  { id: 'elasticsearch', label: 'Elasticsearch', type: 'log', enabled: false, comingSoon: true },
  { id: 'datadog', label: 'Datadog', type: 'log', enabled: false, comingSoon: true },
];
