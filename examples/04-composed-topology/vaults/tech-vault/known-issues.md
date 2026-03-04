# Known Issues and Workarounds

## Active Issues

### ISSUE-2891: Webhook timeout on large payloads
**Status:** In progress (L3 investigating)
**Affected:** Customers with payloads > 1MB
**Workaround:** Ask customer to enable payload chunking in integration settings. This splits large payloads into multiple smaller requests.
**ETA:** Fix scheduled for next release (v2.4.1)

### ISSUE-2934: GitHub integration fails on private repos with SSO
**Status:** Confirmed bug
**Affected:** Enterprise customers using GitHub Enterprise with SAML SSO
**Workaround:** Customer must add the integration as an authorized OAuth app in their GitHub organization SSO settings. Detailed steps in the GitHub integration guide.
**ETA:** No ETA — awaiting GitHub API change

### ISSUE-2956: Export stalls for workspaces with > 100k records
**Status:** Known limitation
**Affected:** Large Enterprise customers
**Workaround:** Use the API to export in batches using pagination. Provide customer with the batch export script from the internal tools repo.
**ETA:** Architectural fix planned for Q3

## Recently Resolved

### ISSUE-2801: Slack notifications duplicated after reconnect
**Resolved:** v2.4.0
**Root cause:** Race condition in the notification service during OAuth token refresh.
**Note:** Customers must disconnect and reconnect the Slack integration to clear the duplicate state.

## Internal Debugging Tools

### Log access
Production logs: logs.internal.example.com (requires VPN)
Filter by customer: `customer_id:12345`
Filter by error: `level:error service:api`

### Admin panel
admin.internal.example.com — L2 and above
Capabilities: user lookup, billing history, manual refunds, account unlock, re-queue jobs

### Metrics dashboard
metrics.internal.example.com
Key dashboards: API latency, error rates, sync queue depth, webhook delivery rate
