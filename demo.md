`	ext
﻿
========================================================================
  REVENUE RECOVERY INTELLIGENCE ENGINE -- LIVE DEMO
========================================================================

  This demo simulates a customer's journey through the full pipeline:
  1. Webhook Event Ingestion & Normalization
  2. Chronological State Store (rolling customer metrics)
  3. Temporal Context Builder (zero future leakage)
  4. Feature Engineering (20-dim vector)
  5. Degradation Detection (systemic vs customer failure)
  6. ML Prediction (P(recovery|action) for 9 actions)
  7. Opportunity Scoring & Priority Ranking

  [OK] Fresh SQLite database initialized


-- STAGE 1: Event Ingestion & Normalization ---------------

  Simulating 3 Razorpay webhook events for customer Priya Sharma:

    [OK]  Event 1: PAYMENT_SUCCESS
        event_id: evt_pay_success_001
        amount: Rs.2,499.00
        method: upi
        failure: UNKNOWN
        timestamp: 2026-08-31 10:00 IST

    [OK]  Event 2: PAYMENT_SUCCESS
        event_id: evt_pay_success_002
        amount: Rs.1,299.00
        method: card
        failure: UNKNOWN
        timestamp: 2026-09-03 10:00 IST

    [FAIL]  Event 3: PAYMENT_FAILED
        event_id: evt_pay_fail_001
        amount: Rs.4,999.00
        method: upi
        failure: TRANSIENT_BANK_TIMEOUT
        timestamp: 2026-09-07 10:00 IST


-- STAGE 2: Chronological State Store ---------------------

  Rolling metrics computed from all events up to the failure:

  customer_id: cust_priya_sharma
  total_transactions: 3
  successful_transactions: 2
  failed_transactions: 1
  success_rate: 66.7%
  total_revenue: Rs.3,798.00
  consecutive_failures: 1
  intervention_fatigue: 0.15
  historical_recovery_rate: 0.00

-- STAGE 3: Temporal Decision Context (Zero Leakage) ------

  Building context for the failed payment event:

2026-08-31 23:09:52 [debug    ] Decision context built successfully as_of=2026-09-07T10:00:00+05:30 context_id=ctx_4cac9a4a96cc customer_id=cust_priya_sharma
  context_id: ctx_4cac9a4a96cc
  as_of_timestamp: 2026-09-07 10:00 IST
  revenue_at_risk: Rs.4,999.00
  is_degraded: False

    Customer Profile:
      name: Valued Customer
      is_vip: False
      lifetime_value: Rs.5,697.00

    Current Event:
      type: PAYMENT_FAILED
      failure_category: TRANSIENT_BANK_TIMEOUT
      amount: Rs.4,999.00

-- STAGE 4: Feature Engineering (20-Dimensional Vector) ---

2026-08-31 23:09:52 [debug    ] Decision context built successfully as_of=2026-09-07T10:00:00+05:30 context_id=ctx_a2e30c2d6bea customer_id=cust_priya_sharma
  Named Features:

    amount_to_avg_ratio.....................     2.6324  ##########
    attempt_count...........................     1.0000  ####
    average_transaction_value...............  1899.0000  ##################
    consecutive_failures_count..............     1.0000  ####
    day_of_week.............................     0.0000  #
    estimated_clv_at_risk................... 10696.0000  ########################################
    failure_category_code...................     1.0000  ####
    historical_recovery_rate................     0.0000  #
    historical_success_rate.................     0.6667  ##
    hour_of_day.............................    10.0000  ########################################
    intervention_fatigue_score..............     0.1500  #
    is_merchant_system_degraded.............     0.0000  #
    is_opted_out............................     0.0000  #
    is_vip_customer.........................     0.0000  #
    payment_method_code.....................     1.0000  ####
    recent_intervention_count...............     0.0000  #
    revenue_at_risk.........................  4999.0000  ########################################
    total_recovery_attempts.................     0.0000  #
    total_revenue_generated.................  3798.0000  #####################################
    total_transactions......................     3.0000  ############

  NumPy Vector Shape: (20,)
  Vector (first 10):  [6.667e-01 3.000e+00 3.798e+03 1.899e+03 0.000e+00 0.000e+00 1.000e+00
 1.500e-01 0.000e+00 4.999e+03]

-- STAGE 5: Merchant System Degradation Detection ---------

2026-08-31 23:09:52 [debug    ] Decision context built successfully as_of=2026-09-07T10:00:00+05:30 context_id=ctx_8022b6f5deca customer_id=cust_priya_sharma
  [OK]  No systemic degradation detected
  Failure appears to be customer/bank-specific, not merchant-wide.

-- STAGE 6: ML Recovery Predictions -- P(recovery | action) -

2026-08-31 23:09:52 [debug    ] Decision context built successfully as_of=2026-09-07T10:00:00+05:30 context_id=ctx_68531d5358e9 customer_id=cust_priya_sharma
  prediction_id: pred_31d5629a0b2b
  model_version: v1.0.0-calibrated-gbm
  overall_propensity: 58.80%
  optimal_delay: 30 minutes

  Action-by-Action Predictions:

    ACTION                              P(rec)     E[V] Rs.     Cost Rs.   Net E[V]    
    -------------------------------------------------------------------------------
  * DELAYED_RETRY                       79.38%   Rs. 3,968.21  Rs.   0.00  Rs. 3,968.21
    SEND_PERSONALIZED_MESSAGE           67.62%   Rs. 3,380.32  Rs.   0.50  Rs. 3,379.82
    IMMEDIATE_RETRY                     64.68%   Rs. 3,233.35  Rs.   0.00  Rs. 3,233.35
    SEND_PAYMENT_REMINDER               58.80%   Rs. 2,939.41  Rs.   0.20  Rs. 2,939.21
    GENERATE_PAYMENT_LINK               58.80%   Rs. 2,939.41  Rs.   0.40  Rs. 2,939.01
    SEND_PAYMENT_METHOD_UPDATE          47.04%   Rs. 2,351.53  Rs.   0.40  Rs. 2,351.13
    START_VOICE_RECOVERY                47.04%   Rs. 2,351.53  Rs.   2.50  Rs. 2,349.03
    ESCALATE_TO_HUMAN                   35.28%   Rs. 1,763.65  Rs.  15.00  Rs. 1,748.65
    SEND_CHECKOUT_RECOVERY              29.40%   Rs. 1,469.71  Rs.   0.40  Rs. 1,469.31

  * = Best candidate action: DELAYED_RETRY
    Best Net Expected Value: Rs.3,968.21

-- STAGE 7: Opportunity Scoring & Priority Ranking --------

2026-08-31 23:09:52 [debug    ] Decision context built successfully as_of=2026-09-07T10:00:00+05:30 context_id=ctx_38d3c19afb40 customer_id=cust_priya_sharma
  opportunity_id: opp_ctx_38d3c19afb40
  customer: Valued Customer (cust_priya_sharma)
  event_type: PAYMENT_FAILED
  amount_at_risk: Rs.4,999.00
  recovery_propensity: 58.80%
  expected_recovery: Rs.3,968.21
  recommended_action: DELAYED_RETRY
  opportunity_score: 3,730.12

      +------------------------------+
    |  PRIORITY:        HIGH        |
    +------------------------------+

-- BONUS: Timing Optimizer -- Optimal Delay per Failure Type -

2026-08-31 23:09:52 [debug    ] Decision context built successfully as_of=2026-08-31T17:39:52.377419+00:00 context_id=ctx_566c6cd6d224 customer_id=cust_timing_test
    Transient Bank Timeout         -> 30 min
2026-08-31 23:09:52 [debug    ] Decision context built successfully as_of=2026-08-31T17:39:52.384648+00:00 context_id=ctx_47c18c3d88ed customer_id=cust_timing_test
    Insufficient Funds             -> 12h 0m
2026-08-31 23:09:52 [debug    ] Decision context built successfully as_of=2026-08-31T17:39:52.386584+00:00 context_id=ctx_9750db629a15 customer_id=cust_timing_test
    Expired/Blocked Card           -> 0 min
2026-08-31 23:09:52 [debug    ] Decision context built successfully as_of=2026-08-31T17:39:52.387497+00:00 context_id=ctx_bc8c5b994d10 customer_id=cust_timing_test
    Checkout Abandonment           -> 45 min
2026-08-31 23:09:52 [debug    ] Decision context built successfully as_of=2026-08-31T17:39:52.388520+00:00 context_id=ctx_08331eb994dc customer_id=cust_timing_test
    Mandate Rejected               -> 0 min

========================================================================
  DEMO COMPLETE
========================================================================

  All 5 completed phases working end-to-end.
  Next: Phase 6 -- Multi-Agent Recovery Layer (4 Specialized Agents)


`