import { useState, useRef, useEffect } from 'react'

const API_BASE = '/api/v1'

// Test order data
const TEST_ORDERS = [
  {
    id: 'ORD-001',
    date: 'June 1, 2024',
    total: 79.99,
    items: [
      {
        name: 'Wireless Headphones',
        price: 79.99,
        qty: 1,
        image: 'headphones'
      }
    ],
    status: 'delivered',
    refundable: true
  },
  {
    id: 'ORD-002',
    date: 'June 5, 2024',
    total: 56.97,
    items: [
      {
        name: 'USB-C Cables',
        price: 56.97,
        qty: 3,
        image: 'cable'
      }
    ],
    status: 'shipped',
    refundable: true
  },
  {
    id: 'ORD-003',
    date: 'June 10, 2024',
    total: 49.99,
    items: [
      {
        name: 'Smart Watch',
        price: 49.99,
        qty: 1,
        image: 'watch'
      }
    ],
    status: 'pending',
    refundable: false,
    refundReason: 'Refunds cannot be initiated before delivery.'
  },
  {
    id: 'ORD-004',
    date: 'March 15, 2024',
    total: 129.99,
    items: [
      {
        name: 'Laptop Stand',
        price: 129.99,
        qty: 1,
        image: 'stand'
      }
    ],
    status: 'delivered',
    refundable: false,
    refundReason: 'Outside 30-day refund window.'
  }
]

// Product icon components
const ProductIcon = ({ type }) => {
  const icons = {
    headphones: (
      <svg viewBox="0 0 64 64" fill="none" xmlns="http://www.w3.org/2000/svg">
        <path d="M16 36v12a4 4 0 004 4h4V32h-4a4 4 0 00-4 4z" fill="#333"/>
        <path d="M48 36v12a4 4 0 01-4 4h-4V32h4a4 4 0 014 4z" fill="#333"/>
        <path d="M12 32c0-11.046 8.954-20 20-20s20 8.954 20 20" stroke="#333" strokeWidth="4" fill="none"/>
        <rect x="18" y="30" width="8" height="24" rx="2" fill="#555"/>
        <rect x="38" y="30" width="8" height="24" rx="2" fill="#555"/>
      </svg>
    ),
    cable: (
      <svg viewBox="0 0 64 64" fill="none" xmlns="http://www.w3.org/2000/svg">
        <rect x="8" y="24" width="20" height="16" rx="3" fill="#ddd" stroke="#999" strokeWidth="2"/>
        <rect x="12" y="30" width="4" height="4" fill="#333"/>
        <rect x="20" y="30" width="4" height="4" fill="#333"/>
        <path d="M28 32h8" stroke="#999" strokeWidth="3"/>
        <path d="M36 32c8 0 12-4 12-4" stroke="#999" strokeWidth="3"/>
        <rect x="46" y="26" width="10" height="12" rx="2" fill="#999"/>
      </svg>
    ),
    watch: (
      <svg viewBox="0 0 64 64" fill="none" xmlns="http://www.w3.org/2000/svg">
        <rect x="18" y="8" width="28" height="12" rx="2" fill="#333"/>
        <rect x="18" y="44" width="28" height="12" rx="2" fill="#333"/>
        <rect x="14" y="16" width="36" height="32" rx="6" fill="#1a1a1a"/>
        <circle cx="32" cy="32" r="12" fill="#2a2a2a"/>
        <circle cx="32" cy="32" r="10" stroke="#4a9" strokeWidth="2"/>
        <path d="M32 24v8l6 4" stroke="#4a9" strokeWidth="2" strokeLinecap="round"/>
      </svg>
    ),
    stand: (
      <svg viewBox="0 0 64 64" fill="none" xmlns="http://www.w3.org/2000/svg">
        <path d="M12 48h40" stroke="#999" strokeWidth="3" strokeLinecap="round"/>
        <path d="M32 48V38" stroke="#999" strokeWidth="3"/>
        <path d="M20 38h24" stroke="#999" strokeWidth="2"/>
        <rect x="8" y="12" width="48" height="28" rx="2" fill="#ccc" stroke="#999" strokeWidth="2"/>
        <rect x="12" y="16" width="40" height="20" fill="#e8e8e8"/>
      </svg>
    )
  }
  return <div className="item-image">{icons[type] || <span className="placeholder-icon">?</span>}</div>
}

// Logo component
const ByteGearLogo = () => (
  <svg viewBox="0 0 40 40" fill="none" xmlns="http://www.w3.org/2000/svg">
    <rect width="40" height="40" rx="8" fill="#F5C518"/>
    <path d="M12 12h6l3 8 3-8h6l-6 16h-6l-6-16z" fill="#1a1a1a"/>
    <circle cx="28" cy="16" r="3" fill="#1a1a1a"/>
    <path d="M24 24h8v2.5h-8z" fill="#1a1a1a"/>
  </svg>
)

