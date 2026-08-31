# Data Input & Razorpay Integration Context

## Revenue Recovery Intelligence Engine

### 1. Purpose

The Revenue Recovery Intelligence Engine is designed to operate on payment and customer-behavior data originating primarily from the Razorpay payment infrastructure.

For the development and demonstration environment, the system should use **Razorpay Test Mode** as the primary source of payment data rather than relying on a completely artificial payment dataset.

The application should be architected so that:

* Razorpay provides payment/order/event data.
* Our backend ingests and normalizes that data.
* Our application maintains its own customer, interaction, decision, and learning state.
* Synthetic data is used only where Razorpay cannot provide the behavioral/contextual information required by the intelligence layer.
* The same internal data model should work with both Razorpay Test Mode and, eventually, Razorpay Live Mode.

---

# 2. Data Source Strategy

The system should support three conceptual data sources.

```text
                    DATA INPUT LAYER
                          │
          ┌───────────────┼────────────────┐
          │               │                │
          ▼               ▼                ▼
   Razorpay Test      Application       Synthetic /
       Mode             Data             Simulation
          │               │                │
          └───────────────┼────────────────┘
                          ▼
                  Unified Data Model
                          │
                          ▼
                 Intelligence Engine
```

## 2.1 Razorpay Test Mode

This is the **primary source of payment-related data during development**.

Use Razorpay Test Mode to generate and observe:

* orders
* payment attempts
* successful payments
* failed payments
* payment status changes
* payment methods
* payment errors
* payment lifecycle events
* webhook events
* retries and repeated payment attempts

The system should treat these events as genuine external payment events, while recognizing that they occur in a non-production test environment.

---

# 3. Do Not Build a Completely Artificial Payment Dataset

The initial implementation should **not depend on a manually generated static dataset such as:**

```text
customers.csv
payments.csv
failures.csv
transactions.csv
```

with thousands of fabricated rows.

Instead, payment events should be generated through the Razorpay Test Environment and ingested dynamically.

The desired flow is:

```text
Razorpay Test Mode
       ↓
Payment / Order Activity
       ↓
Razorpay Webhook
       ↓
Webhook Receiver
       ↓
Event Normalization
       ↓
Internal Database
       ↓
Intelligence Engine
```

This allows the application to demonstrate an actual integration rather than simply pretending that payment events occurred.

---

# 4. Razorpay Test Mode

Razorpay provides a separate Test Environment for development and integration testing.

The application must use **Test API credentials** when running in development/demo mode.

Conceptually:

```env
RAZORPAY_MODE=test
RAZORPAY_KEY_ID=rzp_test_...
RAZORPAY_KEY_SECRET=...
```

Credentials must:

* be stored in environment variables or a secret manager
* never be hard-coded
* never be exposed to the frontend
* never be committed to source control
* remain separate from production credentials

The frontend must never directly receive the Razorpay secret key.

---

# 5. Three Operating Modes

The application should be designed around three operating modes.

## Mode 1 — Simulation

Used for deterministic testing of the intelligence engine.

```text
Synthetic Scenario
       ↓
Internal Event Generator
       ↓
Unified Event Pipeline
       ↓
Intelligence Engine
```

Examples:

```text
Payment failed → customer retries → payment succeeds

Payment failed → customer ignores → recovery fails

Payment failed → second attempt fails → customer changes method → success
```

Simulation is useful when a specific edge case needs to be reproduced repeatedly.

---

## Mode 2 — Razorpay Test Mode

This should be the primary development/demo mode.

```text
Customer/Test Flow
       ↓
Razorpay Test Environment
       ↓
Webhook
       ↓
Our Backend
       ↓
Event Store
       ↓
Intelligence Engine
```

This mode validates that the complete integration works with Razorpay's actual API/event structure.

---

## Mode 3 — Razorpay Live Mode

This is a future production mode.

```text
Real Customer
      ↓
Razorpay Live
      ↓
Webhook
      ↓
Our Backend
      ↓
Intelligence Engine
```

Live Mode must require additional safeguards and must never be enabled accidentally.

The internal architecture should remain the same; primarily the Razorpay configuration/environment changes.

---

