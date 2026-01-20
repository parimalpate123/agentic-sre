import React from 'react';

/**
 * Displays diagnosis results with root cause analysis
 */
export default function DiagnosisView({ diagnosis }) {
  if (!diagnosis) return null;

  const {
    hypothesis,
    confidence,
    category,
    component,
    supporting_evidence = [],
    alternative_causes = [],
    reasoning,
    timeline,
    next_steps = []
  } = diagnosis;

  // Confidence color coding
  const getConfidenceColor = (conf) => {
    if (conf >= 90) return 'bg-green-100 text-green-700 border-green-300';
    if (conf >= 70) return 'bg-blue-100 text-blue-700 border-blue-300';
    if (conf >= 50) return 'bg-yellow-100 text-yellow-700 border-yellow-300';
    return 'bg-red-100 text-red-700 border-red-300';
  };

  // Category styling
  const categoryColors = {
    DEPLOYMENT: 'bg-purple-100 text-purple-700',
    CONFIGURATION: 'bg-orange-100 text-orange-700',
    RESOURCE: 'bg-red-100 text-red-700',
    CODE: 'bg-pink-100 text-pink-700',
    DEPENDENCY: 'bg-indigo-100 text-indigo-700',
    LOAD: 'bg-cyan-100 text-cyan-700',
    UNKNOWN: 'bg-gray-100 text-gray-700'
  };

  const categoryColor = categoryColors[category] || categoryColors.UNKNOWN;

  return (
    <div className="mt-4 border border-blue-200 rounded-lg overflow-hidden">
      {/* Header */}
      <div className="bg-blue-50 px-4 py-3 border-b border-blue-200">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <span className="text-lg">🔍</span>
            <span className="font-semibold text-blue-800">Root Cause Diagnosis</span>
          </div>
          <div className={`px-3 py-1 rounded-full border text-sm font-medium ${getConfidenceColor(confidence)}`}>
            {confidence}% Confidence
          </div>
        </div>
      </div>

      {/* Main Content */}
      <div className="p-4 bg-white">
        {/* Hypothesis (Root Cause) */}
        <div className="mb-4">
          <h3 className="text-sm font-semibold text-gray-700 mb-2">Root Cause Hypothesis</h3>
          <p className="text-base text-gray-900 font-medium">{hypothesis || 'No hypothesis provided'}</p>
        </div>

        {/* Category and Component */}
        <div className="flex flex-wrap gap-2 mb-4">
          <span className={`px-3 py-1 rounded-full text-xs font-medium ${categoryColor}`}>
            {category || 'UNKNOWN'}
          </span>
          {component && (
            <span className="px-3 py-1 rounded-full text-xs font-medium bg-gray-100 text-gray-700">
              Component: {component}
            </span>
          )}
        </div>

        {/* Supporting Evidence */}
        {supporting_evidence && supporting_evidence.length > 0 && (
          <div className="mb-4">
            <h3 className="text-sm font-semibold text-gray-700 mb-2">Supporting Evidence</h3>
            <ul className="list-disc list-inside space-y-1">
              {supporting_evidence.map((evidence, index) => (
                <li key={index} className="text-sm text-gray-600">{evidence}</li>
              ))}
            </ul>
          </div>
        )}

        {/* Alternative Causes */}
        {alternative_causes && alternative_causes.length > 0 && (
          <div className="mb-4">
            <h3 className="text-sm font-semibold text-gray-700 mb-2">Alternative Causes</h3>
            <ul className="list-disc list-inside space-y-1">
              {alternative_causes.map((cause, index) => (
                <li key={index} className="text-sm text-gray-600">{cause}</li>
              ))}
            </ul>
          </div>
        )}

        {/* Reasoning */}
        {reasoning && (
          <div className="mb-4">
            <h3 className="text-sm font-semibold text-gray-700 mb-2">Reasoning</h3>
            <p className="text-sm text-gray-600 whitespace-pre-wrap">{reasoning}</p>
          </div>
        )}

        {/* Timeline */}
        {timeline && (
          <div className="mb-4">
            <h3 className="text-sm font-semibold text-gray-700 mb-2">Timeline</h3>
            <p className="text-sm text-gray-600">{timeline}</p>
          </div>
        )}

        {/* Next Steps */}
        {next_steps && next_steps.length > 0 && (
          <div className="mb-4">
            <h3 className="text-sm font-semibold text-gray-700 mb-2">Recommended Next Steps</h3>
            <ol className="list-decimal list-inside space-y-1">
              {next_steps.map((step, index) => (
                <li key={index} className="text-sm text-gray-600">{step}</li>
              ))}
            </ol>
          </div>
        )}
      </div>

      {/* Footer */}
      <div className="px-4 py-2 bg-gray-50 border-t border-blue-100 text-xs text-gray-500">
        Diagnosis generated at {diagnosis.diagnosed_at ? new Date(diagnosis.diagnosed_at).toLocaleString() : 'unknown time'}
      </div>
    </div>
  );
}
