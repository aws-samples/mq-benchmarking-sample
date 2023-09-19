import aws_cdk as cdk

from amazon_mq_benchmarking.vpc_stack import VpcStack
from amazon_mq_benchmarking.amazon_mq_benchmarking_stack import MQStack
from amazon_mq_benchmarking.ecs_cluster import ECSStack

app = cdk.App()

vpc_stack = VpcStack(app, "VPC")
MQStack(app, "MQ", vpc_stack.vpc)
ECSStack(app, "ECS-Stack", vpc_stack.vpc)

app.synth()
