import re
from constructs import Construct
from aws_cdk import (
    Stack,
    aws_ec2 as ec2,
    aws_amazonmq as mq,
    CfnOutput,
    aws_secretsmanager as secretsmanager,
)


def validate_username(username):
    if len(username) < 2:
        raise ValueError("Username must be at least 2 characters long")
    if re.search("[ ,:=]", username):
        raise ValueError(
            "Username cannot contain spaces, commas, colons, or equal signs"
        )


class MQStack(Stack):
    def __init__(self, scope: Construct, id: str, vpc=ec2.Vpc, **kwargs) -> None:
        super().__init__(scope, id, **kwargs)

        mq_cidr_value = self.node.try_get_context("mq_cidr")
        instance_type = self.node.try_get_context("broker_instance_type")
        allowed_instance_types = [
            "mq.m4.large",
            "mq.m5.large",
            "mq.m5.xlarge",
            "mq.m5.2xlarge",
            "mq.m5.4xlarge",
        ]

        if instance_type not in allowed_instance_types:
            raise ValueError(
                f"Invalid instance type. Allowed types: {', '.join(allowed_instance_types)}"
            )

        broker_username = self.node.try_get_context("mq_username")
        validate_username(broker_username)

        secret = secretsmanager.Secret(
            self,
            "Secret",
            generate_secret_string=secretsmanager.SecretStringGenerator(
                password_length=12,
                exclude_punctuation=True,
            ),
            description="Amazon MQ Console Password",
            secret_name="AmazonMQ-Credentials",
        )

        mq_security_group = ec2.SecurityGroup(
            self,
            "MQSecurityGroup",
            vpc=vpc,
            allow_all_outbound=True,
            security_group_name="MQ Security Group",
        )

        for port in [8162, 61617, 5671, 61614, 8883]:
            mq_security_group.add_ingress_rule(
                ec2.Peer.ipv4(mq_cidr_value),
                ec2.Port.tcp(port),
                f"Allows inbound traffic on port {port} from {mq_cidr_value}",
            )

        active_mq_broker = mq.CfnBroker(
            self,
            "Active MQ Broker",
            auto_minor_version_upgrade=True,
            broker_name="Active_MQ_Broker",
            deployment_mode="ACTIVE_STANDBY_MULTI_AZ",
            engine_type="ACTIVEMQ",
            publicly_accessible=True,
            host_instance_type=instance_type,
            engine_version="5.17.6",
            users=[
                mq.CfnBroker.UserProperty(
                    username=broker_username,
                    password=secret.secret_value.unsafe_unwrap(),
                    console_access=True,
                )
            ],
            subnet_ids=vpc.select_subnets(subnet_type=ec2.SubnetType.PUBLIC).subnet_ids,
            security_groups=[mq_security_group.security_group_id],
        )

        CfnOutput(
            self,
            "MQUsername",
            description="Username for Amazon MQ Console Access",
            value=broker_username,
        )
        CfnOutput(
            self,
            "MQPassword",
            description="ARN of Secrets Manager which contains password for Amazon MQ Console Access",
            value=secret.secret_arn,
        )
