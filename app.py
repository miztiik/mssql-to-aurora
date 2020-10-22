#!/usr/bin/env python3

from aws_cdk import core

from mssql_to_aurora.mssql_to_aurora_stack import MssqlToAuroraStack


app = core.App()
MssqlToAuroraStack(app, "mssql-to-aurora")

app.synth()
