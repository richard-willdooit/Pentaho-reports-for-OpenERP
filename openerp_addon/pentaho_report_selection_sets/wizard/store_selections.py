# -*- encoding: utf-8 -*-

import json

from openerp.osv import fields, orm
from openerp.tools.translate import _

from openerp.addons.pentaho_reports.core import VALID_OUTPUT_TYPES
from openerp.addons.pentaho_reports.java_oe import OPENERP_DATA_TYPES, parameter_resolve_column_name

from ..report_formulae import *


class store_selections_wizard(orm.TransientModel):
    _name = "ir.actions.store.selections.wiz"
    _description = "Store Report Selections Wizard"

    _columns = {
                'existing_selectionset_id': fields.many2one('ir.actions.report.set.header', 'Selection Set', ondelete='set null'),
                'name': fields.char('Selection Set Description', size=64, required=True),
                'report_action_id': fields.many2one('ir.actions.report.xml', 'Report Name', readonly=True),
                'output_type': fields.selection(VALID_OUTPUT_TYPES, 'Report format', help='Choose the format for the output'),
                'parameters_dictionary': fields.text('parameter dictionary'),
                'detail_ids': fields.one2many('ir.actions.store.selections.detail.wiz', 'header_id', 'Selection Details'),
                'def_user_ids': fields.many2many('res.users', 'ir_actions_store_selections_def_user_rel', 'header_id', 'user_id', 'Users (Default)'),
                'def_group_ids': fields.many2many('res.groups', 'ir_actions_store_selections_def_group_rel', 'header_id', 'group_id', 'Groups (Default)'),
                'passing_wizard_id': fields.many2one('ir.actions.report.promptwizard', 'Screen wizard - kept for "Cancel" button')
                }

    def default_get(self, cr, uid, fields, context=None):
        if context is None:
            context = {}
        if not context.get('active_id'):
            raise orm.except_orm(_('Error'), _('No active id passed.'))

        screen_wizard_obj = self.pool.get('ir.actions.report.promptwizard')
        detail_obj = self.pool.get('ir.actions.report.set.detail')
        screen_wizard = screen_wizard_obj.browse(cr, uid, context['active_id'])

        parameters_dictionary = json.loads(screen_wizard.parameters_dictionary)

        res = super(store_selections_wizard, self).default_get(cr, uid, fields, context=context)
        res.update({'existing_selectionset_id': screen_wizard.selectionset_id.id,
                    'name': screen_wizard.selectionset_id and screen_wizard.selectionset_id.name or '',
                    'report_action_id': screen_wizard.report_action_id.id,
                    'output_type': screen_wizard.output_type,
                    'parameters_dictionary': screen_wizard.parameters_dictionary,
                    'detail_ids': [],
                    'def_user_ids': [],
                    'def_group_ids': [],
                    'passing_wizard_id': screen_wizard.id,
                    })

        for index in range(0, len(parameters_dictionary)):
            res['detail_ids'].append((0, 0, {'variable': parameters_dictionary[index]['variable'],
                                             'label': parameters_dictionary[index]['label'],
                                             'counter': index,
                                             'type': parameters_dictionary[index]['type'],
                                             'x2m': parameter_can_2m(parameters_dictionary, index),
                                             'display_value': detail_obj.wizard_value_to_display(cr, uid, getattr(screen_wizard, parameter_resolve_column_name(parameters_dictionary, index)), parameters_dictionary, index, context=context),
                                             'calc_formula': getattr(screen_wizard, parameter_resolve_formula_column_name(parameters_dictionary, index)),
                                             }))

        if screen_wizard.selectionset_id:
            res['def_user_ids'] = [(6, 0, [u.id for u in screen_wizard.selectionset_id.def_user_ids])]
            res['def_group_ids'] = [(6, 0, [g.id for g in screen_wizard.selectionset_id.def_group_ids])]

        return res

    def button_store_new(self, cr, uid, ids, context=None):
        return self.button_store(cr, uid, ids, replace=False, context=context)

    def button_store_replace(self, cr, uid, ids, context=None):
        return self.button_store(cr, uid, ids, replace=True, context=context)

    def button_store(self, cr, uid, ids, replace=True, context=None):
        header_obj = self.pool.get('ir.actions.report.set.header')
        detail_obj = self.pool.get('ir.actions.report.set.detail')

        for wizard in self.browse(cr, uid, ids, context=context):
            clash_ids = header_obj.search(cr, uid, [('name', '=', wizard.name)], context=context)
            if clash_ids and (not replace or len(clash_ids) > 1 or clash_ids[0] != wizard.existing_selectionset_id.id):
                # We enforce this so that users can uniquely identify a selection set.
                raise orm.except_orm(_('Error'), _('Selection Sets must have unique names across all reports.'))

            vals = {'name': wizard.name,
                    'report_action_id': wizard.report_action_id.id,
                    'output_type': wizard.output_type,
                    'parameters_dictionary': wizard.parameters_dictionary,
                    'detail_ids': [(5,)],
                    'def_user_ids': [(6, 0, [u.id for u in wizard.def_user_ids])],
                    'def_group_ids': [(6, 0, [g.id for g in wizard.def_group_ids])],
                    }

            if replace and wizard.existing_selectionset_id:
                header_obj.write(cr, uid, [wizard.existing_selectionset_id.id], vals, context=context)
                hdr_id = wizard.existing_selectionset_id.id
            else:
                hdr_id = header_obj.create(cr, uid, vals, context=context)

            for detail in wizard.detail_ids:
                detail_obj.create(cr, uid, {'header_id': hdr_id,
                                            'variable': detail.variable,
                                            'label': detail.label,
                                            'counter': detail.counter,
                                            'type': detail.type,
                                            'x2m': detail.x2m,
                                            'display_value': detail.display_value,
                                            'calc_formula': detail.calc_formula,
                                            }, context=context)

        new_context = (context or {}).copy()
        new_context['populate_selectionset_id'] = hdr_id
        return {
                'view_mode': 'form',
                'res_model': 'ir.actions.report.promptwizard',
                'type': 'ir.actions.act_window',
                'target': 'new',
                'context': new_context,
                }

    def button_delete(self, cr, uid, ids, context=None):
        header_obj = self.pool.get('ir.actions.report.set.header')
        for wizard in self.browse(cr, uid, ids, context=context):
            if wizard.existing_selectionset_id:
                header_obj.unlink(cr, uid, [wizard.existing_selectionset_id.id], context=context)
        return self.button_cancel(cr, uid, ids, context=context)

    def button_cancel(self, cr, uid, ids, context=None):
        wizard = self.browse(cr, uid, ids[0], context=context)
        if wizard.passing_wizard_id:
            return {
                    'view_mode': 'form',
                    'res_model': 'ir.actions.report.promptwizard',
                    'type': 'ir.actions.act_window',
                    'target': 'new',
                    'res_id': wizard.passing_wizard_id.id,
                    }
        return {'type': 'ir.actions.act_window_close'}

