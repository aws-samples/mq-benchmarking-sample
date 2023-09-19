import uuid
from constructs import Construct
from aws_cdk import (
    Stack,
    aws_ec2 as ec2,
    aws_lambda as _lambda,
    CustomResource,
    RemovalPolicy,
)


class VpcStack(Stack):
    def __init__(self, scope: Construct, id: str, **kwargs) -> None:
        super().__init__(scope, id, **kwargs)

        vpc_cidr = self.node.try_get_context("vpc_cidr")
        self.vpc = ec2.Vpc(
            self,
            "Amazon MQ VPC",
            ip_addresses=ec2.IpAddresses.cidr(vpc_cidr),
            max_azs=3,
        )

        validate_container_repo_function = _lambda.Function(
            self,
            "ValidateRepoLambda",
            runtime=_lambda.Runtime.PYTHON_3_11,
            handler="validate_repo_lambda.lambda_handler",
            code=_lambda.Code.from_asset(
                "./amazon_mq_benchmarking/container_repo_validator_lambda"
            ),
            environment={
                "CONTAINER_REPO_URL": str(self.node.get_context("container_repo_url")),
                "CONTAINER_REPO_TAG": str(self.node.get_context("container_repo_tag")),
            },
        )

        validate_repo_custom_resource = CustomResource(
            self,
            "ValidateRepoCustomResource",
            service_token=validate_container_repo_function.function_arn,
            properties={"DummyProperty": str(uuid.uuid4())},
            removal_policy=RemovalPolicy.DESTROY,
        )
