# Revenue Recovery Intelligence Engine

## Final Product & Technical Specification

**Buildathon:** Razorpay Buildathon
**Track:** Track 03 — AI Revenue Recovery
**Working Product Name:** Revenue Recovery Intelligence Engine
**Status:** Master Specification / Source of Truth
**Primary Goal:** Build a working, measurable, policy-controlled AI system that detects revenue at risk, understands why it is at risk, determines the best recovery strategy, executes the intervention, observes the outcome, and continuously improves from feedback.

---

# 1. Executive Summary

The **Revenue Recovery Intelligence Engine** is an event-driven AI system for merchants that identifies revenue that is at risk of being lost and autonomously determines the most appropriate recovery strategy.

The system processes a chronological stream of merchant events such as:

* successful payments
* failed payments
* checkout abandonment
* subscription payment failures
* overdue invoices
* mandate failures
* recovery attempts
* recovery outcomes

The system does not treat events as isolated transactions.

Instead, it maintains a continuously updated state of customers, payments, subscriptions, invoices, and previous recovery attempts.

For every new event, the system:

1. Classifies the event.
2. Determines whether it represents a recovery opportunity.
3. Retrieves the relevant historical context available up to that point in time.
4. Generates meaningful customer, revenue, and action intelligence.
5. Predicts recovery outcomes for candidate interventions.
6. Selects an appropriate recovery strategy.
7. Validates the decision against merchant-defined policies.
8. Executes the approved action through Razorpay test-mode APIs or a controlled simulation layer.
9. Observes the result.
10. Updates the state.
11. Calculates recovered revenue and other business metrics.
12. Stores the outcome as feedback for future learning.

The core philosophy is:

> **Detect → Understand → Predict → Decide → Govern → Act → Observe → Learn**

---

# 2. Problem Statement

Merchants lose revenue for many reasons.

A customer may:

* experience a payment failure
* abandon checkout
* have a recurring subscription payment fail
* leave an invoice unpaid
* experience a mandate failure
* repeatedly fail recovery attempts
* become inactive during the payment process

Traditional systems often use simple rules such as:

> "Payment failed → retry."

This is inefficient because not every customer, failure, or situation should receive the same intervention.

The objective of this project is therefore not simply to identify failed payments.

The objective is:

> **Maximize useful recovered revenue while minimizing unnecessary interventions, intervention cost, customer friction, and unsafe actions.**

---

# 3. Product Thesis

The product acts as an intelligent revenue-recovery layer between a merchant's event stream and their recovery operations.

It answers:

### What happened?

Event classification.

### What do we know about it?

Historical and contextual state.

### What is likely to work?

Predictive intelligence.

### What should we do?

Recovery strategy selection.

### Are we allowed to do it?

Policy enforcement.

### Did it work?

Outcome measurement.

### What should we learn from it?

Feedback and adaptive learning.

---

# 4. Core Architecture

```text
                    MERCHANT / RAZORPAY EVENTS
                              │
                              ▼
                     ┌─────────────────┐
                     │ EVENT INGESTION │
                     └────────┬────────┘
                              │
                              ▼
                     ┌─────────────────┐
                     │ EVENT CLASSIFIER│
                     └────────┬────────┘
                              │
                    ┌─────────┴─────────┐
                    │                   │
                    ▼                   ▼
             HISTORICAL EVENT     ACTIONABLE EVENT
                    │                   │
                    │                   ▼
                    │             CONTEXT BUILDER
                    │                   │
                    └─────────┬─────────┘
                              ▼
                         STATE STORE
                              │
                              ▼
                       FEATURE ENGINE
                              │
             ┌────────────────┼────────────────┐
             ▼                ▼                ▼
       CUSTOMER SIGNALS  REVENUE SIGNALS  ACTION SIGNALS
             │                │                │
             └────────────────┼────────────────┘
                              ▼
                    RECOVERY PREDICTOR
                              │
                              ▼
                       RECOVERY AGENT
                              │
                              ▼
                       POLICY ENGINE
                              │
                       ┌──────┴──────┐
                       │             │
                    APPROVED       BLOCKED
                       │             │
                       ▼             ▼
                     ACTION       STOP / ESCALATE
                       │
                       ▼
                EXECUTION LAYER
                       │
              ┌────────┴────────┐
              ▼                 ▼
        Razorpay Test      Simulation
             APIs             Engine
              │                 │
              └────────┬────────┘
                       ▼
                    OUTCOME
                       │
              ┌────────┴────────┐
              ▼                 ▼
          RECOVERED            FAILED
              │                 │
              └────────┬────────┘
                       ▼
                 STATE UPDATE
                       │
                       ▼
                 AUDIT + METRICS
                       │
                       ▼
                FEEDBACK STORE
                       │
                       ▼
              LEARNING SYSTEM
                       │
             ┌─────────┴─────────┐
             ▼                   ▼
       MODEL IMPROVEMENT    POLICY CANDIDATE
```

---

# 5. Event-Driven Philosophy

The system must behave as if events are arriving in real time.

A dataset containing 1,000 or more records should therefore be treated as an **ordered event stream**, not merely as a static table.

Example:

```text
E001 SUCCESS
E002 SUCCESS
E003 SUCCESS
E004 PAYMENT_FAILED

→ Recovery decision

R001 RECOVERY_ATTEMPT
R002 PAYMENT_RECOVERED

E005 SUCCESS
E006 SUCCESS

E007 PAYMENT_FAILED

→ Recovery decision
```

