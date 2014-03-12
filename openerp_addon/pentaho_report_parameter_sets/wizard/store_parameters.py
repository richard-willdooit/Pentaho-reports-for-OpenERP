# -*- encoding: utf-8 -*-

import json

from openerp.osv import fields, orm
from openerp.tools.translate import _

from openerp.addons.pentaho_reports.core import VALID_OUTPUT_TYPES
from openerp.addons.pentaho_reports.java_oe import OPENERP_DATA_TYPES, parameter_resolve_column_name


class store_parameters_wizard(orm.TransientModel):
    _name = "ir.actions.store.params.wiz"
    _description = "Store Pentaho Parameters Wizard"

    _columns = {
                'existing_parameters_id': fields.many2one('ir.actions.report.set.header', 'Parameter Set'),
                'name': fields.char('Parameter Set Description', size=64),
                'report_action_id': fields.many2one('ir.actions.report.xml', 'Report Name', readonly=True),
                'output_type': fields.selection(VALID_OUTPUT_TYPES, 'Report format', help='Choose the format for the output'),
                'parameters_dictionary': fields.text('parameter dictionary'),
                'detail_ids': fields.one2many('ir.actions.store.params.detail.wiz', 'header_id', 'Parameter Details'),
                }

    def default_get(self, cr, uid, fields, context=None):
        if context is None:
            context = {}
        if not context.get('active_id'):
            raise orm.except_orm(_('Error'), _('No active id passed.'))

        screen_wizard_pool = self.pool.get('ir.actions.report.promptwizard')
        screen_wizard = screen_wizard_pool.browse(cr, uid, context['active_id'])

        parameters_dictionary = json.loads(screen_wizard.parameters_dictionary)

        res = super(store_parameters_wizard, self).default_get(cr, uid, fields, context=context)
        res.update({'existing_parameters_id': screen_wizard.parameter_set_id.id,
                    'name': screen_wizard.parameter_set_id and screen_wizard.parameter_set_id.name or '',
                    'report_action_id': screen_wizard.report_action_id.id,
                    'output_type': screen_wizard.output_type,
                    'parameters_dictionary': screen_wizard.parameters_dictionary,
                    'detail_ids': [],
                    })

        for index in range(0, len(parameters_dictionary)):
            res['detail_ids'].append((0, 0, {'variable': parameters_dictionary[index]['variable'],
                                             'label': parameters_dictionary[index]['label'],
                                             'counter': index,
                                             'type': parameters_dictionary[index]['type'],
                                             'display_value': screen_wizard_pool.decode_wizard_value(cr, uid, parameters_dictionary, index, getattr(screen_wizard, parameter_resolve_column_name(parameters_dictionary, index)), enc_json=True, context=context),
                                             }))

        return res


    def button_store(self, cr, uid, ids, context=None):
        header_obj = self.pool.get('ir.actions.report.set.header')
        detail_obj = self.pool.get('ir.actions.report.set.detail')

        for wizard in self.browse(cr, uid, ids, context=context):
            vals = {'name': wizard.name,
                    'report_action_id': wizard.report_action_id.id,
                    'output_type': wizard.output_type,
                    'parameters_dictionary': wizard.parameters_dictionary,
                    'detail_ids': [(5,)],
                    }

            if wizard.existing_parameters_id:
                header_obj.write(cr, uid, [wizard.existing_parameters_id.id], vals, context=context)
                hdr_id = wizard.existing_parameters_id.id
            else:
                hdr_id = header_obj.create(cr, uid, vals, context=context)

            for detail in wizard.detail_ids:
                detail_obj.create(cr, uid, {'header_id': hdr_id,
                                            'variable': detail.variable,
                                            'label': detail.label,
                                            'counter': detail.counter,
                                            'type': detail.type,
                                            'display_value': detail.display_value,
                                            }, context=context)

        return {'type': 'ir.actions.act_window_close'}


class store_parameters_dets_wizard(orm.TransientModel):
    _name = 'ir.actions.store.params.detail.wiz'
    _description = "Store Pentaho Parameters Wizard"

    _columns = {'header_id': fields.many2one('ir.actions.store.params.wiz', 'Parameter Set'),
                'variable': fields.char('Variable Name', size=64),
                'label': fields.char('Label', size=64),
                'counter': fields.integer('Parameter Number'),
                'type': fields.selection(OPENERP_DATA_TYPES, 'Data Type'),
                'display_value': fields.text('Value'),
                }
