# L3 Engineering Runbooks

## Database Recovery Procedures

### Corrupted records
1. STOP — do not attempt fixes without a snapshot. Take an RDS snapshot immediately.
2. Identify affected records using the audit log table
3. Check if corruption is isolated or spreading (run integrity check script)
4. If isolated: restore specific records from the point-in-time backup
5. If spreading: initiate full rollback procedure (see below)
6. Post-mortem required for all data corruption incidents

### Full rollback procedure
1. Notify stakeholders via incident channel
2. Put application in maintenance mode (run: `kubectl set env deployment/app MAINTENANCE=true`)
3. Restore from last known good snapshot
4. Run data integrity validation script
5. Remove maintenance mode
6. Verify with L2 that affected customers' data is intact

## Production Incident Response

### P1 — Service down
Response time: 15 minutes
1. Page all on-call engineers
2. Open war room in #incidents-p1
3. Check infrastructure dashboard for root cause
4. If database: follow database recovery procedures
5. If application: roll back last deployment (`kubectl rollout undo deployment/app`)
6. If infrastructure: escalate to DevOps

### P2 — Degraded performance
Response time: 1 hour
1. Identify degraded service from metrics dashboard
2. Check recent deployments and config changes
3. Scale up affected service if resource-constrained
4. Monitor for 30 minutes after fix

## Architecture Notes

### Data layer
Primary database: PostgreSQL 15 on RDS. Read replicas in eu-west-1 and us-east-1.
Cache: Redis cluster, 3 nodes. TTL 300s for user sessions, 60s for API responses.

### Known fragile points
- The sync worker has a memory leak under sustained load above 500 concurrent jobs. Restart the worker pod if memory exceeds 2GB.
- The webhook delivery system retries up to 3 times with exponential backoff. After 3 failures it dead-letters. Check the dead letter queue daily.
