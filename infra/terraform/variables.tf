variable "aws_region" {
  type    = string
  default = "ap-southeast-2"
}

variable "model_id" {
  description = "Bedrock model or inference profile. Nova Micro via the APAC profile works from Asia-Pacific Regions (ap-southeast-2, ap-south-1). In us-east-1/us-east-2 use us.amazon.nova-micro-v1:0, in Europe eu.amazon.nova-micro-v1:0."
  type        = string
  default     = "apac.amazon.nova-micro-v1:0"
}

variable "daily_cap_usd" {
  description = "Hard cap on model + guardrail spend per day. Over it, the free fallback summary is used."
  type        = number
  default     = 0.15
}

variable "monthly_cap_usd" {
  type    = number
  default = 4.5
}

variable "enable_guardrail" {
  description = "Bedrock Guardrail: prompt-attack + harmful-content filters and PII masking on top of the code's own redaction."
  type        = bool
  default     = true
}

variable "allowed_origins" {
  description = "CORS origins for the public demo page. Set to your portfolio URL, e.g. [\"https://d123.cloudfront.net\"]."
  type        = list(string)
  default     = ["*"]
}

variable "allow_custom_text" {
  description = "Let demo visitors submit their own incident text (still redacted, size-limited and budget-capped)."
  type        = bool
  default     = true
}

variable "alarm_prefixes" {
  description = "CloudWatch alarms whose names start with these prefixes are summarised (EventBridge rule)."
  type        = list(string)
  default     = ["incidentscribe-", "shipit-"]
}

variable "reserved_concurrency" {
  description = "-1 = no reservation. New AWS accounts often have a total limit of 10, which makes any reservation fail."
  type        = number
  default     = -1
}

variable "api_rate_limit" {
  description = "Requests per second allowed on the public API (burst is twice this)."
  type        = number
  default     = 2
}

variable "permissions_boundary_name" {
  description = "IAM permissions boundary that aws-foundation creates. Every role this stack creates carries it; the GitHub deploy role refuses to create roles without it. Set \"\" only when you deploy without aws-foundation."
  type        = string
  default     = "gha-workload-boundary"
}
