import os
from constructs import Construct
from aws_cdk import (
    aws_lambda as _lambda,
    aws_iam as iam,
)


def create_my_lambda(
    scope: Construct,
    id: str,
    cluster_name,
    task_defintion,
    subnet_ids,
    container_name,
    **kwargs,
):
    dir_path = os.path.dirname(os.path.realpath(__file__))
    subnet_str = ",".join(subnet_ids)
    number_of_tasks_string = scope.node.try_get_context("tasks")

    try:
        number_of_tasks = int(number_of_tasks_string)
    except ValueError:
        raise ValueError(
            f"An integer is required for number of tasks, got {number_of_tasks_string} instead."
        )

    if number_of_tasks > 10:
        raise ValueError("Number of tasks cannot exceed 10")

    lambda_function = _lambda.Function(
        scope,
        "MyLambda",
        runtime=_lambda.Runtime.PYTHON_3_11,
        handler="lambda.lambda_handler",
        code=_lambda.Code.from_asset("./amazon_mq_benchmarking/ecs_task_lambda"),
        environment={
            "CLUSTER_NAME": cluster_name,
            "TASK_DEFINITION": task_defintion,
            "NUMBER_OF_TASKS": str(number_of_tasks),
            "SUBNETS": subnet_str,
            "CONTAINER_NAME": container_name,
        },
    )

    return lambda_function
