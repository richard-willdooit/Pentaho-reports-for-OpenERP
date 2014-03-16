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

FORMULAE = {'today': {'type': TYPE_TIME,
                      'num_params': 0,
                      'param_types': [],
                      'call': 'datetime.today()'
                      },

            'hours': {'type': FTYPE_TIMEDELTA,
                      'num_params': 1,
                      'param_types': [(TYPE_INTEGER, TYPE_NUMBER),
                                      ],
                      'call': 'timedelta(hours=%s)'
                      }
            }


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
        return TYPE_STRING
    if len(s) > 1 and s[:1] in DIGITS:
        try:
            i = int(s)
            return TYPE_INTEGER
        except ValueError:
            pass
        try:
            f = float(s)
            return TYPE_NUMBER
        except ValueError:
            pass
    return known_variables.get(s, {}).get('type', None)


def split_formula(formula, known_variables):
    result = []

    operand = search_string_to_next(formula, FORMULA_OPERATORS, 1)
    formula = formula.replace(operand,'',1).strip()

    operand_dictionary = {'operator': operand[0:1],
                          'error': False,
                          }
    operand = discard_firstchar(operand)
    if operand:
        if operand[0:1] in (QUOTES + DIGITS):
            operand_dictionary['value'] = operand
            operand_dictionary['returns'] = establish_type(operand, known_variables)
        else:
            function_name = search_string_to_next(operand, '(', 0)
            operand = operand.replace(function_name,'',1).strip()

            if not operand:
                operand_dictionary['value'] = function_name
                operand_dictionary['returns'] = establish_type(operand, known_variables)
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

                if len(operand_dictionary['function_params']) != FORMULAE.get(function_name, {}).get('num_params', 0):
                    operand_dictionary['error'] = _('Parameter count mismatch for formula %s: Expecting %s but got %s') % (function_name,
                                                                                                                           FORMULAE.get(function_name, {}).get('num_params', 0),
                                                                                                                           len(operand_dictionary['function_params']),
                                                                                                                           )
                else:
                    for index in range(0, len(operand_dictionary['function_params'])):
                        function_param = operand_dictionary['function_params'][index]
                        parameter_type = establish_type(function_param, known_variables)
                        if not parameter_type:
                            operand_dictionary['error'] = _('Parameter value unknown for formula %s: %s') % (function_name, function_param)
                            break
                        if not parameter_type in FORMULAE.get(function_name, {}).get('param_types', []):
                            operand_dictionary['error'] = _('Parameter type mismatch for formula %s parameter %s: %s') % (function_name, index+1, function_param)
                            break

                if operand:
                    # remove ')'
                    operand = discard_firstchar(operand)
                    if operand:
                        operand_dictionary['error'] = _('Unable to interpret beyond formula %s: %s') % (function_name, operand)
                else:
                    operand_dictionary['error'] = _('Formula not closed: %s') % (function_name)

    if not operand_dictionary['returns']:
        operand_dictionary['error'] = _('Operand unknown or badly formed: %s' % (operand_dictionary.get('value') or operand_dictionary.get('function_name'),))

    result.append(operand_dictionary)
    if formula:
        result.extend(split_formula(formula, known_variables))

    return result


def operand_type_check(operand_dictionary, valid_operators, valid_types):
    if not operand_dictionary['returns'] in valid_types:
        operand_dictionary['error'] = _('Operand of this type not permitted for this type of parameter: %s' % (operand_dictionary.get('value') or operand_dictionary.get('function_name'),))
        return
    if not operand_dictionary['operator'] in valid_operators: 
        operand_dictionary['error'] = _('Operator of this type not permitted for parameter: %s' % (operand_dictionary.get('value') or operand_dictionary.get('function_name'),))
        return

def check_string_formula(operands):
    # every parameter must be a '+'
    # every standard parameter type can be accepted as they will be converted to strings, and appended...
    for operand_dictionary in operands:
        operand_type_check(operand_dictionary, '+', (TYPE_STRING, TYPE_BOOLEAN, TYPE_INTEGER, TYPE_NUMBER, TYPE_DATE, TYPE_TIME))

def check_boolean_formula(operands):
    # only 1 parameter allowed
    # must be a '+'
    # every standard parameter type can be accepted as they will be converted to booleans using standard Python boolean rules
    operand_dictionary = operands[0]
    operand_type_check(operand_dictionary, '+', (TYPE_STRING, TYPE_BOOLEAN, TYPE_INTEGER, TYPE_NUMBER, TYPE_DATE, TYPE_TIME))
    for operand_dictionary in operands[1:]:
        operand_dictionary['error'] = _('Excess operands not permitted for for this type of parameter: %s' % (operand_dictionary.get('value') or operand_dictionary.get('function_name'),))

def check_numeric_formula(operands):
    # every parameter type is fine
    # only integers and numerics can be accepted
    for operand_dictionary in operands:
        operand_type_check(operand_dictionary, '+-*/', (TYPE_INTEGER, TYPE_NUMBER))

def check_date_formula(operands):
    # first parameter must be a date or datetime and a '+'
    operand_dictionary = operands[0]
    operand_type_check(operand_dictionary, '+', (TYPE_DATE, TYPE_TIME))
    # others must be all time_deltas
    for operand_dictionary in operands[1:]:
        operand_type_check(operand_dictionary, '+-', (FTYPE_TIMEDELTA))

def validate_formula(formula, expected_type, known_variables, fuzzy=False):
    result = {'error': False}

    formula = formula.strip()
    if formula:
        if formula[0:1] == '=':
            formula = discard_firstchar(formula)

        if not formula or not formula[0:1] in FORMULA_OPERATORS:
            formula = '+' + formula

        operands = split_formula(formula, known_variables)
        result['operands'] = operands

        for operand in operands:
            if operand['error'] and not result['error']:
                result['error'] = operand['error']

        if not result['error']:
            if expected_type == 'TYPE_STRING':
                check_string_formula(operands)
            if expected_type == 'TYPE_BOOLEAN':
                check_boolean_formula(operands)
            if expected_type in ('TYPE_INTEGER', 'TYPE_NUMBER'):
                check_numeric_formula(operands)
            if expected_type in ('TYPE_DATE', 'TYPE_TIME'):
                check_date_formula(operands)

            for operand in operands:
                if operand['error'] and not result['error']:
                    result['error'] = operand['error']

        if not result['error']:
            result['dependent_params'] = []
            for operand_dictionary in operands:
                if operand_dictionary.get('value') in known_variables:
                    result['dependent_values'].append(operand_dictionary['value'])
                for function_param in operand_dictionary.get('function_params',[]):
                    if function_param in known_variables:
                        result['dependent_values'].append(function_param)

    return result