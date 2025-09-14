from odoo import models, fields, api
from datetime import datetime
import logging

# Production A3 sheet dimensions (corrected from screenshots)
SHEET_W_MM = 310  # Width in mm (was 438)
SHEET_H_MM = 440  # Height in mm (was 310)
SHEET_AREA_MM2 = SHEET_W_MM * SHEET_H_MM  # 136,400 mm²

# Transfer size dimensions (exact fractional dimensions from production screenshots)
SIZE_DIMS = {
    'a3': (297, 420),         # A3 standard (not ganged)
    'a4': (309, 219.5),       # A4 exact from screenshot
    'a5': (154.5, 219.22),    # A5 exact from screenshot
    'a6': (154.5, 109.75),    # A6 exact from screenshot
    '295x100': (309, 109.75), # 295×100 exact from screenshot
    '95x95': (103, 109.75),   # 95×95 exact from screenshot
    '100x70': (77.25, 109.75),# 100×70 exact from screenshot
    '60x60': (77.25, 73.17),  # 60×60 exact from screenshot
    '290x140': (309, 146),     # 290×140 crop=309×146 as specified by user
}

def get_size_dims_mm(size):
    """Get dimensions (width, height) in mm for any transfer size"""
    return SIZE_DIMS.get(size, (0, 0))

_logger = logging.getLogger(__name__)