class store_selections_dets_wizard(orm.TransientModel):
    _name = 'ir.actions.store.selections.detail.wiz'
    _description = "Store Report Selections Wizard"

    _columns = {'header_id': fields.many2one('ir.actions.store.selections.wiz', 'Selections Set'),
                'variable': fields.char('Variable Name', size=64),
                'label': fields.char('Label', size=64),
                'counter': fields.integer('Parameter Number'),
                'type': fields.selection(OPENERP_DATA_TYPES, 'Data Type'),
                'x2m': fields.boolean('Data List Type'),
                'display_value': fields.text('Value'),
                'calc_formula': fields.char('Formula'),
                }

    _order = 'counter'

    def onchange_calc_formula(self, cr, uid, ids, calc_formula, expected_type, expected_2m, parameters_dictionary, context=None):
        result = {}
        if calc_formula:
            parameters = json.loads(parameters_dictionary)
            known_variables = {}
            for index in range(0, len(parameters)):
                known_variables[parameters[index]['variable']] = {'type': parameters[index]['type'],
                                                                  'x2m': parameter_can_2m(parameters, index),
                                                                  'calculated': False,
                                                                  }

            parsed_formula = self.pool.get('ir.actions.report.set.formula').validate_formula(cr, uid, calc_formula, expected_type, expected_2m, known_variables, context=context)
            if parsed_formula.get('error'):
                result['warning'] = {'title': _('Formula Validation'),
                                     'message': parsed_formula['error'],
                                     }
        return result