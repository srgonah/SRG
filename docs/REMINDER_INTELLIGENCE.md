# Reminder Intelligence

Smart, on-demand insight evaluation that detects conditions across the system and optionally creates derived reminders.

## Overview

Reminder Intelligence upgrades the reminder system from static dates to intelligent alerts. Three rules evaluate system state and return **insights** -- detected conditions that can optionally become derived reminders.

There is no background scheduler. Evaluation happens when the API endpoint is called.

## Architecture

```
Insight (entity)
    |
ReminderIntelligenceService (core service)
    |
EvaluateReminderInsightsUseCase (application)
    |
GET /api/reminders/insights (API route)
```

- **Insight entity** (`src/core/entities/insight.py`) -- pure Pydantic model, not persisted
- **ReminderIntelligenceService** (`src/core/services/reminder_intelligence.py`) -- layer-pure, depends only on core interfaces
- **EvaluateReminderInsightsUseCase** (`src/application/use_cases/evaluate_reminder_insights.py`) -- orchestrates service + optional reminder creation
- **API endpoint** (`src/api/routes/reminders.py`) -- `GET /api/reminders/insights`

## Insight Rules

### 1. Expiring Documents

Checks `ICompanyDocumentStore.list_expiring()` for documents nearing expiry.

- **Category**: `expiring_document`
- **Severity**: `CRITICAL` if <= 7 days, `WARNING` otherwise
- **Linked entity**: `company_document` with document ID

### 2. Unmatched Items

Checks `IInvoiceStore.list_unmatched_items()` for invoice line items with no matched material.

- **Category**: `unmatched_item`
- **Severity**: `INFO`
- **Deduplication**: By normalized (lowercased) item name
- **Linked entity**: `invoice_item` with item ID

### 3. Price Anomalies

Checks recent items via `IInvoiceStore.get_items_for_indexing()` and compares against `IPriceHistoryStore.get_price_stats()`.

- **Category**: `price_anomaly`
- **Severity**: `WARNING`
- **Threshold**: >20% deviation from historical average
- **Minimum data**: >= 2 historical records and positive average price
- **Linked entity**: `invoice_item` with item ID

## API Endpoint

```
GET /api/reminders/insights?expiry_days=30&auto_create=false
```

### Query Parameters

| Parameter     | Type | Default | Description                                    |
|---------------|------|---------|------------------------------------------------|
| `expiry_days` | int  | 30      | Days ahead to check for expiring documents     |
| `auto_create` | bool | false   | Create derived reminders for each insight       |

### Example Response

```json
{
  "total_insights": 3,
  "expiring_documents": 1,
  "unmatched_items": 1,
  "price_anomalies": 1,
  "insights": [
    {
      "category": "expiring_document",
      "severity": "critical",
      "title": "Expiring: Trade License",
      "message": "Trade License expires on 2026-02-15 (5 days remaining)",
      "suggested_due_date": "2026-02-15",
      "linked_entity_type": "company_document",
      "linked_entity_id": 42,
      "details": {"days_left": 5, "document_type": "license"}
    },
    {
      "category": "unmatched_item",
      "severity": "info",
      "title": "Unmatched item: Widget X",
      "message": "Item 'Widget X' has no matched material in the catalog",
      "linked_entity_type": "invoice_item",
      "linked_entity_id": 101,
      "details": {"item_name": "Widget X"}
    },
    {
      "category": "price_anomaly",
      "severity": "warning",
      "title": "Price anomaly: Steel Rod",
      "message": "'Steel Rod' priced at 125.0 deviates 25.0% from average 100.0",
      "linked_entity_type": "invoice_item",
      "linked_entity_id": 55,
      "details": {"unit_price": 125.0, "avg_price": 100.0, "deviation_pct": 25.0}
    }
  ],
  "reminders_created": 0,
  "created_reminder_ids": []
}
```

## Derived Reminders

When `auto_create=true`, the use case creates a reminder for each insight that does not already have an active (not done) reminder.

Derived reminders use `linked_entity_type` with an `insight:` prefix:

| Insight Category    | Reminder `linked_entity_type` |
|---------------------|-------------------------------|
| `expiring_document` | `insight:expiring_doc`        |
| `unmatched_item`    | `insight:unmatched_item`      |
| `price_anomaly`     | `insight:price_anomaly`       |

The `linked_entity_id` matches the insight's linked entity ID. Duplicate detection uses `find_by_linked_entity()` to avoid creating multiple reminders for the same condition.
