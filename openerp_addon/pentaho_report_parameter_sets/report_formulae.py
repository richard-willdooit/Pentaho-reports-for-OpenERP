# -*- encoding: utf-8 -*-

from datetime import date, datetime
from dateutil import parser
import pytz
import json

from openerp.osv import orm, fields
from openerp.tools import DEFAULT_SERVER_DATE_FORMAT, DEFAULT_SERVER_DATETIME_FORMAT
from openerp.tools.translate import _

PARAM_XXX_FORMULA = 'param_%03i_formula'

def parameter_resolve_formula_column_name(parameters, index):
    return PARAM_XXX_FORMULA % index
