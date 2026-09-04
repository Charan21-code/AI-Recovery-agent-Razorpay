# Razorpay Autonomous Revenue Recovery AI Engine
### *Track 03 — AI Revenue Recovery | Razorpay Buildathon*

[![FastAPI](https://img.shields.io/badge/Backend-FastAPI-009688?style=flat&logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/)
[![React](https://img.shields.io/badge/Frontend-React%2019-61DAFB?style=flat&logo=react&logoColor=black)](https://react.dev/)
[![Vite](https://img.shields.io/badge/Bundler-Vite-646CFF?style=flat&logo=vite&logoColor=white)](https://vitejs.dev/)
[![Python](https://img.shields.io/badge/Python-3.11%2B-3776AB?style=flat&logo=python&logoColor=white)](https://python.org)
[![Pytest](https://img.shields.io/badge/Tests-66%20Passing-brightgreen?style=flat&logo=pytest&logoColor=white)](https://pytest.org)

An event-driven, policy-governed Autonomous AI Revenue Recovery Engine designed for Razorpay merchants. The engine proactively identifies revenue at risk (failed payments, checkout abandonments, subscription lapses, and overdue invoices), predicts the optimal recovery intervention using machine learning, orchestrates multi-agent outreach, conducts conversational AI voice calls, and continuously improves recovery yield through contextual bandit feedback loops.

---

## Architecture Overview

The system follows a strict closed-loop intelligence architecture:
$$\textbf{Detect} \longrightarrow \textbf{Understand} \longrightarrow \textbf{Predict} \longrightarrow \textbf{Decide} \longrightarrow \textbf{Govern} \longrightarrow \textbf{Act} \longrightarrow \textbf{Observe} \longrightarrow \textbf{Learn}$$

```text
┌──────────────────────────────────────────────────────────────────────────────┐
│                            RAZORPAY WEBHOOKS & EVENTS                        │
│             (payment.failed, order.abandoned, subscription.halted)           │
└──────────────────────────────────────┬───────────────────────────────────────┘
                                       │ HMAC-SHA256 & Idempotency Guard
                                       ▼
┌──────────────────────────────────────────────────────────────────────────────┐
│                    INGESTION & NORMALIZATION PIPELINE                        │
│      • NormalizedEvent schema (payment, checkout, subscription, invoice)    │
│      • Gateway Degradation Detector (isolate bank outage vs customer failure)│
└──────────────────────────────────────┬───────────────────────────────────────┘
                                       │
                                       ▼
┌──────────────────────────────────────────────────────────────────────────────┐
│                     CHRONOLOGICAL STATE & FEATURE STORE                      │
│      • Point-in-time context builder (strictly zero future leakage)          │
│      • 20-dimensional recovery feature vector                                │
└──────────────────────────────────────┬───────────────────────────────────────┘
                                       │
                                       ▼
┌──────────────────────────────────────────────────────────────────────────────┐
│                  ML PROPENSITY & OPPORTUNITY SCORING ENGINE                  │
│      • P(recovery | action, context) calibrated across 9 action channels     │
│      • Value-at-risk opportunity scoring and urgency prioritization         │
│      • Optimal communication timing optimizer                                │
└──────────────────────────────────────┬───────────────────────────────────────┘
                                       │
                                       ▼
┌──────────────────────────────────────────────────────────────────────────────┐
│                 AUTONOMOUS MULTI-AGENT ORCHESTRATION LAYER                   │
│   ┌────────────────────────┬────────────────────────┬────────────────────┐   │
│   │  PaymentFailureAgent   │ CheckoutAbandonmentAgent│SubscriptionAgent   │   │
│   └────────────────────────┴────────────────────────┴────────────────────┘   │
│   ┌────────────────────────┬─────────────────────────────────────────────┐   │
│   │ OverdueReceivableAgent │ Autonomous Voice Recovery Agent (Real-time) │   │
│   └────────────────────────┴─────────────────────────────────────────────┘   │
└──────────────────────────────────────┬───────────────────────────────────────┘
                                       │ Proposed Action Plan
                                       ▼
┌──────────────────────────────────────────────────────────────────────────────┐
│                      MERCHANT POLICY & GOVERNANCE ENGINE                     │
│      • Frequency capping & anti-fatigue limits                               │
│      • Hard-decline blocks (do not retry stolen/lost card errors)            │
│      • VIP customer escalation rules & opt-out protection                    │
│      • Safe execution guardrails: APPROVED / MODIFIED / BLOCKED / ESCALATED  │
└──────────────────────────────────────┬───────────────────────────────────────┘
                                       │ Approved Action
                                       ▼
┌──────────────────────────────────────────────────────────────────────────────┐
│                         EXECUTION & DISPATCH ADAPTER                         │
│      • Razorpay 1-click WhatsApp/SMS payment links                           │
│      • Automated intelligent gateway re-attempts                             │
│      • Interactive Voice Agent outbound recovery calls                       │
└──────────────────────────────────────┬───────────────────────────────────────┘
                                       │ Event Outcomes
                                       ▼
┌──────────────────────────────────────────────────────────────────────────────┐
│                   OUTCOME AUDIT & CONTEXTUAL BANDIT LEARNING                 │
│      • Multi-Armed Bandit (Upper Confidence Bound / Thompson Sampling)       │
│      • Net recovery ROI calculation (recovered amount - intervention costs)  │
│      • Continuous policy weight updates for future predictions               │
└──────────────────────────────────────────────────────────────────────────────┘
```

---

## Core Features & Modules

### 1. Ingestion & Gateway Degradation Detection
- **HMAC Verification & Idempotency:** Every webhook is verified against merchant secrets and checked for deduplication.
- **Systemic Degradation Isolation:** Automatically distinguishes between an isolated card failure and a massive bank/gateway downtime (e.g., HDFC UPI down), pausing immediate retries to prevent customer fatigue.

### 2. Predictive ML & Opportunity Scoring
- **Propensity Model:** Computes multi-action win probabilities $P(\text{Recovery} \mid \text{Action}, \text{Context})$ across channels (WhatsApp 1-click link, SMS reminder, auto-retry, email notification, outbound voice call).
- **Opportunity Ranking:** Prioritizes opportunities by expected recoverable revenue $(\text{Amount} \times P(\text{Recovery}))$, giving merchant operations an actionable queue.

### 3. Specialized Multi-Agent Framework
- **Payment Failure Agent:** Tiered recovery strategy based on error codes (insufficient funds, bank timeout, authentication drop).
- **Checkout Abandonment Agent:** Engages dropouts with contextual cart recovery links and anti-spam pacing.
- **Subscription Recovery Agent:** Prevents involuntary churn on recurring payments and mandate issues.
- **Overdue Receivable Agent:** Handles B2B invoices with tailored reminders and automated escalation.

### 4. Autonomous Conversational Voice AI Agent
- **Natural, Empathetic Voice Turns:** Communicates in English, Hindi, and Hinglish.
- **Zero-Credential Security Invariant:** Never asks for or accepts CVVs, OTPs, or UPI PINs. Automatically warns customers if they attempt to share credentials.
- **Tool Execution:** Real-time Razorpay status verification, instant 1-click WhatsApp payment link dispatch, and bank deduction dispute ticketing.

### 5. Policy Governance & Audit Engine
- **Deterministic Guardrails:** Hard policy limits defined by the merchant (max retry attempts, quiet hours, cooldown intervals, discount ceilings).
- **Comprehensive Audit Trail:** Immutable execution logging for compliance, tracing why each decision was made.

### 6. Contextual Bandit Continuous Improvement
- Tracks net financial yield: $\text{Net Recovered} = \text{Amount Recovered} - \text{Intervention Cost}$.
- Adjusts multi-armed bandit weights online so winning recovery strategies earn more traffic over time.

---

## Technology Stack

| Layer | Technologies |
|---|---|
| **Backend** | Python 3.11+, FastAPI, SQLAlchemy, Pydantic v2, Uvicorn |
| **Frontend** | React 19, Vite, Vanilla CSS Design System, Lucide Icons, Canvas 3D Graphics |
| **AI / Machine Learning** | Contextual Multi-Armed Bandit, Predictive Propensity Engine, Gemini LLM |
| **Testing** | Pytest 8, AnyIO, AsyncIO, Pytest-Cov (66 automated tests) |

---

## Repository Structure

```text
.
├── backend/
│   ├── api/                  # FastAPI routes and v1 endpoints
│   │   └── v1/router.py      # KPIs, Opportunity Queue, Explorer, Simulator, Voice API
│   ├── core/                 # Config, constants, and logging
│   ├── data/                 # SQLite storage and runtime data files
│   ├── db/                   # SQLAlchemy models and session factory
│   │   └── models/           # Customers, transactions, events, recoveries, feedback
│   ├── schemas/              # Pydantic v2 domain schemas
│   ├── services/
│   │   ├── agents/           # Specialized recovery agents & orchestrator
│   │   ├── analytics/        # Business intelligence and KPI aggregation
│   │   ├── context/          # Temporal context builder (zero leakage)
│   │   ├── execution/        # Razorpay adapter, scheduler, and executor
│   │   ├── features/         # Feature engine & degradation detector
│   │   ├── feedback/         # Contextual bandit learner & feedback store
│   │   ├── ingestion/        # Webhook receiver, HMAC guard, idempotency
│   │   ├── llm/              # LLM reasoning engine with deterministic fallback
│   │   ├── ml/               # Opportunity scorer, propensity predictor, trainer
│   │   ├── normalization/    # Event normalizer for Razorpay payloads
│   │   ├── outcomes/         # Revenue calculator, outcome processor, audit trail
│   │   ├── policy_engine/    # Merchant policy rule engine & validator
│   │   ├── state/            # Chronological customer/order state store
│   │   └── voice/            # Voice recovery agent and tool suite
│   ├── tests/                # 66 comprehensive automated test suites
│   └── main.py               # Application entrypoint & FastAPI app
├── frontend/
│   ├── public/               # Static assets & SVG icons
│   ├── src/
│   │   ├── assets/           # UI media & brand visuals
│   │   ├── components/       # UI components, landing page, navigation
│   │   │   └── dashboard/    # Simulator, Queue, Explorer, Bandit, Voice Agent tabs
│   │   ├── App.jsx           # Main React component with dual Mode (Landing / Console)
│   │   ├── App.css           # Modern dark-mode styling & micro-animations
│   │   └── main.jsx          # React DOM entry point
│   ├── index.html            # HTML5 host page
│   ├── package.json          # Node dependencies
│   └── vite.config.js        # Vite configuration
├── .env.example              # Template environment variables
├── .gitignore                # Production gitignore
├── pytest.ini                # Pytest configuration
└── requirements.txt          # Python dependencies
```

---

## Getting Started

### Prerequisites
- **Python:** 3.11 or higher
- **Node.js:** 18.x or higher
- **npm:** 9.x or higher

---

### Backend Setup

1. **Clone the repository:**
   ```bash
   git clone https://github.com/Charan21-code/AI-Recovery-agent-Razorpay.git
   cd AI-Recovery-agent-Razorpay
   ```

2. **Create and activate a virtual environment:**
   ```bash
   python -m venv .venv
   # Windows:
   .venv\Scripts\activate
   # macOS/Linux:
   source .venv/bin/activate
   ```

3. **Install Python dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

4. **Configure environment variables:**
   ```bash
   cp .env.example .env
   # Edit .env with your optional keys (Razorpay test keys, Gemini API key)
   ```

5. **Start the backend server:**
   ```bash
   uvicorn backend.main:app --host 127.0.0.1 --port 8000 --reload
   ```
   API will be available at: `http://localhost:8000`  
   Interactive API docs (Swagger): `http://localhost:8000/docs`

---

### Frontend Setup

1. **Navigate to the frontend directory:**
   ```bash
   cd frontend
   ```

2. **Install Node dependencies:**
   ```bash
   npm install
   ```

3. **Start the Vite development server:**
   ```bash
   npm run dev
   ```
   Frontend will be available at: `http://localhost:5173`

---

### Running Automated Tests

The test suite covers the full pipeline end-to-end: schema validation, event ingestion, temporal state building, ML predictors, multi-agent dispatch, policy engine governance, voice agent lifecycle, and outcome processing.

```bash
# Run all 66 tests
pytest backend/tests

# Run with verbose output
pytest backend/tests -v
```

---

## Interactive Console Tour

The frontend provides an enterprise console for merchants:
1. **Live Simulator:** Trigger simulated payment failures, bank timeouts, or checkout abandonments and watch the autonomous pipeline execute in real time.
2. **Opportunity Queue:** Prioritized list of at-risk revenue ranked by ML recovery propensity score.
3. **Event Explorer & Customer 360:** Historical event timeline and customer profile metrics with zero future-data leakage.
4. **Bandit Analytics:** Visualizes multi-armed bandit exploration vs. exploitation metrics and channel recovery rates.
5. **Voice AI Console:** Interactive voice agent interface with live speech transcription, intent detection, and automated tool dispatch (payment link SMS/WhatsApp, dispute filing).

---

## License

This project is built for the **Razorpay Buildathon — Track 03: AI Revenue Recovery**.
Distributed under the MIT License.