class ProjectTask(models.Model):
    _inherit = 'project.task'
    
    # Transfer printing specific fields
    transfer_product_type = fields.Selection([
        ('full_colour', 'Full Colour'),
        ('single_colour', 'Single Colour'),
        ('metal', 'Metal'),
        ('zero', 'Zero')
    ], string='Product Type', help='Type of transfer product')
    
    transfer_size = fields.Selection([
        ('a3', 'A3'),
        ('a4', 'A4'),
        ('a5', 'A5'),
        ('a6', 'A6'),
        ('295x100', '295X100MM'),
        ('95x95', '95X95MM'),
        ('100x70', '100X70MM'),
        ('60x60', '60X60MM'),
        ('290x140', '290X140MM'),
    ], string='Transfer Size', help='Size of the transfer')
    
    color_variant = fields.Selection([
        ('white', 'White'),
        ('black', 'Black'),
        ('red', 'Red'),
        ('blue', 'Blue'),
        ('green', 'Green'),
        ('yellow', 'Yellow'),
        ('orange', 'Orange'),
        ('purple', 'Purple'),
        ('pink', 'Pink'),
        ('brown', 'Brown'),
        ('grey', 'Grey'),
        ('navy', 'Navy'),
        ('maroon', 'Maroon'),
        ('teal', 'Teal'),
        ('lime', 'Lime'),
        ('aqua', 'Aqua'),
        ('silver', 'Silver'),
        ('gold', 'Gold'),
        ('magenta', 'Magenta'),
        ('cyan', 'Cyan'),
        ('beige', 'Beige'),
        ('tan', 'Tan'),
        ('khaki', 'Khaki'),
        ('ivory', 'Ivory'),
        ('coral', 'Coral'),
        ('salmon', 'Salmon'),
        ('crimson', 'Crimson'),
        ('indigo', 'Indigo'),
        ('violet', 'Violet'),
    ], string='Color Variant', help='Color for single colour transfers')
    
    transfer_quantity = fields.Integer(string='Quantity', default=1, help='Number of transfers needed')
    remaining_quantity = fields.Integer(string='Remaining Quantity', compute='_compute_remaining_quantity', store=True, help='Quantity not yet assigned to LAY columns')
    deadline_date = fields.Datetime(string='Deadline', help='When this order must be completed')
    
    # Ganging related fields
    is_cost_effective = fields.Boolean(string='Cost Effective to Gang', 
                                     compute='_compute_cost_effectiveness', store=True)
    estimated_waste_cost = fields.Float(string='Estimated Waste Cost', 
                                      compute='_compute_waste_cost', store=True)
    estimated_screen_cost = fields.Float(string='Estimated Screen Cost', default=50.0)
    gang_priority = fields.Integer(string='Gang Priority', 
                                 compute='_compute_gang_priority', store=True)
    can_gang_with_ids = fields.Many2many('project.task', 
                                       'task_ganging_compatibility_rel',
                                       'task_id', 'compatible_task_id',
                                       string='Can Gang With',
                                       compute='_compute_compatible_tasks')
    
    @api.depends('transfer_product_type', 'color_variant', 'stage_id')
    def _compute_compatible_tasks(self):
        """Compute which tasks this task can be ganged with based on product compatibility rules"""
        for task in self:
            compatible_tasks = self.env['project.task']
            
            # Don't gang if not in new orders or if already assigned to LAY column
            if not task.stage_id or 'LAY' in (task.stage_id.name or ''):
                task.can_gang_with_ids = compatible_tasks
                continue
            
            # Find other tasks in new orders that are compatible
            domain = [
                ('id', '!=', task.id),
                ('transfer_product_type', '!=', False),
                ('stage_id', '!=', False),
                ('stage_id.name', 'not ilike', 'LAY')
            ]
            
            if task.transfer_product_type == 'zero':
                # Zero transfers can only be ganged on their own (no compatibility)
                pass
            elif task.transfer_product_type == 'full_colour':
                # Full colour can gang with other full colour and single colour white
                domain.extend([
                    '|',
                    ('transfer_product_type', '=', 'full_colour'),
                    '&',
                    ('transfer_product_type', '=', 'single_colour'),
                    ('color_variant', '=', 'white')
                ])
            elif task.transfer_product_type == 'single_colour':
                if task.color_variant == 'white':
                    # White single colour can gang with full colour and other white
                    domain.extend([
                        '|',
                        ('transfer_product_type', '=', 'full_colour'),
                        '&',
                        ('transfer_product_type', '=', 'single_colour'),
                        ('color_variant', '=', 'white')
                    ])
                else:
                    # Other single colours can only gang with same colour
                    domain.extend([
                        ('transfer_product_type', '=', 'single_colour'),
                        ('color_variant', '=', task.color_variant)
                    ])
            elif task.transfer_product_type == 'metal':
                # Metal can gang with other metal and single colour silver
                domain.extend([
                    '|',
                    ('transfer_product_type', '=', 'metal'),
                    '&',
                    ('transfer_product_type', '=', 'single_colour'),
                    ('color_variant', '=', 'silver')
                ])
            
            compatible_tasks = self.search(domain)
            task.can_gang_with_ids = compatible_tasks
    
    @api.depends('transfer_size', 'transfer_quantity')
    def _compute_waste_cost(self):
        """Calculate estimated waste cost based on A3 utilization"""
        for task in self:
            if not task.transfer_size or not task.transfer_quantity:
                task.estimated_waste_cost = 0.0
                continue
            
            # A3 sheet cost (base cost)
            a3_sheet_cost = 2.0
            
            # Calculate how many can fit on A3
            fits_on_a3 = task._get_fits_on_a3(task.transfer_size)
            if fits_on_a3 == 0:  # A3 cannot be ganged
                task.estimated_waste_cost = 0.0
                continue
            
            # Calculate waste
            sheets_needed = (task.transfer_quantity + fits_on_a3 - 1) // fits_on_a3
            total_capacity = sheets_needed * fits_on_a3
            waste_quantity = total_capacity - task.transfer_quantity
            waste_percentage = waste_quantity / total_capacity if total_capacity > 0 else 0
            
            task.estimated_waste_cost = sheets_needed * a3_sheet_cost * waste_percentage
    
    @api.depends('estimated_waste_cost', 'estimated_screen_cost')
    def _compute_cost_effectiveness(self):
        """Determine if ganging is cost effective"""
        for task in self:
            # Cost effective if waste cost is less than screen cost
            task.is_cost_effective = task.estimated_waste_cost < task.estimated_screen_cost
    
    @api.depends('transfer_quantity', 'stage_id')
    def _compute_remaining_quantity(self):
        """Calculate remaining quantity not yet assigned to LAY columns"""
        for task in self:
            # If task is in a LAY column, remaining quantity is 0
            if task.stage_id and 'LAY' in (task.stage_id.name or ''):
                task.remaining_quantity = 0
            else:
                # For now, remaining quantity equals total quantity
                # TODO: Track partial allocations when implementing task splitting
                task.remaining_quantity = task.transfer_quantity or 0
    
    @api.depends('deadline_date', 'is_cost_effective')
    def _compute_gang_priority(self):
        """Calculate ganging priority based on deadline and cost effectiveness"""
        for task in self:
            priority = 0
            
            # High priority if deadline is soon
            if task.deadline_date:
                days_until_deadline = (task.deadline_date - datetime.now()).days
                if days_until_deadline <= 1:
                    priority += 100  # Critical
                elif days_until_deadline <= 3:
                    priority += 50   # High
                elif days_until_deadline <= 7:
                    priority += 25   # Medium
            
            # Bonus if cost effective
            if task.is_cost_effective:
                priority += 10
            
            task.gang_priority = priority
    
    def _get_size_dims_mm(self, size):
        """Return dimensions (width, height) in mm for each transfer size"""
        return get_size_dims_mm(size)
    
    def _get_fits_on_a3(self, size, gutter_x=0, gutter_y=0, allow_rotate=False):
        """Calculate how many items fit on A3 sheet - NO ROTATION, NO GUTTERS (bleed included in crop)"""
        if size == 'a3':
            return 0  # A3 cannot be ganged
        
        item_w, item_h = self._get_size_dims_mm(size)
        if item_w <= 0 or item_h <= 0:
            return 0
        
        # Check if item fits at all (no gutters since bleed is included in crop dimensions)
        if item_w > SHEET_W_MM or item_h > SHEET_H_MM:
            return 0
        
        # Calculate fit count - NO ROTATION, exact orientation only, no gutters
        across = max(0, int(SHEET_W_MM // item_w))
        down = max(0, int(SHEET_H_MM // item_h))
        
        return across * down
    
    def action_analyze_and_gang_tasks(self):
        """Analyze and gang tasks - can be called on single task or multiple tasks"""
        # If called on specific tasks, use those; otherwise find all unplanned tasks
        if self:
            tasks_to_analyze = self.filtered(lambda t: t.transfer_product_type and 
                                           t.stage_id and 
                                           'LAY' not in (t.stage_id.name or ''))
        else:
            tasks_to_analyze = self.search([
                ('transfer_product_type', '!=', False),
                ('stage_id', '!=', False),
                ('stage_id.name', 'not ilike', 'LAY')
            ])
        
        if not tasks_to_analyze:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'message': 'No transfer tasks available for ganging analysis',
                    'type': 'warning'
                }
            }
        
        ganging_engine = self.env['transfer.ganging.engine']
        return ganging_engine.analyze_and_gang_tasks(tasks_to_analyze)
    
    def action_analyze_all_combinations(self):
        """Generate comprehensive analysis of all possible transfer ganging combinations"""
        analyzer = self.env['transfer.combination.analyzer']
        return analyzer.display_analysis_report()