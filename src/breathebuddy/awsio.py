"""Optional AWS bridge (LocalStack / real AWS).

This isolates every AWS SDK call behind one object so the rest of the codebase
stays cloud-agnostic and runs offline. Only services from the allowed list are
used: S3, DynamoDB, SNS, SQS, OpenSearch, CloudWatch (via logging).
"""
from __future__ import annotations

import json
import logging

from . import config

log = logging.getLogger("breathebuddy.aws")


def _client(name: str):
    import boto3  # imported lazily so the offline demo needs no boto3
    return boto3.client(
        name,
        region_name=config.AWS_REGION,
        endpoint_url=config.AWS_ENDPOINT or None,
    )


class AWSBridge:
    """Best-effort mirror of local state into AWS. Failures never break the demo."""

    def __init__(self, connect: bool = True) -> None:
        self.enabled = False
        self._s3 = self._ddb = self._sns = self._es = None
        if connect:
            try:
                self._s3 = _client("s3")
                self._ddb = _client("dynamodb")
                self._sns = _client("sns")
                self._es = _client("opensearchserverless") if False else None
                self.enabled = True
                log.info("AWS bridge enabled (endpoint=%s)", config.AWS_ENDPOINT or "aws")
            except Exception as exc:  # pragma: no cover - depends on env
                log.warning("AWS bridge disabled: %s", exc)

    # -- S3 + DynamoDB ----------------------------------------------------
    def put_readings(self, readings: list) -> None:
        if not self.enabled:
            return
        try:
            key = f"raw/{readings[0].ts[:10]}/{readings[0].ts}.json"
            self._s3.put_object(
                Bucket=config.S3_RAW_BUCKET,
                Key=key,
                Body=json.dumps([r.to_dict() for r in readings]).encode(),
                ContentType="application/json",
            )
        except Exception as exc:  # pragma: no cover
            log.warning("S3 put failed: %s", exc)
        try:
            with self._ddb.batch_writer() as batch:
                for r in readings:
                    batch.put_item(Item={
                        "station_id": {"S": r.station_id},
                        "ts": {"S": r.ts},
                        "lat": {"N": str(r.lat)},
                        "lon": {"N": str(r.lon)},
                        "aqi": {"N": str(r.aqi)},
                        "payload": {"S": json.dumps(r.to_dict())},
                    })
        except Exception as exc:  # pragma: no cover
            log.warning("DynamoDB readings put failed: %s", exc)

    def put_alert(self, alert) -> None:
        if not self.enabled:
            return
        try:
            self._ddb.put_item(TableName=config.DDB_ALERTS_TABLE, Item={
                "alert_id": {"S": alert.alert_id},
                "ts": {"S": alert.ts},
                "target": {"S": alert.target},
                "kind": {"S": alert.kind},
                "aqi": {"N": str(alert.aqi)},
                "message": {"S": alert.message},
            })
        except Exception as exc:  # pragma: no cover
            log.warning("DynamoDB alert put failed: %s", exc)

    def put_subscriber(self, sub: dict) -> None:
        if not self.enabled:
            return
        try:
            self._ddb.put_item(TableName=config.DDB_SUBSCRIBERS_TABLE, Item={
                "subscriber_id": {"S": sub["subscriber_id"]},
                "payload": {"S": json.dumps(sub)},
            })
        except Exception as exc:  # pragma: no cover
            log.warning("DynamoDB subscriber put failed: %s", exc)

    # -- OpenSearch -------------------------------------------------------
    def index_grid(self, cells: list) -> None:
        """Index grid cells for geo/search. Uses the OpenSearch REST API."""
        if not config.OPENSEARCH_ENDPOINT:
            return
        try:
            import urllib.request
            bulk = []
            for c in cells:
                bulk.append(json.dumps({"index": {"_index": config.OPENSEARCH_INDEX,
                                                  "_id": c["cell_id"]}}))
                doc = {"cell_id": c["cell_id"], "aqi_now": c["aqi_now"],
                       "clean_index": c["clean_index"],
                       "location": {"lat": c["lat"], "lon": c["lon"]}}
                bulk.append(json.dumps(doc))
            body = ("\n".join(bulk) + "\n").encode()
            req = urllib.request.Request(
                config.OPENSEARCH_ENDPOINT.rstrip("/") + "/_bulk",
                data=body, headers={"Content-Type": "application/x-ndjson"})
            urllib.request.urlopen(req, timeout=5).read()
        except Exception as exc:  # pragma: no cover
            log.warning("OpenSearch index failed: %s", exc)

    # -- SNS --------------------------------------------------------------
    def publish_alert(self, alert) -> dict:
        """Publish an alert to SNS. Returns delivery info."""
        if not (self.enabled and config.SNS_TOPIC_ARN and self._sns):
            return {"delivered": False, "channel": "mock-outbox"}
        try:
            resp = self._sns.publish(
                TopicArn=config.SNS_TOPIC_ARN,
                Subject=f"[BreatheBuddy] {alert.kind}",
                Message=json.dumps(alert.to_dict()),
                MessageAttributes={"kind": {"DataType": "String", "StringValue": alert.kind},
                                   "aqi": {"DataType": "Number", "StringValue": str(alert.aqi)}},
            )
            return {"delivered": True, "channel": "sns", "message_id": resp.get("MessageId")}
        except Exception as exc:  # pragma: no cover
            log.warning("SNS publish failed: %s", exc)
            return {"delivered": False, "channel": "mock-outbox", "error": str(exc)}
