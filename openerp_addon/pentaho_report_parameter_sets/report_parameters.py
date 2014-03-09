# -*- encoding: utf-8 -*-

from datetime import date, datetime
import pytz
import json

from openerp.osv import orm, fields
from openerp.tools import DEFAULT_SERVER_DATE_FORMAT, DEFAULT_SERVER_DATETIME_FORMAT
from openerp.tools.translate import _

from openerp.addons.pentaho_reports.java_oe import *
from openerp.addons.pentaho_reports.core import VALID_OUTPUT_TYPES


class parameter_set_header(orm.Model):
    _name = 'ir.actions.report.set.header'
    _description = 'Pentaho Report Parameter Set Header'

    _columns = {
                'name': fields.char('Parameter Set Description', size=64),
                'report_action_id': fields.many2one('ir.actions.report.xml', 'Report Name', readonly=True),
                'output_type': fields.selection(VALID_OUTPUT_TYPES, 'Report format', help='Choose the format for the output'),
                'parameters_dictionary': fields.text('parameter dictionary'), # Not needed, but helpful if we build a parameter set master view...
                'detail_ids': fields.one2many('ir.actions.report.set.detail', 'header_id', 'Parameter Details'),
                }


class parameter_set_parameters(orm.Model):
    _name = 'ir.actions.report.set.detail'
    _description = 'Pentaho Report Parameter Set Detail'

    _columns = {'header_id': fields.many2one('ir.actions.report.set.header', 'Parameter Set', ondelete='cascade', readonly=True),
                'variable': fields.char('Variable Name', size=64, readonly=True),
                'label': fields.char('Label', size=64, readonly=True),
                'counter': fields.integer('Parameter Number', readonly=True),
                'type': fields.selection(OPENERP_DATA_TYPES, 'Data Type', readonly=True),
                'display_value': fields.char('Value', size=64),
                }

    _order = 'counter'


class report_prompt_with_parameter_set(orm.TransientModel):
    _inherit = 'ir.actions.report.promptwizard'

    _columns = {
                'has_params': fields.boolean('Has Parameters...'),
                'parameter_set_id': fields.many2one('ir.actions.report.set.header', 'Parameter Set'),
                }

    def default_get(self, cr, uid, fields, context=None):
        result = super(report_prompt_with_parameter_set, self).default_get(cr, uid, fields, context=context)
        result['has_params'] = self.pool.get('ir.actions.report.set.header').search(cr, uid, [('report_action_id', '=', result['report_action_id'])], context=context, count=True) > 0
        return result

    def onchange_parameter_set_id(self, cr, uid, ids, parameter_set_id, parameters_dictionary, context=None):
        result = {'value': {}}

        if not parameter_set_id:
            xxxxx
        else:
            parameters = json.loads(parameters_dictionary)
            parameters_to_load = self.pool.get('ir.actions.report.set.header').browse(cr, uid, parameter_set_id, context=context)
            for index in range(0, len(parameters)):
                for parameter in parameters_to_load.detail_ids:
                    if parameter.variable == parameters[index]['variable']:
                        expected_type = parameters[index]['type']
                        # check expected_type as TYPE_DATE / TYPE_TIME, etc... and validate display_value is compatible with it

                        result['value'][PARAM_VALUES[expected_type]['value'] % index] = parameter.display_value
                        break

        return result