The outcome of E004 becomes part of the state available when E007 is processed.

---

# 6. Critical Rule: No Future Leakage

The system must never use future information when making a decision.

When processing E004, only information from:

* E001
* E002
* E003
* E004

and information generated as a result of processing E004 may be used.

E005, E006, E007 and later events must not influence the E004 decision.

When E007 arrives, E004's recovery outcome is now legitimate historical information.

This temporal constraint must apply to:

* feature generation
* ML training
* evaluation
* simulation
* agent context
* analytics

This is a non-negotiable requirement.

---

# 7. Dataset Philosophy

The dataset should contain both successful and unsuccessful events.

Successful transactions are extremely important because they establish customer history.

For example:

```text
E001 SUCCESS
E002 SUCCESS
E003 SUCCESS
E004 FAILED
E005 SUCCESS
E006 SUCCESS
E007 FAILED
```

When E007 occurs, the system can know:

```text
Previous transactions = 6
Successful = 5
Failed = 1

Previous failure:
E004

Previous recovery:
E004 → retry → recovered
```

This historical information can influence the next recovery decision.

---

# 8. Historical vs Actionable Events

## Historical Events

These primarily update state:

* successful payments
* completed orders
* successful subscription payments
* previous recovery outcomes
* customer activity
* paid invoices

## Actionable Events

These can trigger recovery workflows:

* payment failures
* checkout abandonment
* subscription payment failures
* overdue invoices
* mandate failures
* other recoverable revenue-loss events

A successful transaction is not discarded.

It updates the customer's historical state.

---

# 9. Event Taxonomy

The architecture should support:

## Payments

```text
PAYMENT_SUCCESS
PAYMENT_FAILED
PAYMENT_PENDING
PAYMENT_REFUNDED
```

## Checkout

```text
CHECKOUT_STARTED
PAYMENT_INITIATED
CHECKOUT_ABANDONED
```

## Subscriptions

```text
SUBSCRIPTION_CREATED
SUBSCRIPTION_ACTIVE
SUBSCRIPTION_PAYMENT_FAILED
SUBSCRIPTION_CANCELLED
SUBSCRIPTION_EXPIRED
```

## Invoices

```text
INVOICE_CREATED
INVOICE_PAID
INVOICE_OVERDUE
```

## Mandates

```text
MANDATE_CREATED
MANDATE_ACTIVE
MANDATE_FAILED
```

## Recovery

```text
RECOVERY_ATTEMPTED
RECOVERY_SUCCESS
RECOVERY_FAILED
RECOVERY_STOPPED
RECOVERY_ESCALATED
```

## Other

```text
UNKNOWN
NON_RECOVERABLE
```

The initial implementation should prioritize:

1. Payment Failure
2. Checkout Abandonment
3. Subscription Payment Failure
4. Overdue Receivable

The architecture must remain extensible to mandate failures and additional event types.

---

# 10. Event Schema

A generic event may contain:

```json
{
  "event_id": "E007",
  "timestamp": "2026-08-30T10:32:00",
  "merchant_id": "M101",
  "customer_id": "C101",

  "event_type": "PAYMENT_FAILED",

  "amount": 2499,
  "currency": "INR",

  "payment_method": "UPI",
  "failure_code": "BANK_TIMEOUT",

  "order_id": "ORD1007",
  "subscription_id": null,
  "invoice_id": null,

  "checkout_stage": null,

  "previous_attempt_count": 0
}
```

The actual implementation must first inspect the provided dataset.

Do not assume these fields exist.

Map real dataset fields into this conceptual schema.

If information is unavailable, mark it unavailable rather than inventing it.

---

# 11. State Store

The State Store is a first-class system component.

It maintains current knowledge about:

* customers
* payments
* orders
* subscriptions
* invoices
* recovery workflows
* merchant policies

Example customer state:

```json
{
  "customer_id": "C101",

  "total_transactions": 9,
  "successful_transactions": 7,
  "failed_transactions": 2,

  "success_rate": 0.778,

  "total_revenue": 22491,
  "average_transaction_value": 2499,

  "previous_recovery_attempts": 2,
  "successful_recoveries": 2,

  "recovery_rate": 1.0,

  "average_recovery_time_minutes": 38,

  "last_activity_timestamp": "...",

  "recent_intervention_count": 1
}
```

State must be updated after every event.

---

# 12. Context Builder

The Context Builder transforms raw event data and state into meaningful context.

It should not simply pass an entire CSV row or the entire dataset to an LLM.

It should retrieve relevant historical information and compute derived features first.

Example:

```text
CURRENT EVENT
Payment Failure
₹4,999
Bank Timeout

CUSTOMER HISTORY
9 previous transactions
7 successful
2 failed

RECOVERY HISTORY
2 previous recovery attempts
2 successful

HISTORICAL RECOVERY RATE
100%

AVERAGE RECOVERY TIME
38 minutes

RECENT ACTIVITY
High

MERCHANT POLICY
Maximum retries = 3
Retry window = 24 hours
```

The recovery system receives this structured context.

---

# 13. Feature Engineering Philosophy

Features must be **decision-relevant**.

A feature should be considered meaningful if changing it could change:

* recovery probability
* recommended action
* intervention priority
* intervention timing
* stopping decision
* escalation decision
* expected recovered revenue
* ROI

Avoid adding features merely to make the dashboard look sophisticated.

---

# 14. Customer Intelligence

## 14.1 Recovery Propensity

Estimate:

> How likely is this customer to recover from a revenue-loss event?

Potential inputs:

