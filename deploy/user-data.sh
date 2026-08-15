#!/bin/bash
# EC2 user-data bootstrap for the ProjectX portal (CA101 Cloud Lab).
# Amazon Linux 2023. Assumes the instance has the projectx-flask-ec2-role
# instance profile attached and the projectx-portal-lab bucket is seeded.
set -euxo pipefail

BUCKET="${PROJECTX_BUCKET:-projectx-portal-lab}"
REGION="${AWS_REGION:-us-east-1}"
APP_DIR="/opt/projectx-portal"

dnf install -y python3 python3-pip git

id projectx &>/dev/null || useradd --system --create-home --shell /usr/sbin/nologin projectx

# Deploy the portal code. Option A: bake it into the AMI / copy via SSM.
# Option B (shown): pull from S3 where you've uploaded the portal/ folder.
# NOTE: the instance role must be allowed to read s3://${BUCKET}-code
# (see iam/flask-ec2-role.json). Do NOT mask a failed sync — fail loudly so a
# missing/denied download doesn't surface later as a confusing pip error.
mkdir -p "$APP_DIR"
aws s3 sync "s3://${BUCKET}-code/portal/" "$APP_DIR/" --region "$REGION"

if [ ! -f "$APP_DIR/requirements.txt" ]; then
  echo "ERROR: portal code not found after sync from s3://${BUCKET}-code/portal/." >&2
  echo "Check that the code bucket exists, contains the portal/ folder, and that" >&2
  echo "the instance role can s3:ListBucket + s3:GetObject on that bucket." >&2
  exit 1
fi

python3 -m venv "$APP_DIR/.venv"
"$APP_DIR/.venv/bin/pip" install --upgrade pip
"$APP_DIR/.venv/bin/pip" install -r "$APP_DIR/requirements.txt"

chown -R projectx:projectx "$APP_DIR"

install -m 0644 "$APP_DIR/projectx-portal.service" /etc/systemd/system/projectx-portal.service 2>/dev/null || \
cat >/etc/systemd/system/projectx-portal.service <<UNIT
[Unit]
Description=ProjectX Customer Portal (CA101 Cloud Lab)
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=projectx
WorkingDirectory=${APP_DIR}
Environment=PROJECTX_BUCKET=${BUCKET}
Environment=AWS_REGION=${REGION}
ExecStart=${APP_DIR}/.venv/bin/gunicorn --bind 0.0.0.0:8080 app:app
Restart=on-failure
RestartSec=3

[Install]
WantedBy=multi-user.target
UNIT

systemctl daemon-reload
systemctl enable --now projectx-portal.service
