# -*- encoding: utf-8 -*-
# v7.0 - Release
{
    "name": "Pentaho Report Parameter Saving",
    "description": """
Pentaho - Report Parameter Saving
=================================
This module builds on the OpenERP Pentaho Report functionality by allowing sets of prompted parameters to be stored
and retrieved.

    """,
    "version": "0.1",
    "author": "WillowIT Pty Ltd",
    "website": "http://www.willowit.com.au/",
    "depends": ["pentaho_reports"],
    "category": "Reporting subsystems",
    "data": [
             "security/ir.model.access.csv",
             "wizard/store_parameters.xml",
             "report_prompt.xml",
             ],
    "installable": True,
    "active": False
}
