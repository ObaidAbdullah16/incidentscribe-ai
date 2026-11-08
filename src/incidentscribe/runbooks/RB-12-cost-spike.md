# RB-12: Unexpected cloud cost spike

Applies to: AWS Budgets alerts, Cost Anomaly Detection alerts, sudden increase in daily spend.

## Symptoms
- Daily spend above budget; anomaly alert naming a service (EC2-Other, NAT Gateway, Bedrock, Data Transfer).

## Likely causes
- A forgotten test stack (ECS/RDS/EKS left running), autoscaling stuck high.
- NAT gateway data processing from a chatty workload (pulling images, S3 traffic without a VPC endpoint).
- LLM token usage spike (prompt loop, abuse of a public endpoint).
- Leaked credentials used for crypto-mining (new instances in unusual regions).

## Diagnose
1. Cost Explorer: group by Service then by Usage Type for the spike day.
2. Check every region for running EC2/ECS/EKS/RDS (`_setup/cost-check.sh`).
3. CloudTrail: RunInstances / CreateAccessKey in unexpected regions.

## Mitigate
- Stop or destroy the stack (`_setup/panic-stop.sh`); add VPC endpoints; cap LLM spend per day.
- If credentials leaked: deactivate keys, rotate, review IAM.

## Escalate
SEV1 for suspected credential compromise; otherwise SEV3 with the owner.
