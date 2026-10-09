"""Create BreatheBuddy resources in LocalStack and print the env to export.

    pip install boto3
    python scripts/localstack_bootstrap.py

Requires LocalStack running (see infra/localstack/docker-compose.yml).
"""
from __future__ import annotations

import json
import os

ENDPOINT = os.getenv("AWS_ENDPOINT_URL", "http://localhost:4566")
REGION = os.getenv("AWS_DEFAULT_REGION", "ap-south-1")


def client(name):
    import boto3
    return boto3.client(name, endpoint_url=ENDPOINT, region_name=REGION,
                        aws_access_key_id="test", aws_secret_access_key="test")


def main() -> None:
    s3, ddb, sns, sqs = client("s3"), client("dynamodb"), client("sns"), client("sqs")

    bucket = "breathebuddy-raw"
    s3.create_bucket(Bucket=bucket, CreateBucketConfiguration={"LocationConstraint": REGION})

    for table, keys in [
        ("breathebuddy-readings", [("station_id", "HASH"), ("ts", "RANGE")]),
        ("breathebuddy-alerts", [("alert_id", "HASH")]),
        ("breathebuddy-subscribers", [("subscriber_id", "HASH")]),
    ]:
        try:
            ddb.create_table(
                TableName=table, BillingMode="PAY_PER_REQUEST",
                AttributeDefinitions=[{"AttributeName": n, "AttributeType": "S"}
                                      for n, _ in keys],
                KeySchema=[{"AttributeName": n, "KeyType": t} for n, t in keys],
            )
        except ddb.exceptions.ResourceInUseException:
            pass

    topic = sns.create_topic(Name="breathebuddy-alerts")["TopicArn"]
    queue = sqs.create_queue(QueueName="breathebuddy-buffer")["QueueUrl"]

    env = {
        "BB_USE_AWS": "true",
        "AWS_ENDPOINT_URL": ENDPOINT,
        "AWS_DEFAULT_REGION": REGION,
        "AWS_ACCESS_KEY_ID": "test",
        "AWS_SECRET_ACCESS_KEY": "test",
        "BB_S3_RAW_BUCKET": bucket,
        "BB_DDB_READINGS_TABLE": "breathebuddy-readings",
        "BB_DDB_ALERTS_TABLE": "breathebuddy-alerts",
        "BB_DDB_SUBSCRIBERS_TABLE": "breathebuddy-subscribers",
        "BB_SNS_TOPIC_ARN": topic,
        "BB_SQS_QUEUE_URL": queue,
    }
    print("LocalStack resources ready.\n")
    print("Export these before running the pipeline:")
    for k, v in env.items():
        print(f'  export {k}="{v}"')
    print("\n(email format)", json.dumps({"topic": topic, "queue": queue}, indent=2))


if __name__ == "__main__":
    main()
