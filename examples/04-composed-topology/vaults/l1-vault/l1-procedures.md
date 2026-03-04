# L1 Support Procedures

## Escalation Policy

### When to escalate to L2
Escalate to L2 when:
- The issue involves API errors, webhook failures, or integration problems
- The customer reports data inconsistencies or missing records
- The issue has been open for more than 2 hours without resolution
- The customer is on an Enterprise plan (always escalate to L2 first)
- You cannot reproduce the issue using standard troubleshooting steps

### When to escalate to L3
Never escalate directly to L3. All escalations go through L2 first.

## Common Issue Scripts

### Password reset not received
1. Ask customer to check spam folder
2. Verify email address is correct in the system
3. Trigger a new reset email from admin panel
4. If still not received after 10 minutes, escalate to L2 (mail delivery issue)

### Billing charge dispute
1. Pull up the customer's billing history
2. Confirm the charge date and amount
3. If charge is within 30-day window, process refund immediately
4. If outside 30-day window, escalate to billing team

### Cannot log in
1. Verify account exists and is active
2. Check for account lockout (5 failed attempts triggers 30-minute lockout)
3. Manually unlock account from admin panel if locked
4. If account is active and not locked, escalate to L2