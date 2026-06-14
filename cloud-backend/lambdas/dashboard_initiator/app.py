"""CloudFormation custom resource that writes frontend config.json."""

from __future__ import annotations

import json
import logging
import urllib.request
from typing import Any

import boto3


logger = logging.getLogger()
logger.setLevel(logging.INFO)


def _send_cfn_response(
    event: dict[str, Any],
    context: Any,
    status: str,
    data: dict[str, Any] | None = None,
    reason: str | None = None,
) -> None:
    response_body = {
        "Status": status,
        "Reason": reason or f"See CloudWatch Logs: {context.log_stream_name}",
        "PhysicalResourceId": event.get("PhysicalResourceId") or context.log_stream_name,
        "StackId": event["StackId"],
        "RequestId": event["RequestId"],
        "LogicalResourceId": event["LogicalResourceId"],
        "NoEcho": False,
        "Data": data or {},
    }
    encoded = json.dumps(response_body).encode("utf-8")
    request = urllib.request.Request(
        event["ResponseURL"],
        data=encoded,
        headers={"Content-Type": "", "Content-Length": str(len(encoded))},
        method="PUT",
    )
    with urllib.request.urlopen(request, timeout=10):
        pass


def lambda_handler(event: dict[str, Any], context: Any) -> None:
    logger.info("Config custom resource event: %s", json.dumps(event))
    try:
        props = event.get("ResourceProperties") or {}
        bucket_name = props["BucketName"]
        api_url = props["ApiUrl"]
        project_name = props.get("ProjectName", "codex_project")

        if event.get("RequestType") in {"Create", "Update"}:
            config = {
                "projectName": project_name,
                "apiUrl": api_url,
            }
            boto3.client("s3").put_object(
                Bucket=bucket_name,
                Key="config.json",
                Body=json.dumps(config, ensure_ascii=False, indent=2).encode("utf-8"),
                ContentType="application/json",
                CacheControl="no-store",
            )

        _send_cfn_response(
            event,
            context,
            "SUCCESS",
            {"BucketName": bucket_name, "ApiUrl": api_url},
        )
    except Exception as exc:
        logger.exception("Failed to write config.json")
        _send_cfn_response(event, context, "FAILED", reason=str(exc))

