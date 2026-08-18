# Cyber Attack Cloud Lab

An intentionally (but benign) vulnerable AWS lab that walks you through a
full cloud attack chain. This service is a Flask "ProjectX" portal that
runs on EC2 and serves documents from S3. There are a couple planted weaknesses let an
attacker pivot from a web flaw all the way to AWS admin, while CloudTrail,
GuardDuty, and Wazuh catch each step.

🔑 After provisioning the AWS infrastructure, you can play this like a CTF before watching the attack chain.

## Layout

```
portal/     Flask portal app (deploy to EC2)
iam/        IAM policy documents
deploy/     EC2 bootstrap (user-data, systemd unit) + configure_lab.py
s3-seed/    Benign objects uploaded into the bucket
spec.md     Full walkthrough: setup, red-team, and blue-team detection
```

### Burp Suite Intruder Seeds

```
public/welcome.txt
internal/org-chart.txt
internal/q3-roadmap.txt
backup/aws_dev_credentials.txt
backup/backup.sql
```

## Getting started

1. Run `python deploy/configure_lab.py` to stamp your bucket names, account ID,
   region, and lab-attacker keys into a ready-to-deploy `build/` copy.

> Deploy only in an isolated lab AWS account. All credentials are throwaway and
> the privilege escalation is scoped to lab resources. We do not take any responsibility for actions performed in or consequences of what has been shown.

