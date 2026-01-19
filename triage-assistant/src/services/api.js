/**
 * API Service for Triage Assistant
 * Connects to the Lambda chat API endpoint
 */

const API_ENDPOINT = import.meta.env.VITE_API_ENDPOINT ||
  'https://42ncxigsnq34qhl7mibjqgt76y0stobv.lambda-url.us-east-1.on.aws/';

/**
 * Send a question to the chat API
 * @param {string} question - The user's question
 * @param {string} service - Optional service name to focus on
 * @param {string} timeRange - Time range to search (e.g., "1h", "6h", "24h")
 * @param {boolean} useMCP - Optional override to use MCP client (null = use server default)
 * @param {string} searchMode - 'quick' for real-time filter_log_events, 'deep' for Logs Insights
 * @returns {Promise<Object>} - The API response
 */
export async function askQuestion(question, service = null, timeRange = '1h', useMCP = null, searchMode = 'quick') {
  const payload = {
    question,
    time_range: timeRange,
    search_mode: searchMode,  // 'quick' = real-time, 'deep' = Logs Insights
  };

  if (service) {
    payload.service = service;
  }

  // Add use_mcp parameter if explicitly provided (overrides server default)
  if (useMCP !== null) {
    payload.use_mcp = useMCP;
  }

  try {
    const response = await fetch(API_ENDPOINT, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(payload),
    });

    if (!response.ok) {
      throw new Error(`API error: ${response.status} ${response.statusText}`);
    }

    const data = await response.json();

    // Parse the body if it's a string (Lambda response format)
    if (typeof data.body === 'string') {
      return JSON.parse(data.body);
    }

    return data;
  } catch (error) {
    console.error('API Error:', error);
    throw error;
  }
}

/**
 * Health check for the API
 * @returns {Promise<boolean>} - True if API is healthy
 */
export async function checkHealth() {
  try {
    const response = await askQuestion('health check', null, '1h');
    return !!response.answer;
  } catch (error) {
    return false;
  }
}

export default {
  askQuestion,
  checkHealth,
};
