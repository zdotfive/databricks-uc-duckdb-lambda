#!/usr/bin/env python3
import os
import aws_cdk as cdk
from stacks.uc_reader_stack import UcReaderStack

app = cdk.App()

UcReaderStack(
    app,
    "UcReaderStack",
    env=cdk.Environment(
        account=os.environ.get("CDK_DEFAULT_ACCOUNT"),
        region=os.environ.get("CDK_DEFAULT_REGION", "eu-central-1"),
    ),
)

app.synth()