* historical payment success rate
* failure count
* previous recovery count
* historical recovery rate
* recovery time
* recent activity
* payment method
* transaction frequency
* transaction value
* previous intervention responses

Example:

```text
Recovery Propensity = 84%
```

---

# 15. Revenue Intelligence

## 15.1 Revenue at Risk

The immediate monetary value associated with the current recoverable event.

Example:

```text
Failed payment = ₹4,999

Revenue at Risk = ₹4,999
```

## 15.2 Expected Recovered Revenue

Conceptually:

```text
Expected Recovery Value
=
Revenue at Risk × Recovery Probability
```

Example:

```text
₹4,999 × 0.81
=
₹4,049.19
```

This is an expected value, not guaranteed revenue.

---

# 16. Customer Lifetime Revenue at Risk

For recurring customers, current transaction value may not represent the full financial impact.

Where sufficient historical information exists, estimate future expected revenue.

Example:

```text
Current failed payment = ₹5,000

Expected future revenue = ₹45,000

Potential total revenue at risk = ₹50,000
```

This must be clearly labeled as an estimate.

Never present predicted future revenue as guaranteed revenue.

---

# 17. Action Intelligence

For each actionable event, evaluate candidate interventions.

Example:

```text
Immediate Retry        61%
Delayed Retry          83%
Payment Update         64%
Reminder               48%
Escalation             19%
```

These represent estimated recovery probabilities if supported by actual training data.

The selected action should consider:

* recovery probability
* revenue value
* intervention cost
* customer friction
* previous interventions
* merchant policy
* timing
* customer history
* stopping rules

---

# 18. Optimal Intervention Timing

Historical data may reveal that recovery probability varies with time.

Example:

```text
Immediate retry       32%
30-minute delay       54%
2-hour delay          71%
Next-day retry        68%
```

If the data supports the pattern, the system may recommend:

> Retry after approximately 2 hours.

The system must not invent temporal patterns.

---

# 19. Intervention Fatigue

Track the number and frequency of interventions.

Possible signals:

* recent intervention count
* time between interventions
* previous intervention response
* customer engagement
* failed recovery attempts

If repeated intervention reduces expected effectiveness, the agent should favor:

* stopping
* escalation
* alternate recovery methods

instead of blindly continuing.

---

# 20. Recovery Window

Estimate how long recovery attempts remain useful.

Example:

```text
Customer A → likely recovery within 2 hours
Customer B → likely recovery within 24 hours
Customer C → little benefit after 6 hours
```

This can inform stopping rules.

---

# 21. Failure Pattern Intelligence

The system should analyze aggregate events for merchant-level patterns.

Examples:

* sudden failure-rate increase
* payment-method degradation
* time-based failure patterns
* segment-specific degradation
* repeated failure codes
* checkout abandonment spikes

Example:

> UPI failures increased 4.2× relative to the historical baseline.

If a merchant-wide degradation is detected, recovery strategy can change.

Example:

```text
Normal:
Immediate retry

Degradation:
Delay retry
```

---

# 22. Recovery Opportunity Score

Create a prioritization score based on expected business value.

Conceptually:

```text
Recovery Opportunity Score
=
Expected Recovery Value
×
Intervention Efficiency
×
Business Priority
```

The exact formula should be determined experimentally.

The purpose is to answer:

> Which revenue recovery opportunity should receive attention first?

---

# 23. Recovery Prediction Model

The prediction model should estimate:

```text
P(recovery | context, action)
```

rather than only:

```text
P(recovery | context)
```

because the system needs to compare possible interventions.

Potential models:

* Logistic Regression
* Random Forest
* XGBoost
* LightGBM
* calibrated gradient boosting
* other suitable tabular ML models

Prefer interpretable, strong tabular methods over unnecessary deep learning.

---

# 24. Model Selection Rule

The implementation agent must inspect the actual dataset before selecting the model.

If the dataset is:

* small → simpler models may be better
* tabular → gradient boosting is likely appropriate
* heavily imbalanced → evaluate PR-AUC and class-specific metrics
* missing intervention outcomes → do not fabricate training labels

The model must be selected based on the data, not on what sounds most advanced.

---

# 25. LLM Role

The LLM is part of the reasoning and communication layer.

It should be responsible for:

* interpreting structured evidence
* generating explanations
* selecting among valid strategies when appropriate
* generating personalized communications
* generating Hinglish/multilingual messages
* summarizing recovery decisions

The LLM should NOT be responsible for:

* basic arithmetic
* state management
* arbitrary database updates
* generating unsupported facts
* bypassing policies
* directly executing financial actions

---

# 26. Recovery Agent

The Recovery Agent receives:

### Current Event

```text
event type
amount
timestamp
failure reason
```

### Customer Context

```text
payment history
failure history
recovery history
recent activity
customer value
```

### Revenue Context

```text
revenue at risk
expected recovery
priority
```

### Prediction Context

```text
candidate actions
predicted recovery probabilities
expected values
```

### Merchant Policy

```text
retry limits
allowed channels
recovery window
escalation rules
```

It produces a structured recovery decision.

Example:

```json
{
  "action": "DELAYED_RETRY",
  "confidence": 0.81,
  "reason": "The customer has historically recovered successfully after similar payment failures and has low intervention fatigue.",
  "expected_recovery_probability": 0.81,
  "expected_recovered_value": 4049.19,
  "recommended_delay_minutes": 30,
  "requires_human_review": false
}
```

---

# 27. Personalized Communication

Personalized messaging is a first-class recovery capability.

