# RB-10: TLS certificate expiring or expired

Applies to: certificate expiry alerts, browsers showing NET::ERR_CERT_DATE_INVALID, failed API clients.

## Symptoms
- DaysToExpiry alarm (ACM), blackbox exporter probe_ssl_earliest_cert_expiry, user reports.

## Likely causes
- Auto-renewal failed: DNS validation record removed, HTTP-01 challenge blocked, cert-manager misconfigured.
- Manually uploaded certificate nobody owns.

## Diagnose
1. `echo | openssl s_client -connect host:443 -servername host 2>/dev/null | openssl x509 -noout -dates -issuer`
2. ACM: `aws acm describe-certificate --certificate-arn <arn>` - RenewalSummary and validation status.
3. cert-manager: `kubectl describe certificate <name>`.

## Mitigate
- Restore the DNS validation CNAME; re-issue; for emergencies issue a new certificate and swap it on the listener.

## Escalate
SEV1 if expired on a customer-facing domain; SEV3 if more than 14 days remain.
