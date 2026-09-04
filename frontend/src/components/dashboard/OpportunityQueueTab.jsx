import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { 
  ListFilter, 
  Sparkles, 
  ArrowUpDown, 
  CheckCircle, 
  Search, 
  RefreshCw, 
  AlertCircle, 
  Phone, 
  ArrowRight,
  TrendingUp,
  ShieldAlert,
  Layers,
  Flame,
  CreditCard
} from 'lucide-react';

export default function OpportunityQueueTab({ onSwitchToVoice }) {
  const navigate = useNavigate();
  const [queue, setQueue] = useState([]);
  const [loading, setLoading] = useState(true);
  const [filterPriority, setFilterPriority] = useState('ALL');
  const [searchTerm, setSearchTerm] = useState('');

  const fetchQueue = async () => {
    setLoading(true);
    try {
      const resp = await fetch('http://localhost:8000/api/v1/analytics/queue?limit=50');
      if (resp.ok) {
        const data = await resp.json();
        setQueue(data);
      }
    } catch (e) {
      console.error('Failed to load queue:', e);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchQueue();
  }, []);

  const filtered = queue.filter((item) => {
    const q = searchTerm.toLowerCase();
    const matchSearch = 
      (item.customer_name && item.customer_name.toLowerCase().includes(q)) ||
      (item.payment_id && item.payment_id.toLowerCase().includes(q)) ||
      (item.customer_id && item.customer_id.toLowerCase().includes(q));
    const matchPriority = filterPriority === 'ALL' || item.priority === filterPriority;
    return matchSearch && matchPriority;
  });

  const totalAtRisk = filtered.reduce((acc, curr) => acc + (curr.amount || 0), 0);
  const totalExpected = filtered.reduce((acc, curr) => acc + (curr.expected_recovery_value || 0), 0);
  const criticalCount = filtered.filter((i) => i.priority === 'CRITICAL').length;

  const handleInitiateCall = (item) => {
    const customerPayload = {
      id: item.customer_id,
      customer_id: item.customer_id,
      name: item.customer_name,
      customer_name: item.customer_name,
      amount: item.amount,
      payment_id: item.payment_id,
      failure_reason: item.failure_category ? item.failure_category.replace(/_/g, ' ') : 'Payment Gateway Dropoff',
      reason: item.failure_category ? item.failure_category.replace(/_/g, ' ') : 'Payment Gateway Dropoff',
      phone: item.phone || '+9198' + Math.floor(10000000 + Math.random() * 90000000),
      autoStart: true,
    };

    if (onSwitchToVoice) {
      onSwitchToVoice(customerPayload);
    } else {
      navigate('/console/voice', { state: { targetCustomer: customerPayload } });
    }
  };

  const formatActionName = (action) => {
    if (!action) return '—';
    const names = {
      START_VOICE_RECOVERY: 'Voice AI Outbound',
      SEND_PAYMENT_METHOD_UPDATE: '1-Click Method Update',
      GENERATE_PAYMENT_LINK: 'Instant Checkout Link',
      IMMEDIATE_RETRY: 'Silent Gateway Retry',
      DELAYED_RETRY: 'Scheduled Off-Peak Retry',
      ESCALATE_TO_HUMAN: 'Account Manager Escalation',
      SEND_CHECKOUT_RECOVERY: 'WhatsApp Cart Recovery',
      SEND_PAYMENT_REMINDER: 'Multi-Channel Reminder'
    };
    return names[action] || action.replace(/_/g, ' ');
  };

  return (
    <div className="queue-tab-container">
      {/* Top Opportunity Queue Stat Highlights */}
      <div className="stream-metrics-grid">
        <div className="stream-metric-card">
          <div className="sm-header">
            <span className="sm-label">Total At-Risk Volume</span>
            <Layers size={15} className="sm-icon text-cyan" />
          </div>
          <div className="sm-val">₹{Math.round(totalAtRisk).toLocaleString('en-IN')}</div>
          <div className="sm-sub">{filtered.length} prioritized transactions</div>
        </div>

        <div className="stream-metric-card highlight">
          <div className="sm-header">
            <span className="sm-label">Expected Net Recovery E[V]</span>
            <TrendingUp size={15} className="sm-icon text-mint" />
          </div>
          <div className="sm-val text-mint">₹{Math.round(totalExpected).toLocaleString('en-IN')}</div>
          <div className="sm-sub">P(recovery) × Value − Delivery Cost</div>
        </div>

        <div className="stream-metric-card">
          <div className="sm-header">
            <span className="sm-label">Critical Priority Cases</span>
            <Flame size={15} className="sm-icon text-coral" />
          </div>
          <div className="sm-val text-coral">{criticalCount}</div>
          <div className="sm-sub">High-value or VIP customer drop-offs</div>
        </div>

        <div className="stream-metric-card">
          <div className="sm-header">
            <span className="sm-label">Mean Propensity Score</span>
            <Sparkles size={15} className="sm-icon text-violet" />
          </div>
          <div className="sm-val text-violet">
            {filtered.length > 0 
              ? `${Math.round((filtered.reduce((a, c) => a + (c.recovery_propensity || 0), 0) / filtered.length) * 100)}%`
              : '—'}
          </div>
          <div className="sm-sub">Contextual ML predicted success</div>
        </div>
      </div>

      {/* Filter and Search Bar */}
      <div className="events-toolbar">
        <div className="events-search-wrapper">
          <Search size={15} className="search-icon" />
          <input
            type="text"
            placeholder="Search by customer name, ID, or payment ID..."
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            className="events-search-input"
          />
          {searchTerm && (
            <button className="clear-search-btn" onClick={() => setSearchTerm('')}>✕</button>
          )}
        </div>

        <div className="feed-filter-pills">
          <button 
            className={`filter-pill ${filterPriority === 'ALL' ? 'active' : ''}`}
            onClick={() => setFilterPriority('ALL')}
          >
            All Priority ({queue.length})
          </button>
          <button 
            className={`filter-pill ${filterPriority === 'CRITICAL' ? 'active' : ''}`}
            onClick={() => setFilterPriority('CRITICAL')}
          >
            Critical Tier
          </button>
          <button 
            className={`filter-pill ${filterPriority === 'HIGH' ? 'active' : ''}`}
            onClick={() => setFilterPriority('HIGH')}
          >
            High Priority
          </button>
          <button 
            className={`filter-pill ${filterPriority === 'MEDIUM' ? 'active' : ''}`}
            onClick={() => setFilterPriority('MEDIUM')}
          >
            Medium
          </button>

          <button className="btn btn-secondary btn-sm" onClick={fetchQueue} title="Refresh Queue">
            <RefreshCw size={13} className={loading ? 'animate-spin' : ''} />
          </button>
        </div>
      </div>

      {/* Ranked Queue Table */}
      <div className="events-table-card">
        <div className="table-responsive-wrapper">
          <table className="events-ledger-table">
            <thead>
              <tr>
                <th style={{ width: '65px' }}>Rank</th>
                <th style={{ width: '160px' }}>Customer</th>
                <th style={{ width: '95px' }}>Priority</th>
                <th style={{ width: '110px' }}>At-Risk Amount</th>
                <th style={{ width: '150px' }}>Failure Reason</th>
                <th style={{ width: '130px' }}>ML Propensity</th>
                <th style={{ width: '130px' }}>Expected Value E[V]</th>
                <th style={{ width: '170px' }}>Recommended Action</th>
                <th style={{ width: '140px', textAlign: 'right' }}>Action</th>
              </tr>
            </thead>
            <tbody>
              {loading ? (
                <tr>
                  <td colSpan="9" className="table-loading-cell">
                    Computing optimal opportunity ranking...
                  </td>
                </tr>
              ) : filtered.length === 0 ? (
                <tr>
                  <td colSpan="9" className="table-empty-cell">
                    No matching opportunity cases found.
                  </td>
                </tr>
              ) : (
                filtered.map((item) => {
                  const isVoice = item.recommended_action === 'START_VOICE_RECOVERY';
                  return (
                    <tr key={item.event_id || item.payment_id}>
                      {/* Rank */}
                      <td>
                        <span className={`rank-pill ${item.rank === 1 ? 'rank-gold' : ''}`}>
                          #{item.rank}
                        </span>
                      </td>

                      {/* Customer */}
                      <td>
                        <div className="customer-cell-wrap">
                          <span className="customer-name-text">{item.customer_name}</span>
                          {item.is_vip && <span className="vip-badge-sm">VIP</span>}
                        </div>
                      </td>

                      {/* Priority */}
                      <td>
                        <span className={`badge ${
                          item.priority === 'CRITICAL' ? 'badge-coral' : 
                          item.priority === 'HIGH' ? 'badge-amber' : 'badge-cyan'
                        }`}>
                          {item.priority}
                        </span>
                      </td>

                      {/* Amount */}
                      <td>
                        <span className="amount-bold">₹{Math.round(item.amount).toLocaleString('en-IN')}</span>
                      </td>

                      {/* Failure Reason */}
                      <td>
                        <span className="category-chip" style={{ borderColor: 'rgba(255, 255, 255, 0.1)', color: 'var(--text-secondary)' }}>
                          {(item.failure_category || 'DROP_OFF').replace(/_/g, ' ')}
                        </span>
                      </td>

                      {/* ML Propensity */}
                      <td>
                        <div className="propensity-bar-wrap">
                          <div className="propensity-bar-track">
                            <div 
                              className="propensity-bar-fill" 
                              style={{ 
                                width: `${Math.round((item.recovery_propensity || 0) * 100)}%`,
                                background: item.recovery_propensity > 0.65 ? 'var(--mint)' : item.recovery_propensity > 0.35 ? 'var(--cyan)' : 'var(--amber)'
                              }} 
                            />
                          </div>
                          <span className="propensity-pct-text">
                            {Math.round((item.recovery_propensity || 0) * 100)}%
                          </span>
                        </div>
                      </td>

                      {/* Expected Value */}
                      <td>
                        <span className="net-reward-mint font-bold">
                          ₹{Math.round(item.expected_recovery_value).toLocaleString('en-IN')}
                        </span>
                      </td>

                      {/* Recommended Action */}
                      <td>
                        <span className="action-pill-code">
                          {formatActionName(item.recommended_action)}
                        </span>
                      </td>

                      {/* Action Button */}
                      <td style={{ textAlign: 'right' }}>
                        <div style={{ display: 'inline-flex', gap: '6px', alignItems: 'center' }}>
                          <button 
                            className={`btn ${isVoice ? 'btn-primary' : 'btn-secondary'} btn-sm`}
                            title={`Initiate recovery call for ${item.customer_name}`}
                            onClick={() => handleInitiateCall(item)}
                          >
                            <Phone size={12} />
                            <span>Call</span>
                          </button>
                        </div>
                      </td>
                    </tr>
                  );
                })
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
