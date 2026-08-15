"""
ProjectX Customer Portal
Intentionally vulnerable lab application (CA101 Cloud Lab).

The app runs on an EC2 instance whose instance profile ("Flask EC2 Role")
grants read access to the projectx-portal-lab bucket. boto3 picks up those
credentials automatically via the default provider chain.

DO NOT deploy outside an isolated lab account.
"""
import os

import boto3
from botocore.exceptions import ClientError
from flask import (
    Flask,
    Response,
    abort,
    redirect,
    render_template,
    request,
    url_for,
)

APP_NAME = "ProjectX Customer Portal"
BUCKET = os.environ.get("PROJECTX_BUCKET", "projectx-portal-lab")
PUBLIC_PREFIX = "public/"
REGION = os.environ.get("AWS_REGION", "us-east-1")

app = Flask(__name__)
s3 = boto3.client("s3", region_name=REGION)


@app.route("/")
def index():
    return render_template("index.html", app_name=APP_NAME, bucket=BUCKET)


@app.route("/documents")
def documents():
    # The portal is *intended* to only surface files under public/.
    resp = s3.list_objects_v2(Bucket=BUCKET, Prefix=PUBLIC_PREFIX)
    keys = [obj["Key"] for obj in resp.get("Contents", [])]
    return render_template("documents.html", app_name=APP_NAME, keys=keys)


@app.route("/view")
def view():
    # -----------------------------------------------------------------
    # INTENTIONAL VULNERABILITY #1 — Broken access control / IDOR.
    #
    # The viewer streams whatever S3 key the caller supplies. The UI only
    # links objects under public/, but the server never enforces that
    # prefix, and the EC2 role can read the entire bucket. An attacker can
    # therefore request objects outside public/, e.g.:
    #
    #     GET /view?key=internal/q3-roadmap.txt
    #     GET /view?key=backup/aws_dev_credentials.txt
    #
    # A safe version would reject any key not starting with PUBLIC_PREFIX.
    # -----------------------------------------------------------------
    key = request.args.get("key", "")
    if not key:
        return redirect(url_for("documents"))
    try:
        obj = s3.get_object(Bucket=BUCKET, Key=key)
    except ClientError:
        abort(404)
    body = obj["Body"].read()
    content_type = obj.get("ContentType", "application/octet-stream")
    return Response(body, mimetype=content_type)


@app.route("/health")
def health():
    return {"status": "ok", "app": APP_NAME}, 200


if __name__ == "__main__":
    # Bind to 0.0.0.0 so the EC2 security group governs exposure.
    app.run(host="0.0.0.0", port=8080)
