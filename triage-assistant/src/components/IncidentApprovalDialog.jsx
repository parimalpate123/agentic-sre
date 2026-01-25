/**
 * Incident Approval Dialog
 * Shows full workflow preview and requires user approval before creating GitHub issue
 */

export default function IncidentApprovalDialog({ 
  isOpen, 
  onApprove, 
  onCancel, 
  incidentPreview 
}) {
  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
      <div className="bg-white rounded-lg shadow-xl max-w-2xl w-full mx-4 max-h-[90vh] overflow-y-auto">
        <div className="p-6">
          {/* Header */}
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-xl font-bold text-gray-800">Approve Incident Creation</h2>
            <button
              onClick={onCancel}
              className="text-gray-400 hover:text-gray-600 text-2xl leading-none"
            >
              ×
            </button>
          </div>

          {/* Workflow Preview */}
          <div className="mb-6">
            <h3 className="text-sm font-semibold text-gray-700 mb-3">Remediation Workflow Preview</h3>
            
            <div className="space-y-4">
              {/* Step 1: Issue Creation */}
              <div className="border-l-4 border-blue-500 pl-4 py-2">
                <div className="flex items-start gap-2">
                  <div className="w-6 h-6 bg-blue-500 text-white rounded-full flex items-center justify-center text-xs font-bold flex-shrink-0 mt-0.5">
                    1
                  </div>
                  <div className="flex-1">
                    <h4 className="font-semibold text-gray-800">GitHub Issue Creation</h4>
                    <p className="text-sm text-gray-600 mt-1">
                      A GitHub issue will be created in <span className="font-mono text-xs bg-gray-100 px-1 rounded">{incidentPreview?.repo || 'service repository'}</span> with:
                    </p>
                    <ul className="text-sm text-gray-600 mt-2 ml-4 list-disc space-y-1">
                      <li>Root cause analysis</li>
                      <li>Error patterns and logs</li>
                      <li>Recommended fix</li>
                      <li>Incident context</li>
                    </ul>
                  </div>
                </div>
              </div>

              {/* Step 2: Issue Agent */}
              <div className="border-l-4 border-purple-500 pl-4 py-2">
                <div className="flex items-start gap-2">
                  <div className="w-6 h-6 bg-purple-500 text-white rounded-full flex items-center justify-center text-xs font-bold flex-shrink-0 mt-0.5">
                    2
                  </div>
                  <div className="flex-1">
                    <h4 className="font-semibold text-gray-800">Issue Agent Analysis</h4>
                    <p className="text-sm text-gray-600 mt-1">
                      The Issue Agent (GitHub Action) will automatically:
                    </p>
                    <ul className="text-sm text-gray-600 mt-2 ml-4 list-disc space-y-1">
                      <li>Analyze the issue and identify affected code</li>
                      <li>Generate code fix using AI (Claude via Bedrock)</li>
                      <li>Create a Pull Request with the fix</li>
                    </ul>
                  </div>
                </div>
              </div>

              {/* Step 3: PR Review */}
              <div className="border-l-4 border-green-500 pl-4 py-2">
                <div className="flex items-start gap-2">
                  <div className="w-6 h-6 bg-green-500 text-white rounded-full flex items-center justify-center text-xs font-bold flex-shrink-0 mt-0.5">
                    3
                  </div>
                  <div className="flex-1">
                    <h4 className="font-semibold text-gray-800">PR Review Agent</h4>
                    <p className="text-sm text-gray-600 mt-1">
                      The PR Review Agent will automatically:
                    </p>
                    <ul className="text-sm text-gray-600 mt-2 ml-4 list-disc space-y-1">
                      <li>Review the generated code fix</li>
                      <li>Validate the changes</li>
                      <li>Approve or request changes</li>
                    </ul>
                  </div>
                </div>
              </div>

              {/* Step 4: Human Approval */}
              <div className="border-l-4 border-orange-500 pl-4 py-2">
                <div className="flex items-start gap-2">
                  <div className="w-6 h-6 bg-orange-500 text-white rounded-full flex items-center justify-center text-xs font-bold flex-shrink-0 mt-0.5">
                    4
                  </div>
                  <div className="flex-1">
                    <h4 className="font-semibold text-gray-800">Human Approval Required</h4>
                    <p className="text-sm text-gray-600 mt-1">
                      You will be notified when the PR is ready. You can:
                    </p>
                    <ul className="text-sm text-gray-600 mt-2 ml-4 list-disc space-y-1">
                      <li>Review the PR in GitHub</li>
                      <li>Merge the PR when satisfied</li>
                      <li>Request changes if needed</li>
                    </ul>
                  </div>
                </div>
              </div>
            </div>
          </div>

          {/* Incident Summary */}
          {incidentPreview && (
            <div className="bg-gray-50 rounded-lg p-4 mb-6">
              <h3 className="text-sm font-semibold text-gray-700 mb-2">Incident Summary</h3>
              <div className="space-y-2 text-sm">
                <div>
                  <span className="font-medium text-gray-700">Service:</span>{' '}
                  <span className="text-gray-600">{incidentPreview.service || 'Unknown'}</span>
                </div>
                {incidentPreview.rootCause && (
                  <div>
                    <span className="font-medium text-gray-700">Root Cause:</span>{' '}
                    <span className="text-gray-600">{incidentPreview.rootCause}</span>
                  </div>
                )}
                {incidentPreview.confidence !== undefined && (
                  <div>
                    <span className="font-medium text-gray-700">Confidence:</span>{' '}
                    <span className="text-gray-600">{incidentPreview.confidence}%</span>
                  </div>
                )}
              </div>
            </div>
          )}

          {/* Warning */}
          <div className="bg-yellow-50 border border-yellow-200 rounded-lg p-4 mb-6">
            <div className="flex items-start gap-2">
              <span className="text-yellow-600 text-lg">⚠️</span>
              <div className="flex-1">
                <p className="text-sm font-medium text-yellow-800">
                  This will create a GitHub issue and trigger automated code fix generation.
                </p>
                <p className="text-xs text-yellow-700 mt-1">
                  The Issue Agent will analyze the problem and create a PR with a proposed fix. 
                  You'll have full visibility and control throughout the process.
                </p>
              </div>
            </div>
          </div>

          {/* Actions */}
          <div className="flex gap-3 justify-end">
            <button
              onClick={onCancel}
              className="px-4 py-2 text-sm font-medium text-gray-700 bg-gray-100 hover:bg-gray-200 rounded-lg transition-colors"
            >
              Cancel
            </button>
            <button
              onClick={onApprove}
              className="px-4 py-2 text-sm font-medium text-white bg-blue-600 hover:bg-blue-700 rounded-lg transition-colors"
            >
              Approve & Create Issue
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
