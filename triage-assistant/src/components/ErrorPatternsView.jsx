import React from 'react';

/**
 * Displays error pattern analysis with visual statistics
 */
export default function ErrorPatternsView({ patternData }) {
  if (!patternData) return null;

  const { patterns = [], total_errors = 0 } = patternData;

  if (patterns.length === 0) {
    return (
      <div className="mt-4 p-4 bg-green-50 border border-green-200 rounded-lg">
        <p className="text-green-700 text-sm">No error patterns found in this time range.</p>
      </div>
    );
  }

  // Find max count for bar scaling
  const maxCount = Math.max(...patterns.map(p => p.count));

  return (
    <div className="mt-4 border border-orange-200 rounded-lg overflow-hidden">
      {/* Header */}
      <div className="bg-orange-50 px-4 py-3 border-b border-orange-200">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <span className="text-lg">📊</span>
            <span className="font-semibold text-orange-800">Error Pattern Analysis</span>
          </div>
          <span className="text-xs bg-orange-100 text-orange-700 px-2 py-1 rounded-full">
            {total_errors.toLocaleString()} total errors
          </span>
        </div>
      </div>

      {/* Pattern List */}
      <div className="p-4">
        <table className="w-full text-sm">
          <thead>
            <tr className="text-left text-gray-500 text-xs">
              <th className="pb-2">Error Type</th>
              <th className="pb-2 text-right">Count</th>
              <th className="pb-2 text-right">%</th>
              <th className="pb-2 w-32">Distribution</th>
            </tr>
          </thead>
          <tbody>
            {patterns.map((pattern, index) => (
              <tr key={index} className="border-t border-gray-100">
                <td className="py-2">
                  <span className={`font-medium ${index === 0 ? 'text-red-600' : 'text-gray-700'}`}>
                    {pattern.error_type}
                  </span>
                </td>
                <td className="py-2 text-right font-mono">
                  {pattern.count.toLocaleString()}
                </td>
                <td className="py-2 text-right text-gray-500">
                  {pattern.percentage}%
                </td>
                <td className="py-2">
                  <div className="w-full bg-gray-100 rounded-full h-2">
                    <div
                      className={`h-2 rounded-full ${index === 0 ? 'bg-red-500' : 'bg-orange-400'}`}
                      style={{ width: `${(pattern.count / maxCount) * 100}%` }}
                    />
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* Summary */}
      <div className="px-4 py-2 bg-gray-50 border-t border-orange-100 text-xs text-gray-500">
        Top error accounts for {patterns[0]?.percentage || 0}% of all errors
      </div>
    </div>
  );
}
