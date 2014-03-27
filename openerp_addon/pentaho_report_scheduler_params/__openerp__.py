# -*- coding: utf-8 -*-
# v7.0 - Release
{
    'name': 'Report Scheduler Parameters',
    "version": "0.1",
    "author": "WillowIT Pty Ltd",
    'website': 'http://www.willowit.com.au',
    "category": "Reporting subsystems",
    'summary':'Report Scheduler with Parameter Sets',
    'images': [],
    'depends': ['pentaho_report_parameter_sets',
                'pentaho_report_scheduler',
                ],
    'description': """
Report Scheduler with Parameter Sets
====================================
This module provides extends the report scheduler and allows the scheduling of Pentaho reports that have parameter
sets defined.

The desired parameter set to be run needs to be chosen in the report schedule group.
    """,
    'data': [
             'scheduler_view.xml',
            ],
    'demo': [],
    'test': [],
    'installable': True,
    'auto_install': False,
    'application': False,
}
