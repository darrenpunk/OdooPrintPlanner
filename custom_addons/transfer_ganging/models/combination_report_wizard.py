from odoo import models, fields, api
import json

class CombinationReportWizard(models.TransientModel):
    _name = 'transfer.combination.report.wizard'
    _description = 'Transfer Combination Analysis Report'
    
    name = fields.Char(string='Report Title', default='Transfer Ganging Combination Analysis')
    
    # Summary statistics
    sheet_dimensions = fields.Char(string='Sheet Dimensions', readonly=True)
    total_single_combinations = fields.Integer(string='Single-Size Combinations', readonly=True)
    total_mixed_combinations = fields.Integer(string='Mixed-Size Combinations', readonly=True)
    highest_single_utilization = fields.Float(string='Best Single Utilization (%)', readonly=True)
    highest_mixed_utilization = fields.Float(string='Best Mixed Utilization (%)', readonly=True)
    combinations_over_90_percent = fields.Integer(string='Combinations >90%', readonly=True)
    combinations_over_95_percent = fields.Integer(string='Combinations >95%', readonly=True)
    
    # Report data stored as JSON text
    single_combinations_data = fields.Text(string='Single Combinations Data', readonly=True)
    mixed_combinations_data = fields.Text(string='Mixed Combinations Data', readonly=True)
    
    # Formatted report sections
    single_combinations_html = fields.Html(string='Single-Size Combinations', readonly=True)
    mixed_combinations_html = fields.Html(string='Top Mixed-Size Combinations', readonly=True)
    
    @api.model
    def create_report(self, analysis_data):
        """Create a new report wizard with analysis data"""
        # Extract summary statistics
        stats = analysis_data['summary_statistics']
        
        # Create HTML tables for display
        single_html = self._format_single_combinations_html(analysis_data['single_size_combinations'])
        mixed_html = self._format_mixed_combinations_html(analysis_data['mixed_size_combinations'])
        
        wizard = self.create({
            'sheet_dimensions': analysis_data['sheet_dimensions'],
            'total_single_combinations': stats['total_single_combinations'],
            'total_mixed_combinations': stats['total_mixed_combinations'],
            'highest_single_utilization': stats['highest_single_utilization'],
            'highest_mixed_utilization': stats['highest_mixed_utilization'],
            'combinations_over_90_percent': stats['combinations_over_90_percent'],
            'combinations_over_95_percent': stats['combinations_over_95_percent'],
            'single_combinations_data': json.dumps(analysis_data['single_size_combinations']),
            'mixed_combinations_data': json.dumps(analysis_data['mixed_size_combinations']),
            'single_combinations_html': single_html,
            'mixed_combinations_html': mixed_html,
        })
        
        return {
            'type': 'ir.actions.act_window',
            'name': 'Transfer Ganging Analysis Report',
            'res_model': 'transfer.combination.report.wizard',
            'res_id': wizard.id,
            'view_mode': 'form',
            'target': 'new',
            'context': {'form_view_initial_mode': 'readonly'},
        }
    
    def _format_single_combinations_html(self, single_combinations):
        """Format single combinations as HTML table"""
        html = '''
        <div style="margin: 10px 0;">
            <h4 style="color: #875A7B;">Single-Size Combinations</h4>
            <table class="table table-striped" style="width: 100%;">
                <thead style="background-color: #f8f9fa;">
                    <tr>
                        <th>Size</th>
                        <th>Dimensions</th>
                        <th>Max Qty</th>
                        <th>Layout</th>
                        <th>Utilization</th>
                        <th>Waste Area</th>
                    </tr>
                </thead>
                <tbody>
        '''
        
        for combo in single_combinations[:10]:  # Show top 10
            utilization_class = 'success' if combo['utilization_percent'] >= 90 else 'warning' if combo['utilization_percent'] >= 70 else 'secondary'
            html += f'''
                <tr>
                    <td><strong>{combo['size'].upper()}</strong></td>
                    <td>{combo['dimensions']}</td>
                    <td>{combo['max_quantity']}</td>
                    <td>{combo['layout_pattern']}</td>
                    <td><span class="badge badge-{utilization_class}">{combo['utilization_percent']:.1f}%</span></td>
                    <td>{combo['waste_area']:,.0f}mm²</td>
                </tr>
            '''
        
        html += '''
                </tbody>
            </table>
        </div>
        '''
        return html
    
    def _format_mixed_combinations_html(self, mixed_combinations):
        """Format mixed combinations as HTML table"""
        html = '''
        <div style="margin: 10px 0;">
            <h4 style="color: #875A7B;">Top Mixed-Size Combinations</h4>
            <table class="table table-striped" style="width: 100%;">
                <thead style="background-color: #f8f9fa;">
                    <tr>
                        <th>Combination</th>
                        <th>Items</th>
                        <th>Utilization</th>
                        <th>Efficiency</th>
                        <th>Waste Area</th>
                    </tr>
                </thead>
                <tbody>
        '''
        
        # Show top 20 combinations
        for combo in mixed_combinations[:20]:
            utilization_class = 'success' if combo['utilization_percent'] >= 95 else 'info' if combo['utilization_percent'] >= 90 else 'warning'
            html += f'''
                <tr>
                    <td><strong>{combo['description']}</strong></td>
                    <td>{combo['total_items']}</td>
                    <td><span class="badge badge-{utilization_class}">{combo['utilization_percent']:.1f}%</span></td>
                    <td>{combo['layout_efficiency']:.1f}</td>
                    <td>{combo['waste_area']:,.0f}mm²</td>
                </tr>
            '''
        
        html += '''
                </tbody>
            </table>
        </div>
        '''
        return html
    
    def action_export_to_csv(self):
        """Export the analysis report to CSV"""
        # This could be implemented later if needed
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'message': 'CSV export feature coming soon!',
                'type': 'info'
            }
        }