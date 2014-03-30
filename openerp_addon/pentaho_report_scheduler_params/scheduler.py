from osv import fields, orm
from tools.translate import _

import json


class ReportSchedulerParams(orm.Model):
    _inherit = "ir.actions.report.scheduler"


    def _check_overriding_values(self, cr, uid, line, values_so_far, context=None):
        result = super(ReportSchedulerParams, self)._check_overriding_values(cr, uid, line, values_so_far, context=context)
        if line.parameterset_id and values_so_far:
            result.update(self.pool.get('ir.actions.report.set.header').parameters_to_dictionary(cr, uid, line.parameterset_id.id, json.loads(values_so_far.get('parameters_dictionary')), values_so_far.get('x2m_unique_id'), context=context))

        return result

class ReportSchedulerLinesParams(orm.Model):
    _inherit = "ir.actions.report.scheduler.line"

    _columns = {'parameterset_id': fields.many2one('ir.actions.report.set.header', 'Parameters', ondelete='cascade'),
                }

    def onchange_parameters(self, cr, uid, ids, parameterset_id, context=None):
        result = {}
        if parameterset_id:
            result['value']={'report_id': self.pool.get('ir.actions.report.set.header').browse(cr, uid, parameterset_id, context=context).report_action_id.id}
        return result

    def onchange_report_p(self, cr, uid, ids, report_id, parameterset_id, context=None):
        if parameterset_id:
            paramset = self.pool.get('ir.actions.report.set.header').browse(cr, uid, parameterset_id, context=context)
            if report_id != paramset.report_action_id.id:
                return {'value': {'report_id': paramset.report_action_id.id}}

        return self.onchange_report(cr, uid, ids, report_id, context=context)