function App() {
  const [messages, setMessages] = useState([])
  const [input, setInput] = useState('')
  const [loading, setLoading] = useState(false)
  const [customerId] = useState('CUST-123')
  const [dialogOpen, setDialogOpen] = useState(false)
  const [debugStats, setDebugStats] = useState({
    lastAgent: '-',
    lastEndpoint: '-',
    lastEndpointUrl: '-',
    lastModel: '-',
    lastLatencyMs: null,
    lastTokens: null,
    lastRequestType: '-',
    totalRequests: 0,
    localRequests: 0,
    cloudRequests: 0,
    totalTokens: 0,
    avgLatencyMs: 0,
  })
  const chatContainerRef = useRef(null)

  useEffect(() => {
    if (chatContainerRef.current) {
      chatContainerRef.current.scrollTop = chatContainerRef.current.scrollHeight
    }
  }, [messages, loading])

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

  useEffect(() => {
    fetchServerStats()
  }, [])

  const openRefundDialog = () => {
    setMessages([])
    setDialogOpen(true)
  }

  const closeDialog = () => {
    setDialogOpen(false)
    setMessages([])
  }

  const sendMessage = async (e) => {
    e.preventDefault()
    if (!input.trim() || loading) return

    const userMessage = input.trim()
    setInput('')
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
      setMessages(prev => [...prev, {
        type: 'bot',
        content: data.response,
        refundId: data.refund_id,
        refundInitiated: data.refund_initiated,
      }])

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

  const handleQuickAction = (productName) => {
    setInput(`I want to request a refund for ${productName}`)
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

  const getRefundableProducts = () => {
    return TEST_ORDERS.filter(o => o.refundable).flatMap(o => o.items.map(i => i.name))
  }

  return (
    <div className="app">
      {/* Navigation Header */}
      <nav className="nav-header">
        <div className="nav-logo">
          <ByteGearLogo />
          <span>BYTE GEAR</span>
        </div>
        <div className="nav-links">
          <a href="#">SHOP</a>
          <a href="#" className="active">DEALS</a>
          <a href="#">BUILD YOUR PC</a>
          <a href="#">SUPPORT</a>
        </div>
        <div className="nav-user">
          <div className="avatar">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <circle cx="12" cy="8" r="4"/>
              <path d="M4 20c0-4 4-6 8-6s8 2 8 6"/>
            </svg>
          </div>
          <span>Welcome, Alex!</span>
          <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <path d="M6 9l6 6 6-6"/>
          </svg>
        </div>
      </nav>

      {/* Main Content */}
      <main className="main-content">
        <div className="page-title">
          <h1>ORDER HISTORY</h1>
        </div>
        <p className="page-subtitle">Manage your purchases and refunds.</p>

        <div className="orders-container">
          {TEST_ORDERS.map(order => (
            <div key={order.id} className="order-card">
              <div className="order-header">
                <div className="order-info">
                  <h3>ORDER <span className="order-id">#{order.id}</span></h3>
                  <div className="order-total">TOTAL: ${order.total.toFixed(2)}</div>
                </div>
                <div className="order-date">
                  ORDER PLACED: {order.date}
                </div>
              </div>

              <div className="order-items">
                {order.items.map((item, idx) => (
                  <div key={idx} className="order-item">
                    <ProductIcon type={item.image} />
                    <div className="item-details">
                      <h4>{item.name}</h4>
                      <div className="item-qty">Qty: {item.qty}</div>
                      <div className="item-price">Price ${item.price.toFixed(2)}</div>
                      <span className={`status-badge ${order.status}`}>
                        {order.status}
                      </span>
                    </div>
                  </div>
                ))}
              </div>

              <div className="order-actions">
                <button className="btn btn-primary">VIEW DETAILS</button>
                <button className="btn btn-track">TRACK SHIPMENT</button>
                {order.refundable ? (
                  <button
                    className="btn btn-refund"
                    onClick={() => openRefundDialog(order)}
                  >
                    INITIATE REFUND
                  </button>
                ) : (
                  <div className="tooltip-container">
                    <button className="btn btn-refund" disabled>
                      INITIATE REFUND
                    </button>
                    <span className="info-icon">i</span>
                    <div className="tooltip">{order.refundReason}</div>
                  </div>
                )}
              </div>
            </div>
          ))}
        </div>
      </main>

      {/* Footer */}
      <footer className="footer">
        <div className="footer-links">
          <a href="#">ABOUT US</a>
          <a href="#">CAREERS</a>
          <a href="#">PRIVACY POLICY</a>
          <a href="#">TERMS OF SERVICE</a>
        </div>
        <div className="footer-copyright">
          &copy; 2024 BYTE GEAR
        </div>
      </footer>

      {/* Support Chat Button */}
      <button className="support-chat-btn" onClick={() => openRefundDialog(null)}>
        <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
          <path d="M21 15a2 2 0 01-2 2H7l-4 4V5a2 2 0 012-2h14a2 2 0 012 2z"/>
        </svg>
        Support Chat
        <span className="badge">1</span>
      </button>

      {/* Refund Dialog */}
      {dialogOpen && (
        <div className="dialog-overlay" onClick={(e) => e.target === e.currentTarget && closeDialog()}>
          <div className="refund-dialog">
            <div className="dialog-header">
              <h3>Need help with your refund?</h3>
              <button className="dialog-close" onClick={closeDialog}>&times;</button>
            </div>

            <div className="dialog-content" ref={chatContainerRef}>
              {messages.length === 0 && (
                <div className="chat-message bot">
                  Hi Alex, I can help your refund. Please select your item:
                  <div className="quick-actions">
                    {getRefundableProducts().map((product, idx) => (
                      <button
                        key={idx}
                        className="quick-action-btn"
                        onClick={() => handleQuickAction(product)}
                      >
                        {product}
                      </button>
                    ))}
                  </div>
                </div>
              )}

              {messages.map((msg, index) => (
                <div key={index} className={`chat-message ${msg.type}`}>
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

            <form className="dialog-input" onSubmit={sendMessage}>
              <input
                type="text"
                value={input}
                onChange={(e) => setInput(e.target.value)}
                placeholder="Type you message here..."
                disabled={loading}
              />
              <button type="submit" disabled={loading || !input.trim()}>
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                  <path d="M3 12l9-9v6h9v6h-9v6z" transform="rotate(-90 12 12)"/>
                </svg>
              </button>
            </form>
          </div>
        </div>
      )}

      {/* Debug Panel */}
      <aside className="debug-panel">
        <h2>
          Debug Panel
          <button className="reset-btn" onClick={resetStats}>Reset</button>
        </h2>

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
  )
}

export default App