The recovery decision determines:

> Whether communication is appropriate.

The LLM determines:

> How the message should be expressed.

Context may include:

* customer name
* amount
* payment issue
* preferred language
* recovery action
* payment link
* merchant tone
* customer history

Example:

```text
Customer:
Rahul

Language:
Hinglish

Issue:
Subscription payment failed

Amount:
₹1,999

Action:
Payment-method update
```

Possible output:

> "Hi Rahul! Aapka ₹1,999 ka subscription payment complete nahi ho paya. Aap apna payment method update karke payment easily complete kar sakte hain."

The generated message must not contain unsupported claims.

---

# 28. Hinglish Voice Recovery Agent

Voice recovery is an advanced communication channel.

It should reuse the same recovery context as other channels.

Architecture:

```text
Recovery Decision
       │
       ▼
Communication Strategy
       │
       ├── SMS
       ├── Email
       ├── WhatsApp-style message
       └── Voice
              │
              ▼
       Hinglish Voice Agent
              │
              ▼
       Customer Interaction
              │
              ▼
          Outcome
```

The voice agent may:

* explain the payment issue
* guide the customer
* provide a payment link
* explain payment-method recovery
* answer simple recovery-related questions
* terminate the interaction when recovery is not possible

It must not invent payment status or perform unauthorized actions.

---

# 29. Communication Channel Selection

The system may eventually predict the best communication channel.

Example:

```text
SMS       → 32%
WhatsApp  → 51%
Voice     → 67%
Email     → 28%
```

If actual data supports these estimates, the system may choose voice.

The same decision engine should govern all communication channels.

---

# 30. Policy Engine

The Policy Engine is a mandatory safety layer.

The LLM must never directly execute financial actions.

Correct flow:

```text
Recovery Agent
      ↓
Action Proposal
      ↓
Policy Engine
      ↓
Approved / Rejected
      ↓
Execution
```

Policies may include:

* maximum retries
* minimum confidence
* maximum recovery window
* minimum retry interval
* allowed communication channels
* maximum automated interventions
* escalation threshold
* customer opt-out
* merchant-specific restrictions
* maximum discount/incentive

---

# 31. Example Merchant Policy

```json
{
  "max_payment_retries": 3,
  "minimum_confidence": 0.70,
  "retry_window_hours": 24,
  "minimum_retry_interval_minutes": 30,
  "max_automated_interventions": 3,
  "allow_discount": false,
  "human_escalation_after": 3
}
```

The actual values must be configurable.

---

# 32. Stopping Rules

The agent must explicitly determine when to stop.

Possible conditions:

* successful recovery
* maximum retry count reached
* recovery probability below threshold
* recovery window expired
* customer opted out
* subscription cancelled
* intervention fatigue too high
* merchant policy prohibits further action
* expected recovery value is lower than intervention cost
* repeated failures indicate low probability of success

The system must never run recovery loops indefinitely.

---

# 33. Recovery Actions

The action interface should support:

```text
IMMEDIATE_RETRY
DELAYED_RETRY
SEND_PAYMENT_REMINDER
SEND_PAYMENT_METHOD_UPDATE
SEND_CHECKOUT_RECOVERY
GENERATE_PAYMENT_LINK
SEND_PERSONALIZED_MESSAGE
START_VOICE_RECOVERY
ESCALATE_TO_HUMAN
WAIT
STOP
```

The action interface should remain extensible.

---

# 34. Outcome Processing

Every action must produce an outcome.

Example:

```text
PAYMENT_FAILED
      ↓
DELAYED_RETRY
      ↓
RECOVERY_ATTEMPT
      ↓
PAYMENT_SUCCESS
```

or:

```text
PAYMENT_FAILED
      ↓
DELAYED_RETRY
      ↓
RECOVERY_ATTEMPT
      ↓
PAYMENT_FAILED
      ↓
NEXT DECISION
```

Outcomes must update state.

---

# 35. Audit Trail

Every decision must be traceable.

Example:

```text
10:32:01
Event received
E007
Payment failure
₹4,999

10:32:02
Classified
PAYMENT_FAILED
Confidence: 96.2%

10:32:03
Customer context retrieved

10:32:03
Recovery propensity
81%

10:32:04
Candidate strategies evaluated

10:32:04
Delayed retry selected

10:32:04
Policy check
APPROVED

11:02:00
Recovery action executed

11:02:03
Payment recovered

11:02:03
Revenue recovered
₹4,999
```

Every important action must have a traceable ID.

---

# 36. Explainability

For every automated action, the system should be able to explain:

1. What happened?
2. What evidence was used?
3. What was predicted?
4. What alternatives were considered?
5. Why was the chosen action selected?
6. Was it permitted?
7. What happened afterward?

Example:

> Delayed retry was selected because the customer has a high historical payment success rate, previous similar failures were successfully recovered through retry, intervention fatigue is low, and the predicted recovery probability is 81%.

Every numerical statement must originate from actual computation.

---

# 37. Feedback Loop

Every recovery interaction produces a learning record.

Example:

```text
CONTEXT
Customer + event + history

ACTION
Delayed Retry

OUTCOME
Payment recovered

REWARD
₹4,999 - intervention cost
```

Or:

```text
CONTEXT
Customer + event + history

ACTION
Reminder

OUTCOME
No recovery

REWARD
Negative / zero depending on configured reward
```

Store:

```text
Context
Action
Outcome
Reward
Timestamp
Policy version
Model version
```

---

# 38. Reward Function

