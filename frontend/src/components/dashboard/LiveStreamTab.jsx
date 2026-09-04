import React, { useState, useEffect, useRef, useMemo } from 'react';
import { 
  Activity, 
  Pause, 
  Play, 
  Zap, 
  TrendingUp, 
  ShieldCheck, 
  AlertTriangle, 
  Wifi, 
  WifiOff, 
  RotateCcw,
  Sparkles,
  Filter,
  ArrowUpRight
} from 'lucide-react';

const MAX_EVENTS = 60;

const CATEGORY_META = {
  TRANSIENT_BANK_TIMEOUT: { label: 'Bank Timeout', color: 'var(--cyan)' },
  MANDATE_REJECTED: { label: 'Mandate Reject', color: 'var(--violet)' },
  INSUFFICIENT_FUNDS: { label: 'Low Balance', color: 'var(--amber)' },
  AUTHENTICATION_FAILED: { label: 'Auth Failed', color: 'var(--coral)' },
  EXPIRED_OR_BLOCKED_CARD: { label: 'Card Blocked', color: '#ec4899' },
  USER_CANCELLED: { label: 'Cart Abandoned', color: 'var(--text-muted)' },
  INACTIVITY_DROPOFF: { label: 'Drop-off', color: 'var(--text-muted)' },
};