# 6. Data Categories

The application should separate incoming data into several categories.

## 6.1 Payment Data

This is primarily obtained from Razorpay.

Examples:

* payment ID
* order ID
* amount
* currency
* payment status
* payment method
* timestamp
* failure information
* payment attempt information

Example normalized structure:

```json
{
  "payment_id": "pay_xxxxx",
  "order_id": "order_xxxxx",
  "amount": 1499,
  "currency": "INR",
  "status": "failed",
  "payment_method": "card",
  "timestamp": "..."
}
```

The exact fields must be based on the Razorpay API response rather than assumptions.

---

# 7. Order Data

Orders provide context around payment attempts.

A single order may have multiple payment attempts.

Example:

```text
Order #123
│
├── Attempt 1
│     Card → Failed
│
├── Attempt 2
│     Card → Failed
│
└── Attempt 3
      UPI → Successful
```

This sequence is extremely important for the recovery engine.

The system should therefore maintain the relationship:

```text
Customer
   ↓
Order
   ↓
Payment Attempts
   ↓
Payment Outcomes
```

rather than treating every payment as an isolated record.

---

# 8. Webhook Data

Webhooks are the preferred mechanism for detecting important payment events.

Conceptual architecture:

```text
Razorpay
    │
    │ Event
    ▼
POST /webhooks/razorpay
    │
    ▼
Signature Verification
    │
    ├── Invalid → Reject
    │
    └── Valid
          ↓
       Parse Event
          ↓
       Store Event
          ↓
       Process Event
```

The webhook service must:

1. receive the event
2. verify authenticity/signature according to Razorpay's webhook mechanism
3. identify the event type
4. validate the payload
5. store the raw event where appropriate
6. normalize it into the internal event format
7. update application state
8. trigger downstream processing

---

# 9. Webhook Idempotency

Webhook processing must be idempotent.

The same event may potentially be delivered more than once.

The system must therefore prevent:

```text
Event A
Event A
```

from becoming:

```text
Recovery Action
Recovery Action
```

Instead:

```text
Event A
   ↓
Already processed?
   │
   ├── YES → Ignore duplicate
   │
   └── NO → Process
```

Every externally received event should have an appropriate unique identifier or deduplication mechanism.

---

# 10. Internal Normalized Event Model

The intelligence engine should **not depend directly on Razorpay's raw response format**.

Introduce an internal normalized event model.

Example:

```json
{
  "event_id": "evt_123",
  "source": "razorpay",
  "environment": "test",
  "event_type": "payment_failed",
  "customer_id": "cust_123",
  "order_id": "order_123",
  "payment_id": "pay_123",
  "timestamp": "...",
  "amount": 1499,
  "currency": "INR",
  "payment_method": "card",
  "failure_reason": "...",
  "metadata": {}
}
```

The exact schema should evolve based on the actual Razorpay payloads encountered.

---

# 11. Razorpay Adapter

All Razorpay-specific logic should be isolated inside a dedicated adapter/service.

Conceptually:

```text
Application
    │
    ▼
Razorpay Adapter
    │
    ├── Create/Fetch Order
    ├── Fetch Payment
    ├── Fetch Payment History
    ├── Handle Razorpay-specific responses
    └── Map Razorpay data
             ↓
       Internal Data Model
```

The intelligence engine should never contain Razorpay-specific API logic.

For example, avoid:

```text
PredictionEngine → Razorpay API
```

Prefer:

```text
PredictionEngine
       ↓
Internal Models
       ↓
Execution Service
       ↓
Razorpay Adapter
       ↓
Razorpay
```

This abstraction will make future migration from Test Mode to Live Mode much easier.

---

# 12. Application-Owned Customer Data

Razorpay payment data alone is not sufficient for the complete intelligence engine.

Our application should maintain its own customer/context layer.

Potential fields include:

```text
Customer Profile
├── internal_customer_id
├── Razorpay customer reference
├── preferred language
├── communication preferences
├── previous interaction history
├── recovery history
├── successful recovery count
├── unsuccessful recovery count
└── behavioral features
```

These fields belong to our application's intelligence layer and should not be assumed to come directly from Razorpay.

---

# 13. Communication Data

