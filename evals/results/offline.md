# IncidentScribe evaluation

Synthetic incidents: 30 (12 runbooks, 2 with PII/secrets, 1 prompt injection).

## Offline (deterministic)

| Metric | Value |
|---|---|
| cases | 30 |
| retrieval@1 | 0.967 |
| retrieval@3 | 1.0 |
| redaction_recall | 1.0 |
| cases_with_raw_pii_in_prompt | 0 |
| false_positive_cases | 0 |

| Case | Expected | Top 3 retrieved | Redactions |
|---|---|---|---|
| EVAL-01 | RB-01 | RB-01, RB-07, RB-06 | - |
| EVAL-02 | RB-01 | RB-01, RB-07, RB-12 | - |
| EVAL-03 | RB-01 | RB-01, RB-11, RB-02 | - |
| EVAL-04 | RB-02 | RB-02, RB-01, RB-06 | - |
| EVAL-05 | RB-02 | RB-02, RB-12, RB-04 | - |
| EVAL-06 | RB-02 | RB-02, RB-01, RB-06 | - |
| EVAL-07 | RB-03 | RB-03, RB-01, RB-05 | - |
| EVAL-08 | RB-03 | RB-03, RB-01, RB-09 | - |
| EVAL-09 | RB-03 | RB-01, RB-03, RB-09 | - |
| EVAL-10 | RB-04 | RB-04, RB-02, RB-01 | - |
| EVAL-11 | RB-04 | RB-04, RB-02, RB-01 | - |
| EVAL-12 | RB-05 | RB-05, RB-04, RB-10 | - |
| EVAL-13 | RB-05 | RB-05, RB-04, RB-09 | - |
| EVAL-14 | RB-06 | RB-06, RB-09, RB-02 | - |
| EVAL-15 | RB-06 | RB-06, RB-04, RB-02 | - |
| EVAL-16 | RB-07 | RB-07, RB-06, RB-01 | - |
| EVAL-17 | RB-07 | RB-07, RB-03, RB-01 | - |
| EVAL-18 | RB-08 | RB-08, RB-05, RB-12 | - |
| EVAL-19 | RB-08 | RB-08, RB-12, RB-05 | - |
| EVAL-20 | RB-09 | RB-09, RB-03, RB-01 | - |
| EVAL-21 | RB-09 | RB-09, RB-03, RB-02 | - |
| EVAL-22 | RB-10 | RB-10, RB-07, RB-03 | - |
| EVAL-23 | RB-10 | RB-10, RB-09, RB-12 | - |
| EVAL-24 | RB-11 | RB-11, RB-10, RB-06 | - |
| EVAL-25 | RB-11 | RB-11, RB-05, RB-06 | - |
| EVAL-26 | RB-12 | RB-12, RB-09, RB-11 | - |
| EVAL-27 | RB-12 | RB-12, RB-02, RB-01 | - |
| EVAL-28 | RB-01 | RB-01, RB-10, RB-03 | {'EMAIL': 1, 'CARD': 1, 'PHONE': 1, 'IP': 1} |
| EVAL-29 | RB-03 | RB-03, RB-01, RB-07 | {'AWS_ACCESS_KEY': 1, 'PASSWORD': 1, 'CONN_STRING_CREDS': 1} |
| EVAL-30 | RB-08 | RB-08, RB-05, RB-12 | - |
