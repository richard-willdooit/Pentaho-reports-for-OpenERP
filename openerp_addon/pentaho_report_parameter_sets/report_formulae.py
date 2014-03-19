# -*- encoding: utf-8 -*-

from datetime import date, datetime, timedelta
from dateutil import parser
import pytz
import json

from openerp.osv import orm, fields
from openerp.tools import DEFAULT_SERVER_DATE_FORMAT, DEFAULT_SERVER_DATETIME_FORMAT
from openerp.tools.translate import _

from openerp.addons.pentaho_reports.java_oe import *

PARAM_XXX_FORMULA = 'param_%03i_formula'

FORMULA_OPERATORS = '+-*/'
QUOTES = "'" + '"'
DIGITS = '1234567890'

FTYPE_TIMEDELTA = 'tdel'
FUNCTION_TYPES = OPENERP_DATA_TYPES + [(FTYPE_TIMEDELTA, 'Time Delta')]

FORMULAE = {'today': {'type': TYPE_TIME,
                      'parameters': [],
                      'call': 'self.localise(cr, uid, datetime.today(), context=context)',
                      },

            'hours': {'type': FTYPE_TIMEDELTA,
                      'parameters': [('hours', (TYPE_INTEGER, TYPE_NUMBER)),
                                     ],
                      'call': 'timedelta(%1)',
                      }
            }

VALUE_CONSTANT = 'constant'
VALUE_VARIABLE = 'variable'
VALUE_UNKNOWN = 'unknown'


def parameter_resolve_formula_column_name(parameters, index):
    return PARAM_XXX_FORMULA % index

def search_string_to_next(s, searching, pointer):
    in_QUOTES = ''
    while pointer < len(s):
        pointer += 1
        if s[pointer-1:pointer] == in_QUOTES:
            in_QUOTES = ''
        elif s[pointer-1:pointer] in QUOTES:
            in_QUOTES = s[pointer-1:pointer]
        elif not in_QUOTES and s[pointer-1:pointer] in searching:
            return s[:pointer-1]
    return s

def discard_firstchar(s):
    return s[1:].strip()

def establish_type(s, known_variables):
    if len(s) >= 2 and s[:1] in QUOTES and s[-1:] == s[:1]:
        return TYPE_STRING, VALUE_CONSTANT
    if len(s) > 0 and s[:1] in DIGITS:
        try:
            i = int(s)
            return TYPE_INTEGER, VALUE_CONSTANT
        except ValueError:
            pass
        try:
            f = float(s)
            return TYPE_NUMBER, VALUE_CONSTANT
        except ValueError:
            pass
    return known_variables.get(s, {}).get('type', None), s in known_variables and VALUE_VARIABLE or VALUE_UNKNOWN

def retrieve_value(s, known_variables):
    if len(s) >= 2 and s[:1] in QUOTES and s[-1:] == s[:1]:
        return s[1:-1]
    if len(s) > 0 and s[:1] in DIGITS:
        try:
            i = int(s)
            return i
        except ValueError:
            pass
        try:
            f = float(s)
            return f
        except ValueError:
            pass
    result = known_variables[s]['calced_value']
    if known_variables[s]['type'] == TYPE_DATE:
        result = datetime.strptime(result, DEFAULT_SERVER_DATETIME_FORMAT).date()
    if known_variables[s]['type'] == TYPE_TIME:
        result = datetime.strptime(result, DEFAULT_SERVER_DATETIME_FORMAT)
    return result


