/**
 * SynthesisPanel — right-side panel showing AI insights and recommendations
 * from the most recent assistant message. Appears dynamically when content
 * is available; user can hide/show with the toggle button in the controls header.
 */

export default function SynthesisPanel({ synthesis, onClose }) {
  const { insights = [], recommendations = [] } = synthesis;
  const hasContent = insights.length > 0 || recommendations.length > 0;

  if (!hasContent) return null;

  return (
    <div className="w-64 border-l border-gray-200 bg-white flex flex-col shrink-0 overflow-hidden">
      {/* Header */}
      <div className="flex items-center justify-between px-3 py-2 border-b border-gray-100 shrink-0">
        <span className="text-xs font-semibold text-gray-600 tracking-wide uppercase">Analysis</span>
        <button
          type="button"
          onClick={onClose}
          className="text-gray-400 hover:text-gray-600 transition-colors p-0.5 rounded"
          title="Hide panel"
        >
          <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" strokeWidth={2} viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" d="M9 5l7 7-7 7" />
          </svg>
        </button>
      </div>

      {/* Scrollable content */}
      <div className="flex-1 overflow-y-auto px-3 py-3 space-y-4">
        {/* Key Insights */}
        {insights.length > 0 && (
          <section>
            <p className="text-[10px] font-semibold text-violet-600 uppercase tracking-wider mb-2">
              Key Insights
            </p>
            <ul className="space-y-2">
              {insights.map((insight, i) => (
                <li key={i} className="flex gap-1.5 text-xs text-gray-600 leading-relaxed">
                  <span className="text-violet-400 shrink-0 mt-0.5 font-bold">·</span>
                  <span>{insight}</span>
                </li>
              ))}
            </ul>
          </section>
        )}

        {/* Recommendations */}
        {recommendations.length > 0 && (
          <section>
            <p className="text-[10px] font-semibold text-violet-600 uppercase tracking-wider mb-2">
              Recommendations
            </p>
            <ul className="space-y-2">
              {recommendations.map((rec, i) => (
                <li key={i} className="flex gap-1.5 text-xs text-gray-600 leading-relaxed">
                  <span className="text-amber-500 shrink-0 mt-0.5">→</span>
                  <span>{rec}</span>
                </li>
              ))}
            </ul>
          </section>
        )}
      </div>
    </div>
  );
}
