import React, { useState, useEffect } from 'react';
import { NavLink, useLocation, useNavigate } from 'react-router-dom';
import { 
  ShieldCheck, 
  Terminal, 
  Activity, 
  Mic, 
  ListOrdered, 
  BrainCircuit, 
  Menu, 
  X,
  Play,
  Search
} from 'lucide-react';

const Navbar = () => {
  const [isScrolled, setIsScrolled] = useState(false);
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);
  const location = useLocation();
  const navigate = useNavigate();

  const isConsole = location.pathname.startsWith('/console');

  useEffect(() => {
    const handleScroll = () => {
      setIsScrolled(window.scrollY > 20);
    };
    window.addEventListener('scroll', handleScroll);
    return () => window.removeEventListener('scroll', handleScroll);
  }, []);

  // Close mobile menu on route change
  useEffect(() => {
    setMobileMenuOpen(false);
  }, [location]);

  return (
    <nav className={`navbar-container ${isScrolled ? 'scrolled' : ''}`}>
      <div className="navbar-content">
        {/* Brand */}
        <div className="brand-logo" onClick={() => navigate('/')}>
          <div className="logo-icon-box">
            <ShieldCheck size={20} strokeWidth={2.5} />
            <div className="logo-pulse"></div>
          </div>
          <div className="brand-text">
            <span className="brand-title">RAZORPAY <span className="brand-accent">RECOVERY AI</span></span>
            <span className="brand-sub">Autonomous Revenue Intelligence</span>
          </div>
        </div>

        {/* Console Sub-navigation (only shows when in /console) */}
        {isConsole && (
          <div className="nav-links">
            <NavLink to="/console/simulator" className={({isActive}) => isActive ? "nav-link active" : "nav-link"}>
              <Play size={13} /> Simulator
            </NavLink>
            <NavLink to="/console/livestream" className={({isActive}) => isActive ? "nav-link active" : "nav-link"}>
              <Activity size={13} /> Live Stream
            </NavLink>
            <NavLink to="/console/voice" className={({isActive}) => isActive ? "nav-link active" : "nav-link"}>
              <Mic size={13} /> Voice Agent
            </NavLink>
            <NavLink to="/console/queue" className={({isActive}) => isActive ? "nav-link active" : "nav-link"}>
              <ListOrdered size={13} /> Queue
            </NavLink>
            <NavLink to="/console/bandit" className={({isActive}) => isActive ? "nav-link active" : "nav-link"}>
              <BrainCircuit size={13} /> Bandits
            </NavLink>
            <NavLink to="/console/explorer" className={({isActive}) => isActive ? "nav-link active" : "nav-link"}>
              <Search size={13} /> Explorer
            </NavLink>
          </div>
        )}

        {/* Status & CTA */}
        <div className="nav-actions">
          {isConsole ? (
            <div className="nav-status-indicators">
              <div className="badge badge-mint"><span className="dot"></span> GATEWAY LIVE</div>
              <div className="badge badge-violet">ZERO-CRED SAFE</div>
            </div>
          ) : (
            <button className="btn btn-primary nav-cta" onClick={() => navigate('/console')}>
              Launch Console <Activity size={16} />
            </button>
          )}

          {/* Mobile Menu Toggle */}
          <button 
            className="mobile-menu-btn" 
            onClick={() => setMobileMenuOpen(!mobileMenuOpen)}
            style={{ background: 'transparent', border: 'none', color: 'white', cursor: 'pointer', display: 'none' }} // Hidden by default, show in media query if needed
          >
            {mobileMenuOpen ? <X size={24} /> : <Menu size={24} />}
          </button>
        </div>
      </div>
    </nav>
  );
};

export default Navbar;
