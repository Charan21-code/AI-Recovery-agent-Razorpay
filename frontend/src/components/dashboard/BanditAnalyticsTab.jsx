import React, { useState, useEffect } from 'react';
import { 
  Cpu, 
  TrendingUp, 
  Sparkles, 
  RotateCcw, 
  ShieldCheck, 
  CheckCircle2, 
  Layers, 
  Flame, 
  Sliders,
  DollarSign,
  ArrowUpRight,
  BrainCircuit
} from 'lucide-react';

export default function BanditAnalyticsTab() {
  const [banditData, setBanditData] = useState(null);
  const [loading, setLoading] = useState(true);

  const fetchBandit = async () => {
    setLoading(true);
    try {
      const resp = await fetch('http://localhost:8000/api/v1/analytics/bandit');
      if (resp.ok) {
        const data = await resp.json();
        setBanditData(data);
      }
    } catch (e) {
      console.error('Failed to load bandit data:', e);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchBandit();
  }, []);

  const formatActionName = (action) => {
    if (!action) return '—';
    const names = {
      SEND_PAYMENT_METHOD_UPDATE: '1-Click Payment Method Update',
      GENERATE_PAYMENT_LINK: 'Instant Checkout Payment Link',
      IMMEDIATE_RETRY: 'Silent Zero-Touch Gateway Retry',
      DELAYED_RETRY: 'Smart Off-Peak Scheduled Retry',
      ESCALATE_TO_HUMAN: 'Account Manager VIP Escalation',
      SEND_CHECKOUT_RECOVERY: 'WhatsApp Cart Abandonment Flow',
      START_VOICE_RECOVERY: 'Autonomous Voice AI Outbound Call',
      SEND_PAYMENT_REMINDER: 'SMS & WhatsApp Dynamic Reminder',
      SEND_PERSONALIZED_MESSAGE: 'Personalized Incentive Message',
      SCHEDULE_DUNNING_STEP: 'Automated Dunning Cycle Step',
      PROGRESSIVE_FOLLOWUP: 'Progressive Multi-Channel Followup',
      WAIT: 'Transient Hold & Wait',
      STOP: 'Fatigue Cut-off (Halt)'
    };
    return names[action] || action.replace(/_/g, ' ');
  };

  const arms = banditData?.arms || [];
  const sortedArms = [...arms].sort((a, b) => b.total_recovered - a.total_recovered);
  const totalSystemRecovered = arms.reduce((sum, a) => sum + (a.total_recovered || 0), 0);
  const totalPulls = arms.reduce((sum, a) => sum + (a.pull_count || 0), 0);

  return (
    <div className="bandit-tab-page">
      {/* Top Header Banner */}
      <div className="bandit-hero-banner">
        <div className="bandit-banner-info">
          <div className="badge badge-violet">
            <BrainCircuit size={13} />
            <span>Autonomous Reinforcement Learning</span>
          </div>
          <h2 className="bandit-banner-title">Multi-Armed Bandit (MAB) Decision Engine</h2>
          <p className="bandit-banner-desc">
            Dynamically balances exploring candidate intervention channels against exploiting historically high-conversion pathways. 
            Arm payoffs reflect net financial rewards after subtracting real-time channel delivery costs and customer fatigue penalties.
          </p>
        </div>

        <div className="bandit-policy-summary-card">
          <div className="policy-stat-row">
            <span className="policy-lbl">Learning Policy</span>
            <span className="policy-val">Contextual UCB-1</span>
          </div>
          <div className="policy-stat-row">
            <span className="policy-lbl">Exploration Bound</span>
            <span className="policy-val text-cyan">c = {banditData?.exploration_constant_c || 1.414} (Adaptive)</span>
          </div>
          <div className="policy-stat-row">
            <span className="policy-lbl">Dominant Channel</span>
            <span className="policy-val text-mint">{formatActionName(banditData?.top_policy_action)}</span>
          </div>
        </div>
      </div>

      {/* Summary Metrics */}
      <div className="bandit-metrics-grid">
        <div className="stream-metric-card highlight">
          <div className="sm-header">
            <span className="sm-label">Total Net Reward Generated</span>
            <DollarSign size={15} className="sm-icon text-cyan" />
          </div>
          <div className="sm-val text-gradient">₹{Math.round(totalSystemRecovered).toLocaleString('en-IN')}</div>
          <div className="sm-sub">Cumulative payoff across all active arms</div>
        </div>

        <div className="stream-metric-card">
          <div className="sm-header">
            <span className="sm-label">Total Decision Pulls</span>
            <Layers size={15} className="sm-icon text-violet" />
          </div>
          <div className="sm-val">{totalPulls.toLocaleString()}</div>
          <div className="sm-sub">Live customer intervention evaluations</div>
        </div>

        <div className="stream-metric-card">
          <div className="sm-header">
            <span className="sm-label">Leading Arm Yield</span>
            <TrendingUp size={15} className="sm-icon text-mint" />
          </div>
          <div className="sm-val text-mint">
            {sortedArms.length > 0 ? `${sortedArms[0].conversion_rate_pct}%` : '—'}
          </div>
          <div className="sm-sub">Peak empirical conversion rate</div>
        </div>

        <div className="stream-metric-card">
          <div className="sm-header">
            <span className="sm-label">Active Action Channels</span>
            <Cpu size={15} className="sm-icon text-cyan" />
          </div>
          <div className="sm-val">{arms.length} Channels</div>
          <div className="sm-sub">Autonomous execution arms</div>
        </div>
      </div>

      {/* Arms Performance Table & Safety Grid */}
      <div className="bandit-main-content-grid">
        {/* Left Column: Arms Performance Ledger */}
        <div className="arms-ledger-card">
          <div className="arms-ledger-header">
            <div>
              <h3 className="card-title">Bandit Channel Payoff Ledger</h3>
              <p className="card-subtitle">Real-time reward ranking updated after each intervention outcome</p>
            </div>
            <button className="btn btn-secondary btn-sm" onClick={fetchBandit}>
              <RotateCcw size={13} className={loading ? 'animate-spin' : ''} />
              <span>Refresh Ledger</span>
            </button>
          </div>

          <div className="table-responsive-wrapper">
            <table className="bandit-arms-table">
              <thead>
                <tr>
                  <th>Rank & Channel</th>
                  <th>Total Pulls</th>
                  <th>Conversion Rate</th>
                  <th>Mean Net Payoff</th>
                  <th>Cumulative Recovered</th>
                  <th>Policy Allocation</th>
                </tr>
              </thead>
              <tbody>
                {loading ? (
                  <tr>
                    <td colSpan="6" className="table-loading-cell">
                      Loading bandit arm distributions...
                    </td>
                  </tr>
                ) : (
                  sortedArms.map((arm, idx) => {
                    const isTop = idx === 0;
                    return (
                      <tr key={arm.action} className={isTop ? 'top-arm-highlight' : ''}>
                        <td>
                          <div className="arm-name-group">
                            <span className={`rank-pill ${isTop ? 'rank-gold' : ''}`}>
                              #{idx + 1}
                            </span>
                            <div className="arm-title-col">
                              <span className="arm-human-name">
                                {formatActionName(arm.action)}
                              </span>
                              <span className="arm-system-code">{arm.action}</span>
                            </div>
                          </div>
                        </td>

                        <td>
                          <span className="pull-count-text">{arm.pull_count.toLocaleString()}</span>
                        </td>

                        <td>
                          <div className="conv-rate-cell">
                            <div className="conv-mini-track">
                              <div 
                                className="conv-mini-fill" 
                                style={{ 
                                  width: `${Math.min(100, arm.conversion_rate_pct)}%`,
                                  background: arm.conversion_rate_pct > 60 ? 'var(--mint)' : arm.conversion_rate_pct > 25 ? 'var(--cyan)' : 'var(--text-muted)'
                                }} 
                              />
                            </div>
                            <span className={`conv-pct-text ${arm.conversion_rate_pct > 50 ? 'text-mint' : ''}`}>
                              {arm.conversion_rate_pct}%
                            </span>
                          </div>
                        </td>

                        <td>
                          <span className="mean-payoff-text">
                            ₹{Math.round(arm.average_reward).toLocaleString('en-IN')}
                          </span>
                        </td>

                        <td>
                          <span className="cumulative-val">
                            ₹{Math.round(arm.total_recovered).toLocaleString('en-IN')}
                          </span>
                        </td>

                        <td>
                          {isTop ? (
                            <span className="badge badge-mint">
                              <Sparkles size={11} /> Primary Exploit
                            </span>
                          ) : arm.pull_count > 0 ? (
                            <span className="badge badge-cyan">Controlled Explore</span>
                          ) : (
                            <span className="badge badge-subtle">Cold Start</span>
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

        {/* Right Column: Safety Bounds & Constraints */}
        <div className="bandit-safeguards-panel">
          <div className="safeguards-header">
            <ShieldCheck size={18} className="text-cyan" />
            <h4 className="safeguards-title">Autonomous Safety Bounds</h4>
          </div>
          <p className="safeguards-desc">
            Deterministic merchant policies and friction thresholds act as hard constraints that override bandit exploration.
          </p>

          <div className="safeguards-list">
            <div className="safeguard-card">
              <div className="sg-icon-box text-mint">
                <CheckCircle2 size={16} />
              </div>
              <div className="sg-content">
                <span className="sg-title">Deterministic Policy Gate</span>
                <p className="sg-detail">
                  Bandit models can only select from actions that have passed all deterministic business, compliance, and regulatory rules.
                </p>
              </div>
            </div>

            <div className="safeguard-card">
              <div className="sg-icon-box text-amber">
                <Flame size={16} />
              </div>
              <div className="sg-content">
                <span className="sg-title">Customer Fatigue Dampener</span>
                <p className="sg-detail">
                  Outbound touchpoints (WhatsApp/Voice) are automatically dampened when a buyer's rolling friction score exceeds 0.65.
                </p>
              </div>
            </div>

            <div className="safeguard-card">
              <div className="sg-icon-box text-violet">
                <DollarSign size={16} />
              </div>
              <div className="sg-content">
                <span className="sg-title">Net Unit Margin Deduction</span>
                <p className="sg-detail">
                  Direct delivery expenses (₹2.00 Voice AI, ₹0.50 WhatsApp) are deducted immediately from gross recovery before updating arm expectations.
                </p>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
