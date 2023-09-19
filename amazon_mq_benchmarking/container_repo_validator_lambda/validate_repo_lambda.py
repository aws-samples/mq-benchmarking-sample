import os
import json
import http.client
import re
from urllib.parse import urlparse


def send_response(
    event,
    context,
    response_status,
    response_data,
    physical_resource_id=None,
    no_echo=False,
):
    response_url = event["ResponseURL"]
    url = urlparse(response_url)
    body = json.dumps(
        {
            "Status": response_status,
            "Reason": "See the details in CloudWatch Log Stream: "
            + context.log_stream_name,
            "PhysicalResourceId": physical_resource_id or context.log_stream_name,
            "StackId": event["StackId"],
            "RequestId": event["RequestId"],
            "LogicalResourceId": event["LogicalResourceId"],
            "NoEcho": no_echo,
            "Data": response_data,
        }
    )
    headers = {"content-type": "", "content-length": str(len(body))}
    connection = http.client.HTTPSConnection(url.hostname)
    connection.request("PUT", url.path + "?" + url.query, body, headers)
    response = connection.getresponse()
    print("Status code: ", response.reason)


def lambda_handler(event, context):
    print("Received event: " + json.dumps(event))
    status = "SUCCESS"
    responseData = {}

    try:
        if event["RequestType"] == "Create" or event["RequestType"] == "Update":
            repository_url = os.environ.get("CONTAINER_REPO_URL")
            repository_tag = os.environ.get("CONTAINER_REPO_TAG")

            repo_url_pattern = r"^(?:[a-z0-9]+(?:[._-][a-z0-9]+)*\.)?[a-z0-9][a-z0-9-]{0,62}(?:\.[a-z]{2,})?/[a-z0-9-_]+/[a-z0-9-_]+$"

            if not re.match(repo_url_pattern, repository_url):
                raise ValueError("Invalid container_repo_url format")
            if not repository_url or not repository_tag:
                raise ValueError(
                    "container_repo_url and container_repo_tag must be provided"
                )
            tag_pattern = r"^[a-zA-Z0-9_.-]+$"
            if not re.match(tag_pattern, repository_tag):
                raise ValueError("Invalid container_repo_tag format")

        elif event["RequestType"] == "Delete":
            pass

    except Exception as e:
        print("Validation failed:", e)
        status = "FAILED"

    send_response(event, context, status, responseData)
