from odoo import models, fields, api
import re

class ProjectProject(models.Model):
    _inherit = 'project.project'
    
    # Cost configuration for ganging analysis
    gang_screen_cost = fields.Float(string='Screen Setup Cost', default=50.0,
                                        help='Cost of setting up screens for printing')
    gang_a3_sheet_cost = fields.Float(string='A3 Sheet Cost', default=2.0,
                                help='Base cost per A3 sheet')
    
    def action_analyze_and_gang_tasks(self):
        """Analyze and gang all transfer tasks in this project"""
        # Find all transfer tasks in this project that haven't been assigned to LAY columns
        transfer_tasks = self.task_ids.filtered(lambda t: 
            t.get_parsed_product_type() and 
            t.stage_id and 
            'LAY' not in (t.stage_id.name or ''))
        
        if not transfer_tasks:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'message': 'No transfer tasks available for ganging analysis in this project',
                    'type': 'warning'
                }
            }
        
        ganging_engine = self.env['transfer.ganging.engine']
        return ganging_engine.analyze_and_gang_tasks(transfer_tasks)
    
    def action_analyze_all_combinations(self):
        """Generate comprehensive analysis of all possible transfer ganging combinations"""
        analyzer = self.env['transfer.combination.analyzer']
        return analyzer.display_analysis_report()
    
    def action_view_transfer_tasks(self):
        """View all transfer tasks in this project"""
        action = self.env.ref('project.act_project_project_2_project_task_all').read()[0]
        action['domain'] = [('project_id', '=', self.id)]
        action['context'] = {
            'default_project_id': self.id,
            'search_default_transfer_tasks': 1,
        }
        return action