export default function LiveStreamTab() {
  const [events, setEvents] = useState([]);
  const [connected, setConnected] = useState(false);
  const [paused, setPaused] = useState(false);
  const [totalProcessed, setTotalProcessed] = useState(0);
  const [totalRecovered, setTotalRecovered] = useState(0);
  const [stats, setStats] = useState({ recovered: 0, failed: 0, blocked: 0, escalated: 0 });
  const [activeFilter, setActiveFilter] = useState('ALL'); // ALL, RECOVERED, ESCALATED, VIP

  const esRef = useRef(null);
  const pausedRef = useRef(false);
  const tableContainerRef = useRef(null);

  const startStream = () => {
    if (esRef.current) esRef.current.close();

    const es = new EventSource('http://localhost:8000/api/v1/stream/live-events?interval_seconds=3');
    esRef.current = es;

    es.onopen = () => setConnected(true);

    es.onmessage = (e) => {
      if (pausedRef.current) return;
      try {
        const data = JSON.parse(e.data);
        if (data.stream_type === 'connected' || data.stream_type === 'error') return;

        setEvents((prev) => [data, ...prev].slice(0, MAX_EVENTS));
        setTotalProcessed((n) => n + 1);

        if (data.payment_success) {
          setTotalRecovered((r) => r + (data.net_reward || 0));
          setStats((s) => ({ ...s, recovered: s.recovered + 1 }));
        } else if (data.policy_verdict === 'BLOCKED') {
          setStats((s) => ({ ...s, blocked: s.blocked + 1 }));
        } else if (data.policy_verdict === 'ESCALATED') {
          setStats((s) => ({ ...s, escalated: s.escalated + 1 }));
        } else {
          setStats((s) => ({ ...s, failed: s.failed + 1 }));
        }
      } catch {
        /* skip parse error */
      }
    };

    es.onerror = () => {
      setConnected(false);
      es.close();
    };
  };

  useEffect(() => {
    startStream();
    return () => esRef.current?.close();
  }, []);

  // Auto-scroll to top when a new event arrives
  useEffect(() => {
    if (tableContainerRef.current && !paused) {
      tableContainerRef.current.scrollTop = 0;
    }
  }, [events]);

  const handlePauseToggle = () => {
    const next = !paused;
    setPaused(next);
    pausedRef.current = next;
  };

  const handleReset = () => {
    setEvents([]);
    setTotalProcessed(0);
    setTotalRecovered(0);
    setStats({ recovered: 0, failed: 0, blocked: 0, escalated: 0 });
    startStream();
  };

  const formatTime = (iso) => {
    try {
      return new Date(iso).toLocaleTimeString('en-IN', { hour12: false });
    } catch {
      return '--:--:--';
    }
  };

  const filteredEvents = useMemo(() => {
    if (activeFilter === 'RECOVERED') return events.filter(e => e.payment_success);
    if (activeFilter === 'ESCALATED') return events.filter(e => e.policy_verdict === 'ESCALATED');
    if (activeFilter === 'VIP') return events.filter(e => e.is_vip);
    return events;
  }, [events, activeFilter]);

  const formatAction = (act) => {
    if (!act) return '—';
    return act.replace(/_/g, ' ');
  };

  return (
    <div className="stream-tab-page">
      {/* Stream Control & Status Bar */}
      <div className="stream-ctrl-bar">
        <div className="stream-status-box">
          <div className={`live-pulse-badge ${connected ? (paused ? 'paused' : 'live') : 'offline'}`}>
            <span className="pulse-dot"></span>
            {connected ? (paused ? 'STREAM PAUSED' : 'LIVE SSE STREAM') : 'STREAM OFFLINE'}
          </div>
          <span className="stream-rate-label">Autonomous recovery pipeline event stream (~3s interval)</span>
        </div>

        <div className="stream-actions-group">
          <button 
            className={`btn ${paused ? 'btn-primary' : 'btn-secondary'} btn-sm`}
            onClick={handlePauseToggle}
          >
            {paused ? <Play size={13} /> : <Pause size={13} />}
            <span>{paused ? 'Resume Stream' : 'Pause Stream'}</span>
          </button>

          <button 
            className="btn btn-secondary btn-sm"
            onClick={handleReset}
            title="Reset event buffer and counters"
          >
            <RotateCcw size={13} />
            <span>Reset</span>
          </button>
        </div>
      </div>

      {/* Live Stream Metrics Strip */}
      <div className="stream-metrics-grid">
        <div className="stream-metric-card">
          <div className="sm-header">
            <span className="sm-label">Events Processed</span>
            <Activity size={15} className="sm-icon text-cyan" />
          </div>
          <div className="sm-val">{totalProcessed.toLocaleString()}</div>
          <div className="sm-sub">Normalized ledger entries</div>
        </div>

        <div className="stream-metric-card">
          <div className="sm-header">
            <span className="sm-label">Autonomous Recoveries</span>
            <TrendingUp size={15} className="sm-icon text-mint" />
          </div>
          <div className="sm-val text-mint">{stats.recovered.toLocaleString()}</div>
          <div className="sm-sub">
            {totalProcessed > 0 ? `${((stats.recovered / totalProcessed) * 100).toFixed(1)}% recovery rate` : 'Awaiting data'}
          </div>
        </div>

        <div className="stream-metric-card">
          <div className="sm-header">
            <span className="sm-label">Escalated / Blocked</span>
            <ShieldCheck size={15} className="sm-icon text-violet" />
          </div>
          <div className="sm-val text-violet">{(stats.escalated + stats.blocked).toLocaleString()}</div>
          <div className="sm-sub">Protected by fatigue bounds</div>
        </div>

        <div className="stream-metric-card highlight">
          <div className="sm-header">
            <span className="sm-label">Net Reward Logged</span>
            <Zap size={15} className="sm-icon text-cyan" />
          </div>
          <div className="sm-val text-gradient">₹{Math.round(totalRecovered).toLocaleString('en-IN')}</div>
          <div className="sm-sub">Delivery cost auto-subtracted</div>
        </div>
      </div>

      {/* Live Event Feed Panel */}
      <div className="stream-feed-wrapper">
        {/* Filter Bar */}
        <div className="feed-filter-bar">
          <div className="filter-title-group">
            <h4 className="feed-title">Real-Time Ingestion Feed</h4>
            <span className="feed-count-pill">{filteredEvents.length} events</span>
          </div>

          <div className="feed-filter-pills">
            <button 
              className={`filter-pill ${activeFilter === 'ALL' ? 'active' : ''}`}
              onClick={() => setActiveFilter('ALL')}
            >
              All Events ({events.length})
            </button>
            <button 
              className={`filter-pill ${activeFilter === 'RECOVERED' ? 'active' : ''}`}
              onClick={() => setActiveFilter('RECOVERED')}
            >
              Recovered ({stats.recovered})
            </button>
            <button 
              className={`filter-pill ${activeFilter === 'ESCALATED' ? 'active' : ''}`}
              onClick={() => setActiveFilter('ESCALATED')}
            >
              Escalated ({stats.escalated})
            </button>
            <button 
              className={`filter-pill ${activeFilter === 'VIP' ? 'active' : ''}`}
              onClick={() => setActiveFilter('VIP')}
            >
              VIP Tier Only
            </button>
          </div>
        </div>

        {/* Rock-Solid Table Container with Horizontal Scroll & Sticky Header */}
        <div className="stream-table-scroll-container" ref={tableContainerRef}>
          <table className="stream-dedicated-table">
            <thead>
              <tr>
                <th style={{ width: '85px' }}>TIME</th>
                <th style={{ width: '140px' }}>CUSTOMER</th>
                <th style={{ width: '95px' }}>AMOUNT</th>
                <th style={{ width: '135px' }}>FAILURE CLASS</th>
                <th style={{ width: '120px' }}>ML PROPENSITY</th>
                <th style={{ width: '160px' }}>ACTION DISPATCHED</th>
                <th style={{ width: '105px' }}>POLICY</th>
                <th style={{ minWidth: '260px', maxWidth: '360px' }}>AI REASONING</th>
                <th style={{ width: '110px' }}>OUTCOME</th>
                <th style={{ width: '115px', textAlign: 'right' }}>NET REWARD</th>
              </tr>
            </thead>
            <tbody>
              {filteredEvents.length === 0 ? (
                <tr>
                  <td colSpan="10" className="stream-empty-td">
                    <div className="stream-empty-state">
                      <Activity size={32} className="stream-pulse-icon" />
                      <p className="empty-text">
                        {connected 
                          ? (events.length === 0 ? 'Connecting to live pipeline stream... First event arriving in ~3s' : 'No events match the selected filter')
                          : 'Stream offline. Reconnecting to local pipeline server...'}
                      </p>
                    </div>
                  </td>
                </tr>
              ) : (
                filteredEvents.map((ev, idx) => {
                  const meta = CATEGORY_META[ev.failure_category] || { label: ev.failure_category, color: 'var(--text-muted)' };
                  return (
                    <tr 
                      key={ev.simulation_id ? `${ev.simulation_id}-${idx}` : idx}
                      className={`${idx === 0 && !paused ? 'row-just-arrived' : ''} ${ev.payment_success ? 'status-recovered-tr' : ev.policy_verdict === 'BLOCKED' ? 'status-blocked-tr' : ''}`}
                    >
                      {/* TIME */}
                      <td>
                        <span className="mono-time">{formatTime(ev.timestamp)}</span>
                      </td>

                      {/* CUSTOMER */}
                      <td>
                        <div className="customer-cell-wrap">
                          <span className="customer-name-text">{ev.customer_name}</span>
                          {ev.is_vip && <span className="vip-badge-sm">VIP</span>}
                        </div>
                      </td>

                      {/* AMOUNT */}
                      <td>
                        <span className="amount-bold">₹{Math.round(ev.amount).toLocaleString('en-IN')}</span>
                      </td>

                      {/* FAILURE CLASS */}
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

                      {/* ML PROPENSITY */}
                      <td>
                        <div className="propensity-bar-wrap">
                          <div className="propensity-bar-track">
                            <div 
                              className="propensity-bar-fill"
                              style={{
                                width: `${ev.recovery_propensity_pct}%`,
                                background: ev.recovery_propensity_pct > 65 ? 'var(--mint)' : ev.recovery_propensity_pct > 35 ? 'var(--cyan)' : 'var(--amber)'
                              }}
                            />
                          </div>
                          <span className="propensity-pct-text">{ev.recovery_propensity_pct}%</span>
                        </div>
                      </td>

                      {/* ACTION DISPATCHED */}
                      <td>
                        <span className="action-pill-code">{formatAction(ev.proposed_action)}</span>
                      </td>

                      {/* POLICY */}
                      <td>
                        <span className={`badge ${ev.policy_verdict === 'APPROVED' ? 'badge-mint' : ev.policy_verdict === 'ESCALATED' ? 'badge-violet' : 'badge-coral'}`}>
                          {ev.policy_verdict}
                        </span>
                      </td>

                      {/* AI REASONING */}
                      <td>
                        <div className="reason-wrap" title={ev.llm_reason}>
                          <span className="reason-snippet">{ev.llm_reason || '—'}</span>
                        </div>
                      </td>

                      {/* OUTCOME */}
                      <td>
                        {ev.payment_success ? (
                          <span className="badge badge-mint">CAPTURED</span>
                        ) : ev.policy_verdict === 'BLOCKED' ? (
                          <span className="badge badge-coral">BLOCKED</span>
                        ) : ev.policy_verdict === 'ESCALATED' ? (
                          <span className="badge badge-violet">ESCALATED</span>
                        ) : (
                          <span className="badge badge-amber">PENDING</span>
                        )}
                      </td>

                      {/* NET REWARD */}
                      <td style={{ textAlign: 'right' }}>
                        {ev.payment_success ? (
                          <span className="net-reward-mint">+₹{Math.round(ev.net_reward).toLocaleString('en-IN')}</span>
                        ) : (
                          <span className="net-reward-dim">₹0</span>
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
