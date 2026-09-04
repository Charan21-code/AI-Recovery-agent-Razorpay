import React, { useState, useEffect } from 'react';
import { Routes, Route, Navigate, useNavigate } from 'react-router-dom';
import { TrendingUp, Activity, CheckCircle2, DollarSign, BrainCircuit } from 'lucide-react';
import AnimatedCounter from '../AnimatedCounter';

// Sub-tabs
import SimulatorTab from './SimulatorTab';
import LiveStreamTab from './LiveStreamTab';
import VoiceAgentTab from './VoiceAgentTab';
import OpportunityQueueTab from './OpportunityQueueTab';
import BanditAnalyticsTab from './BanditAnalyticsTab';
import EventExplorerTab from './EventExplorerTab';

const Dashboard = () => {
  const navigate = useNavigate();
  const [targetCustomer, setTargetCustomer] = useState(null);
  const [metrics, setMetrics] = useState({
    recovered: 10734394,
    rate: 72.4,
    roi: 63.8,
    activeWorkflows: 44
  });

  const handleSwitchToVoice = (customer) => {
    setTargetCustomer(customer);
    navigate('/console/voice');
  };

  // Simulate live metric updates
  useEffect(() => {
    const interval = setInterval(() => {
      setMetrics(prev => ({
        ...prev,
        recovered: prev.recovered + Math.floor(Math.random() * 5000),
        activeWorkflows: Math.max(30, prev.activeWorkflows + (Math.random() > 0.5 ? 1 : -1))
      }));
    }, 4000);
    return () => clearInterval(interval);
  }, []);

  return (
    <div className="main-content-area">
      <div className="dashboard-container">
        
        {/* Top KPI Bar */}
        <div className="dashboard-kpi-bar">
          <div className="kpi-card" key={`kpi-1-${metrics.recovered}`}>
            <div className="kpi-card-header">
              <span className="kpi-label">Total Net Recovered</span>
              <span className="kpi-trend positive"><TrendingUp size={14} /> +18.4%</span>
            </div>
            <div className="kpi-value">
              ₹{metrics.recovered.toLocaleString('en-IN')}
            </div>
            <span className="kpi-subtext">Across 4 Autonomous Channels</span>
          </div>

          <div className="kpi-card">
            <div className="kpi-card-header">
              <span className="kpi-label">Macro Recovery Rate</span>
              <div className="badge badge-mint">OPTIMAL</div>
            </div>
            <div className="kpi-value">
              <AnimatedCounter value={metrics.rate} />%
            </div>
            <span className="kpi-subtext">Baseline industry average: ~18%</span>
          </div>

          <div className="kpi-card">
            <div className="kpi-card-header">
              <span className="kpi-label">Intervention ROI Multiple</span>
              <div className="badge badge-violet">63.8X</div>
            </div>
            <div className="kpi-value">
              ₹1,68,354
            </div>
            <span className="kpi-subtext">Net delivery cost (1.6% of recovery)</span>
          </div>

          <div className="kpi-card" key={`kpi-4-${metrics.activeWorkflows}`}>
            <div className="kpi-card-header">
              <span className="kpi-label">Active Recovery Workflows</span>
              <div className="status-live-dot"></div>
            </div>
            <div className="kpi-value">
              {metrics.activeWorkflows}
            </div>
            <span className="kpi-subtext">Updated recently</span>
          </div>
        </div>

        {/* Nested Routes for Tabs */}
        <div className="tab-content-area">
          <Routes>
            <Route path="/" element={<Navigate to="simulator" replace />} />
            <Route path="simulator" element={<SimulatorTab />} />
            <Route 
              path="voice" 
              element={
                <VoiceAgentTab 
                  targetCustomer={targetCustomer} 
                  onClearTarget={() => setTargetCustomer(null)} 
                />
              } 
            />
            <Route 
              path="queue" 
              element={<OpportunityQueueTab onSwitchToVoice={handleSwitchToVoice} />} 
            />
            <Route path="bandit" element={<BanditAnalyticsTab />} />
            
            {/* Additional tabs */}
            <Route path="livestream" element={<LiveStreamTab />} />
            <Route path="explorer" element={<EventExplorerTab />} />
          </Routes>
        </div>
      </div>
    </div>
  );
};

export default Dashboard;