A basic reward function may be:

```text
Reward
=
Recovered Revenue
-
Intervention Cost
-
Customer Friction Penalty
-
Unnecessary Action Penalty
```

This is preferable to:

```text
Reward = Payment Successful ? 1 : 0
```

because the system should optimize business value, not merely conversion.

The exact reward function should be configurable and validated experimentally.

---

# 39. Learning Architecture

The project should evolve through multiple levels.

## Level 1 — Static Policy + ML

```text
Context
 ↓
Prediction
 ↓
Recovery Agent
 ↓
Policy
 ↓
Action
```

## Level 2 — Feedback-Based Retraining

```text
Action
 ↓
Outcome
 ↓
Feedback Dataset
 ↓
Model Retraining
 ↓
Improved Predictions
```

## Level 3 — Contextual Bandit

```text
Context
 ↓
Candidate Actions
 ↓
Choose Action
 ↓
Reward
 ↓
Update Action Policy
```

## Level 4 — Sequential Reinforcement Learning

```text
State
 ↓
Action
 ↓
New State
 ↓
Action
 ↓
New State
 ↓
Reward
```

---

# 40. Important RL Safety Principle

The learning system must NEVER directly rewrite hard financial safety constraints.

For example:

```text
Maximum retries = 3
```

must remain a hard policy.

RL may learn:

> Which of the allowed actions is most effective?

RL must not learn:

> "Ignore the retry limit."

Architecture:

```text
Learning System
      ↓
Policy Candidate
      ↓
Offline Evaluation
      ↓
Human / Safety Approval
      ↓
New Policy Version
```

Not:

```text
RL
 ↓
Directly modify live financial rules
```

---

# 41. Contextual Bandit Recommendation

Contextual bandits are a strong intermediate learning mechanism.

The system observes:

```text
Customer context
+
Event context
```

Then selects:

```text
Retry
Delayed Retry
Reminder
Payment Update
Voice
Escalation
```

It observes the resulting reward.

Over time, it learns which action works best for different contexts.

This is more appropriate as an early adaptive-learning architecture than immediately implementing full RL.

---

# 42. Sequential RL Future Direction

Full RL becomes meaningful when recovery consists of multiple actions.

Example:

```text
Payment Failed
      ↓
Wait
      ↓
Reminder
      ↓
Payment Update
      ↓
Retry
      ↓
Recovered
```

The system can learn:

> Which sequence of actions maximizes long-term net recovered revenue?

This is a future research direction unless the available dataset supports sequential learning.

---

# 43. Model Retraining

The initial system should prefer offline retraining.

Workflow:

```text
Historical Outcomes
        ↓
Training Dataset
        ↓
Model Training
        ↓
Validation
        ↓
Held-out Evaluation
        ↓
Candidate Model
        ↓
Approval
        ↓
Deployment
```

Avoid uncontrolled online model updates in the initial version.

---

# 44. Baselines

The proposed system must be compared against simpler strategies.

## Baseline 1

No recovery.

## Baseline 2

Naive retry.

```text
Every payment failure → retry
```

## Baseline 3

Rule-based recovery.

```text
Failure reason → predefined action
```

## Proposed System

```text
Context
+
Prediction
+
Recovery Agent
+
Policy Engine
```

The purpose is to prove that the additional intelligence creates measurable value.

---

# 45. Evaluation Dataset

Use a meaningful event batch.

Minimum demonstration target:

```text
1,000+ events
```

Preferably:

```text
5,000–10,000+
```

if practical.

The dataset should contain:

* successful events
* failed events
* recoverable events
* unrecoverable events
* multiple customers
* historical customer activity
* multiple event categories
* recovery outcomes

---

# 46. Temporal Dataset Split

For time-dependent prediction:

```text
Historical Training Period
          ↓
Validation Period
          ↓
Held-out Test Period
```

Within each period, maintain chronological order.

Never randomly mix future and historical information when doing temporal prediction.

---

# 47. Classifier Evaluation

If a learned classifier is used, measure:

* precision
* recall
* F1
* macro F1
* confusion matrix
* per-class performance

Accuracy alone is insufficient when classes are imbalanced.

---

# 48. Recovery Model Evaluation

Measure:

* prediction quality
* calibration
* PR-AUC where appropriate
* ROC-AUC where appropriate
* recovery rate
* revenue recovered
* expected vs actual recovery
* action effectiveness

The primary business question is:

> **Does better prediction lead to more useful recovered revenue?**

---

# 49. Business Metrics

The dashboard should track:

## Revenue at Risk

Total monetary value of actionable revenue loss.

## Expected Recovery

Predicted recoverable value.

## Actual Revenue Recovered

Revenue successfully recovered.

## Recovery Rate

```text
Recovered Revenue / Revenue at Risk
```

## Customer Recovery Rate

```text
Recovered Cases / Actionable Cases
```

## Intervention Success Rate

```text
Successful Interventions / Total Interventions
```

## Average Recovery Time

Time from revenue-loss event to successful recovery.

## Intervention Cost

Estimated cost of recovery actions.

## Net Recovery

```text
Recovered Revenue - Intervention Cost
```

## Recovery ROI

```text
Net Recovery / Intervention Cost
```

---

# 50. Dashboard

The primary dashboard should immediately communicate business impact.

## Revenue Overview

```text
Revenue at Risk
₹18.7L

Expected Recovery
₹11.2L

Recovered
₹7.86L

Recovery Rate
42%
```

## Event Distribution

```text
Payment Failures
Checkout Abandonments
Subscription Failures
Overdue Receivables
```

