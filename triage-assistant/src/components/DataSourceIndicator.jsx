/**
 * DataSourceIndicator - Shows which data sources contributed to the response
 * Displays badges for CloudWatch, Elasticsearch with counts
 */

export default function DataSourceIndicator({ dataSources }) {
  if (!dataSources || dataSources.length === 0) return null;

  const cwSource = dataSources.find(s => s.name === 'CloudWatch');
  const esSource = dataSources.find(s => s.name === 'Elasticsearch');

  return (
    <div className="flex items-center gap-2 flex-wrap">
      <span className="text-xs font-semibold text-gray-500">Sources:</span>

      {/* CloudWatch badge */}
      {cwSource && (
        <span className={`inline-flex items-center gap-1 text-xs px-2 py-0.5 rounded-full font-medium ${
          cwSource.count > 0
            ? 'bg-orange-100 text-orange-700 border border-orange-200'
            : 'bg-gray-100 text-gray-500 border border-gray-200'
        }`}>
          <svg className="w-3 h-3" viewBox="0 0 24 24" fill="none" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
          </svg>
          CloudWatch ({cwSource.count} logs)
          {cwSource.count > 0 && cwSource.url && (
            <a
              href={cwSource.url}
              target="_blank"
              rel="noopener noreferrer"
              className="ml-0.5 hover:text-orange-900"
              title="Open in CloudWatch Console"
            >
              <svg className="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14" />
              </svg>
            </a>
          )}
        </span>
      )}

      {/* Elasticsearch badge */}
      {esSource && (
        <span className="inline-flex items-center gap-1 text-xs px-2 py-0.5 rounded-full font-medium bg-amber-100 text-amber-700 border border-amber-200">
          <svg className="w-3 h-3" viewBox="0 0 24 24" fill="none" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" />
          </svg>
          Elasticsearch ({esSource.count} data points)
        </span>
      )}
    </div>
  );
}
