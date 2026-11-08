# RB-11: Queue backlog / consumer lag

Applies to: SQS ApproximateAgeOfOldestMessage, ApproximateNumberOfMessagesVisible, Kafka consumer lag, Redis list length.

## Symptoms
- Messages piling up, processing delay growing, downstream users see stale data.

## Likely causes
- Consumers crashed or scaled to zero; poison message retried forever; downstream slow.
- Traffic spike larger than consumer capacity.

## Diagnose
1. Are consumers running and processing? Check worker logs and error counts.
2. Look for a message that fails repeatedly (same ID in logs); check the DLQ.
3. Compare incoming rate (NumberOfMessagesSent) with processing rate.

## Mitigate
- Scale consumers; move the poison message to a DLQ (set maxReceiveCount); fix and redrive.

## Escalate
SEV2 if user-visible delay exceeds the agreed processing time.