## Recovery Actions

```text
Delayed Retry
Payment Update
Reminder
Voice
Escalation
Stopped
```

## Performance

```text
Recovery Rate
Average Recovery Time
Net Revenue Recovered
Intervention Efficiency
```

---

# 51. Recovery Opportunity Queue

Rank opportunities according to Recovery Opportunity Score.

Example:

| Priority | Customer | Event           |  Amount | Recovery Probability | Expected Value | Action        |
| -------- | -------- | --------------- | ------: | -------------------: | -------------: | ------------- |
| High     | C103     | Payment Failure | ₹20,000 |                  42% |         ₹8,400 | Retry         |
| High     | C209     | Invoice Overdue | ₹50,000 |                  31% |        ₹15,500 | Escalate      |
| Medium   | C101     | Payment Failure |  ₹2,499 |                  81% |         ₹2,024 | Delayed Retry |

The exact numbers must be generated by the system.

---

# 52. Event Explorer

For every actionable event, show:

```text
Event ID
Customer
Amount
Event Type
Timestamp
Failure Reason

Customer History

Recovery Propensity

Revenue at Risk

Expected Recovery

Candidate Actions

Selected Action

Reason

Policy Result

Execution Result

Outcome

Audit Trail
```

This should be one of the strongest demo screens.

---

# 53. Customer Detail View

Display:

```text
Customer Profile
        │
        ├── Transaction History
        ├── Success Rate
        ├── Failure History
        ├── Recovery History
        ├── Recovery Propensity
        ├── Revenue Contribution
        ├── Revenue at Risk
        ├── Intervention History
        └── Current Recovery State
```

The interface should make the system's reasoning understandable.

---

# 54. Recovery Simulation

Provide a simulation mode.

Flow:

```text
Load Dataset
     ↓
Process Event
     ↓
Classify
     ↓
Update State
     ↓
Build Context
     ↓
Generate Features
     ↓
Predict
     ↓
Decide
     ↓
Policy Check
     ↓
Execute
     ↓
Generate Outcome
     ↓
Update State
     ↓
Process Next Event
```

The dashboard should show this process visibly.

---

# 55. Demonstration Event

A strong demo should show one event completely.

Example:

```text
EVENT #487

₹4,999 PAYMENT FAILED

        ↓

Classification:
PAYMENT_FAILURE

        ↓

Customer Context:
9 previous payments
7 successful
2 failed
2 previous recoveries

        ↓

Recovery Propensity:
81%

        ↓

Best Action:
Delayed Retry

        ↓

Expected Recovery:
₹4,049

        ↓

Policy:
APPROVED

        ↓

Action:
Retry after 30 minutes

        ↓

RESULT:
PAYMENT RECOVERED

        ↓

₹4,999 RECOVERED
```

Then demonstrate that the State Store has changed.

---

# 56. Chronological State Demonstration

The demo should optionally demonstrate learning from previous events.

Example:

```text
E004 PAYMENT_FAILED
        ↓
Delayed Retry
        ↓
RECOVERED
        ↓
STATE UPDATED

...

E007 PAYMENT_FAILED
        ↓
Context now includes E004 recovery
        ↓
Agent recognizes previous successful recovery
        ↓
Uses this evidence in its new decision
```

This demonstrates that the system is stateful.

---

# 57. Merchant Configuration

The merchant should be able to configure:

```text
Maximum retries
Retry interval
Recovery window
Minimum confidence
Allowed communication channels
Escalation threshold
Maximum automated interventions
Discount policy
Customer opt-out rules
```

These configurations must affect real system behavior.

---

# 58. Razorpay Integration

The system should use Razorpay test-mode capabilities where practical.

The integration should be isolated behind an adapter.

Conceptually:

```text
Recovery Action
      ↓
Execution Service
      ↓
Razorpay Adapter
      ↓
Razorpay Test APIs
```

A local simulation layer should also exist.

The system must never depend entirely on external APIs for the core demonstration.

---

# 59. Simulation Layer

Simulation is required where real API behavior cannot reproduce the complete recovery lifecycle.

Simulation must:

* be reproducible
* support deterministic seeds
* generate explicit outcomes
* record simulated actions
* clearly label simulated results

Never present simulated recovery as real financial activity.

---

# 60. API Failure Handling

If an API action fails:

```text
Action Requested
      ↓
API Failure
      ↓
Record Failure
      ↓
Do NOT mark recovered
      ↓
Retry / Escalate / Stop according to policy
```

---

# 61. LLM Failure Handling

If the LLM is unavailable:

* use deterministic safe fallback rules where appropriate
* otherwise stop or escalate
* never execute an undefined action

---

# 62. Low Confidence Handling

If the prediction or agent confidence is below the configured threshold:

```text
Low Confidence
      ↓
Do Not Automatically Execute
      ↓
Human Review / Stop
```

---

# 63. Missing Data Handling

If required context is missing:

```text
Missing Information
       ↓
Reduce Confidence
       ↓
Safe Fallback
       ↓
or Escalate
```

The system must never fill missing values with fabricated facts.

---

# 64. Data Integrity Rules

The implementation must NEVER:

* fabricate customer history
* fabricate transaction outcomes
* fabricate recovery outcomes
* claim an API action succeeded without confirmation
* use future information
* invent unsupported features
* invent unsupported model performance
* hard-code final business metrics
* present simulation results as real transactions
* silently discard failures
* allow an LLM to bypass policies

---

# 65. Observability

Track:

