import React, { useState, useEffect, useRef, useCallback } from 'react';
import { useLocation } from 'react-router-dom';
import { 
  Phone, PhoneOff, Mic, MicOff, Send, ShieldAlert, Sparkles,
  RefreshCw, Volume2, User, AlertCircle, CheckCircle, Clock,
  AlertTriangle, XCircle, FileText
} from 'lucide-react';

// ─── Web Speech API hook ─────────────────────────────────────────────────────
function useSpeechRecognition({ lang = 'hi-IN', onResult, onError }) {
  const recognitionRef = useRef(null);
  const onResultRef   = useRef(onResult);
  const onErrorRef    = useRef(onError);
  const [listening, setListening] = useState(false);
  const [interim,   setInterim]   = useState('');
  const supported = typeof window !== 'undefined' &&
    ('SpeechRecognition' in window || 'webkitSpeechRecognition' in window);

  useEffect(() => { onResultRef.current = onResult; }, [onResult]);
  useEffect(() => { onErrorRef.current  = onError;  }, [onError]);

  useEffect(() => {
    if (!supported) return;
    const SR  = window.SpeechRecognition || window.webkitSpeechRecognition;
    const rec = new SR();
    rec.continuous      = false;
    rec.interimResults  = true;
    rec.maxAlternatives = 1;
    rec.lang            = lang;

    rec.onstart = () => setListening(true);
    rec.onend   = () => { setListening(false); setInterim(''); };

    rec.onresult = (e) => {
      let final = '', interimText = '';
      for (let i = e.resultIndex; i < e.results.length; i++) {
        if (e.results[i].isFinal) final       += e.results[i][0].transcript;
        else                       interimText += e.results[i][0].transcript;
      }
      setInterim(interimText);
      if (final.trim() && onResultRef.current) onResultRef.current(final.trim());
    };

    rec.onerror = (e) => {
      setListening(false);
      setInterim('');
      if (onErrorRef.current) onErrorRef.current(e.error);
    };

    recognitionRef.current = rec;
    return () => rec.abort();
  }, [lang, supported]);

  const start = useCallback(() => {
    if (recognitionRef.current && !listening) {
      try { recognitionRef.current.start(); }
      catch (e) { console.warn('Speech start error:', e); }
    }
  }, [listening]);

  const stop = useCallback(() => {
    if (recognitionRef.current && listening) {
      try { recognitionRef.current.stop(); }
      catch (e) { console.warn('Speech stop error:', e); }
    }
  }, [listening]);

  return { listening, interim, supported, start, stop };
}

// ─── Constants ───────────────────────────────────────────────────────────────
const LANG_LOCALE = { hinglish: 'hi-IN', hi: 'hi-IN', en: 'en-IN' };

const SESSION_STATUS_CONFIG = {
  active:    { label: 'Active',    color: 'badge-emerald', icon: null },
  completed: { label: 'Resolved',  color: 'badge-blue',   icon: CheckCircle },
  escalated: { label: 'Escalated', color: 'badge-rose',   icon: AlertTriangle },
  scheduled: { label: 'Scheduled', color: 'badge-purple', icon: Clock },
  refused:   { label: 'Opted Out', color: 'badge-amber',  icon: XCircle },
  disputed:  { label: 'Disputed',  color: 'badge-amber',  icon: FileText },
};

const DEFAULT_CUSTOMER_PROFILES = [
  { id: 'cust_blr_01', name: 'Aditya Roy',      phone: '+919876543210', amount: 14999.0,  reason: 'Bank Gateway Timeout (UPI)' },
  { id: 'cust_mum_02', name: 'Deepika Sen',      phone: '+919820011223', amount: 28500.0,  reason: 'Mandate Authorization Declined (Card)' },
  { id: 'cust_del_03', name: 'Vikram Sethi',     phone: '+919811223344', amount: 3499.0,   reason: 'Insufficient Funds (UPI)' },
  { id: 'cust_hyd_04', name: 'Sneha Reddy',      phone: '+919833445566', amount: 1850.0,   reason: 'User dropped off at checkout' },
  { id: 'cust_pnq_05', name: 'Rahul Deshmukh',   phone: '+919844556677', amount: 45000.0,  reason: 'Card Expired on File (Card)' },
  { id: 'cust_chn_06', name: 'Ananya Sundaram',  phone: '+919855667788', amount: 5999.0,   reason: 'Authentication Failed (OTP)' },
  { id: 'cust_kol_07', name: 'Sourav Banerjee',  phone: '+919866778899', amount: 2200.0,   reason: 'Netbanking Server Timeout' },
  { id: 'cust_ncr_08', name: 'Meera Kapoor',     phone: '+919877889900', amount: 62000.0,  reason: 'Mandate Authorization Declined (NACH)' },
];

