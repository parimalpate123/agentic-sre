/**
 * SourcePanel - Generic, schema-driven component for rendering data sources.
 *
 * Each source in the `dataSources` array follows a uniform schema:
 *   name          — display name (e.g. "CloudWatch Logs", "Elasticsearch APM")
 *   color         — tailwind color key: orange, amber, blue, green, purple
 *   count         — number of data points
 *   label         — badge text (e.g. "14 log entries", "320 data points")
 *   url           — optional external link
 *   expanded      — whether the terminal box starts open
 *   entries[]     — { timestamp, content, meta } for terminal rendering
 *   total_entries — total count for "N total" display
 *
 * Adding a new source (Datadog, Dynatrace, etc.) requires NO frontend changes —
 * just have the backend append to the data_sources array with the same schema.
 */

import { useState } from 'react';

// Color mappings — maps the `color` key to Tailwind classes
const COLORS = {
  orange:  { badge: 'bg-orange-100 text-orange-700 border-orange-200', border: 'border-orange-500', text: 'text-orange-400' },
  amber:   { badge: 'bg-amber-100 text-amber-700 border-amber-200',   border: 'border-amber-500',  text: 'text-amber-400'  },
  blue:    { badge: 'bg-blue-100 text-blue-700 border-blue-200',       border: 'border-blue-500',   text: 'text-blue-400'   },
  green:   { badge: 'bg-green-100 text-green-700 border-green-200',    border: 'border-green-500',  text: 'text-green-400'  },
  purple:  { badge: 'bg-purple-100 text-purple-700 border-purple-200', border: 'border-purple-500', text: 'text-purple-400' },
  red:     { badge: 'bg-red-100 text-red-700 border-red-200',          border: 'border-red-500',    text: 'text-red-400'    },
  gray:    { badge: 'bg-gray-100 text-gray-600 border-gray-200',       border: 'border-gray-500',   text: 'text-gray-400'   },
};

function getColor(key) {
  return COLORS[key] || COLORS.gray;
}

/** A single source's terminal box */
function SourceTerminal({ source }) {
  const [open, setOpen] = useState(source.expanded ?? false);
  const c = getColor(source.color);
  const hasEntries = source.entries && source.entries.length > 0;

  if (!hasEntries) return null;

  return (
    <div className="mt-2">
      <div className="flex items-center justify-between">
        <button
          type="button"
          onClick={() => setOpen(v => !v)}
          className={`flex items-center gap-1.5 text-xs font-medium ${c.text.replace('text-', 'text-').replace('-400', '-600')} hover:opacity-80`}
        >
          <svg
            className={`w-3 h-3 transition-transform ${open ? 'rotate-180' : ''}`}
            fill="none"
            stroke="currentColor"
            viewBox="0 0 24 24"
          >
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
          </svg>
          {source.name} ({source.total_entries ?? source.entries.length} total)
        </button>
        {source.url && (
          <a
            href={source.url}
            target="_blank"
            rel="noopener noreferrer"
            className="text-xs text-violet-600 hover:text-violet-800 hover:underline flex items-center gap-1 transition-colors"
          >
            <svg className="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14" />
            </svg>
            View in {source.name.split(' ')[0]}
          </a>
        )}
      </div>

      {open && (
        <div className="mt-1.5 bg-gray-800 rounded-lg p-3 max-h-96 overflow-y-auto space-y-2">
          {source.entries.map((entry, idx) => (
            <div key={idx} className={`border-l-2 ${c.border} pl-2`}>
              {entry.timestamp && (
                <p className="text-xs text-gray-400 font-mono mb-0.5">
                  {entry.timestamp}
                  {entry.meta && (
                    <span className="text-gray-500 ml-2" title={entry.meta}>
                      {entry.meta.split('/').pop()}
                    </span>
                  )}
                </p>
              )}
              {!entry.timestamp && entry.meta && (
                <p className={`text-xs font-mono font-semibold mb-0.5 ${c.text}`}>
                  {entry.meta}
                </p>
              )}
              <p className="text-xs text-green-400 font-mono whitespace-pre-wrap break-words">
                {entry.content}
              </p>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

/** Main component: badge row + terminal boxes for each source */
export default function SourcePanel({ dataSources }) {
  if (!dataSources || dataSources.length === 0) return null;

  return (
    <div className="space-y-1">
      {/* Badge row */}
      <div className="flex items-center gap-2 flex-wrap">
        <span className="text-xs font-semibold text-gray-500">Sources:</span>
        {dataSources.map((source) => {
          const c = getColor(source.color);
          return (
            <span
              key={source.name}
              className={`inline-flex items-center gap-1 text-xs px-2 py-0.5 rounded-full font-medium border ${
                source.count > 0 ? c.badge : 'bg-gray-100 text-gray-500 border-gray-200'
              }`}
            >
              {source.name} ({source.label})
              {source.url && source.count > 0 && (
                <a
                  href={source.url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="ml-0.5 hover:opacity-70"
                  title={`Open in ${source.name.split(' ')[0]}`}
                >
                  <svg className="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14" />
                  </svg>
                </a>
              )}
            </span>
          );
        })}
      </div>

      {/* Terminal boxes — one per source with entries */}
      {dataSources.map((source) => (
        <SourceTerminal key={source.name} source={source} />
      ))}
    </div>
  );
}