```text
Events Processed
Events Classified
Actionable Events
Recovery Opportunities
Actions Attempted
Actions Successful
Actions Blocked
Actions Failed
API Failures
LLM Failures
Average Model Confidence
Revenue at Risk
Expected Recovery
Recovered Revenue
Net Recovery
```

Every event should have a traceable ID.

Recommended relationship:

```text
event_id
    ↓
classification_id
    ↓
decision_id
    ↓
policy_check_id
    ↓
action_id
    ↓
outcome_id
```

---

# 66. Security

The system must:

* never expose API keys to the frontend
* use environment variables for secrets
* validate inputs
* validate LLM outputs
* enforce policies server-side
* separate test and production configurations
* use least-privilege credentials
* log financial actions
* prevent arbitrary LLM API calls

---

# 67. Logical System Components

The system should contain these logical modules:

```text
1. Event Ingestion
2. Event Classifier
3. State Management
4. Context Builder
5. Feature Engineering
6. Recovery Prediction
7. Recovery Agent
8. Policy Engine
9. Action Execution
10. Outcome Processor
11. Audit Service
12. Feedback Store
13. Learning System
14. Analytics/Evaluation
15. Dashboard
16. Communication Layer
17. Voice Recovery Layer
```

These do not have to be separate microservices.

A modular monolith is acceptable and may be preferable for the buildathon.

---

# 68. Recommended Technology Direction

The exact technology must be chosen after inspecting the actual dataset and integration requirements.

A practical starting point is:

## Frontend

* React
* Next.js
* TypeScript
* Tailwind CSS

## Backend

* Python
* FastAPI

## Data

* PostgreSQL
* Redis if required for caching/state

## ML

* Python
* pandas
* NumPy
* scikit-learn
* XGBoost or LightGBM

## LLM

* LLM API through an abstraction layer
* structured JSON output
* schema validation

## Visualization

* Recharts
* Plotly
* or another stable visualization library

## Integration

* Razorpay test-mode APIs
* webhook/event simulation where necessary

Avoid unnecessary infrastructure complexity.

---

# 69. LLM Output Contract

LLM output must be structured.

Example:

```json
{
  "action": "DELAYED_RETRY",
  "confidence": 0.81,
  "reason": "The customer has historically recovered successfully after similar payment failures.",
  "evidence": [
    "7 of 9 historical payments succeeded",
    "2 of 2 previous recovery attempts succeeded",
    "Current intervention count is below the configured threshold"
  ],
  "recommended_delay_minutes": 30,
  "requires_human_review": false
}
```

Backend validation is mandatory.

Natural-language output must never be directly interpreted as an executable financial command.

---

# 70. Separation of Responsibilities

## Classifier

> What happened?

## State Store

> What do we know?

## Context Builder

> What context matters?

## Feature Engine

> What useful signals can we derive?

## Prediction Model

> What is likely to happen under each action?

## Recovery Agent

> Which strategy should we use?

## Policy Engine

> Are we allowed to use it?

## Execution Layer

> Perform the approved action.

## Outcome Processor

> What happened?

## Feedback System

> What did we learn?

## Analytics

> Did the system create value?

---

# 71. Future Advanced Features

The architecture should allow future extensions.

## Customer Lifetime Value

Estimate long-term revenue exposure.

## Advanced Channel Selection

Predict SMS/email/WhatsApp/voice effectiveness.

## Dynamic Recovery Windows

Learn when interventions stop being useful.

## Merchant-Wide Degradation Detection

Detect payment-system-level problems.

## Contextual Bandits

Learn action effectiveness from feedback.

## Uplift Modeling

Estimate incremental benefit of an intervention versus no intervention.

## Sequential Reinforcement Learning

Optimize multi-step recovery sequences.

## Multi-Agent Architecture

Specialized agents:

```text
Recovery Orchestrator
       │
       ├── Payment Recovery Agent
       ├── Checkout Recovery Agent
       ├── Subscription Recovery Agent
       └── Receivables Agent
```

These should only be introduced when they provide actual value.

---

# 72. Development Strategy

## Phase 0 — Dataset Audit

Before writing the main application:

1. Inspect all available files.
2. Identify columns.
3. Determine event types.
4. Determine timestamp quality.
5. Identify customer identifiers.
6. Identify transaction identifiers.
7. Identify recovery outcomes.
8. Identify intervention history.
9. Identify missing data.
10. Determine which proposed predictions are actually learnable.

Produce a **Data Capability Report**.

Do not invent unavailable information.

---

# 73. Phase 1 — Data Foundation

Implement:

* schema
* normalization
* validation
* timestamp ordering
* entity identification
* event ingestion

---

# 74. Phase 2 — State Engine

Implement:

* customer state
* payment state
* subscription state
* invoice state
* recovery state

Verify chronological updates.

---

# 75. Phase 3 — Event Classification

Implement:

* event classification
* confidence
* unknown handling
* classifier evaluation

If the dataset already contains reliable event labels, use those labels for system routing and evaluate whether an ML classifier is genuinely useful rather than creating unnecessary complexity.

---

# 76. Phase 4 — Context Engine

Implement:

* historical context retrieval
* temporal feature generation
* customer history
* recovery history
* revenue context
* merchant policy context

Verify that future events are inaccessible during historical decisions.

---

# 77. Phase 5 — Predictive Intelligence

Implement:

* recovery propensity
* expected recovery
* action-specific prediction
* opportunity scoring
* timing prediction where supported

Evaluate against held-out data.

---

