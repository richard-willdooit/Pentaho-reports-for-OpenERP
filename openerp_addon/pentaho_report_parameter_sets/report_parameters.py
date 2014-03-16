# -*- encoding: utf-8 -*-

from datetime import date, datetime
from dateutil import parser
import pytz
import json

from lxml import etree

from openerp.osv import orm, fields
from openerp.tools import DEFAULT_SERVER_DATE_FORMAT, DEFAULT_SERVER_DATETIME_FORMAT
from openerp.tools.translate import _

from openerp.addons.pentaho_reports.java_oe import *
from openerp.addons.pentaho_reports.core import VALID_OUTPUT_TYPES

from report_formulae import *


def conv_to_number(s):
    if type(s) in (str, unicode) and s == "":
        s = 0
    try:
        f = float(s)
        return f
    except ValueError:
        return 0

def conv_to_date(s):
    result = None
    if s:
        try:
            result = datetime.strptime(s, DEFAULT_SERVER_DATE_FORMAT).date()
        except ValueError:
            try:
                result = parser.parse(s, fuzzy=True, dayfirst=True).date()
            except ValueError:
                result = None
    return result and result.strftime(DEFAULT_SERVER_DATE_FORMAT)

def conv_to_datetime(s):
    result = None
    if s:
        try:
            result = datetime.strptime(s, DEFAULT_SERVER_DATE_FORMAT).date()
        except ValueError:
            try:
                result = parser.parse(s, fuzzy=True, dayfirst=True)
            except ValueError:
                result = None
    return result and result.strftime(DEFAULT_SERVER_DATETIME_FORMAT)


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

    def parameters_to_dictionary(self, cr, uid, id, parameters, x2m_unique_id, context=None):
        detail_obj = self.pool.get('ir.actions.report.set.detail')
        wiz_obj = self.pool.get('ir.actions.report.promptwizard')

        result = {}
        parameters_to_load = self.browse(cr, uid, id, context=context)

        arbitrary_force_calc = False
        known_variables = {}
        for index in range(0, len(parameters)):
            known_variables[parameters[index]['variable']] = {'type': parameters[index]['type'],
                                                              'calculated': False,
                                                              }

        while True:
            any_calculated_this_time = False
            still_needed_dependent_values = []
            for index in range(0, len(parameters)):
                if not known_variables[parameters[index]['variable']]['calculated']:
                    for detail in parameters_to_load.detail_ids:
                        if detail.variable == parameters[index]['variable']:
                            expected_type = parameters[index]['type']
                            # check expected_type as TYPE_DATE / TYPE_TIME, etc... and validate display_value is compatible with it

                            if not detail.calc_formula:
                                calculate_formula_this_time = False
                                override_formula_this_time = True

                            else:
                                formula = validate_formula(detail.calc_formula, expected_type, known_variables, fuzzy=True)

                                # if there is an error, we want to ignore the formula and use standard processing of the value...
                                # if we are arbitrarily forcing a value, then also use standard processing of the value...
                                # if no error, then try to evaluate the formula
                                if formula['error'] or detail.variable == arbitrary_force_calc:
                                    calculate_formula_this_time = False
                                    override_formula_this_time = True

                                else:
                                    calculate_formula_this_time = True
                                    override_formula_this_time = False

                                    for dv in formula['dependent_values']:
                                        if not known_variables[dv].calculated:
                                            calculate_formula_this_time = False
                                            still_needed_dependent_values.append(dv)

                            if calculate_formula_this_time or override_formula_this_time:
                                if calculate_formula_this_time:
                                    xxxxxxxxx

                                if ignore_formula_this_time:
                                    if parameter_can_2m(parameters, index):
                                        value = detail.display_value
                                    else:
                                        value = detail_obj.validate_display_value(cr, uid, detail, expected_type, context=context)
                                    result[parameter_resolve_column_name(parameters, index)] = wiz_obj.encode_wizard_value(cr, uid, parameters, index, x2m_unique_id, value, enc_json=True, context=context)

                                result[parameter_resolve_formula_column_name(parameters, index)] = detail.calc_formula

                                known_variables[parameters[index]['variable']]['calculated'] = True
                                any_calculated_this_time = True

                            break

            # if there are no outstanding calculations, then break
            if not still_needed_dependent_values:
                break

            # if some were calculated, and there are outstanding calculations, then loop again
            # if none were calculated, then force a calculation to break potential deadlocks of dependent values
            if any_calculated_this_time:
                arbitrary_force_calc = False
            else:
                arbitrary_force_calc = still_needed_dependent_values[0]
        return result


