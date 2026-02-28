import { useState } from 'react';

/**
 * SuggestedQuestions Component
 * Displays categorized predefined questions in a compact dropdown format
 * AI suggestions from API are shown separately as a flat list
 */

// Categorized predefined questions (exported for use in compact suggestions strip)
export const PREDEFINED_QUESTIONS = {
  'Pattern Analysis': [
    'Show me error patterns in payment-service',
    'What are the common errors in rating-service?',
    'Error breakdown for policy-service',
    'Error statistics for order-service',
  ],
  'Correlation Trace': [
    'Trace CORR-ABBFE258-2314-494A-B9BB-ADB33142404F across services',
    'What happened to request CORR-B4CADDFF-BEE2-4263-BA6F-28D635DD9B50?',
    'Follow correlation ID CORR-96D38CAE-BF5A-45C2-A3A5-440265690931 through all services',
  ],
  'Service Insights': [
    'What errors occurred in payment-service?',
    'Can you provide insights on rating service?',
    'Show me policy-service errors with policy_number',
    'What rating calculations failed in rating-service?',
  ],
  'Error Investigation': [
    'Are there any database connection issues?',
    'What policies were created for account_number ACC-12345678?',
    'Show me logs with correlation_id',
    'Can you find relevant log for policy - POL-201519?',
  ],
};

export default function SuggestedQuestions({ suggestions = [], onQuestionClick, disabled = false }) {
  const [selectedCategory, setSelectedCategory] = useState('');

  const totalQuestions = Object.values(PREDEFINED_QUESTIONS).flat().length;
  const selectedQuestions = selectedCategory ? PREDEFINED_QUESTIONS[selectedCategory] || [] : [];

  // Sample questions to show as examples
  const exampleQuestions = [
    'What errors occurred in payment-service?',
    'Show me policy-service errors with policy_number',
    'What rating calculations failed in rating-service?',
  ];

  return (
    <div className="flex flex-col h-full overflow-y-auto bg-gray-50">
      <div className="px-4 py-3 flex-1">
        {/* Welcome Message */}
        <div className="mb-4 pb-3 border-b border-gray-200">
          <p className="text-xs text-gray-700 leading-relaxed mb-2">
            Hi! I'm <span className="font-bold text-violet-800">TARS</span><span className="text-gray-500"> - Telemetry Analysis & Resolution System</span>. I help analyze CloudWatch logs, identify incidents, and track automated remediation workflows.
          </p>
          <p className="text-xs text-gray-500 italic">
            💡 Try the examples below or select from predefined questions
          </p>
        </div>

        {/* Example Questions - Single line, wrap to 2nd line; full text, smaller font */}
        <div className="mb-4">
          <span className="text-[11px] text-gray-500 mb-2 block font-medium">Example Questions:</span>
          <div className="flex flex-wrap items-center gap-2">
            {exampleQuestions.map((question, index) => (
              <button
                key={index}
                onClick={() => onQuestionClick(question)}
                disabled={disabled}
                className={`shrink-0 text-left text-[11px] px-2.5 py-1.5 rounded-lg border transition-colors max-w-[320px] ${
                  disabled
                    ? 'bg-gray-100 text-gray-400 border-gray-200 cursor-not-allowed'
                    : 'bg-white text-violet-600 border-violet-200 hover:bg-violet-50 hover:border-violet-300'
                }`}
              >
                {question}
              </button>
            ))}
          </div>
        </div>

        {/* AI Suggestions from API (flat list - same as before) */}
        {suggestions.length > 0 && (
          <div className="mb-4">
            <span className="text-xs text-gray-500 mb-2 block font-medium">💡 Suggested questions:</span>
            <div className="flex flex-col gap-2">
              {suggestions.map((question, index) => (
                <button
                  key={index}
                  onClick={() => onQuestionClick(question)}
                  disabled={disabled}
                  className={`w-full text-left text-xs px-3 py-2 rounded-lg border transition-colors ${
                    disabled
                      ? 'bg-gray-100 text-gray-400 border-gray-200 cursor-not-allowed'
                      : 'bg-white text-violet-600 border-violet-200 hover:bg-violet-50 hover:border-violet-300'
                  }`}
                >
                  {question}
                </button>
              ))}
            </div>
          </div>
        )}

        {/* More Questions - Single line only (horizontal scroll if needed) */}
        <div className="flex flex-nowrap items-center gap-2 overflow-x-auto pb-1">
          <span className="text-[11px] text-gray-500 font-medium shrink-0">More Questions:</span>
          <select
            value={selectedCategory}
            onChange={(e) => setSelectedCategory(e.target.value)}
            disabled={disabled}
            className={`shrink-0 text-[11px] px-2.5 py-1.5 bg-white border border-gray-300 rounded-lg text-gray-700 focus:ring-2 focus:ring-violet-500 focus:border-violet-500 min-w-[160px] ${
              disabled ? 'opacity-50 cursor-not-allowed' : 'cursor-pointer'
            }`}
          >
            <option value="">Select category ({totalQuestions} questions)</option>
            {Object.entries(PREDEFINED_QUESTIONS).map(([category, questions]) => (
              <option key={category} value={category}>
                {category} ({questions.length})
              </option>
            ))}
          </select>
          {selectedCategory && selectedQuestions.length > 0 && selectedQuestions.map((question, index) => (
            <button
              key={index}
              onClick={() => onQuestionClick(question)}
              disabled={disabled}
              className={`shrink-0 text-left text-[11px] px-2.5 py-1.5 rounded-lg border transition-colors whitespace-nowrap ${
                disabled
                  ? 'bg-gray-100 text-gray-400 border-gray-200 cursor-not-allowed'
                  : 'bg-white text-violet-600 border-violet-200 hover:bg-violet-50 hover:border-violet-300'
              }`}
              title={question}
            >
              {question}
            </button>
          ))}
        </div>
      </div>
    </div>
  );
}
