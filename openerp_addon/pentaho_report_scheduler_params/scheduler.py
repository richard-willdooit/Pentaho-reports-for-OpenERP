from osv import fields, orm
from tools.translate import _


class ReportSchedulerParams(orm.Model):
    _inherit = "ir.actions.report.scheduler"


#    def _run_one(self, cr, uid, sched, context=None):
#        if sched.line_ids or sched.user_list:
#            rpt_obj = self.pool.get('ir.actions.report.xml')
#            user_obj = self.pool.get('res.users')
#            report_output = []
#            for line in sched.line_ids:
#                report = line.report_id
#                service_name = "report.%s" % report.report_name
#                datas = {'model': self._name,
#                         }
#                content, type = netsvc.LocalService(service_name).create(cr, uid, [], datas, context)
#                report_output.append((report.name, content, type))
#            if report_output:
#                self._send_reports(cr, uid, sched, report_output, context=context)


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
