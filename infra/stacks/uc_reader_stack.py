import os

import aws_cdk as cdk
from aws_cdk import (
    aws_lambda as lambda_,
    aws_iam as iam,
    aws_ssm as ssm,
    aws_apigateway as apigw,
    Duration,
    Stack,
)
from constructs import Construct

SSM_PREFIX = "/uc-reader"

LAYER_ZIP = os.path.join(
    os.path.dirname(__file__), "..", "lambda_layer", "dist", "layer.zip"
)
LAMBDA_CODE_DIR = os.path.join(os.path.dirname(__file__), "..", "..")


class UcReaderStack(Stack):
    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # ---------------------------------------------------------------------------
        # Layer  duckdb + pyarrow + requests
        # ---------------------------------------------------------------------------
        duckdb_layer = lambda_.LayerVersion(
            self,
            "DuckDbLayer",
            code=lambda_.Code.from_asset(LAYER_ZIP),
            compatible_runtimes=[lambda_.Runtime.PYTHON_3_12],
            compatible_architectures=[lambda_.Architecture.X86_64],
            description="duckdb + pyarrow + requests for Unity Catalog reader",
        )

        # ---------------------------------------------------------------------------
        # SSM Parameter Store — la Lambda legge i valori a runtime via boto3
        # Il SecureString non può essere passato come env var CloudFormation
        # ---------------------------------------------------------------------------
        workspace_param = ssm.StringParameter.from_string_parameter_name(
            self,
            "WorkspaceParam",
            string_parameter_name=f"{SSM_PREFIX}/databricks-workspace",
        )

        token_param = ssm.StringParameter.from_secure_string_parameter_attributes(
            self,
            "TokenParam",
            parameter_name=f"{SSM_PREFIX}/databricks-token",
        )

        # ---------------------------------------------------------------------------
        # Lambda function — env vars contengono i NOMI dei parametri SSM, non i valori
        # ---------------------------------------------------------------------------
        fn = lambda_.Function(
            self,
            "UcReaderFunction",
            runtime=lambda_.Runtime.PYTHON_3_12,
            architecture=lambda_.Architecture.X86_64,
            handler="uc_reader.handler",
            code=lambda_.Code.from_asset(
                LAMBDA_CODE_DIR,
                exclude=[
                    "infra",
                    "cdk.out",
                    "__pycache__",
                    "**/__pycache__",
                    "*.pyc",
                    "**/*.pyc",
                    ".venv",
                    "local_test.py",
                    "*.md",
                    ".git",
                    ".claude",
                    ".mcp.json",
                ],
            ),
            layers=[duckdb_layer],
            timeout=Duration.seconds(60),
            memory_size=1536,
            environment={
                "SSM_WORKSPACE": f"{SSM_PREFIX}/databricks-workspace",
                "SSM_TOKEN":     f"{SSM_PREFIX}/databricks-token",
            },
            description="Reads Databricks Unity Catalog Delta tables via DuckDB",
        )

        # Permessi SSM alla Lambda
        workspace_param.grant_read(fn)
        token_param.grant_read(fn)

        # ---------------------------------------------------------------------------
        # REST API Gateway con cache
        # ---------------------------------------------------------------------------
        api = apigw.RestApi(
            self,
            "UcReaderApi",
            rest_api_name="uc-reader-api",
            description="Query Databricks Unity Catalog tables via DuckDB",
            deploy_options=apigw.StageOptions(
                stage_name="prod",
                # Cache: 0.5 GB, TTL 60s — evita di invocare Lambda per query identiche
                caching_enabled=True,
                cache_cluster_size="0.5",
                cache_ttl=Duration.seconds(60),
                # Throttling di default
                throttling_rate_limit=50,
                throttling_burst_limit=100,
                # Log livello minimal
                metrics_enabled=True,
            ),
        )

        # Integrazione Lambda proxy
        lambda_integration = apigw.LambdaIntegration(
            fn,
            proxy=True,
            cache_key_parameters=[
                "method.request.querystring.table",
                "method.request.querystring.filters",
                "method.request.querystring.limit",
            ],
        )

        # GET /query
        query_resource = api.root.add_resource("query")
        query_resource.add_method(
            "GET",
            lambda_integration,
            request_parameters={
                "method.request.querystring.table":   True,   # obbligatorio
                "method.request.querystring.filters": False,  # opzionale
                "method.request.querystring.limit":   False,  # opzionale
            },
            request_validator=apigw.RequestValidator(
                self,
                "QueryValidator",
                rest_api=api,
                validate_request_parameters=True,
            ),
        )

        # ---------------------------------------------------------------------------
        # Output
        # ---------------------------------------------------------------------------
        cdk.CfnOutput(self, "FunctionArn",  value=fn.function_arn)
        cdk.CfnOutput(self, "FunctionName", value=fn.function_name)
        cdk.CfnOutput(self, "ApiUrl",       value=f"{api.url}query")