const quickSpeechChips = [
  { label: "💸 'Paise kat gaye!'",    text: "Arre paise kat gaye mere bank account se, status failed kyu dikha raha hai?" },
  { label: "🔗 'Send WhatsApp link'", text: "Mujhe WhatsApp par payment link bhej do, main abhi UPI se pay kar deta hoon." },
  { label: "❌ 'Link nahi mila'",     text: "Mujhe payment link receive nahi hua, abhi tak nahi aaya." },
  { label: "✅ 'Pay kar diya'",        text: "Maine abhi payment complete kar diya hai." },
  { label: "🚨 OTP Security Test",    text: "Mera OTP 492019 hai, kya aap ise enter kar sakte ho?" },
  { label: "⏰ 'Call later'",          text: "Main abhi driving kar raha hoon, kya aap kal subah call kar sakte ho?" },
  { label: "👤 'Talk to manager'",    text: "Mujhe kisi human manager se baat karni hai, dispute raise karna hai." },
  { label: "🔄 'Retry via UPI'",      text: "Please retry again with UPI, I will authorize it on PhonePe." },
  { label: "💰 'Want refund'",        text: "Mujhe refund chahiye, order cancel karna hai." },
  { label: "❓ 'Why did it fail?'",   text: "Mujhe explain karo, kyun fail hua mera payment? Kya issue tha?" },
];

// ─── Tool result renderer ─────────────────────────────────────────────────────
function ToolResultText({ tc }) {
  const { tool_name: name, result: r } = tc;
  if (name === 'get_payment_status')
    return <span>Status: <strong>{r.status}</strong> • Captured: {r.captured ? '✅ Yes' : '❌ No'} ({r.verified_source || 'gateway'})</span>;
  if (name === 'create_payment_link')
    return <span>Link: <strong>{r.short_url || 'Sent'}</strong> → {r.customer_phone} via WhatsApp & SMS</span>;
  if (name === 'schedule_recovery')
    return <span>Callback scheduled: <strong>{r.scheduled_time}</strong></span>;
  if (name === 'escalate_to_human')
    return <span>Ticket: <strong>#{r.ticket_id}</strong> (Priority: {r.priority})</span>;
  if (name === 'retry_payment')
    return <span>Retry via: <strong>{r.preferred_method?.toUpperCase()}</strong> — {r.status}</span>;
  if (name === 'record_customer_intent')
    return <span>Intent logged: <strong>{r.intent}</strong> ({r.sentiment})</span>;
  if (name === 'file_dispute_complaint')
    return <span>Dispute: <strong>#{r.ticket_id}</strong> • {r.expected_resolution_days} resolution</span>;
  if (name === 'send_refund_request')
    return <span>Refund: <strong>#{r.refund_ticket_id}</strong> • {r.expected_days}</span>;
  return <span>{JSON.stringify(r).slice(0, 80)}</span>;
}

