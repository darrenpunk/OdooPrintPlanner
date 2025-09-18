from odoo import models, fields, api
from datetime import datetime
import logging
import re

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
    
    # =============================================
    # PARSING HELPERS - Extract data from existing fields
    # =============================================
    
    def get_parsed_product_type(self):
        """Parse transfer product type from task name"""
        if not self.name:
            return None
        
        name_lower = self.name.lower()
        
        # Look for product type indicators in task name
        # Check full colour first - more specific patterns
        if 'full colour' in name_lower or 'full color' in name_lower or 'cmyk' in name_lower:
            return 'full_colour'
        # Only check for single colour if full colour not found - be more specific
        elif 'single colour' in name_lower or 'single color' in name_lower:
            return 'single_colour'
        elif 'metal' in name_lower or 'metallic' in name_lower:
            return 'metal'
        elif 'zero' in name_lower:
            return 'zero'
        
        # If no explicit type found, try to infer from other patterns
        if any(color in name_lower for color in ['white', 'black', 'red', 'blue', 'green']):
            return 'single_colour'
        
        # Default to full_colour if nothing specific found
        return 'full_colour'
    
    def get_parsed_transfer_size(self):
        """Parse transfer size from task name"""
        if not self.name:
            return None
        
        name_lower = self.name.lower()
        
        # Size patterns to match
        size_patterns = {
            'a3': r'\ba3\b',
            'a4': r'\ba4\b',
            'a5': r'\ba5\b', 
            'a6': r'\ba6\b',
            '295x100': r'295\s*[x×]\s*100|295x100',
            '95x95': r'95\s*[x×]\s*95|95x95',
            '100x70': r'100\s*[x×]\s*70|100x70',
            '60x60': r'60\s*[x×]\s*60|60x60',
            '290x140': r'290\s*[x×]\s*140|290x140',
        }
        
        # Check each pattern
        for size, pattern in size_patterns.items():
            if re.search(pattern, name_lower):
                return size
        
        # Default to A4 if no size found
        return 'a4'
    
    def get_parsed_color_variant(self):
        """Parse color variant from task description or name"""
        text_to_parse = (self.description or '') + ' ' + (self.name or '')
        text_lower = text_to_parse.lower()
        
        # Color mapping
        color_keywords = {
            'white': ['white', '01 white', 'ink colour: 01'],
            'black': ['black', '02 black', 'ink colour: 02'],
            'red': ['red', '03 red', 'ink colour: 03'],
            'blue': ['blue', '04 blue', 'ink colour: 04'],
            'green': ['green', '05 green', 'ink colour: 05'],
            'yellow': ['yellow', '06 yellow', 'ink colour: 06'],
            'orange': ['orange', '07 orange', 'ink colour: 07'],
            'purple': ['purple', '08 purple', 'ink colour: 08'],
            'pink': ['pink', '09 pink', 'ink colour: 09'],
            'brown': ['brown', '10 brown', 'ink colour: 10'],
            'grey': ['grey', 'gray', '11 grey', 'ink colour: 11'],
            'navy': ['navy', '12 navy', 'ink colour: 12'],
            'maroon': ['maroon', '13 maroon', 'ink colour: 13'],
            'teal': ['teal', '14 teal', 'ink colour: 14'],
            'lime': ['lime', '15 lime', 'ink colour: 15'],
            'silver': ['silver', '16 silver', 'ink colour: 16'],
            'gold': ['gold', '17 gold', 'ink colour: 17'],
        }
        
        # Check for color matches
        for color, keywords in color_keywords.items():
            for keyword in keywords:
                if keyword in text_lower:
                    return color
        
        # Default to white for single colour, None for others
        product_type = self.get_parsed_product_type()
        if product_type == 'single_colour':
            return 'white'
        return None
    
    def get_parsed_quantity(self):
        """Parse quantity from existing fields, task name, or description"""
        # First try to use planned_hours as quantity if it makes sense
        if self.planned_hours and self.planned_hours > 0 and self.planned_hours <= 10000:
            return int(self.planned_hours)
        
        # Try to parse from both task name and description
        text_to_parse = (self.name or '') + ' ' + (self.description or '')
        
        if text_to_parse:
            # Look for patterns like "x50", "qty: 25", "25 pieces", "Quantity Required: 20.00", etc.
            qty_patterns = [
                r'\bquantity\s+required:?\s*(\d+(?:\.\d+)?)\b',  # Quantity Required: 20.00
                r'\bx(\d+)\b',                                   # x50
                r'\bqty:?\s*(\d+)\b',                           # qty: 25
                r'\b(\d+)\s*pieces?\b',                         # 25 pieces
                r'\b(\d+)\s*pcs?\b',                            # 25 pcs
                r'\bquantity:?\s*(\d+)\b',                      # quantity: 25
                r'\brequired:?\s*(\d+(?:\.\d+)?)\b',           # required: 20.00
            ]
            
            for pattern in qty_patterns:
                match = re.search(pattern, text_to_parse.lower())
                if match:
                    qty = float(match.group(1))
                    qty_int = int(qty)  # Convert float to int (20.00 -> 20)
                    if 1 <= qty_int <= 10000:  # Reasonable range
                        return qty_int
        
        # Default to 1
        return 1
    
    def get_parsed_deadline(self):
        """Get deadline date - use existing date_deadline field"""
        return self.date_deadline
    
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
    
    # =============================================
    # UTILITY FUNCTIONS
    # =============================================
    
    def get_gang_priority(self):
        """Calculate ganging priority based on deadline and cost effectiveness"""
        priority = 0
        
        # High priority if deadline is soon
        deadline = self.get_parsed_deadline()
        if deadline:
            days_until_deadline = (deadline - datetime.now().date()).days
            if days_until_deadline <= 1:
                priority += 100  # Critical
            elif days_until_deadline <= 3:
                priority += 50   # High
            elif days_until_deadline <= 7:
                priority += 25   # Medium
        
        # Bonus for cost effectiveness (based on size utilization)
        size = self.get_parsed_transfer_size()
        quantity = self.get_parsed_quantity()
        if self.is_cost_effective_to_gang(size, quantity):
            priority += 10
        
        return priority
    
    def is_cost_effective_to_gang(self, size=None, quantity=None):
        """Check if ganging is cost effective based on waste vs screen cost"""
        if not size:
            size = self.get_parsed_transfer_size()
        if not quantity:
            quantity = self.get_parsed_quantity()
        
        if not size or not quantity:
            return False
        
        # Get project-level settings or use defaults
        project = self.project_id
        a3_sheet_cost = getattr(project, 'gang_a3_sheet_cost', 2.0)
        screen_cost = getattr(project, 'gang_screen_cost', 50.0)
        
        # Calculate waste cost
        fits_on_a3 = self._get_fits_on_a3(size)
        if fits_on_a3 == 0:  # A3 cannot be ganged
            return False
        
        sheets_needed = (quantity + fits_on_a3 - 1) // fits_on_a3
        total_capacity = sheets_needed * fits_on_a3
        waste_quantity = total_capacity - quantity
        waste_percentage = waste_quantity / total_capacity if total_capacity > 0 else 0
        waste_cost = sheets_needed * a3_sheet_cost * waste_percentage
        
        return waste_cost < screen_cost
    
    def get_remaining_quantity(self):
        """Get remaining quantity not yet assigned to LAY columns"""
        # If task is in a LAY column, remaining quantity is 0
        if self.stage_id and 'LAY' in (self.stage_id.name or ''):
            return 0
        else:
            # Return parsed quantity
            return self.get_parsed_quantity()
    
    def get_compatible_tasks(self):
        """Get tasks that this task can be ganged with based on product compatibility"""
        compatible_tasks = self.env['project.task']
        
        # Don't gang if not in new orders or if already assigned to LAY column
        if not self.stage_id or 'LAY' in (self.stage_id.name or ''):
            return compatible_tasks
        
        my_product_type = self.get_parsed_product_type()
        my_color = self.get_parsed_color_variant()
        
        # Find other tasks in new orders
        all_tasks = self.search([
            ('id', '!=', self.id),
            ('stage_id', '!=', False),
            ('stage_id.name', 'not ilike', 'LAY')
        ])
        
        for task in all_tasks:
            task_product_type = task.get_parsed_product_type()
            task_color = task.get_parsed_color_variant()
            
            # Check compatibility
            compatible = self._check_compatibility(my_product_type, my_color, task_product_type, task_color)
            if compatible:
                compatible_tasks |= task
        
        return compatible_tasks
    
    def _check_compatibility(self, type1, color1, type2, color2):
        """Check if two product types and colors are compatible for ganging"""
        if type1 == 'zero' or type2 == 'zero':
            return False  # Zero transfers can only be ganged on their own
        
        if type1 == 'full_colour' and type2 == 'full_colour':
            return True
        
        if type1 == 'full_colour' and type2 == 'single_colour' and color2 == 'white':
            return True
        
        if type2 == 'full_colour' and type1 == 'single_colour' and color1 == 'white':
            return True
        
        if type1 == 'single_colour' and type2 == 'single_colour' and color1 == color2:
            return True
        
        if type1 == 'metal' and type2 == 'metal':
            return True
        
        if type1 == 'metal' and type2 == 'single_colour' and color2 == 'silver':
            return True
        
        if type2 == 'metal' and type1 == 'single_colour' and color1 == 'silver':
            return True
        
        return False