import React, { useState } from 'react';
import { 
  Play, 
  Settings2, 
  CheckCircle2, 
  AlertTriangle,
  BrainCircuit,
  ShieldCheck,
  PhoneCall,
  Activity,
  Award,
  Zap,
  TerminalSquare
} from 'lucide-react';
import { motion, AnimatePresence } from 'framer-motion';

export default function SimulatorTab() {
  const [isRunning, setIsRunning] = useState(false);
  const [activeStage, setActiveStage] = useState(-1);
  
  // Form State
  const [amount, setAmount] = useState(4999);
  const [failureCategory, setFailureCategory] = useState("TRANSIENT_BANK_TIMEOUT");
  const [attempts, setAttempts] = useState(0);
  const [customerVip, setCustomerVip] = useState(false);
  const [optedOut, setOptedOut] = useState(false);
  const [gatewayDegradation, setGatewayDegradation] = useState(false);

  // Hardcoded simulation trace (cleaner, no math)
  const simulationTrace = [
    {
      id: "stage01",
      name: "Ingestion & Normalization",
      icon: <TerminalSquare size={16} />,
      statusBadge: { text: failureCategory, type: "cyan" },
      summary: `Normalized entity PAYMENT_FAILED with attempt count ${attempts}.`,
      rationale: `Detected pattern indicative of transient issuing bank latency.`
    },
    {
      id: "stage02",
      name: "Temporal Context Snapshot",
      icon: <Activity size={16} />,
      statusBadge: { text: "POINT-IN-TIME SAFE", type: "violet" },
      summary: "Customer historical success rate: 91.7% (12 txns).",
      rationale: "Intervention fatigue score: 0 (No recent interventions)."
    },
    {
      id: "stage03",
      name: "Feature Vector & Degradation",
      icon: <Zap size={16} />,
      statusBadge: { text: gatewayDegradation ? "GATEWAY DEGRADED" : "GATEWAY HEALTHY", type: gatewayDegradation ? "amber" : "mint" },
      summary: "Extracted 20 real-time features into calibrated model vector.",
      rationale: gatewayDegradation 
        ? "Network degradation detected. Applying penalization factor 0.4."
        : "Standard feature weighting applied. No degradation detected."
    },
    {
      id: "stage04",
      name: "ML Propensity & Opportunity Score",
      icon: <BrainCircuit size={16} />,
      statusBadge: { text: "CALIBRATED GRADIENT BOOSTING", type: "cyan" },
      summary: "Predicted probability of successful recovery.",
      propensity: 89.7,
      opportunityScore: "4899.02"
    },
    {
      id: "stage05",
      name: "Specialized Agent Proposal",
      icon: <PhoneCall size={16} />,
      statusBadge: { text: "PAYMENTFAILUREAGENT", type: "violet" },
      summary: "Proposed Action: IMMEDIATE_RETRY via channel NONE.",
      rationale: "Optimal action selected by ML inference engine for attempt 0."
    },
    {
      id: "stage06",
      name: "Deterministic Policy Engine",
      icon: <ShieldCheck size={16} />,
      statusBadge: { text: optedOut ? "BLOCKED" : "APPROVED", type: optedOut ? "coral" : "mint" },
      summary: optedOut 
        ? "Final Action Blocked: Customer Opt-Out Policy triggered."
        : "Final Approved Action: IMMEDIATE_RETRY",
      checks: [
        { label: "Communication Opt-Out", pass: !optedOut },
        { label: "Max Interventions", pass: attempts < 3 },
        { label: "Minimum Confidence", pass: true }
      ]
    },
    {
      id: "stage07",
      name: "Autonomous Execution",
      icon: <Play size={16} />,
      statusBadge: { text: optedOut ? "HALTED" : "EXECUTED", type: optedOut ? "amber" : "violet" },
      summary: optedOut 
        ? "Execution halted by policy engine."
        : "Executing action IMMEDIATE_RETRY without customer friction.",
      actionCode: optedOut ? null : "api.razorpay.payments.retry(evt.id)"
    },
    {
      id: "stage08",
      name: "Outcome & Bandit Reinforcement",
      icon: <Award size={16} />,
      statusBadge: { text: optedOut ? "YIELD_ZERO" : "PAYMENT CAPTURED", type: optedOut ? "amber" : "mint" },
      summary: "Closed-loop feedback logged to UCB1 bandit arms.",
      reward: optedOut ? 0 : amount
    }
  ];

  const handleRunSimulation = () => {
    setIsRunning(true);
    setActiveStage(-1);
    
    let currentStage = 0;
    const timer = setInterval(() => {
      setActiveStage(currentStage);
      currentStage++;
      if (currentStage >= simulationTrace.length) {
        clearInterval(timer);
        setIsRunning(false);
      }
    }, 600); // Animation speed
  };

  return (
    <div className="simulator-grid">
      {/* ── SIDEBAR CONFIGURATION ── */}
      <div className="simulator-sidebar glass-panel">
        <div className="sidebar-header">
          <h3 className="sidebar-title">Pipeline Configuration</h3>
          <div className="badge badge-violet">INTERACTIVE</div>
        </div>

        <div className="preset-buttons-group">
          <span className="field-label">Quick Presets</span>
          <div className="presets-list">
            <button className="preset-chip-btn" onClick={() => {
              setFailureCategory("TRANSIENT_BANK_TIMEOUT");
              setAmount(4999);
              setAttempts(0);
              setOptedOut(false);
              setGatewayDegradation(false);
            }}>
              💳 UPI Bank Timeout (Transient)
            </button>
            <button className="preset-chip-btn" onClick={() => {
              setFailureCategory("CUSTOMER_OPT_OUT");
              setOptedOut(true);
            }}>
              🚫 Customer Opted-Out (Policy Block)
            </button>
            <button className="preset-chip-btn" onClick={() => {
              setGatewayDegradation(true);
            }}>
              ⚠️ System Gateway Degradation
            </button>
          </div>
        </div>

        <div className="form-fields-wrapper">
          <div className="form-field">
            <label className="field-label">At-Risk Amount (INR)</label>
            <input 
              type="number" 
              className="input-field" 
              value={amount} 
              onChange={(e) => setAmount(Number(e.target.value))}
            />
          </div>

          <div className="form-field">
            <label className="field-label">Failure Category</label>
            <select 
              className="input-field"
              value={failureCategory}
              onChange={(e) => setFailureCategory(e.target.value)}
            >
              <option value="TRANSIENT_BANK_TIMEOUT">TRANSIENT_BANK_TIMEOUT (Bank Down)</option>
              <option value="INSUFFICIENT_FUNDS">INSUFFICIENT_FUNDS</option>
              <option value="MANDATE_REJECTED">MANDATE_REJECTED (High Value)</option>
              <option value="CART_ABANDONED">CART_ABANDONED (Inactivity)</option>
            </select>
          </div>

          <div className="form-field">
            <div className="slider-label-row">
              <label className="field-label">Previous Automated Attempts</label>
              <span className="slider-val-badge">{attempts}</span>
            </div>
            <input 
              type="range" 
              className="range-slider" 
              min="0" max="5" 
              value={attempts} 
              onChange={(e) => setAttempts(Number(e.target.value))}
            />
          </div>

          <div className="toggles-wrapper">
            <label className="toggle-label">
              <input type="checkbox" checked={customerVip} onChange={(e) => setCustomerVip(e.target.checked)} />
              Customer VIP Status
            </label>
            <label className="toggle-label">
              <input type="checkbox" checked={optedOut} onChange={(e) => setOptedOut(e.target.checked)} />
              Customer Opted-Out of Comms
            </label>
            <label className="toggle-label">
              <input type="checkbox" checked={gatewayDegradation} onChange={(e) => setGatewayDegradation(e.target.checked)} />
              Simulate Gateway Degradation
            </label>
          </div>
        </div>

        <button 
          className="btn btn-primary run-btn"
          onClick={handleRunSimulation}
          disabled={isRunning}
        >
          {isRunning ? "Running Pipeline..." : "Run Autonomous Pipeline"}
          {!isRunning && <Play size={16} fill="currentColor" />}
        </button>
      </div>

      {/* ── SIMULATOR OUTPUT AREA ── */}
      <div className="simulator-results-area">
        {activeStage === -1 && !isRunning ? (
          <div className="empty-state-card glass-panel">
            <Settings2 size={48} className="empty-icon animate-spin" style={{ animationDuration: '3s' }} />
            <h3>Pipeline Ready</h3>
            <p>Configure parameters on the left and run the simulation to trace the 8-stage decision pipeline in real-time.</p>
          </div>
        ) : (
          <div className="stages-trace-container">
            <div className="trace-header glass-panel">
              <div>
                <div className="badge badge-mint" style={{ marginBottom: '6px' }}>SIMULATION RUNNING</div>
                <h3 className="trace-title">Event: evt_sim_{Math.floor(Math.random() * 9000) + 1000}</h3>
              </div>
              <div className="trace-stats">
                <div className="stat-pill">
                  <span className="p-label">At-Risk</span>
                  <span className="p-val">₹{amount}</span>
                </div>
                {activeStage >= 3 && (
                  <div className="stat-pill">
                    <span className="p-label">ML Propensity</span>
                    <span className="p-val text-cyan">89.7%</span>
                  </div>
                )}
              </div>
            </div>

            {/* Progress Dots */}
            <div className="pipeline-progress">
              {simulationTrace.map((_, idx) => (
                <React.Fragment key={`prog-${idx}`}>
                  <div className={`progress-dot ${idx <= activeStage ? 'active' : ''} ${idx < activeStage ? 'completed' : ''}`}></div>
                  {idx < simulationTrace.length - 1 && (
                    <div className={`progress-line ${idx < activeStage ? 'completed' : ''}`}></div>
                  )}
                </React.Fragment>
              ))}
            </div>

            <div className="stage-cards-stack">
              <AnimatePresence>
                {simulationTrace.map((stage, idx) => {
                  if (idx > activeStage) return null;
                  
                  return (
                    <motion.div 
                      key={stage.id}
                      initial={{ opacity: 0, y: 20, scale: 0.98 }}
                      animate={{ opacity: 1, y: 0, scale: 1 }}
                      transition={{ duration: 0.3 }}
                      className={`stage-step-card glass-panel ${idx === activeStage ? 'highlight-stage' : ''} ${idx === 7 ? 'reward-card' : ''}`}
                    >
                      <div className="card-step-badge">Stage 0{idx + 1}</div>
                      
                      <div className="card-main-content">
                        <div className="card-title-row">
                          <h4 style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                            {stage.icon} {stage.name}
                          </h4>
                          <div className={`badge badge-${stage.statusBadge.type}`}>{stage.statusBadge.text}</div>
                        </div>
                        
                        <p className="card-detail">{stage.summary}</p>
                        
                        {stage.rationale && (
                          <p className="rationale-text">"{stage.rationale}"</p>
                        )}
                        
                        {stage.propensity && (
                          <div className="propensity-bar-container">
                            <div className="propensity-label-row">
                              <span>Recovery Propensity</span>
                              <span className="text-cyan">{stage.propensity}%</span>
                            </div>
                            <div className="propensity-track">
                              <div className="propensity-fill" style={{ width: `${stage.propensity}%` }}></div>
                            </div>
                            <span className="p-label" style={{ marginTop: '4px' }}>Opportunity Score: <strong style={{ color: 'white' }}>{stage.opportunityScore}</strong></span>
                          </div>
                        )}
                        
                        {stage.checks && (
                          <div className="safety-checks-tags">
                            {stage.checks.map((chk, i) => (
                              <div key={i} className="safety-pill">
                                {chk.pass ? <CheckCircle2 size={12} color="var(--mint)" /> : <AlertTriangle size={12} color="var(--coral)" />}
                                {chk.label}
                              </div>
                            ))}
                          </div>
                        )}
                        
                        {stage.actionCode && (
                          <div style={{ marginTop: '6px' }}>
                            <span className="action-code">{stage.actionCode}</span>
                          </div>
                        )}
                        
                        {stage.reward !== undefined && (
                          <div className="reward-details-row">
                            <div className="reward-box">
                              <span>Gross Recovered</span>
                              <strong>₹{stage.reward}</strong>
                            </div>
                            <div className="reward-box">
                              <span>Net Financial Reward</span>
                              <strong className="text-mint">₹{stage.reward}</strong>
                            </div>
                          </div>
                        )}
                      </div>
                    </motion.div>
                  );
                })}
              </AnimatePresence>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