The personalization engine requires information that is outside the payment gateway.

The application should maintain:

```text
Interaction History
├── customer_id
├── event_id
├── channel
├── message
├── language
├── timestamp
├── action_type
├── customer_response
└── outcome
```

Example:

```text
Payment failed
      ↓
Recovery message sent
      ↓
Customer retries
      ↓
Payment succeeds
```

The complete sequence becomes a learning example.

---

# 14. Hinglish / Personalized Communication

The system should support personalized communication.

For example:

```text
Customer preference:
Hinglish

Payment:
Failed

Recovery message:
"Hey! Aapka payment complete nahi ho paya.
Ek baar phir try karoge?"
```

The message-generation system should use application-owned customer context together with the current payment context.

However, the LLM should not directly execute financial operations.

Correct architecture:

```text
Payment Event
     ↓
Context Engine
     ↓
Decision Engine
     ↓
LLM / Communication Generator
     ↓
Candidate Action
     ↓
Policy Engine
     ↓
Execution Service
```

---

# 15. Behavioral Data

The intelligence layer should derive behavioral features from sequences of actual events.

For example:

```text
Customer C123

Previous payments: 10
Successful: 8
Failed: 2

Typical retry interval: 4 minutes

Previous recovery:
Message → Retry → Success
```

These features should be generated from stored event history rather than fabricated wherever possible.

---

# 16. Recovery Dataset

The application should eventually build its own learning dataset from real test interactions.

Each recovery episode can be represented conceptually as:

```json
{
  "customer_context": {},
  "payment_context": {},
  "historical_context": {},
  "action": "send_recovery_message",
  "action_parameters": {},
  "outcome": "payment_success",
  "reward": 1
}
```

This dataset is created by the application itself as the system operates.

Therefore:

```text
Razorpay Test Events
        +
Application Context
        +
Agent Actions
        +
Observed Outcomes
        ↓
Internal Learning Dataset
```

---

# 17. RL / Feedback Data

The learning system should record:

```text
State
Action
Outcome
Reward
```

Example:

```text
State:
Payment failed
Customer historically retries
Customer prefers UPI
Failure occurred recently

Action:
Send personalized UPI recovery message

Outcome:
Customer retries using UPI

Result:
Payment successful

Reward:
Positive
```

This allows future development of:

* contextual bandits
* policy optimization
* reinforcement learning
* offline learning
* action ranking
* recovery strategy optimization

Initially, the system should prioritize **logging and evaluation** rather than allowing unrestricted online RL to control financial actions.

---

# 18. Synthetic Data — When It Is Allowed

Synthetic data should be treated as an augmentation mechanism, not the primary source of payment truth.

Use synthetic data when:

### A. Razorpay does not provide the required attribute

For example:

```text
Preferred language = Hinglish
```

This may belong to our application profile.

### B. A rare edge case is difficult to reproduce

Example:

```text
5 consecutive payment failures
```

A simulator can create the scenario for testing.

### C. Large-scale ML experiments are required

If the model requires millions of examples, synthetic augmentation may be useful during research.

### D. Deterministic testing is required

Example:

```text
Given state X
→ expected policy = Y
```

The simulator can reproduce X repeatedly.

---

# 19. Synthetic Data — What It Should NOT Replace

Synthetic data should not replace actual integration testing for:

* Razorpay API behavior
* authentication
* webhook payloads
* webhook signatures
* payment status handling
* API errors
* request/response formats
* Test Mode integration
* actual Razorpay lifecycle events

Those should be tested against Razorpay Test Mode.

---

# 20. Recommended Data Pipeline

The complete pipeline should be:

```text
                     RAZORPAY TEST MODE
                             │
                   ┌─────────┴─────────┐
                   │                   │
                  API               Webhook
                   │                   │
                   └─────────┬─────────┘
                             ▼
                    Razorpay Adapter
                             │
                             ▼
                    Event Normalizer
                             │
                             ▼
                     Event Database
                             │
                             ▼
                     Context Builder
                             │
                  ┌──────────┴──────────┐
                  │                     │
           Customer Context       Payment Context
                  │                     │
                  └──────────┬──────────┘
                             ▼
                    Intelligence Engine
                             │
                             ▼
                     Policy Engine
                             │
                             ▼
                    Action / Agent
                             │
                             ▼
                    Execution Service
                             │
                             ▼
                         Razorpay
                             │
                             ▼
                         New Event
                             │
                             ▼
                        Feedback
                             │
                             ▼
                    Learning Dataset
```

