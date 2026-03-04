# L2 Technical Support Procedures

## Escalation to L3 Policy

### When to escalate to L3
Escalate to L3 when:
- Data corruption or loss is confirmed or suspected
- The issue affects more than 10 customers simultaneously (potential incident)
- A bug has been identified in production code
- Database queries are timing out or returning incorrect results
- Security vulnerability is suspected
- Infrastructure is degraded (high latency, error rate above 1%)

### How to escalate
1. Open an incident ticket with full reproduction steps
2. Attach relevant logs from the logging dashboard
3. Page L3 via PagerDuty if severity is P1 or P2
4. For P3/P4, create a Jira ticket and assign to the on-call L3 engineer

## Diagnostic Procedures

### API error investigation
1. Pull customer API logs from the logging dashboard (filter by customer_id)
2. Check rate limiting status — customers on Free plan are limited to 100 req/min
3. Verify API key is active and has correct permissions
4. Check for known issues in the internal status page

### Webhook failure investigation
1. Check webhook delivery logs in admin panel
2. Verify customer endpoint is reachable (run connectivity test)
3. Check SSL certificate validity on customer endpoint
4. Review payload format — breaking changes are documented in the changelog

### Data sync issues
1. Check the sync queue status for the customer's workspace
2. Look for failed jobs in the background job dashboard
3. If jobs are stuck, manually re-queue from admin panel

### Data integrity issues
1. If data is inconsistent, do NOT attempt manual fixes — escalate to L3