class parameter_set_detail(orm.Model):
    _name = 'ir.actions.report.set.detail'
    _description = 'Pentaho Report Parameter Set Detail'

    _columns = {'header_id': fields.many2one('ir.actions.report.set.header', 'Parameter Set', ondelete='cascade', readonly=True),
                'variable': fields.char('Variable Name', size=64, readonly=True),
                'label': fields.char('Label', size=64, readonly=True),
                'counter': fields.integer('Parameter Number', readonly=True),
                'type': fields.selection(OPENERP_DATA_TYPES, 'Data Type', readonly=True),
                'display_value': fields.text('Value'),
                'calc_formula': fields.char('Formula'),
                }

    _order = 'counter'

    def validate_display_value(self, cr, uid, detail, expected_type, context=None):
        result = False
        # Be forgiving as possible here for possible parameter type changes
        if expected_type == TYPE_STRING:
            result = detail.display_value
        if expected_type == TYPE_BOOLEAN:
            result = detail.display_value and detail.display_value.lower() in ('true', 't', '1', 'yes', 'y')
        if expected_type == TYPE_INTEGER:
            result = int(conv_to_number(detail.display_value))
        if expected_type == TYPE_NUMBER:
            result = conv_to_number(detail.display_value)
        if expected_type == TYPE_DATE:
            result = conv_to_date(detail.display_value)
        if expected_type == TYPE_TIME:
            result = conv_to_datetime(detail.display_value)
        return result


class report_prompt_with_parameter_set(orm.TransientModel):
    _inherit = 'ir.actions.report.promptwizard'

    _columns = {
                'has_params': fields.boolean('Has Parameters...'),
                'parameter_set_id': fields.many2one('ir.actions.report.set.header', 'Parameter Set'),
                }

    def __init__(self, pool, cr):
        """ Dynamically add columns."""

        super(report_prompt_with_parameter_set, self).__init__(pool, cr)

        for counter in range(0, MAX_PARAMS):
            field_name = PARAM_XXX_FORMULA % counter
            self._columns[field_name] = fields.char('Formula')

    def default_get(self, cr, uid, fields, context=None):
        result = super(report_prompt_with_parameter_set, self).default_get(cr, uid, fields, context=context)
        result['has_params'] = self.pool.get('ir.actions.report.set.header').search(cr, uid, [('report_action_id', '=', result['report_action_id'])], context=context, count=True) > 0

        parameters = json.loads(result.get('parameters_dictionary', []))
        for index in range(0, len(parameters)):
            result[parameter_resolve_formula_column_name(parameters, index)] = ''

        return result

    def fvg_add_one_parameter(self, cr, uid, result, selection_groups, parameters, index, first_parameter, context=None):

        def add_subelement(element, type, **kwargs):
            sf = etree.SubElement(element, type)
            for k, v in kwargs.iteritems():
                if v is not None:
                    sf.set(k, v)

        super(report_prompt_with_parameter_set, self).fvg_add_one_parameter(cr, uid, result, selection_groups, parameters, index, first_parameter, context=context)

        field_name = parameter_resolve_formula_column_name(parameters, index)
        result['fields'][field_name] = {'selectable': self._columns[field_name].selectable,
                                        'type': self._columns[field_name]._type,
                                        'size': self._columns[field_name].size,
                                        'string': self._columns[field_name].string,
                                        'views': {}
                                        }

        for sel_group in selection_groups:
            add_subelement(sel_group,
                           'field',
                           name = field_name,
                           modifiers = '{"invisible": true}',
                           )

    def onchange_parameter_set_id(self, cr, uid, ids, parameter_set_id, parameters_dictionary, x2m_unique_id, context=None):
        result = {'value': {}}

        if not parameter_set_id:
            xxxxx
        else:
            parameters = json.loads(parameters_dictionary)
            result['value'].update(self.pool.get('ir.actions.report.set.header').parameters_to_dictionary(cr, uid, parameter_set_id, parameters, x2m_unique_id, context=context))

        return result
