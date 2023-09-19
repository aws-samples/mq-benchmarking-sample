import os
import boto3
import json
import http.client
from urllib.parse import urlparse

client = boto3.client("ecs")
ssm = boto3.client("ssm")


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
            response = client.run_task(
                cluster=os.environ["CLUSTER_NAME"],
                taskDefinition=os.environ["TASK_DEFINITION"],
                count=int(os.environ["NUMBER_OF_TASKS"]),
                launchType="FARGATE",
                networkConfiguration={
                    "awsvpcConfiguration": {
                        "subnets": os.environ["SUBNETS"].split(","),
                        "assignPublicIp": "ENABLED",
                    }
                },
                overrides={
                    "containerOverrides": [
                        {
                            "name": os.environ["CONTAINER_NAME"],
                            "command": [
                                "/bin/sh",
                                "-c",
                                "while true; do echo Running; sleep 60; done;",
                            ],
                            "environment": [
                                {"name": "environment", "value": "production"},
                            ],
                        },
                    ]
                },
                enableExecuteCommand=True,
            )
            task_arns = [task["taskArn"] for task in response["tasks"]]
            ssm.put_parameter(
                Name="/ecsTaskExecution/taskArns",
                Value=json.dumps(task_arns),
                Type="String",
                Overwrite=True,
            )
            responseData = {"TaskArns": task_arns}
        elif event["RequestType"] == "Delete":
            task_arns = json.loads(
                ssm.get_parameter(Name="/ecsTaskExecution/taskArns")["Parameter"][
                    "Value"
                ]
            )
            for task_arn in task_arns:
                client.stop_task(cluster=os.environ["CLUSTER_NAME"], task=task_arn)
    except Exception as e:
        print("Failed to process:", e)
        status = "FAILED"
    send_response(event, context, status, responseData)