# 78. Phase 6 — Recovery Agent

Implement:

* structured context
* candidate strategies
* decision generation
* explanation
* structured output
* LLM fallback

---

# 79. Phase 7 — Policy Engine

Implement:

* retry limits
* confidence thresholds
* recovery windows
* intervention limits
* escalation
* stopping rules

Verify that policies cannot be bypassed by the LLM.

---

# 80. Phase 8 — Execution

Implement:

* simulation mode
* Razorpay test-mode adapter
* action logging
* API failure handling

---

# 81. Phase 9 — Outcome Engine

Implement:

* recovery success
* recovery failure
* action outcome
* state update
* revenue calculations
* audit trail

---

# 82. Phase 10 — Feedback System

Implement:

```text
Context
+
Action
+
Outcome
+
Reward
```

Store every learning event.

---

# 83. Phase 11 — Dashboard

Implement:

* revenue overview
* recovery queue
* event explorer
* customer view
* audit trail
* simulation mode
* model metrics
* recovery analytics
* learning analytics

---

# 84. Phase 12 — Evaluation

Run:

* baseline comparison
* held-out test
* temporal evaluation
* recovery evaluation
* revenue evaluation
* failure scenarios
* policy tests

---

# 85. Phase 13 — Advanced Learning

Only after the previous system is reliable:

1. Offline model retraining
2. Contextual bandit experimentation
3. Policy candidate generation
4. Offline policy evaluation
5. Human approval
6. Policy versioning
7. Sequential RL research

---

# 86. Final Non-Negotiable Rules for the Implementation Agent

The implementation agent must follow these rules throughout development.

### Rule 1

Inspect the actual dataset before designing assumptions.

### Rule 2

Never invent unavailable fields.

### Rule 3

Never fabricate outcomes.

### Rule 4

Never use future information for past decisions.

### Rule 5

Successful events must be retained as historical context.

### Rule 6

State must be updated chronologically.

### Rule 7

The LLM must not directly execute financial actions.

### Rule 8

All financial actions must pass through the Policy Engine.

### Rule 9

Every action must have an audit trail.

### Rule 10

Every recovery result must be backed by an actual outcome or explicitly labeled simulation.

### Rule 11

Numerical predictions must come from actual models/calculations.

### Rule 12

If data does not support a prediction, report it as unavailable.

### Rule 13

Do not fabricate model metrics.

### Rule 14

Do not hard-code final recovery metrics.

### Rule 15

Do not use complex ML/RL merely for appearance.

### Rule 16

Do not introduce microservices unless they provide a clear benefit.

### Rule 17

Safety constraints are hard constraints and cannot be learned away.

### Rule 18

Online self-modification of financial policies is prohibited in the initial system.

### Rule 19

All learning experiments must be reproducible.

### Rule 20

The primary business objective is **net useful revenue recovered**, not number of actions taken.

---

# 87. Final Product Flow

The complete system should behave like this:

```text
                 SOMETHING HAPPENED
                         │
                         ▼
                  WHAT HAPPENED?
                    CLASSIFIER
                         │
                         ▼
                  WHAT DO WE KNOW?
                  STATE + CONTEXT
                         │
                         ▼
                  WHAT IS LIKELY?
                  ML PREDICTION
                         │
                         ▼
                  WHAT SHOULD WE DO?
                  RECOVERY AGENT
                         │
                         ▼
                  ARE WE ALLOWED?
                  POLICY ENGINE
                         │
                         ▼
                       ACTION
                         │
                         ▼
                  DID IT WORK?
                    OUTCOME
                         │
                         ▼
                  UPDATE STATE
                         │
                         ▼
                  CALCULATE REWARD
                         │
                         ▼
                   LEARN FROM IT
                         │
                         └──────────────► NEXT EVENT
```

---

# 88. Final Product Definition

> **The Revenue Recovery Intelligence Engine is an event-driven AI system that continuously processes merchant revenue events, identifies recoverable revenue loss, maintains chronological customer and transaction state, derives meaningful business signals, predicts the effectiveness of possible interventions, selects the most valuable safe recovery strategy, communicates or executes the intervention through approved channels, observes the outcome, measures actual revenue recovered, and learns from historical outcomes to improve future recovery decisions.**

The system combines:

**Event Intelligence + Temporal State + ML Prediction + AI Reasoning + Policy-Controlled Agents + Personalized Communication + Voice Recovery + Outcome Measurement + Feedback Learning**

while maintaining strict financial safety, temporal correctness, explainability, and reproducibility.

---

# 89. Core Design Philosophy

The system must always follow:

```text
DATA
 ↓
CONTEXT
 ↓
PREDICTION
 ↓
DECISION
 ↓
POLICY
 ↓
ACTION
 ↓
OUTCOME
 ↓
FEEDBACK
 ↓
LEARNING
```

It must never become:

```text
DATA
 ↓
LLM
 ↓
MAGIC
```

The LLM is one component of the intelligence layer.

The product's intelligence comes from the combination of:

* real event data
* chronological state
* meaningful feature engineering
* predictive models
* agent reasoning
* deterministic policy enforcement
* actual outcomes
* measurable rewards
* continuous evaluation

---

# 90. North-Star Metric

The ultimate product metric is:

# **Net Revenue Recovered**

Not:

* number of events processed
* number of AI decisions
* number of messages sent
* number of retries
* LLM calls
* model accuracy alone

The system succeeds when it can demonstrate:

> **More revenue recovered, with fewer unnecessary interventions, under safe and explainable policies.**
