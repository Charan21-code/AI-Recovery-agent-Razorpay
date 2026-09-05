import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  ArrowRight,
  Activity,
  ShieldCheck,
  Bot,
  Zap,
  Target,
  LineChart,
  BrainCircuit,
  Lock,
  PhoneCall,
  Search,
  CheckCircle2,
  ChevronRight
} from 'lucide-react';
import HeroCanvas from './HeroCanvas';
import AnimatedSection from './AnimatedSection';
import AnimatedCounter from './AnimatedCounter';

const LandingPage = () => {
  const navigate = useNavigate();
  const [atRiskGmv, setAtRiskGmv] = useState(500000);

  const recoveryRate = 0.707;
  const recoveredRevenue = atRiskGmv * recoveryRate;
  const executionCost = recoveredRevenue * 0.016;
  const netProfit = recoveredRevenue - executionCost;

  return (
    <div className="landing-page-wrapper">
      {/* ── HERO SECTION ── */}
      <section className="hero-section">
        <div className="hero-canvas-wrapper">
          <HeroCanvas />
        </div>

        <div className="hero-content">
          <AnimatedSection delay={0.1}>
            <div className="hero-badge-strip">
              <div className="badge badge-violet"><Bot size={14} /> AUTONOMOUS REVENUE INTELLIGENCE</div>
              <div className="badge badge-mint"><ShieldCheck size={14} /> RAZORPAY TEST GATEWAY CERTIFIED</div>
            </div>
          </AnimatedSection>

          <AnimatedSection delay={0.2}>
            <h1 className="hero-title">
              Recover <span className="text-gradient">70%+</span> of At-Risk Revenue <br />
              With Autonomous <span className="text-gradient">AI Agents</span>
            </h1>
          </AnimatedSection>

          <AnimatedSection delay={0.3}>
            <p className="hero-subtitle">
              An end-to-end intelligent recovery engine that replaces dumb payment retries with calibrated ML propensity scoring, deterministic merchant policy guardrails, and multilingual autonomous voice agents.
            </p>
          </AnimatedSection>

          <AnimatedSection delay={0.4}>
            <div className="hero-cta-group">
              <button className="btn btn-primary btn-large" onClick={() => navigate('/console')}>
                Launch Recovery Console <ArrowRight size={18} />
              </button>
              <button className="btn btn-secondary btn-large" onClick={() => navigate('/console/voice')}>
                <PhoneCall size={18} /> Interactive Voice AI Demo
              </button>
            </div>
          </AnimatedSection>

          <AnimatedSection delay={0.5}>
            <div className="hero-stats-banner">
              <div className="hero-stat-item">
                <span className="hero-stat-number">₹<AnimatedCounter value={10.48} />M+</span>
                <span className="hero-stat-label">Net Recovered Revenue</span>
              </div>
              <div className="hero-stat-item">
                <span className="hero-stat-number"><AnimatedCounter value={70.7} />%</span>
                <span className="hero-stat-label">Macro Recovery Rate</span>
              </div>
              <div className="hero-stat-item">
                <span className="hero-stat-number"><AnimatedCounter value={61.5} />x</span>
                <span className="hero-stat-label">Intervention ROI</span>
              </div>
              <div className="hero-stat-item">
                <span className="hero-stat-number">&lt; <AnimatedCounter value={150} format={(v) => Math.round(v).toString()} />ms</span>
                <span className="hero-stat-label">Decision Latency</span>
              </div>
            </div>
          </AnimatedSection>
        </div>
      </section>

      {/* ── HOW IT WORKS (3 STEP FLOW) ── */}
      <section className="section-container">
        <AnimatedSection className="section-header">
          <span className="section-tag">Intelligent Pipeline</span>
          <h2 className="section-title">Engineered For Zero Friction & Maximum Yield</h2>
          <p className="section-subtitle">How autonomous intelligence outperforms conventional rule-based dunning tools.</p>
        </AnimatedSection>

        <div className="steps-grid">
          <AnimatedSection delay={0.1}>
            <div className="step-card">
              <div className="step-number step-1"><Search size={28} /></div>
              <h3 className="step-title">1. Detect & Analyze</h3>
              <p className="step-desc">
                Instantly captures failed payments, normalizes the event data, and builds a comprehensive contextual snapshot of the customer's history.
              </p>
            </div>
            <div className="step-connector"><ChevronRight size={32} /></div>
          </AnimatedSection>

          <AnimatedSection delay={0.3}>
            <div className="step-card">
              <div className="step-number step-2"><BrainCircuit size={28} /></div>
              <h3 className="step-title">2. Decide & Guard</h3>
              <p className="step-desc">
                Calibrated ML models score recovery propensity, while a deterministic policy engine enforces your brand's strict communication guardrails.
              </p>
            </div>
            <div className="step-connector"><ChevronRight size={32} /></div>
          </AnimatedSection>

          <AnimatedSection delay={0.5}>
            <div className="step-card">
              <div className="step-number step-3"><Bot size={28} /></div>
              <h3 className="step-title">3. Autonomous Recovery</h3>
              <p className="step-desc">
                Specialized domain agents execute the optimal strategy—from silent retries to deploying empathetic, multilingual voice AI calls.
              </p>
            </div>
          </AnimatedSection>
        </div>
      </section>

      {/* ── BENTO FEATURES GRID ── */}
      <section className="section-container" style={{ paddingTop: '2rem' }}>
        <div className="bento-grid">
          <AnimatedSection delay={0.1} className="bento-card wide">
            <div className="bento-icon-box violet">
              <PhoneCall size={26} />
            </div>
            <h3 className="bento-title">Empathetic Voice Recovery</h3>
            <p className="bento-desc">
              Multi-turn conversational voice calling in English, Hindi, and Hinglish. Checks live gateway status in real-time, addresses customer concerns, and dispatches 1-click WhatsApp payment links instantly. Never asks for credentials.
            </p>
          </AnimatedSection>

          <AnimatedSection delay={0.2} className="bento-card">
            <div className="bento-icon-box cyan">
              <ShieldCheck size={26} />
            </div>
            <h3 className="bento-title">Deterministic Guardrails</h3>
            <p className="bento-desc">
              AI suggestions are never executed blindly. A non-bypassable policy engine enforces strict regulatory and brand-protection constraints like opt-out filtering and max-retry exhaustion.
            </p>
          </AnimatedSection>

          <AnimatedSection delay={0.3} className="bento-card">
            <div className="bento-icon-box mint">
              <LineChart size={26} />
            </div>
            <h3 className="bento-title">Closed-Loop Bandit Learning</h3>
            <p className="bento-desc">
              Continuously balances exploration of new recovery channels with exploitation of high-yield policies using UCB1 contextual multi-armed bandit math to maximize yield over time.
            </p>
          </AnimatedSection>
        </div>
      </section>

      {/* ── ROI CALCULATOR ── */}
      <section className="section-container roi-section">
        <AnimatedSection>
          <div className="roi-calculator-container">
            <div className="roi-content">
              <div className="badge badge-mint" style={{ width: 'fit-content' }}>INTERACTIVE BUSINESS CASE</div>
              <h2 className="roi-title">Calculate Your Monthly Revenue Recovery</h2>
              <p className="roi-subtitle">
                Enter your monthly at-risk transaction volume to see projected revenue recovered by the AI engine.
              </p>

              <div className="calculator-controls">
                <div className="control-group">
                  <div className="control-label-row">
                    <span>Monthly Failed / At-Risk GMV</span>
                    <span className="control-value">₹{(atRiskGmv / 100000).toFixed(1)} Lakhs</span>
                  </div>
                  <input
                    type="range"
                    className="roi-slider"
                    min="100000"
                    max="20000000"
                    step="100000"
                    value={atRiskGmv}
                    onChange={(e) => setAtRiskGmv(Number(e.target.value))}
                  />
                  <div className="slider-ticks">
                    <span>₹1L</span>
                    <span>₹50L</span>
                    <span>₹1Cr</span>
                    <span>₹2Cr</span>
                  </div>
                </div>

                <div className="control-group">
                  <div className="control-label-row">
                    <span>AI Recovery Rate Model</span>
                    <span className="control-value">70.7%</span>
                  </div>
                  <input
                    type="range"
                    className="roi-slider"
                    min="0" max="100"
                    value="70.7"
                    readOnly
                    style={{ background: `linear-gradient(90deg, var(--violet) 70.7%, rgba(255,255,255,0.1) 70.7%)` }}
                  />
                </div>
              </div>
            </div>

            <div className="roi-results-card">
              <div className="roi-card-tag">PROJECTED MONTHLY IMPACT</div>

              <div className="roi-result-row primary">
                <span className="result-label">Recovered Revenue</span>
                <span className="result-amount">₹{recoveredRevenue.toLocaleString('en-IN', { maximumFractionDigits: 0 })}</span>
              </div>

              <div className="roi-result-row">
                <span className="result-label">AI Execution Cost (~1.6%)</span>
                <span className="result-amount" style={{ color: 'var(--text-muted)' }}>₹{executionCost.toLocaleString('en-IN', { maximumFractionDigits: 0 })}</span>
              </div>

              <div className="roi-divider"></div>

              <div className="roi-result-row highlight">
                <span className="result-label" style={{ color: '#ffffff', fontWeight: 600 }}>Net Profit Recovered</span>
                <span className="result-amount">₹{netProfit.toLocaleString('en-IN', { maximumFractionDigits: 0 })}</span>
              </div>

              <div className="roi-badge-box">
                <div className="badge badge-mint">62.5X ROI MULTIPLE</div>
                <div className="badge badge-violet">ZERO FIXED OVERHEAD</div>
              </div>

              <button className="btn btn-primary btn-block" style={{ marginTop: '1rem' }} onClick={() => navigate('/console')}>
                Start Recovering Now <ArrowRight size={16} />
              </button>
            </div>
          </div>
        </AnimatedSection>
      </section>

      {/* ── COMPARISON SECTION ── */}
      <section className="section-container">
        <AnimatedSection className="section-header">
          <h2 className="section-title">How Razorpay Recovery AI Compares</h2>
          <p className="section-subtitle">A side-by-side comparison with legacy alternatives.</p>
        </AnimatedSection>

        <div className="comparison-scroll">
          <AnimatedSection delay={0.1}>
            <div className="comparison-card muted">
              <h3 className="comparison-card-title text-muted">Naive Retries (Standard Gateway)</h3>
              <div className="comp-metric">
                <span className="comp-metric-label">Decision Latency</span>
                <span className="comp-metric-value">Fixed timer (e.g. 24h)</span>
              </div>
              <div className="comp-metric">
                <span className="comp-metric-label">Voice Recovery</span>
                <span className="comp-metric-value">None</span>
              </div>
              <div className="comp-metric">
                <span className="comp-metric-label">Customer Fatigue</span>
                <span className="comp-metric-value text-coral">Spams until failure</span>
              </div>
              <div className="comp-metric">
                <span className="comp-metric-label">Intervention Cost</span>
                <span className="comp-metric-value">₹0.00 (Zero recovery yield)</span>
              </div>
            </div>
          </AnimatedSection>

          <AnimatedSection delay={0.2}>
            <div className="comparison-card featured">
              <div className="badge badge-violet" style={{ width: 'fit-content', marginBottom: '-10px' }}>RECOMMENDED</div>
              <h3 className="comparison-card-title text-gradient">Razorpay AI Recovery</h3>
              <div className="comp-metric">
                <span className="comp-metric-label">Decision Latency</span>
                <span className="comp-metric-value text-mint">&lt; 150ms Instant</span>
              </div>
              <div className="comp-metric">
                <span className="comp-metric-label">Voice Recovery</span>
                <span className="comp-metric-value text-mint">Autonomous Multilingual AI</span>
              </div>
              <div className="comp-metric">
                <span className="comp-metric-label">Customer Fatigue</span>
                <span className="comp-metric-value text-mint">Deterministic Brake (Max 3)</span>
              </div>
              <div className="comp-metric" style={{ borderBottom: 'none' }}>
                <span className="comp-metric-label">Intervention Cost</span>
                <span className="comp-metric-value text-mint">₹0.00 to ₹2.00 / attempt</span>
              </div>
            </div>
          </AnimatedSection>

          <AnimatedSection delay={0.3}>
            <div className="comparison-card muted">
              <h3 className="comparison-card-title text-muted">Manual BPO Call Centers</h3>
              <div className="comp-metric">
                <span className="comp-metric-label">Decision Latency</span>
                <span className="comp-metric-value">24 to 72 hours later</span>
              </div>
              <div className="comp-metric">
                <span className="comp-metric-label">Voice Recovery</span>
                <span className="comp-metric-value">High friction human calls</span>
              </div>
              <div className="comp-metric">
                <span className="comp-metric-label">Customer Fatigue</span>
                <span className="comp-metric-value">Inconsistent notes</span>
              </div>
              <div className="comp-metric">
                <span className="comp-metric-label">Intervention Cost</span>
                <span className="comp-metric-value text-coral">₹45.00 to ₹90.00 / call</span>
              </div>
            </div>
          </AnimatedSection>
        </div>
      </section>

      {/* ── CTA BANNER ── */}
      <section className="cta-banner-section">
        <AnimatedSection>
          <div className="cta-banner-content">
            <h2 className="cta-title">Ready To Stop Revenue Leaks in Your Payment Flow?</h2>
            <p className="cta-sub">
              Explore live simulations, test the autonomous voice agent, and review real-time opportunity rankings.
            </p>
            <div className="hero-cta-group" style={{ marginTop: '1rem' }}>
              <button className="btn btn-primary btn-large" onClick={() => navigate('/console')}>
                Launch Recovery Console <ArrowRight size={18} />
              </button>
              <button className="btn btn-secondary btn-large" onClick={() => navigate('/console/voice')}>
                <PhoneCall size={18} /> Simulate Voice Agent
              </button>
            </div>
          </div>
        </AnimatedSection>
      </section>
    </div>
  );
};

export default LandingPage;
