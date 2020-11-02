from aws_cdk import core
from aws_cdk import aws_ec2 as _ec2
from aws_cdk import aws_iam as _iam

from custom_resources.ssh_key_generator.ssh_key_generator_stack import SshKeyGeneratorStack


class GlobalArgs:
    """
    Helper to define global statics
    """

    OWNER = "MystiqueAutomation"
    ENVIRONMENT = "production"
    REPO_NAME = "mssql-to-aurora"
    SOURCE_INFO = f"https://github.com/miztiik/{REPO_NAME}"
    VERSION = "2020_10_30"
    MIZTIIK_SUPPORT_EMAIL = ["mystique@example.com", ]


class DatabaseMigrationPrerequisiteStack(core.Stack):

    def __init__(
        self,
        scope: core.Construct,
        id: str,
        vpc,
        stack_log_level,
        **kwargs
    ) -> None:
        super().__init__(scope, id, **kwargs)

        # Create DMS VPC Role

        # # # # # # # # # # # # # # # # # # # # # # # # # # # # #
        # THIS STACK WILL FAIL, IF ROLE WITH SIMILAR NAME EXISTS #
        # # # # # # # # # # # # # # # # # # # # # # # # # # # # #
        dms_vpc_role = _iam.Role(
            self,
            "dmsVpcRole",
            assumed_by=_iam.ServicePrincipal("dms.amazonaws.com"),
            description="Miztiik Automation: DMS VPC Role",
            role_name="dms-vpc-role"
        )

        # https://docs.aws.amazon.com/dms/latest/userguide/CHAP_Security.html
        # aws iam get-policy --policy-arn arn:aws:iam::aws:policy/service-role/AmazonDMSVPCManagementRole

        dms_vpc_role.add_managed_policy(
            # _iam.ManagedPolicy.from_aws_managed_policy_name("AmazonDMSVPCManagementRole")
            _iam.ManagedPolicy.from_managed_policy_arn(
                self,
                "dmsRolePolicyArn",
                managed_policy_arn="arn:aws:iam::aws:policy/service-role/AmazonDMSVPCManagementRole"
            )
        )

        # Create DMS VPC Role
        dms_cloudwatch_logs_role = _iam.Role(
            self,
            "dmsCloudwatchRole",
            assumed_by=_iam.ServicePrincipal("dms.amazonaws.com"),
            description="Miztiik Automation: DMS VPC Role",
            role_name="dms-cloudwatch-logs-role"
        )

        dms_cloudwatch_logs_role.add_managed_policy(
            _iam.ManagedPolicy.from_managed_policy_arn(
                self,
                "dmsCloudWatchRolePolicyArn",
                managed_policy_arn="arn:aws:iam::aws:policy/service-role/AmazonDMSCloudWatchLogsRole"
            )
        )
        # Create DMS Assessment S3 Access Role
        dms_s3_access_role = _iam.Role(
            self,
            "dmsS3AccessRole",
            assumed_by=_iam.ServicePrincipal("dms.amazonaws.com"),
            description="Miztiik Automation: DMS S3 Access Role",
            role_name="dms-s3-access-role"
        )

        dms_s3_access_role.add_managed_policy(
            _iam.ManagedPolicy.from_managed_policy_arn(
                self,
                "dmsS3AccessRolePolicyArn",
                managed_policy_arn="arn:aws:iam::aws:policy/AmazonS3FullAccess"
            )
        )
        # Create DMS DynamoDB Role
        self.dms_dynamodb_role = _iam.Role(
            self,
            "dmsDynamoDbRole",
            assumed_by=_iam.ServicePrincipal("dms.amazonaws.com"),
            description="Miztiik Automation: DMS DynamoDB Role",
            role_name="dms-dynamodb-role"
        )

        role_stmt1 = _iam.PolicyStatement(
            effect=_iam.Effect.ALLOW,
            resources=[
                f"arn:aws:dynamodb:{core.Aws.REGION}:{core.Aws.ACCOUNT_ID}:table/*",
                f"arn:aws:dynamodb:{core.Aws.REGION}:{core.Aws.ACCOUNT_ID}:table/awsdms_apply_exceptions",
                f"arn:aws:dynamodb:{core.Aws.REGION}:{core.Aws.ACCOUNT_ID}:table/awsdms_full_load_exceptions"
            ],
            actions=[
                "dynamodb:PutItem",
                "dynamodb:CreateTable",
                "dynamodb:DescribeTable",
                "dynamodb:DeleteTable",
                "dynamodb:DeleteItem",
                "dynamodb:UpdateItem"
            ]
        )
        role_stmt1.sid = "AllowDMSToManageDDBrestrictTOspecificTABLEinPROD"

        role_stmt2 = _iam.PolicyStatement(
            effect=_iam.Effect.ALLOW,
            resources=["*"],
            actions=["dynamodb:ListTables"]
        )
        role_stmt1.sid = "AllowDMSToListDDBTables"

        self.dms_dynamodb_role.add_to_policy(role_stmt1)
        self.dms_dynamodb_role.add_to_policy(role_stmt2)

        # Create SSH Key and Store in Parameter Store
        self.custom_ssh_key_name = "mystique-automation-ssh-key"
        ssh_key_generator = SshKeyGeneratorStack(
            self,
            "ssh-key-generator",
            ssh_key_name=self.custom_ssh_key_name
        )

        # Export Value
        self.ssh_key_gen_status = ssh_key_generator.response

        # Create Security Group for DMS Instance
        dms_sg = _ec2.SecurityGroup(
            self,
            id="dmsSecurityGroup",
            vpc=vpc,
            security_group_name=f"dms_sg_{id}",
            description="Security Group for DMS replication instance to interact with source and target databases"
        )

        dms_sg.add_ingress_rule(
            peer=_ec2.Peer.ipv4(vpc.vpc_cidr_block),
            connection=_ec2.Port.tcp(27017),
            description="Allow MongoDB inbound connetions"
        )
        dms_sg.add_ingress_rule(
            peer=_ec2.Peer.ipv4(vpc.vpc_cidr_block),
            connection=_ec2.Port.tcp(1433),
            description="Allow MSSQL inbound connetions"
        )
        dms_sg.add_ingress_rule(
            peer=_ec2.Peer.ipv4(vpc.vpc_cidr_block),
            connection=_ec2.Port.tcp(3306),
            description="Allow MySQL inbound connetions"
        )

        # Create Security Group for DocsDB Instance
        docsdb_sg = _ec2.SecurityGroup(
            self,
            id="docsDbSecurityGroup",
            vpc=vpc,
            security_group_name=f"docsdb_sg_{id}",
            description="Security Group for DocsDB"
        )

        docsdb_sg.add_ingress_rule(
            peer=_ec2.Peer.ipv4(vpc.vpc_cidr_block),
            connection=_ec2.Port.tcp(27017),
            description="Allow DocsDB inbound connetions")

        # Create Security Group for MSSQL Server Instance
        ms_sql_db_sg = _ec2.SecurityGroup(
            self,
            id="msSqlDbSecurityGroup",
            vpc=vpc,
            security_group_name=f"mssql_db_sg_{id}",
            description="Security Group for MSSQL"
        )

        ms_sql_db_sg.add_ingress_rule(
            peer=_ec2.Peer.ipv4(vpc.vpc_cidr_block),
            connection=_ec2.Port.tcp(1433),
            description="Allow MSSQL inbound connetions"
        )

        # Create Security Group for MySQL Server Instance
        my_sql_db_sg = _ec2.SecurityGroup(
            self,
            id="mySqlDbSecurityGroup",
            vpc=vpc,
            security_group_name=f"mysql_db_sg_{id}",
            description="Security Group for MySQL"
        )

        my_sql_db_sg.add_ingress_rule(
            peer=_ec2.Peer.ipv4(vpc.vpc_cidr_block),
            connection=_ec2.Port.tcp(3306),
            description="Allow MySQL inbound connetions"
        )

        # Outputs
        output_0 = core.CfnOutput(
            self,
            "AutomationFrom",
            value=f"{GlobalArgs.SOURCE_INFO}",
            description="To know more about this automation stack, check out our github page."
        )

        output_1 = core.CfnOutput(
            self,
            "SshKeyGenerationStatus",
            value=f"{self.ssh_key_gen_status}",
            description="Ssh Key Generation Status. Check SSM Parameter 'mystique-automation-ssh-key' for key material(private key)"
        )
        output_2 = core.CfnOutput(
            self,
            "DMSDynamoDBRole",
            value=f"{self.dms_dynamodb_role.role_arn}",
            description="This IAM role should allow AWS DMS to assume and grants access to the DynamoDB tables"
        )
