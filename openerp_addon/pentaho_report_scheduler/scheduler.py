from osv import fields, orm
import datetime
from tools.translate import _
import netsvc
import json

from openerp.addons.pentaho_reports.java_oe import parameter_resolve_column_name


class ReportScheduler(orm.Model):
    _name = "ir.actions.report.scheduler"
    _description = "Report Scheduler"

    _columns = {
                'name': fields.char('Name', size=64, required=True),
                'description': fields.text('Description'),
                'action_type' : fields.selection([('email', 'Send Email'), ('notification', 'Send to User Notifications'), ('both', 'Notification and Email')], 'Type', required=True),
                'line_ids': fields.one2many('ir.actions.report.scheduler.line', 'scheduler_id', string='List of Reports', help="Enter a list of reports to run."),
                'user_list': fields.many2many('res.users', 'rep_sched_user_rel', 'sched_id', 'user_id', string='List of Users', help="Enter a list of users to receive the reports."),
                }

    def dt_to_local(self, cr, uid, dt, context=None):
        """Convert a UTC date/time to local.
    
        @param dt: A date/time with a UTC time.
        @param context: This must contain the user's local timezone
            as context['tz'].
        """
        # Returns 'NONE' if user has no tz defined or tz not passed
        # in the context.
        return fields.datetime.context_timestamp(cr, uid, timestamp=dt, context=context)

    def _send_reports(self, cr, uid, sched, reports, context=None):
        run_on = datetime.datetime.now()
        run_on_local = self.dt_to_local(cr, uid, run_on, context=context)
        if not run_on_local:
            run_on_local = run_on

        user_obj = self.pool.get('res.users')
        mail_message_obj = self.pool.get('mail.message')
        mail_mail_obj = self.pool.get('mail.mail')
        attachment_obj = self.pool.get('ir.attachment')
        report_summary = """Run on:%s

%s""" % (run_on_local.strftime('%d-%b-%Y at %H:%M:%S'),sched.description or '')

#        attachments={}
#        for rpt_name, content, type in reports:
#            attach_fname = "%s-%s.%s" % (rpt_name, run_on_local.strftime('%Y-%m-%d-%H-%M-%S'), type)
#            attachments[attach_fname] = content

        attachment_ids = []
        for rpt_name, content, type in reports:
            attachment_ids.append(attachment_obj.create(cr, uid, {'datas': content.encode('base64'),
                                                                  'name': rpt_name,
                                                                  'datas_fname': '%s.%s' % (rpt_name, type),
                                                                  },
                                                        context=context))

        if sched.action_type in ('email', 'both'):
            email_addresses = [x.user_email for x in sched.user_list if x.user_email]
            if email_addresses:
                msg_id = mail_mail_obj.create(cr, uid, {'subject' : sched.name,
                                                        'email_from' : user_obj.browse(cr, uid, uid, context=context).user_email,
                                                        'email_to' : ','.join(email_addresses),
                                                        'attachment_ids' : [(6, 0, attachment_ids)],
                                                        'body_html' : report_summary,
                                                        }
                                              ,context=context)
                mail_mail_obj.send(cr, uid, [msg_id], context=context)

        if sched.action_type in ('notification', 'both'):
            receiver_ids = [x.partner_id.id for x in sched.user_list]
            if receiver_ids:
                mail_message_obj.create(cr, uid, {'subject': sched.name,
                                                  'type': "notification",
                                                  'partner_ids': [(6, 0, receiver_ids)],
                                                  'notified_partner_ids': [(6, 0, receiver_ids)],
                                                  'attachment_ids': [(6, 0, attachment_ids)],
                                                  'body': report_summary,
                                                  },
                                        context=context)

    def _check_overriding_values(self, cr, uid, line, values_so_far, context=None):
        return {}

    def _report_variables(self, cr, uid, line, context=None):
        result = {}
        if line.is_pentaho_report:
            # attempt to fill the prompt wizard as if we had gone in to it from a menu and then run.
            promptwizard_obj = self.pool.get('ir.actions.report.promptwizard')

            # default_get creates a dictionary of wizard default values
            values = promptwizard_obj.default_get_external(cr, uid, line.report_id.id, context=context)
            # this hook is provided to allow for selection set values, which are not necessarily installed
            values.update(self._check_overriding_values(cr, uid, line, values, context=context))

            if values:
                # now convert virtual screen values from prompt wizard to values which can be passed to the report action
                result = {'output_type': values.get('output_type'),
                          'variables': {}}
                parameters = json.loads(values.get('parameters_dictionary'))
                for index in range(0, len(parameters)):
                    result['variables'][parameters[index]['variable']] = promptwizard_obj.decode_wizard_value(cr, uid, parameters, index, values[parameter_resolve_column_name(parameters, index)], context=context)

        return result

    def _run_one(self, cr, uid, sched, context=None):
        if sched.line_ids or sched.user_list:
            rpt_obj = self.pool.get('ir.actions.report.xml')
            user_obj = self.pool.get('res.users')
            report_output = []
            for line in sched.line_ids:
                report = line.report_id
                service_name = "report.%s" % report.report_name
                datas = {'model': self._name,
                         }
                datas.update(self._report_variables(cr, uid, line, context=context))
                content, type = netsvc.LocalService(service_name).create(cr, uid, [], datas, context)
                report_output.append((report.name, content, type))
            if report_output:
                self._send_reports(cr, uid, sched, report_output, context=context)

    def button_run_now(self, cr, uid, ids, context=None):
        for sched in self.browse(cr, uid, ids, context=context):
            self._run_one(cr, uid, sched, context=context)
        return {}

    def run_report_email_scheduler(self, cr, uid, scheduled_name='', context=None):
        for sched in self.browse(cr, uid, self.search(cr, uid, [('name', '=', scheduled_name)], context=context), context=context):
            self._run_one(cr, uid, sched, context=context)


