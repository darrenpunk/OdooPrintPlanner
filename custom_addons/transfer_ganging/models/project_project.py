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
        # Columns to ignore during ganging analysis
        ignored_stages = ['On Hold', 'Artwork in Progress', 'Waiting on Approval', 'Waiting approval']
        
        # Find all transfer tasks in this project that haven't been assigned to LAY columns
        # and are not in ignored stages
        transfer_tasks = self.task_ids.filtered(lambda t: 
            t.get_parsed_product_type() and 
            t.stage_id and 
            'LAY' not in (t.stage_id.name or '') and
            (t.stage_id.name or '') not in ignored_stages)
        
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
    
    def action_reset_and_regang_tasks(self):
        """Reset all LAY assignments and re-gang with optimized consolidation logic"""
        # Find all tasks currently in LAY columns
        lay_tasks = self.task_ids.filtered(lambda t: 
            t.stage_id and 'LAY' in (t.stage_id.name or ''))
        
        if not lay_tasks:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'message': 'No tasks in LAY columns to reset',
                    'type': 'warning'
                }
            }
        
        # Find a suitable non-LAY stage from THIS PROJECT's stages (not global search)
        # Prefer "To Do" or similar stage, ordered by sequence
        project_stages = self.type_ids.filtered(lambda s: 
            'LAY' not in (s.name or '') and
            s.name not in ['On Hold', 'Artwork in Progress', 'Waiting on Approval', 'Waiting approval'])
        
        # Try to find "To Do" stage first
        non_lay_stage = project_stages.filtered(lambda s: 
            'to do' in (s.name or '').lower())[:1]
        
        # If no "To Do", use first available project stage
        if not non_lay_stage:
            non_lay_stage = project_stages.sorted('sequence')[:1]
        
        if not non_lay_stage:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'message': 'No suitable non-LAY stage found in this project to reset tasks',
                    'type': 'error'
                }
            }
        
        # Count tasks and LAY columns before reset
        num_tasks = len(lay_tasks)
        lay_columns_used = len(set(t.stage_id.name for t in lay_tasks if t.stage_id))
        
        # Move all LAY tasks back to non-LAY stage
        lay_tasks.write({'stage_id': non_lay_stage.id})
        
        # Now run ganging with new consolidation logic
        result = self.action_analyze_and_gang_tasks()
        
        # If successful, add summary message
        if result.get('type') == 'ir.actions.client' and result.get('params', {}).get('type') == 'success':
            result['params']['message'] = (
                f"Reset complete: {num_tasks} tasks moved from {lay_columns_used} LAY columns. "
                + result['params']['message']
            )
        
        return result
    
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