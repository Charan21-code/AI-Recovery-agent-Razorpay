import React, { useState, useEffect, useMemo } from 'react';
import { 
  Activity, 
  RefreshCw, 
  CheckCircle, 
  AlertCircle, 
  Search, 
  Clock, 
  Filter, 
  ArrowRight,
  ShieldCheck,
  CreditCard,
  Layers,
  Sparkles
} from 'lucide-react';

const CATEGORY_CHIPS = {
  TRANSIENT_BANK_TIMEOUT: { label: 'Bank Timeout', color: 'var(--cyan)' },
  MANDATE_REJECTED: { label: 'Mandate Reject', color: 'var(--violet)' },
  INSUFFICIENT_FUNDS: { label: 'Low Balance', color: 'var(--amber)' },
  AUTHENTICATION_FAILED: { label: 'Auth Failed', color: 'var(--coral)' },
  EXPIRED_OR_BLOCKED_CARD: { label: 'Card Blocked', color: '#ec4899' },
  USER_CANCELLED: { label: 'Cart Abandoned', color: 'var(--text-muted)' },
  SUCCESS: { label: 'Captured', color: 'var(--mint)' }
};

export default function EventExplorerTab() {
  const [events, setEvents] = useState([]);
  const [loading, setLoading] = useState(true);
  const [searchQuery, setSearchQuery] = useState('');
  const [activeFilter, setActiveFilter] = useState('ALL'); // ALL, ACTIONABLE, FAILED, ABANDONED

  const fetchEvents = async () => {
    setLoading(true);
    try {
      const resp = await fetch('http://localhost:8000/api/v1/analytics/events?limit=50');
      if (resp.ok) {
        const data = await resp.json();
        setEvents(Array.isArray(data) ? data : (data.value || []));
      }
    } catch (e) {
      console.error('Failed to load events:', e);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchEvents();
  }, []);

  const filteredEvents = useMemo(() => {
    return events.filter((ev) => {
      // Search matching
      const q = searchQuery.toLowerCase().trim();
      const matchesSearch = !q || 
        (ev.event_id && ev.event_id.toLowerCase().includes(q)) ||
        (ev.customer_id && ev.customer_id.toLowerCase().includes(q)) ||
        (ev.failure_reason && ev.failure_reason.toLowerCase().includes(q)) ||
        (ev.failure_category && ev.failure_category.toLowerCase().includes(q));

      if (!matchesSearch) return false;

      // Filter pill matching
      if (activeFilter === 'ACTIONABLE') return ev.is_actionable;
      if (activeFilter === 'FAILED') return (ev.event_type || '').includes('failed');
      if (activeFilter === 'ABANDONED') return (ev.event_type || '').includes('abandoned');
      return true;
    });
  }, [events, searchQuery, activeFilter]);

  const actionableCount = useMemo(() => events.filter(e => e.is_actionable).length, [events]);
  const highValueCount = useMemo(() => events.filter(e => (e.amount || 0) >= 10000).length, [events]);

  const formatTime = (iso) => {
    if (!iso) return '—';
    try {
      return new Date(iso).toLocaleTimeString('en-IN', { hour12: false });
    } catch {
      return iso;
    }
  };

  return (
    <div className="events-tab-page">
      {/* Top Banner */}
      <div className="events-header-card">
        <div className="events-header-info">
          <div className="badge badge-cyan">
            <Layers size={13} />
            <span>Telemetry Ledger</span>
          </div>
          <h2 className="events-page-title">Normalized Event Ingestion & Audit Ledger</h2>
          <p className="events-page-desc">
            Point-in-time normalized ledger of payments, checkout drop-offs, and mandate failures. Every event is evaluated for multi-channel recovery eligibility.
          </p>
        </div>

        <div className="events-action-bar">
          <button className="btn btn-secondary btn-sm" onClick={fetchEvents}>
            <RefreshCw size={13} className={loading ? 'animate-spin' : ''} />
            <span>Refresh Ledger</span>
          </button>
        </div>
      </div>

      {/* Summary KPI Strip */}
      <div className="stream-metrics-grid">
        <div className="stream-metric-card">
          <div className="sm-header">
            <span className="sm-label">Total Ingested Events</span>
            <Activity size={15} className="sm-icon text-cyan" />
          </div>
          <div className="sm-val">{events.length}</div>
          <div className="sm-sub">Normalized ledger entries</div>
        </div>

        <div className="stream-metric-card highlight">
          <div className="sm-header">
            <span className="sm-label">Actionable Opportunities</span>
            <Sparkles size={15} className="sm-icon text-mint" />
          </div>
          <div className="sm-val text-mint">{actionableCount}</div>
          <div className="sm-sub">
            {events.length > 0 ? `${((actionableCount / events.length) * 100).toFixed(0)}% eligibility rate` : '—'}
          </div>
        </div>

        <div className="stream-metric-card">
          <div className="sm-header">
            <span className="sm-label">High-Value Occurrences</span>
            <CreditCard size={15} className="sm-icon text-violet" />
          </div>
          <div className="sm-val text-violet">{highValueCount}</div>
          <div className="sm-sub">Transactions &ge; ₹10,000</div>
        </div>

        <div className="stream-metric-card">
          <div className="sm-header">
            <span className="sm-label">Filtered / Non-Actionable</span>
            <ShieldCheck size={15} className="sm-icon text-amber" />
          </div>
          <div className="sm-val">{events.length - actionableCount}</div>
          <div className="sm-sub">Filtered by policy constraints</div>
        </div>
      </div>

      {/* Search & Filter Toolbar */}
      <div className="events-toolbar">
        <div className="events-search-wrapper">
          <Search size={15} className="search-icon" />
          <input 
            type="text" 
            className="events-search-input"
            placeholder="Search by customer, event ID, failure reason..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
          />
          {searchQuery && (
            <button className="clear-search-btn" onClick={() => setSearchQuery('')}>✕</button>
          )}
        </div>

        <div className="feed-filter-pills">
          <button 
            className={`filter-pill ${activeFilter === 'ALL' ? 'active' : ''}`}
            onClick={() => setActiveFilter('ALL')}
          >
            All ({events.length})
          </button>
          <button 
            className={`filter-pill ${activeFilter === 'ACTIONABLE' ? 'active' : ''}`}
            onClick={() => setActiveFilter('ACTIONABLE')}
          >
            Actionable ({actionableCount})
          </button>
          <button 
            className={`filter-pill ${activeFilter === 'FAILED' ? 'active' : ''}`}
            onClick={() => setActiveFilter('FAILED')}
          >
            Payment Failures
          </button>
          <button 
            className={`filter-pill ${activeFilter === 'ABANDONED' ? 'active' : ''}`}
            onClick={() => setActiveFilter('ABANDONED')}
          >
            Cart Drops
          </button>
        </div>
      </div>

      {/* Events Table Container */}
      <div className="events-table-card">
        <div className="table-responsive-wrapper">
          <table className="events-ledger-table">
            <thead>
              <tr>
                <th>Event ID</th>
                <th>Time</th>
                <th>Event Type</th>
                <th>Customer</th>
                <th>Amount</th>
                <th>Method</th>
                <th>Failure Category</th>
                <th>Gateway Reason</th>
                <th>Eligibility</th>
              </tr>
            </thead>
            <tbody>
              {loading ? (
                <tr>
                  <td colSpan="9" className="table-loading-cell">
                    Fetching normalized events ledger...
                  </td>
                </tr>
              ) : filteredEvents.length === 0 ? (
                <tr>
                  <td colSpan="9" className="table-empty-cell">
                    No matching events found in ledger.
                  </td>
                </tr>
              ) : (
                filteredEvents.map((ev) => {
                  const meta = CATEGORY_CHIPS[ev.failure_category] || { label: ev.failure_category || '—', color: 'var(--text-muted)' };
                  return (
                    <tr key={ev.event_id}>
                      <td>
                        <span className="mono-code-chip">{ev.event_id}</span>
                      </td>

                      <td>
                        <span className="time-subtext">{formatTime(ev.timestamp)}</span>
                      </td>

                      <td>
                        <span className={`badge ${
                          (ev.event_type || '').includes('failed') ? 'badge-coral' :
                          (ev.event_type || '').includes('captured') ? 'badge-mint' :
                          (ev.event_type || '').includes('halted') ? 'badge-violet' : 'badge-amber'
                        }`}>
                          {ev.event_type}
                        </span>
                      </td>

                      <td>
                        <span className="customer-id-text">{ev.customer_id}</span>
                      </td>

                      <td>
                        <span className="amount-bold">₹{Math.round(ev.amount || 0).toLocaleString('en-IN')}</span>
                      </td>

                      <td>
                        <span className="method-caps">{ev.payment_method?.toUpperCase() || '—'}</span>
                      </td>

                      <td>
                        <span 
                          className="category-chip"
                          style={{
                            borderColor: `${meta.color}40`,
                            color: meta.color,
                            background: `${meta.color}10`
                          }}
                        >
                          {meta.label}
                        </span>
                      </td>

                      <td>
                        <span className="gateway-reason-text" title={ev.failure_reason}>
                          {ev.failure_reason || '—'}
                        </span>
                      </td>

                      <td>
                        {ev.is_actionable ? (
                          <span className="badge badge-mint">
                            <CheckCircle size={11} /> Eligible
                          </span>
                        ) : (
                          <span className="badge badge-subtle">
                            Filtered
                          </span>
                        )}
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