class ReportSchedulerLines(orm.Model):
    _name = "ir.actions.report.scheduler.line"
    _description = "Report Scheduler Lines"

    def check_pentaho_installed(self, cr, uid, context=None):
        return self.pool.get('ir.module.module').search(cr, uid,
                                                        [('name', '=', 'pentaho_reports'), 
                                                         ('state', 'in', ['installed', 'to upgrade', 'to remove'])
                                                         ], count=True, context=context
                                                        ) > 0

    def _check_pentaho_values(self, cr, uid, report, pentaho_installed, context=None):
        if pentaho_installed and report.is_pentaho_report:
            result = {'is_pentaho_report': True,
                      'model': report.pentaho_report_model_id.name,
                      'report_type': report.pentaho_report_output_type,
                      }
        else:
            result = {'is_pentaho_report': False,
                      'model': report.model,
                      'report_type': report.report_type,
                      }
        return result

    def _action_values(self, cr, uid, ids, name, args, context=None):
        pentaho_installed = self.check_pentaho_installed(cr, uid, context=context)
        res = {}
        for line in self.browse(cr, uid, ids, context=context):
            res[line.id] = self._check_pentaho_values(cr, uid, line.report_id, pentaho_installed, context=context)
        return res

    _columns = {'scheduler_id': fields.many2one('ir.actions.report.scheduler', 'Scheduler'),
                'report_id': fields.many2one('ir.actions.report.xml', string='Report', required=True, ondelete='cascade'),
                'sequence': fields.integer('Sequence'),
                'is_pentaho_report': fields.function(_action_values, multi='ipr', string='Pentaho', type='boolean', readonly=True),
                'model': fields.function(_action_values, multi='ipr', string='Object', type='char', readonly=True),
                'type': fields.related('report_id', 'type', string='Action Type', type='char', readonly=True),
                'report_type': fields.function(_action_values, multi='ipr', string='Report Type', type='char', readonly=True),
                }

    _order='sequence'

    def onchange_report(self, cr, uid, ids, report_id, context=None):
        result = {}
        if report_id:
            report = self.pool.get('ir.actions.report.xml').browse(cr, uid, report_id, context=context)
            result['value'] = self._check_pentaho_values(cr, uid, report, self.check_pentaho_installed(cr, uid, context=context), context=context)
            result['value']['type'] = report.type
        return result