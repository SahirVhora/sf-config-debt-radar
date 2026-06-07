# Evidence data folder

Use this folder for client-approved, zero-employee-data extracts that support areas not fully proven by OData `$metadata`.

The browser app can read `$metadata` for schema signals, entity names, fields, navigation properties, and custom-field concentration. It cannot prove usage, ownership, runtime volume, role overlap, or workflow aging without separate extracts.

Recommended files:

| File | Area | Source | Minimum columns |
|---|---|---|---|
| `business-rules.csv` | Business Rules | Admin Center > Configure Business Rules, Integration Center, or API extract if enabled | rule_id, rule_name, base_object, trigger, target_field, active, owner, last_modified |
| `rbp-matrix.csv` | RBP | Admin Center > Manage Permission Roles / Groups, RBP API, or Integration Center if enabled | role_name, permission_block, permission, target_population, group_name, user_count, last_reviewed |
| `workflows.csv` | Workflows | Workflow config export and workflow request extract | workflow_id, object, approver_path, escalation, fallback_approver, pending_count, max_age_days |
| `event-reasons.csv` | Event Reasons | Manage Organization, Pay and Job Structures plus EmpJob counts by eventReason | event_reason, status, employee_status, usage_count, last_used |
| `foundation-objects.csv` | Foundation Objects | Foundation Object export or OData counts | object_type, code, active, parent, record_count, last_modified |
| `custom-fields.csv` | Custom Fields | `$metadata` plus usage analysis from reports/integrations/counts | object, field, label, visible, populated_count, report_usage, integration_dependency, owner |
| `picklists.csv` | Picklists | Picklist Center or OData Picklist/PicklistOption | picklist, option_id, label, status, parent, translation_count, usage_count |
| `mdf-objects.csv` | MDF Objects | Configure Object Definitions and OData counts | object, effective_dated, api_visible, secured, owner, record_count |
| `integrations.csv` | Integrations | Integration Center, Scheduled Job Manager, API audit, middleware catalogue | interface, object, fields, direction, consumer, schedule, last_run, owner |
| `reports.csv` | Reports | Report Center inventory | report_name, report_type, owner, last_run, field_list, audience |

Rules:
- Do not store employee records, names, emails, payroll values, or exported tenant data.
- Use counts, schema, ownership, status, and dependency fields only.
- Keep client extracts anonymised before committing.
- Put repeatable sample templates here, not credentials.