class parameter_set_formula(orm.Model):
    _name = 'ir.actions.report.set.formula'
    _description = 'Pentaho Report Parameter Set Formulae'

    _columns = {
                }


    def split_formula(self, cr, uid, formula_str, known_variables, context=None):
        """
        returns a list of operands.
        each operand is a dictionary:
            operator:        +-*/
            error:           string of one error in operand
            value:           an string with quotes, a number, or a variable
                             !!! undefined if it is a function
            returns:         type that this operand returns
            function_name:
            function_params: list of quoted strings, numbers, or variables
        """
        result = []

        operand = search_string_to_next(formula_str, FORMULA_OPERATORS, 1)
        formula_str = formula_str.replace(operand,'',1).strip()

        operand_dictionary = {'operator': operand[0:1],
                              'error': False,
                              }
        operand = discard_firstchar(operand)
        if operand:
            value_gives_type, value_is_type = establish_type(operand, known_variables)
            if value_is_type != VALUE_UNKNOWN:
                operand_dictionary['value'] = operand
                operand_dictionary['returns'] = value_gives_type
            else:
                function_name = search_string_to_next(operand, '(', 0)
                operand = operand.replace(function_name,'',1).strip()

                if not operand:
                    operand_dictionary['value'] = function_name
                    operand_dictionary['returns'] = None
                else:
                    operand_dictionary['function_name'] = function_name
                    operand_dictionary['returns'] = FORMULAE.get(function_name,{}).get('type', None)
                    operand_dictionary['function_params'] = []
                    operand = discard_firstchar(operand)
                    while operand and operand[0:1] != ')':
                        if len(operand_dictionary['function_params']) > 0:
                            # don't strip first character for first parameter, after this, the first character is the ','
                            operand = discard_firstchar(operand)
                        function_param = search_string_to_next(operand, ',)', 0)
                        operand = operand.replace(function_param,'',1).strip()
                        operand_dictionary['function_params'].append(function_param)

                    if len(operand_dictionary['function_params']) != len(FORMULAE.get(function_name, {}).get('parameters', [])):
                        operand_dictionary['error'] = _('Parameter count mismatch for formula %s: Expecting %s but got %s') % (function_name,
                                                                                                                               len(FORMULAE.get(function_name, {}).get('parameters', [])),
                                                                                                                               len(operand_dictionary['function_params']),
                                                                                                                               )
                    else:
                        for index in range(0, len(operand_dictionary['function_params'])):
                            function_param = operand_dictionary['function_params'][index]
                            value_gives_type, value_is_type = establish_type(function_param, known_variables)
                            if value_is_type == VALUE_UNKNOWN:
                                operand_dictionary['error'] = _('Parameter value unknown for formula "%s": %s') % (function_name, function_param)
                                break
                            if not value_gives_type in FORMULAE.get(function_name, {}).get('parameters', [])[index][1]:
                                operand_dictionary['error'] = _('Parameter type mismatch for formula "%s" parameter %s: %s') % (function_name, index+1, function_param)
                                break

                    if operand:
                        # remove ')'
                        operand = discard_firstchar(operand)
                        if operand:
                            operand_dictionary['error'] = _('Unable to interpret beyond formula "%s": %s') % (function_name, operand)
                    else:
                        operand_dictionary['error'] = _('Formula not closed: %s') % (function_name)

        if not operand_dictionary['returns']:
            operand_dictionary['error'] = _('Operand unknown or badly formed: %s' % (operand_dictionary.get('value') or operand_dictionary.get('function_name'),))

        result.append(operand_dictionary)
        if formula_str:
            result.extend(self.split_formula(cr, uid, formula_str, known_variables, context=context))

        return result

    def operand_type_check(self, cr, uid, operand_dictionary, valid_operators, valid_types, context=None):
        if not operand_dictionary['error']:
            if not operand_dictionary['returns'] in valid_types:
                operand_dictionary['error'] = _('Operand of this type not permitted for this type of parameter: %s' % (operand_dictionary.get('value') or operand_dictionary.get('function_name'),))
            elif not operand_dictionary['operator'] in valid_operators: 
                operand_dictionary['error'] = _('Operator of this type not permitted for parameter: %s' % (operand_dictionary.get('value') or operand_dictionary.get('function_name'),))

    def eval_operand(self, cr, uid, operand_dictionary, known_variables, context=None):
        if operand_dictionary.get('value'):
            return operand_dictionary['operator'], operand_dictionary['returns'], retrieve_value(operand_dictionary['value'], known_variables)

        formula_definition = FORMULAE[operand_dictionary['function_name']]

        variables = {}
        eval_string = formula_definition['call']
        for index in range(0, len(formula_definition['parameters'])):
            variables[index] = retrieve_value(operand_dictionary['function_params'][index], known_variables)
            value = 'variables[%s]' % (index,)

            if formula_definition['parameters'][index][0]:
                value = formula_definition['parameters'][index][0] + '=' + value

            eval_string = eval_string.replace('%%%s' % (index+1,), value)
        return operand_dictionary['operator'], operand_dictionary['returns'], eval(eval_string)

    def check_string_formula(self, cr, uid, operands, context=None):
        # every parameter must be a '+'
        # every standard parameter type can be accepted as they will be converted to strings, and appended...
        for operand_dictionary in operands:
            self.operand_type_check(cr, uid, operand_dictionary, '+', (TYPE_STRING, TYPE_BOOLEAN, TYPE_INTEGER, TYPE_NUMBER, TYPE_DATE, TYPE_TIME), context=context)

    def eval_string_formula(self, cr, uid, operands, known_variables, expected_type, context=None):
        def to_string(value, op_type):
            return op_type in (TYPE_STRING) and value or str(value)

        result_string = ''
        for operand_dictionary in operands:
            op_op, op_type, op_result = self.eval_operand(cr, uid, operand_dictionary, known_variables, context=context)
            result_string += to_string(op_result, op_type)
        return result_string

    def check_boolean_formula(self, cr, uid, operands, context=None):
        # only 1 parameter allowed
        # must be a '+'
        # every standard parameter type can be accepted as they will be converted to booleans using standard Python boolean rules
        self.operand_type_check(cr, uid, operands[0], '+', (TYPE_STRING, TYPE_BOOLEAN, TYPE_INTEGER, TYPE_NUMBER, TYPE_DATE, TYPE_TIME), context=context)
        for operand_dictionary in operands[1:]:
            operand_dictionary['error'] = _('Excess operands not permitted for for this type of parameter: %s' % (operand_dictionary.get('value') or operand_dictionary.get('function_name'),))

    def eval_boolean_formula(self, cr, uid, operands, known_variables, expected_type, context=None):
        def to_boolean(value, op_type):
            return op_type in (TYPE_BOOLEAN) and value or bool(value)

        op_op, op_type, op_result = self.eval_operand(cr, uid, operands[0], known_variables, context=context)
        result_bool += to_boolean(op_result, op_type)
        return result_bool

    def check_numeric_formula(self, cr, uid, operands, context=None):
        # every parameter type is fine
        # only integers and numerics can be accepted
        for operand_dictionary in operands:
            self.operand_type_check(cr, uid, operand_dictionary, '+-*/', (TYPE_INTEGER, TYPE_NUMBER), context=context)

    def eval_numeric_formula(self, cr, uid, operands, known_variables, expected_type, context=None):
        # all parameters have been validated as integers or numbers already, so this is redundant.
        def to_number(value, op_type):
            return op_type in (TYPE_INTEGER, TYPE_NUMBER) and value or float(value)

        result_num = 0.0
        for operand_dictionary in operands:
            op_op, op_type, op_result = self.eval_operand(cr, uid, operand_dictionary, known_variables, context=context)
            result_num = eval('result_num %s to_number(op_result, op_type)' % (op_op,))
        return expected_type == TYPE_INTEGER and int(result_num) or result_num

    def check_date_formula(self, cr, uid, operands, context=None):
        # first parameter must be a date or datetime and a '+'
        self.operand_type_check(cr, uid, operands[0], '+', (TYPE_DATE, TYPE_TIME), context=context)
        # others must be all time_deltas
        for operand_dictionary in operands[1:]:
            self.operand_type_check(cr, uid, operand_dictionary, '+-', (FTYPE_TIMEDELTA), context=context)

    def eval_date_formula(self, cr, uid, operands, known_variables, expected_type, context=None):
        import ipdb
        ipbd.set_trace()
        # all parameters have been validated as correct type, so these are redundant - if it errors, then we have a coding problem in the formula checks...
        def to_date(value, op_type):
            return op_type in (TYPE_DATE, TYPE_TIME) and value or datetime.now()
        def to_timedelta(value, op_type):
            return op_type in (FTYPE_TIMEDELTA) and value or timedelta()

        op_op, op_type, op_result = self.eval_operand(cr, uid, operands[0], known_variables, context=context)
        result_dtm = op_result
        for operand_dictionary in operands[1:]:
            op_op, op_type, op_result = self.eval_operand(cr, uid, operand_dictionary, known_variables, context=context)
            result_dtm = eval('result_dtm %s to_timedelta(op_result, op_type)' % (op_op,))
        return expected_type == TYPE_DATE and result_dtm.strftime(DEFAULT_SERVER_DATE_FORMAT) or result_dtm.strftime(DEFAULT_SERVER_DATETIME_FORMAT)

    def localise(self, cr, uid, value, context=None):
        if context is None:
            context = {}
        return value

    def validate_formula(self, cr, uid, formula_str, expected_type, known_variables, context=None):
        """
        returns a dictionary
            error:            string of one error in formula
            operands:         list of operand dictionaries
            dependent_params: list of variables needed for this formula to calculate
        """
        result = {'error': False}

        formula_str = formula_str.strip()
        if formula_str:
            if formula_str[0:1] == '=':
                formula_str = discard_firstchar(formula_str)

            if not formula_str or not formula_str[0:1] in FORMULA_OPERATORS:
                formula_str = '+' + formula_str

            operands = self.split_formula(cr, uid, formula_str, known_variables, context=context)
            result['operands'] = operands

            if expected_type == 'TYPE_STRING':
                self.check_string_formula(cr, uid, operands, expected_type, context=context)
            if expected_type == 'TYPE_BOOLEAN':
                self.check_boolean_formula(cr, uid, operands, expected_type, context=context)
            if expected_type in ('TYPE_INTEGER', 'TYPE_NUMBER'):
                self.check_numeric_formula(cr, uid, operands, expected_type, context=context)
            if expected_type in ('TYPE_DATE', 'TYPE_TIME'):
                self.check_date_formula(cr, uid, operands, expected_type, context=context)

            for operand in operands:
                if operand['error']:
                    result['error'] = operand['error']
                    break

            if not result['error']:
                result['dependent_values'] = []
                for operand_dictionary in operands:
                    if operand_dictionary.get('value') in known_variables:
                        result['dependent_values'].append(operand_dictionary['value'])
                    for function_param in operand_dictionary.get('function_params',[]):
                        if function_param in known_variables:
                            result['dependent_values'].append(function_param)

        return result

    def evaluate_formula(self, cr, uid, formula_dict, expected_type, known_variables, context=None):
        if expected_type == TYPE_STRING:
            return self.eval_string_formula(cr, uid, formula_dict['operands'], known_variables, expected_type, context=context)
        if expected_type == TYPE_BOOLEAN:
            return self.eval_boolean_formula(cr, uid, formula_dict['operands'], known_variables, expected_type, context=context)
        if expected_type in (TYPE_INTEGER, TYPE_NUMBER):
            return self.eval_numeric_formula(cr, uid, formula_dict['operands'], known_variables, expected_type, context=context)
        if expected_type in (TYPE_DATE, TYPE_TIME):
            return self.eval_numeric_formula(cr, uid, formula_dict['operands'], known_variables, expected_type, context=context)
        return None