import { useState, useRef, useEffect } from 'react'

const API_BASE = '/api/v1'

function App() {
  const [messages, setMessages] = useState([])
  const [input, setInput] = useState('')
  const [loading, setLoading] = useState(false)
  const [customerId, setCustomerId] = useState('CUST-123')
  const [debugStats, setDebugStats] = useState({
    // Last request info
    lastAgent: '-',
    lastEndpoint: '-',
    lastEndpointUrl: '-',
    lastModel: '-',
    lastLatencyMs: null,
    lastTokens: null,
    lastRequestType: '-',
    // Aggregate stats (from server)
    totalRequests: 0,
    localRequests: 0,
    cloudRequests: 0,
    totalTokens: 0,
    avgLatencyMs: 0,
  })
  const chatContainerRef = useRef(null)

  // Auto-scroll to bottom when new messages arrive
  useEffect(() => {
    if (chatContainerRef.current) {
      chatContainerRef.current.scrollTop = chatContainerRef.current.scrollHeight
    }
  }, [messages, loading])

  // Fetch aggregate stats from server
  const fetchServerStats = async () => {
    try {
      const response = await fetch('/debug/stats')
      if (response.ok) {
        const data = await response.json()
        setDebugStats(prev => ({
          ...prev,
          totalRequests: data.total_requests || 0,
          localRequests: data.local_requests || 0,
          cloudRequests: data.cloud_requests || 0,
          totalTokens: data.total_tokens || 0,
          avgLatencyMs: data.avg_latency_ms || 0,
        }))
      }
    } catch (error) {
      console.error('Failed to fetch server stats:', error)
    }
  }

  // Fetch stats on mount
  useEffect(() => {
    fetchServerStats()
  }, [])

  const sendMessage = async (e) => {
    e.preventDefault()
    if (!input.trim() || loading) return

    const userMessage = input.trim()
    setInput('')

    // Add user message to chat
    setMessages(prev => [...prev, { type: 'user', content: userMessage }])
    setLoading(true)

    try {
      const response = await fetch(`${API_BASE}/chat`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          customer_id: customerId,
          message: userMessage,
        }),
      })

      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`)
      }

      const data = await response.json()

      // Add bot response to chat
      setMessages(prev => [...prev, {
        type: 'bot',
        content: data.response,
        refundId: data.refund_id,
        refundInitiated: data.refund_initiated,
      }])

      // Update debug stats from response
      if (data.llm_debug) {
        const latency = typeof data.llm_debug.latency_ms === 'number' ? data.llm_debug.latency_ms : 0
        const agent = data.llm_debug.is_local ? 'Local (Ollama)' : 'Cloud (OpenAI)'

        setDebugStats(prev => ({
          ...prev,
          lastAgent: agent,
          lastEndpoint: data.llm_debug.endpoint || '-',
          lastEndpointUrl: data.llm_debug.endpoint_url || '-',
          lastModel: data.llm_debug.model || '-',
          lastLatencyMs: latency || null,
          lastTokens: data.llm_debug.tokens ?? null,
          lastRequestType: data.llm_debug.request_type || '-',
        }))
      }

      // Refresh aggregate stats from server
      await fetchServerStats()

    } catch (error) {
      console.error('Error sending message:', error)
      setMessages(prev => [...prev, {
        type: 'system',
        content: `Error: Could not connect to the RefundBot service. Make sure the backend is running on port 8000.`,
      }])
    } finally {
      setLoading(false)
    }
  }

  const resetStats = async () => {
    try {
      await fetch('/debug/stats/reset', { method: 'POST' })
      await fetchServerStats()
      setDebugStats(prev => ({
        ...prev,
        lastAgent: '-',
        lastEndpoint: '-',
        lastEndpointUrl: '-',
        lastModel: '-',
        lastLatencyMs: null,
        lastTokens: null,
        lastRequestType: '-',
      }))
    } catch (error) {
      console.error('Failed to reset stats:', error)
    }
  }

  return (
    <div className="app">
      <header className="header">
        <h1>RefundBot</h1>
        <p>AI-Powered Customer Service</p>
      </header>

      <div className="layout">
        <div className="main-panel">
          <div className="customer-id-input">
            <label>Customer ID:</label>
            <input
              type="text"
              value={customerId}
              onChange={(e) => setCustomerId(e.target.value)}
              placeholder="CUST-123"
            />
          </div>

          <div className="chat-container" ref={chatContainerRef}>
            {messages.length === 0 && (
              <div className="welcome-message">
                <h2>Welcome to RefundBot</h2>
                <p>
                  I'm here to help you with refund requests. Just tell me about your order
                  and I'll assist you with the refund process.
                </p>
                <div className="orders-list">
                  <h3>Test Orders Available:</h3>
                  <ul>
                    <li><code>ORD-001</code> - Wireless Headphones ($79.99) - Delivered</li>
                    <li><code>ORD-002</code> - USB-C Cables ($56.97) - Shipped</li>
                    <li><code>ORD-003</code> - Smart Watch ($49.99) - Pending (not refundable)</li>
                    <li><code>ORD-004</code> - Laptop Stand ($129.99) - Outside refund window</li>
                  </ul>
                </div>
              </div>
            )}

            {messages.map((msg, index) => (
              <div key={index} className={`message ${msg.type}`}>
                {msg.content}
                {msg.refundInitiated && msg.refundId && (
                  <div className="refund-badge">
                    Refund ID: {msg.refundId}
                  </div>
                )}
              </div>
            ))}

            {loading && (
              <div className="typing-indicator">
                <span></span>
                <span></span>
                <span></span>
              </div>
            )}
          </div>

          <form className="input-container" onSubmit={sendMessage}>
            <input
              type="text"
              value={input}
              onChange={(e) => setInput(e.target.value)}
              placeholder="Type your message..."
              disabled={loading}
            />
            <button type="submit" disabled={loading || !input.trim()}>
              Send
            </button>
          </form>
        </div>

        <aside className="debug-panel">
          <div className="debug-header">
            <h2>Debug Panel</h2>
            <button className="reset-btn" onClick={resetStats} title="Reset stats">
              Reset
            </button>
          </div>

          <div className="debug-section">
            <h3>Last Request</h3>
            <div className="debug-row">
              <span>Agent</span>
              <strong className={debugStats.lastAgent.includes('Local') ? 'local' : debugStats.lastAgent.includes('Cloud') ? 'cloud' : ''}>
                {debugStats.lastAgent}
              </strong>
            </div>
            <div className="debug-row">
              <span>Endpoint</span>
              <strong>{debugStats.lastEndpoint}</strong>
            </div>
            <div className="debug-row">
              <span>Model</span>
              <strong>{debugStats.lastModel}</strong>
            </div>
            <div className="debug-row">
              <span>Request Type</span>
              <strong>{debugStats.lastRequestType}</strong>
            </div>
            <div className="debug-row">
              <span>Latency</span>
              <strong>
                {debugStats.lastLatencyMs ? `${debugStats.lastLatencyMs.toFixed(1)} ms` : '-'}
              </strong>
            </div>
            <div className="debug-row">
              <span>Tokens</span>
              <strong>{debugStats.lastTokens ?? '-'}</strong>
            </div>
          </div>

          <div className="debug-section">
            <h3>Routing Stats</h3>
            <div className="debug-row">
              <span>Total Requests</span>
              <strong>{debugStats.totalRequests}</strong>
            </div>
            <div className="debug-row">
              <span>Local (Ollama)</span>
              <strong className="local">{debugStats.localRequests}</strong>
            </div>
            <div className="debug-row">
              <span>Cloud (OpenAI)</span>
              <strong className="cloud">{debugStats.cloudRequests}</strong>
            </div>
            <div className="debug-row">
              <span>Avg Latency</span>
              <strong>
                {debugStats.avgLatencyMs ? `${debugStats.avgLatencyMs.toFixed(1)} ms` : '-'}
              </strong>
            </div>
            <div className="debug-row">
              <span>Total Tokens</span>
              <strong>{debugStats.totalTokens}</strong>
            </div>
          </div>

          {debugStats.totalRequests > 0 && (
            <div className="debug-section">
              <h3>Distribution</h3>
              <div className="distribution-bar">
                <div
                  className="local-bar"
                  style={{ width: `${(debugStats.localRequests / debugStats.totalRequests) * 100}%` }}
                  title={`Local: ${debugStats.localRequests}`}
                />
                <div
                  className="cloud-bar"
                  style={{ width: `${(debugStats.cloudRequests / debugStats.totalRequests) * 100}%` }}
                  title={`Cloud: ${debugStats.cloudRequests}`}
                />
              </div>
              <div className="distribution-legend">
                <span className="legend-local">Local ({Math.round((debugStats.localRequests / debugStats.totalRequests) * 100)}%)</span>
                <span className="legend-cloud">Cloud ({Math.round((debugStats.cloudRequests / debugStats.totalRequests) * 100)}%)</span>
              </div>
            </div>
          )}
        </aside>
      </div>
    </div>
  )
}

export default App