// ─── Main component ───────────────────────────────────────────────────────────
export default function VoiceAgentTab({ targetCustomer: propTargetCustomer, onClearTarget }) {
  const location = useLocation();
  const targetCustomer = propTargetCustomer || location.state?.targetCustomer;

  const [session,          setSession]          = useState(null);
  const [callActive,       setCallActive]       = useState(false);
  const [callDuration,     setCallDuration]     = useState(0);
  const [inputText,        setInputText]        = useState('');
  const [loading,          setLoading]          = useState(false);
  const [isSpeaking,       setIsSpeaking]       = useState(false);
  const [customerProfiles, setCustomerProfiles] = useState(DEFAULT_CUSTOMER_PROFILES);
  const [selectedCustomer, setSelectedCustomer] = useState(
    () => targetCustomer?.customer_id || targetCustomer?.id || 'cust_blr_01'
  );
  const [selectedLanguage, setSelectedLanguage] = useState('hinglish');
  const [micError,         setMicError]         = useState('');

  // ── Mic queue: store pending text if loading when mic fires ─────────────
  const pendingMicRef  = useRef(null);
  const sessionRef     = useRef(session);
  sessionRef.current   = session;
  const loadingRef     = useRef(loading);
  loadingRef.current   = loading;

  const chatBottomRef        = useRef(null);
  const autoCallInitiatedRef = useRef(null);

  // ── Sync targetCustomer ──────────────────────────────────────────────────
  useEffect(() => {
    if (!targetCustomer) return;
    const targetId = targetCustomer.customer_id || targetCustomer.id;
    if (!targetId) return;
    setSelectedCustomer(targetId);
    setCustomerProfiles((prev) => {
      const idx        = prev.findIndex((c) => c.id === targetId);
      const normalized = {
        id:         targetId,
        name:       targetCustomer.customer_name || targetCustomer.name || 'Valued Customer',
        phone:      targetCustomer.phone || (idx >= 0 ? prev[idx].phone : '+919876543210'),
        amount:     targetCustomer.amount !== undefined ? targetCustomer.amount : (idx >= 0 ? prev[idx].amount : 2499.0),
        reason:     targetCustomer.reason || targetCustomer.failure_reason || (idx >= 0 ? prev[idx].reason : 'Payment Issue'),
        payment_id: targetCustomer.payment_id || (idx >= 0 ? prev[idx].payment_id : `pay_${targetId}_1`),
      };
      if (idx >= 0) { const u = [...prev]; u[idx] = { ...u[idx], ...normalized }; return u; }
      return [normalized, ...prev];
    });
    if (targetCustomer.autoStart && autoCallInitiatedRef.current !== targetId) {
      autoCallInitiatedRef.current = targetId;
      handleStartCall(targetCustomer);
    }
  }, [targetCustomer]);

  // ── Fetch dynamic queue ──────────────────────────────────────────────────
  useEffect(() => {
    let isMounted = true;
    fetch('http://localhost:8000/api/v1/analytics/queue')
      .then((res) => (res.ok ? res.json() : null))
      .then((data) => {
        if (!isMounted || !data || !Array.isArray(data)) return;
        const mapped = data.map((item) => ({
          id:         item.customer_id,
          name:       item.customer_name,
          phone:      '+9198' + Math.floor(10000000 + Math.random() * 90000000),
          amount:     item.amount,
          reason:     item.failure_category ? item.failure_category.replace(/_/g, ' ') : 'Payment Gateway Dropoff',
          payment_id: item.payment_id,
        }));
        if (mapped.length > 0) {
          setCustomerProfiles((prev) => {
            const targetId = targetCustomer?.customer_id || targetCustomer?.id;
            if (targetId && !mapped.some((m) => m.id === targetId)) {
              const current = prev.find((c) => c.id === targetId);
              return current ? [current, ...mapped] : mapped;
            }
            return mapped;
          });
          setSelectedCustomer((prev) => {
            const targetId = targetCustomer?.customer_id || targetCustomer?.id;
            if (targetId) return targetId;
            return prev || mapped[0].id;
          });
        }
      })
      .catch((err) => console.log('Using default customer profiles:', err.message));
    return () => { isMounted = false; };
  }, [targetCustomer]);

  // ── TTS ──────────────────────────────────────────────────────────────────
  const speakText = useCallback((text, lang) => {
    if (typeof window === 'undefined' || !('speechSynthesis' in window)) return;
    try {
      window.speechSynthesis.cancel();
      const utt  = new SpeechSynthesisUtterance(text);
      utt.lang   = LANG_LOCALE[lang] || 'hi-IN';
      utt.rate   = 1.0;
      utt.pitch  = 1.0;
      utt.onstart = () => setIsSpeaking(true);
      utt.onend   = () => setIsSpeaking(false);
      utt.onerror = () => setIsSpeaking(false);
      window.speechSynthesis.speak(utt);
    } catch (e) {
      console.warn('TTS error:', e);
      setIsSpeaking(false);
    }
  }, []);

  // ── Send turn ─────────────────────────────────────────────────────────────
  const handleSendTurn = useCallback(async (textToSend) => {
    const text           = (textToSend || inputText || '').trim();
    const currentSession = sessionRef.current;
    if (!text || !currentSession?.sessionId) return;

    setInputText('');
    pendingMicRef.current = null;
    setLoading(true);

    // Cancel any ongoing TTS
    if (typeof window !== 'undefined' && 'speechSynthesis' in window) {
      window.speechSynthesis.cancel();
    }
    setIsSpeaking(false);

    // Optimistic user bubble
    setSession((prev) => ({
      ...prev,
      turns: [
        ...prev.turns,
        {
          turn_id:    `u_${Date.now()}`,
          role:       'user',
          content:    text,
          timestamp:  new Date().toISOString(),
          tool_calls: [],
        },
      ],
    }));

    try {
      const resp = await fetch('http://localhost:8000/api/v1/voice/session/turn', {
        method:  'POST',
        headers: { 'Content-Type': 'application/json' },
        body:    JSON.stringify({ session_id: currentSession.sessionId, speech_text: text }),
      });

      if (!resp.ok) {
        let errMsg = `Backend error (${resp.status})`;
        try { const j = await resp.json(); errMsg = j.detail || errMsg; } catch (_) {}
        throw new Error(errMsg);
      }

      const data = await resp.json();
      setSession((prev) => ({
        ...prev,
        status: data.session_status,
        turns:  [...prev.turns, data.turn],
      }));

      if (data.turn?.content) {
        speakText(data.turn.content, currentSession.language || selectedLanguage);
      }
    } catch (err) {
      // Add error inline in the chat instead of alert
      const errorMessage = `⚠️ Error: ${err.message}`;
      setSession((prev) => ({
        ...prev,
        turns: [
          ...prev.turns,
          {
            turn_id:    `err_${Date.now()}`,
            role:       'system',
            content:    errorMessage,
            timestamp:  new Date().toISOString(),
            tool_calls: [],
          },
        ],
      }));
    } finally {
      setLoading(false);
    }
  }, [inputText, selectedLanguage, speakText]);

  // ── Drain mic queue when loading finishes ────────────────────────────────
  useEffect(() => {
    if (!loading && pendingMicRef.current) {
      const queued          = pendingMicRef.current;
      pendingMicRef.current = null;
      handleSendTurn(queued);
    }
  }, [loading, handleSendTurn]);

  // ── Speech recognition ────────────────────────────────────────────────────
  const { listening, interim, supported: micSupported, start: startMic, stop: stopMic } =
    useSpeechRecognition({
      lang:     LANG_LOCALE[selectedLanguage] || 'hi-IN',
      onResult: useCallback((text) => {
        if (loadingRef.current) {
          // Queue for when loading finishes — don't drop it
          pendingMicRef.current = text;
        } else {
          handleSendTurn(text);
        }
      }, [handleSendTurn]),
      onError: useCallback((err) => {
        setMicError(
          err === 'not-allowed'
            ? 'Microphone permission denied. Allow mic in browser settings.'
            : `Speech error: ${err}`
        );
        setTimeout(() => setMicError(''), 4000);
      }, []),
    });

  // ── Timer ─────────────────────────────────────────────────────────────────
  useEffect(() => {
    let t;
    if (callActive) t = setInterval(() => setCallDuration((d) => d + 1), 1000);
    else setCallDuration(0);
    return () => clearInterval(t);
  }, [callActive]);

  // ── Auto-scroll ───────────────────────────────────────────────────────────
  useEffect(() => {
    chatBottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [session?.turns]);

  const formatTimer = (s) =>
    `${Math.floor(s / 60).toString().padStart(2, '0')}:${(s % 60).toString().padStart(2, '0')}`;

  // ── Start call ────────────────────────────────────────────────────────────
  const handleStartCall = async (targetOverride) => {
    setLoading(true);
    setMicError('');
    try {
      const activeTarget = targetOverride
        || (targetCustomer && (targetCustomer.id === selectedCustomer || targetCustomer.customer_id === selectedCustomer)
          ? targetCustomer
          : null);
      const custId   = activeTarget?.customer_id || activeTarget?.id || selectedCustomer;
      const custObj  = customerProfiles.find((c) => c.id === custId) || activeTarget || {};

      const custName   = activeTarget?.customer_name || activeTarget?.name  || custObj.name   || 'Valued Customer';
      const custAmount = activeTarget?.amount !== undefined               ? activeTarget.amount : (custObj.amount || 2499.0);
      const custPhone  = activeTarget?.phone  || custObj.phone  || '+919876543210';
      const custReason = activeTarget?.failure_reason || activeTarget?.reason || custObj.reason || 'Bank gateway timeout';
      const paymentId  = activeTarget?.payment_id || custObj.payment_id || `pay_${custId}_1`;

      const resp = await fetch('http://localhost:8000/api/v1/voice/session/start', {
        method:  'POST',
        headers: { 'Content-Type': 'application/json' },
        body:    JSON.stringify({
          customer_id:    custId,
          payment_id:     paymentId,
          language:       selectedLanguage,
          customer_name:  custName,
          amount:         custAmount,
          customer_phone: custPhone,
          failure_reason: custReason,
        }),
      });
      if (!resp.ok) {
        let errMsg = `Failed to start call (${resp.status})`;
        try { const j = await resp.json(); errMsg = j.detail || errMsg; } catch (_) {}
        throw new Error(errMsg);
      }
      const data = await resp.json();
      setSession({
        sessionId:    data.session_id,
        customerName: data.customer_name,
        amount:       data.amount,
        language:     data.language,
        status:       data.status,
        turns:        data.greeting_turn ? [data.greeting_turn] : [],
      });
      setCallActive(true);

      if (data.greeting_turn?.content) {
        speakText(data.greeting_turn.content, data.language || selectedLanguage);
      }
    } catch (err) {
      setMicError(`Call failed: ${err.message}`);
    } finally {
      setLoading(false);
    }
  };

  const handleEndCall = () => {
    setCallActive(false);
    if (listening) stopMic();
    if (typeof window !== 'undefined' && 'speechSynthesis' in window) window.speechSynthesis.cancel();
    setIsSpeaking(false);
    pendingMicRef.current = null;
    // When ending call, mark session resolved if payment was addressed
    setSession((prev) => {
      if (!prev) return prev;
      return {
        ...prev,
        status: prev.status === 'refused' ? 'refused' : 'completed',
      };
    });
  };

  const handleMicClick = () => {
    if (!callActive) return;
    if (listening) stopMic();
    else startMic();
  };

  const currentCust = customerProfiles.find((c) => c.id === selectedCustomer)
    || customerProfiles[0]
    || { id: 'cust_blr_01', name: 'Aditya Roy', phone: '+919876543210', amount: 14999.0, reason: 'Bank Gateway Timeout (UPI)' };

  const isFromQueue    = targetCustomer && (targetCustomer.id === selectedCustomer || targetCustomer.customer_id === selectedCustomer);
  const sessionStatus  = session?.status || 'active';
  const statusCfg      = SESSION_STATUS_CONFIG[sessionStatus] || SESSION_STATUS_CONFIG.active;
  const StatusIcon     = statusCfg.icon;
  const sessionEnded   = (!callActive && session !== null) || sessionStatus === 'refused';

  return (
    <div className="voice-tab-container">
      {/* ── Top Config Strip ── */}
      <div className="voice-top-strip glass-panel">
        <div className="target-customer-info">
          <div className="cust-avatar-box"><User size={20} /></div>
          <div>
            <div className="cust-name-row">
              <span className="cust-name">{currentCust.name}</span>
              <span className="badge badge-emerald">₹{Number(currentCust.amount || 0).toLocaleString('en-IN')} At Risk</span>
              {isFromQueue && (
                <span className="badge badge-purple" style={{ fontSize: '10px', padding: '2px 8px' }}>
                  ⚡ From Opportunity Queue
                </span>
              )}
            </div>
            <span className="cust-meta">{currentCust.phone} • {currentCust.reason}</span>
          </div>
        </div>

        <div className="voice-controls-bar">
          <div className="control-select-pair">
            <label>Customer Target:</label>
            <select
              className="mini-select"
              disabled={callActive}
              value={selectedCustomer}
              onChange={(e) => { setSelectedCustomer(e.target.value); if (onClearTarget) onClearTarget(); }}
            >
              {customerProfiles.map((c) => (
                <option key={c.id} value={c.id}>{c.name} (₹{Number(c.amount || 0).toLocaleString('en-IN')})</option>
              ))}
            </select>
          </div>

          <div className="control-select-pair">
            <label>Language:</label>
            <select
              className="mini-select"
              disabled={callActive}
              value={selectedLanguage}
              onChange={(e) => setSelectedLanguage(e.target.value)}
            >
              <option value="hinglish">Hinglish (Conversational)</option>
              <option value="hi">Hindi (Formal)</option>
              <option value="en">English (Professional)</option>
            </select>
          </div>

          {!callActive ? (
            <button className="btn btn-emerald call-action-btn" disabled={loading} onClick={() => handleStartCall()}>
              <Phone size={16} />
              <span>{loading ? 'Connecting...' : 'Start Autonomous Call'}</span>
            </button>
          ) : (
            <button className="btn btn-rose call-action-btn" onClick={handleEndCall}>
              <PhoneOff size={16} />
              <span>End Call ({formatTimer(callDuration)})</span>
            </button>
          )}
        </div>
      </div>

      {/* ── Main Screen ── */}
      <div className="voice-screen-grid">
        {/* Left: Telephony Visual */}
        <div className="telephony-screen glass-panel">
          <div className="telephony-header">
            <div className="status-indicator">
              <span className={`status-dot ${callActive ? 'active' : ''}`}></span>
              <span>
                {callActive
                  ? (isSpeaking ? 'Agent Speaking • Real-time TTS' : 'Call Connected • Real-time Speech')
                  : 'Line Idle'}
              </span>
            </div>
            {callActive && <span className="call-clock badge badge-blue">{formatTimer(callDuration)}</span>}
          </div>

          <div className="caller-visual-center">
            <div className={`audio-pulse-ring ${callActive ? 'pulsing' : ''} ${listening ? 'mic-active-ring' : ''} ${isSpeaking ? 'speaking-active-ring' : ''}`}>
              <div className="agent-avatar-circle">
                {listening
                  ? <Mic    size={36} className="agent-icon text-emerald pulse-anim" />
                  : <Volume2 size={36} className={`agent-icon ${isSpeaking ? 'text-cyan animate-pulse' : ''}`} />
                }
              </div>
            </div>

            <h3 className="calling-title">Razorpay Recovery Specialist</h3>
            <span className="calling-subtitle">
              {listening
                ? '🎙 Listening... speak now'
                : isSpeaking
                  ? '🔊 Agent speaking response...'
                  : callActive
                    ? (loading
                        ? (pendingMicRef.current ? 'Mic input queued — processing...' : 'Agent processing & executing tools...')
                        : 'Tap 🎙 mic or type to respond')
                    : 'Press "Start Autonomous Call" to initiate conversation'}
            </span>

            {/* Interim transcript while listening */}
            {interim && (
              <div className="interim-transcript">
                <span className="interim-dot"></span>
                <em>"{interim}..."</em>
              </div>
            )}

            {/* Pending mic queue indicator */}
            {pendingMicRef.current && loading && (
              <div className="interim-transcript" style={{ borderColor: 'var(--amber-500)' }}>
                <span className="interim-dot" style={{ background: 'var(--amber-400)' }}></span>
                <em>Queued: "{pendingMicRef.current}"</em>
              </div>
            )}

            {/* Animated sound wave bars */}
            {callActive && (
              <div className={`sound-wave-bars ${listening ? 'wave-mic' : ''} ${isSpeaking ? 'wave-speaking' : ''}`}>
                <span className="bar b1"></span><span className="bar b2"></span>
                <span className="bar b3"></span><span className="bar b4"></span>
                <span className="bar b5"></span><span className="bar b6"></span>
                <span className="bar b7"></span>
              </div>
            )}
          </div>

          {!micSupported && callActive && (
            <div className="mic-not-supported-banner">
              ⚠ Web Speech API not available. Use Chrome or Edge for voice input.
            </div>
          )}
          {micError && <div className="mic-error-banner">{micError}</div>}

          {/* Security Invariant Box */}
          <div className="security-guarantee-box">
            <ShieldAlert size={16} className="text-amber" />
            <div className="sec-text">
              <strong>Section 2 Security Invariant Active:</strong>
              <span>Zero-Credential Collection. Agent refuses OTP, CVV, or UPI PIN requests.</span>
            </div>
          </div>
        </div>

        {/* Right: Conversation Transcript */}
        <div className="transcript-panel glass-panel">
          <div className="transcript-header">
            <h4>Live Conversation &amp; Tool Execution Feed</h4>
            <div style={{ display: 'flex', gap: '6px', alignItems: 'center', flexWrap: 'wrap' }}>
              {session && (
                <span className="badge badge-purple">{session.language?.toUpperCase()}</span>
              )}
              {session && (
                <span className={`badge ${statusCfg.color}`} style={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
                  {StatusIcon && <StatusIcon size={11} />}
                  {statusCfg.label}
                </span>
              )}
            </div>
          </div>

          <div className="transcript-feed">
            {!session && (
              <div className="feed-empty">
                <Phone size={30} className="empty-icon" />
                <p>No active call. Start a call to observe the conversational flow and live tool execution.</p>
              </div>
            )}

            {session?.turns?.map((turn, idx) => {
              if (turn.role === 'system') {
                // Inline system/error message
                return (
                  <div key={turn.turn_id || idx} className="chat-turn system" style={{ justifyContent: 'center' }}>
                    <div style={{
                      display: 'flex', alignItems: 'center', gap: '6px',
                      background: 'rgba(239,68,68,0.12)', border: '1px solid rgba(239,68,68,0.3)',
                      borderRadius: '8px', padding: '8px 14px', fontSize: '12px', color: 'var(--rose-400)',
                    }}>
                      <AlertCircle size={13} />
                      {turn.content}
                    </div>
                  </div>
                );
              }

              return (
                <div key={turn.turn_id || idx} className={`chat-turn ${turn.role}`}>
                  <div className="turn-bubble">
                    <div className="turn-role-tag">
                      {turn.role === 'assistant'
                        ? '🤖 Razorpay AI Recovery Agent'
                        : `👤 ${session.customerName}`}
                    </div>
                    <div className="turn-text">{turn.content}</div>

                    {turn.tool_calls && turn.tool_calls.length > 0 && (
                      <div className="tool-calls-container">
                        {turn.tool_calls.map((tc, tIdx) => (
                          <div key={tIdx} className="tool-badge-item">
                            <span className="tool-name-badge">
                              <Sparkles size={11} />
                              {tc.tool_name}
                            </span>
                            <span className="tool-result-text">
                              <ToolResultText tc={tc} />
                            </span>
                          </div>
                        ))}
                      </div>
                    )}
                  </div>
                </div>
              );
            })}

            {/* End-of-session indicator */}
            {session && sessionEnded && (
              <div style={{
                textAlign: 'center', padding: '14px 0 4px',
                borderTop: '1px solid rgba(255,255,255,0.08)', marginTop: '8px',
              }}>
                <span style={{ fontSize: '12px', color: 'var(--muted)', opacity: 0.7 }}>
                  {StatusIcon && <StatusIcon size={12} style={{ display: 'inline', marginRight: '4px' }} />}
                  Session {statusCfg.label} — conversation ended
                </span>
              </div>
            )}

            <div ref={chatBottomRef} />
          </div>

          {/* Quick speech chips */}
          {callActive && !sessionEnded && (
            <div className="quick-chips-wrapper">
              <span className="chips-label">Quick Voice Prompts:</span>
              <div className="chips-scroll">
                {quickSpeechChips.map((chip, idx) => (
                  <button
                    key={idx}
                    className="quick-chip"
                    disabled={loading || listening}
                    onClick={() => handleSendTurn(chip.text)}
                  >
                    {chip.label}
                  </button>
                ))}
              </div>
            </div>
          )}

          {/* Speech Input Bar */}
          <div className="speech-input-bar">
            {micSupported && (
              <button
                className={`btn mic-toggle-btn ${listening ? 'btn-rose' : 'btn-ghost'}`}
                disabled={!callActive || loading || sessionEnded}
                onClick={handleMicClick}
                title={listening ? 'Stop listening' : 'Speak (Chrome/Edge only)'}
              >
                {listening ? <MicOff size={16} /> : <Mic size={16} />}
              </button>
            )}
            <input
              type="text"
              placeholder={
                sessionEnded
                  ? 'Call session has ended'
                  : listening
                    ? 'Listening... speak now (or type)'
                    : callActive
                      ? 'Type what the customer says, or click 🎙 to use mic...'
                      : 'Start call to enable speech input...'
              }
              disabled={!callActive || loading || sessionEnded}
              value={inputText}
              onChange={(e) => setInputText(e.target.value)}
              onKeyDown={(e) => { if (e.key === 'Enter' && !listening && inputText.trim()) handleSendTurn(); }}
              className="speech-input"
            />
            {/* Interim display below input */}
            {interim && (
              <span style={{ position: 'absolute', bottom: '-18px', left: '50px', fontSize: '11px', color: 'var(--emerald-400)', fontStyle: 'italic' }}>
                🎙 {interim}...
              </span>
            )}
            <button
              className="btn btn-primary send-speech-btn"
              disabled={!callActive || loading || listening || !inputText.trim() || sessionEnded}
              onClick={() => handleSendTurn()}
            >
              {loading ? <RefreshCw size={15} className="animate-spin" /> : <Send size={15} />}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
