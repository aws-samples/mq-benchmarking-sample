from constructs import Construct
from aws_cdk import (
    aws_ec2 as ec2,
    aws_ecs as ecs,
    aws_kms as kms,
    aws_logs as logs,
    aws_s3 as s3,
    aws_iam as iam,
    aws_ssm as ssm,
    CfnOutput,
    Stack,
    CustomResource,
    RemovalPolicy,
)
from .lambda_function import create_my_lambda


class ECSStack(Stack):
    def __init__(self, scope: Construct, id: str, vpc=ec2.Vpc, **kwargs) -> None:
        super().__init__(scope, id, **kwargs)

        ecs_execution_role = iam.Role(
            self,
            "MyExecutionRole",
            assumed_by=iam.ServicePrincipal("ecs-tasks.amazonaws.com"),
        )

        ecs_execution_role.add_managed_policy(
            iam.ManagedPolicy.from_aws_managed_policy_name(
                "service-role/AmazonECSTaskExecutionRolePolicy"
            )
        )

        fargate_task = ecs.FargateTaskDefinition(
            self,
            "TaskDefinition",
            memory_limit_mib=16384,
            cpu=4096,
            execution_role=ecs_execution_role,
        )

        repository_url = self.node.try_get_context("container_repo_url")
        repository_tag = self.node.try_get_context("container_repo_tag")

        container = fargate_task.add_container(
            "Benchmarking-Container",
            image=ecs.ContainerImage.from_registry(
                f"{repository_url}:{repository_tag}"
            ),
            linux_parameters=ecs.LinuxParameters(
                self, "LinuxParameters", init_process_enabled=True
            ),
            logging=ecs.AwsLogDriver(stream_prefix="ecs-fargate-task"),
        )

        kms_key = kms.Key(
            self,
            "KmsKey",
            enable_key_rotation=True,
            removal_policy=RemovalPolicy.DESTROY,
        )

        kms_key.add_to_resource_policy(
            iam.PolicyStatement(
                actions=["kms:*"],
                effect=iam.Effect.ALLOW,
                principals=[iam.ServicePrincipal("logs.amazonaws.com")],
                resources=["*"],
            )
        )

        kms_key.add_to_resource_policy(
            iam.PolicyStatement(
                actions=["kms:*"],
                effect=iam.Effect.ALLOW,
                principals=[iam.ServicePrincipal("s3.amazonaws.com")],
                resources=["*"],
            )
        )

        log_group = logs.LogGroup(
            self,
            "LogGroup",
            encryption_key=kms_key,
            removal_policy=RemovalPolicy.DESTROY,
        )

        exec_bucket = s3.Bucket(
            self,
            "EcsExecBucket",
            encryption_key=kms_key,
            removal_policy=RemovalPolicy.DESTROY,
        )

        cluster = ecs.Cluster(
            self,
            "Cluster",
            vpc=vpc,
            execute_command_configuration=ecs.ExecuteCommandConfiguration(
                kms_key=kms_key,
                log_configuration=ecs.ExecuteCommandLogConfiguration(
                    cloud_watch_log_group=log_group,
                    cloud_watch_encryption_enabled=True,
                    s3_bucket=exec_bucket,
                    s3_encryption_enabled=True,
                    s3_key_prefix="exec-command-output",
                ),
                logging=ecs.ExecuteCommandLogging.OVERRIDE,
            ),
        )

        fargate_task.add_to_task_role_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=[
                    "ssmmessages:CreateControlChannel",
                    "ssmmessages:CreateDataChannel",
                    "ssmmessages:OpenControlChannel",
                    "ssmmessages:OpenDataChannel",
                ],
                resources=["*"],
            )
        )
        fargate_task.add_to_task_role_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=["kms:Decrypt"],
                resources=[kms_key.key_arn],
            )
        )
        fargate_task.add_to_task_role_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=["logs:DescribeLogGroups"],
                resources=["*"],
            )
        )
        fargate_task.add_to_task_role_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=[
                    "logs:CreateLogStream",
                    "logs:DescribeLogStreams",
                    "logs:PutLogEvents",
                ],
                resources=[log_group.log_group_arn],
            )
        )
        fargate_task.add_to_task_role_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=["s3:PutObject"],
                resources=[exec_bucket.bucket_arn + "/*"],
            )
        )
        fargate_task.add_to_task_role_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=["s3:GetEncryptionConfiguration"],
                resources=[exec_bucket.bucket_arn],
            )
        )

        task_arn_parameter = ssm.StringParameter(
            self,
            "TaskArnParameter",
            string_value="placeholder",
            parameter_name="/ecsTaskExecution/taskArns",
            description="ECS Task ARNs",
            tier=ssm.ParameterTier.STANDARD,
        )

        ecs_lambda = create_my_lambda(
            self,
            "ECSLambda",
            cluster_name=cluster.cluster_name,
            task_defintion=fargate_task.task_definition_arn,
            subnet_ids=[subnet.subnet_id for subnet in cluster.vpc.public_subnets],
            container_name=container.container_name,
        )

        statement = iam.PolicyStatement(
            actions=["ssm:PutParameter", "ssm:GetParameter"],
            resources=[task_arn_parameter.parameter_arn],
        )

        ecs_lambda.add_to_role_policy(statement)

        ecs_lambda.add_to_role_policy(
            iam.PolicyStatement(
                actions=[
                    "ecs:RunTask",
                    "ecs:StopTask",
                    "ecs:DescribeTasks",
                    "iam:PassRole",
                ],
                resources=["*"],
            )
        )

        custom_resource = CustomResource(
            self,
            "CustomResource",
            service_token=ecs_lambda.function_arn,
            removal_policy=RemovalPolicy.DESTROY,
        )

        command = "/bin/bash"
        CfnOutput(
            self,
            "EcsExecCommandOutput",
            value=f'aws ecs execute-command --region {Stack.of(self).region} --cluster {cluster.cluster_arn} --task <TASK-ARN> --container {container.container_name} --command "{command}" --interactive',
        )
