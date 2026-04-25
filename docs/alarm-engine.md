# Alarm Engine Deep-Dive

The Alarm Engine is the reactive component of Manifold that monitors financial data and triggers notifications when specific conditions are met.

## Alarm Definition Model

An alarm consists of several key components:
- **Condition Tree**: A JSON-based Abstract Syntax Tree (AST) representing the logical rule.
- **Context**: The scope of the alarm (e.g., a specific account, all accounts, or a sync run).
- **Thresholds**: Duration-based rules (e.g., "fire if condition is true for 10 minutes").
- **Cooldown**: Minimum time between firing events to prevent notification storms.

## Condition Expression Tree

Manifold uses a structured JSON format for conditions to ensure safe evaluation and easy UI integration.

### Structure
```json
{
  "operator": "AND",
  "conditions": [
    {
      "field": "account.balance",
      "operator": "<",
      "value": 100
    },
    {
      "field": "account.currency",
      "operator": "==",
      "value": "GBP"
    }
  ]
}
```

### Supported Operators
- **Comparison**: `==`, `!=`, `<`, `<=`, `>`, `>=`
- **Logical**: `AND`, `OR`, `NOT`
- **Collection**: `IN`, `NOT IN`, `CONTAINS`

## Evaluation Context

When an alarm is evaluated, it is provided with a "context" containing real-time data:

| Field Path | Description |
| :--- | :--- |
| `account.balance` | Current balance of the target account. |
| `account.available` | Available balance (including overdraft). |
| `transaction.amount` | Amount of the most recent transaction. |
| `transaction.description` | Description/Merchant of the most recent transaction. |
| `sync_run.status` | Status of the last synchronization (`success`, `failed`). |
| `sync_run.error_code` | Error code if the last sync failed. |
| `connection.status` | Status of the provider connection (`linked`, `error`). |

## State Machine

Alarms follow a strict state machine to manage their lifecycle:

```text
       ┌────────┐          Condition True          ┌───────────┐
       │   OK   │─────────────────────────────────▶│  PENDING  │
       └────────┘                                  └─────┬─────┘
           ▲                                             │
           │           Condition False                   │ Duration Met
           │          (before duration)                  │
           └─────────────────────────────────────────────┘
                                                         │
       ┌────────┐          Condition False         ┌─────▼─────┐
       │RESOLVED│◀─────────────────────────────────│  FIRING   │
       └────────┘                                  └─────┬─────┘
           │                                             │
           │           After Cooldown                    │ User Actions
           └──────────────────┬──────────────────────────┤
                              │                    ┌─────▼─────┐
                              ▼                    │   MUTED   │
                           ┌────┐                  └───────────┘
                           │ OK │
                           └────┘
```

- **OK**: Condition is false.
- **PENDING**: Condition is true, but the `for_duration` threshold hasn't been reached.
- **FIRING**: Condition has been true for the required duration. A notification is sent.
- **RESOLVED**: Condition was true but has now returned to false.
- **MUTED**: The user has silenced the alarm.

## Repeat and Cooldown Semantics

- **Repeat Count**: How many times a notification should be sent if the condition remains true.
- **Repeat Interval**: How often to re-notify (e.g., every 24 hours).
- **Cooldown**: The mandatory "quiet period" after an alarm is resolved before it can fire again.

## Alarm Versioning

To ensure auditability, Manifold maintains a history of alarm conditions. When you edit an alarm, a new version is created. This allows you to see exactly what rule was in effect when a specific notification was triggered in the past.

## Latency Expectations

The time between a financial event (e.g., a purchase) and an alarm firing depends on several factors:

| Phase | Duration |
| :--- | :--- |
| **Bank Latency** | Seconds to Hours (depends on bank/TrueLayer). |
| **Sync Interval** | 1 minute to 24 hours (user-configured). |
| **Evaluation** | < 1 second (triggered immediately after sync). |
| **Notification** | 1-5 seconds (depends on SMTP/Slack/Telegram). |

## Example Alarms

### Low Balance
- **Condition**: `account.balance < 50`
- **Purpose**: Notify when an account is running low on funds.

### Sync Failure
- **Condition**: `sync_run.status == "failed" AND sync_run.error_code != "interrupted"`
- **Purpose**: Detect issues with provider connections.

### Large Purchase
- **Condition**: `transaction.amount > 1000`
- **Purpose**: Monitor for significant spending.

## Advanced Alarm Patterns

### Composite Logic
By nesting `AND` and `OR` operators, you can create highly specific rules:
```json
{
  "operator": "AND",
  "conditions": [
    {
      "operator": "OR",
      "conditions": [
        { "field": "account.type", "operator": "==", "value": "savings" },
        { "field": "account.type", "operator": "==", "value": "investment" }
      ]
    },
    { "field": "account.balance", "operator": "<", "value": 1000 }
  ]
}
```
This pattern allows you to monitor groups of accounts (e.g., all "Liquid Assets") with a single alarm.

### Temporal Conditions (for_duration)
The `for_duration` field prevents alerts for transient states. For example, if your balance dips below a threshold only for a few minutes due to pending transactions, you can set `for_duration: "1h"` to only notify if it stays low for a full hour. This is essential for reducing noise in high-frequency accounts.

### Detection of Missing Events
Alarms can be configured to fire when something *doesn't* happen:
- **Rule**: `sync_run.status != "success"` with `for_duration: "24h"`
- **Effect**: Alerts you if the system hasn't successfully synced data in the last day, indicating a potential connection or infrastructure issue.

## Scaling Alarm Evaluation

The Alarm Engine is designed to scale with your financial history:
- **Incremental Evaluation**: Most alarms only evaluate against the "Newest" data point, keeping the calculation cost low.
- **Indexing**: Database columns used frequently in alarms (like `balance` and `status`) are indexed to ensure sub-millisecond query times.
- **Batched Execution**: When a sync run finishes, the system evaluates all alarms for that user in a single background transaction, minimizing database overhead.

## Troubleshooting Alarms

If an alarm isn't firing as expected, check the following in the Manifold dashboard:
- **Evaluation Log**: A detailed trace of the last 10 evaluation attempts, showing the values extracted from the context and the result of each logical branch.
- **Context Preview**: See exactly what data the engine sees for a specific account or transaction.
- **State Audit**: Review the transition history (e.g., why an alarm stayed in `PENDING` instead of moving to `FIRING`).
