/**
 * KBSourceIndicator - Expandable panel shown when KB context was used in a response
 */

import { useState } from 'react';

export default function KBSourceIndicator({ sources }) {
  const [expanded, setExpanded] = useState(false);

  if (!sources || sources.length === 0) return null;

  return (
    <div className="mt-2 w-full">
      <button
        type="button"
        onClick={() => setExpanded((v) => !v)}
        className="flex items-center gap-1.5 text-xs text-violet-600 hover:text-violet-800 font-medium"
      >
        <svg className="w-3.5 h-3.5 shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 6.253v13m0-13C10.832 5.477 9.246 5 7.5 5S4.168 5.477 3 6.253v13C4.168 18.477 5.754 18 7.5 18s3.332.477 4.5 1.253m0-13C13.168 5.477 14.754 5 16.5 5c1.747 0 3.332.477 4.5 1.253v13C19.832 18.477 18.247 18 16.5 18c-1.746 0-3.332.477-4.5 1.253" />
        </svg>
        KB Context Used ({sources.length} source{sources.length !== 1 ? 's' : ''})
        <svg
          className={`w-3 h-3 transition-transform ${expanded ? 'rotate-180' : ''}`}
          fill="none"
          stroke="currentColor"
          viewBox="0 0 24 24"
        >
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
        </svg>
      </button>

      {expanded && (
        <div className="mt-2 space-y-2">
          {sources.map((source, idx) => (
            <div
              key={idx}
              className="bg-violet-50 border border-violet-200 rounded-lg p-3 text-xs"
            >
              <div className="flex items-center justify-between mb-1">
                <span className="font-semibold text-violet-700 truncate max-w-[70%]">
                  {source.source_doc || 'KB Document'}
                  {source.section_title ? ` › ${source.section_title}` : ''}
                </span>
                <span className="text-violet-500 shrink-0 ml-2">
                  {Math.round((source.similarity || 0) * 100)}% match
                </span>
              </div>
              <p className="text-gray-600 line-clamp-3 leading-relaxed">
                {source.content}
              </p>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