---

# 21. Source of Truth

The system should maintain clear ownership of data.

### Razorpay is the source of truth for

* payment state
* payment identifiers
* order/payment information
* payment lifecycle events
* gateway-level payment outcomes

### Our application is the source of truth for

* customer intelligence profile
* communication history
* agent decisions
* policy decisions
* recovery attempts
* behavioral features
* rewards
* model predictions
* learning history

This separation is critical.

---

# 22. Raw Data vs Normalized Data

Store both where useful.

```text
Razorpay Raw Event
       │
       ├──────────────► Raw Event Store
       │
       ▼
Normalizer
       │
       ▼
Normalized Event
       │
       ▼
Application Database
```

Raw events are useful for:

* debugging
* replaying events
* investigating integration failures
* adapting to future Razorpay changes
* auditability

Normalized events are useful for:

* analytics
* prediction
* policy evaluation
* ML/RL
* application logic

---

# 23. Environment Isolation

Test and Live data must never accidentally mix.

Every event should have an environment identifier.

Example:

```json
{
  "environment": "test"
}
```

Possible values:

```text
test
live
simulation
```

Database queries, analytics, models, and dashboards should be able to filter by environment.

For example:

```text
environment = test
```

should never accidentally appear as production revenue.

---

# 24. Development Strategy

Implementation should happen in this order:

### Step 1

Create Razorpay Test Mode credentials.

### Step 2

Implement Razorpay Adapter.

### Step 3

Implement order/payment retrieval.

### Step 4

Implement webhook receiver.

### Step 5

Implement webhook verification.

### Step 6

Store raw Razorpay events.

### Step 7

Build normalized internal event schema.

### Step 8

Build customer/payment context.

### Step 9

Implement recovery decision engine.

### Step 10

Implement personalized communication.

### Step 11

Implement policy validation.

### Step 12

Implement action execution.

### Step 13

Capture outcomes.

### Step 14

Generate reward/feedback records.

### Step 15

Build learning/evaluation pipeline.

### Step 16

Add simulation for difficult or rare scenarios.

---

# 25. Important Architectural Principle

The application must not be designed around:

```text
Fake Dataset
      ↓
AI Model
      ↓
Demo
```

It should instead be designed around:

```text
External Payment Events
          ↓
     Data Ingestion
          ↓
      Event Store
          ↓
     Context Engine
          ↓
   Intelligence Engine
          ↓
     Policy Engine
          ↓
     Action Layer
          ↓
    External Outcome
          ↓
       Feedback
          ↓
       Learning
```

The application is therefore an **event-driven closed-loop system**.

---

# 26. Final Data Strategy

The recommended strategy is:

```text
                PAYMENT DATA
                     │
                     ▼
            Razorpay Test Mode
                     │
                     ▼
              Actual Test Events
                     │
                     ▼
             Our Internal Store
                     │
          ┌──────────┴──────────┐
          │                     │
          ▼                     ▼
   Customer Context       Payment Context
          │                     │
          └──────────┬──────────┘
                     ▼
             Intelligence Layer
                     │
                     ▼
               Agent / Policy
                     │
                     ▼
                 Action
                     │
                     ▼
                Razorpay
                     │
                     ▼
                Outcome
                     │
                     ▼
               Feedback Data
                     │
                     ▼
              Learning System
```

### Core rule

**Do not fabricate payment data when Razorpay Test Mode can provide it.**

Use Razorpay Test Mode for the actual payment lifecycle.

**Do not expect Razorpay to provide all intelligence-related customer context.**

Maintain those attributes inside our own application.

**Use synthetic/simulated data only to fill gaps, reproduce rare scenarios, stress-test the system, or perform controlled ML experiments.**

This gives the system a credible progression from:

**Test Mode → validated prototype → production-ready architecture → Live Mode.**
