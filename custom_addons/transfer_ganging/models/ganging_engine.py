from odoo import models, fields, api
import logging

# Import sheet dimensions and size mappings from project_task
from . import project_task
from .project_task import SHEET_W_MM, SHEET_H_MM, SHEET_AREA_MM2, get_size_dims_mm

_logger = logging.getLogger(__name__)

class TransferGangingEngine(models.Model):
    _name = 'transfer.ganging.engine'
    _description = 'Transfer Ganging Optimization Engine'
    
    def analyze_and_gang_tasks(self, tasks):
        """
        Main algorithm for analyzing and ganging tasks optimally
        
        Logic:
        1. Group tasks by compatibility (product type and color)
        2. For each group, calculate optimal A3 utilization
        3. Only gang if cost-effective OR deadline is critical
        4. Assign to LAY columns based on optimization
        """
        if not tasks:
            return {'type': 'ir.actions.client', 'tag': 'display_notification',
                   'params': {'message': 'No tasks to analyze', 'type': 'warning'}}
        
        ganged_count = 0
        left_unplanned = 0
        
        # Group tasks by compatibility
        compatibility_groups = self._group_by_compatibility(tasks)
        
        # Find available LAY columns
        lay_stages = self._get_lay_stages()
        
        for group_key, group_tasks in compatibility_groups.items():
            result = self._process_compatibility_group(group_tasks, lay_stages)
            ganged_count += result['ganged']
            left_unplanned += result['unplanned']
        
        message = f"Analysis complete: {ganged_count} tasks ganged, {left_unplanned} left unplanned for better opportunities"
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'message': message,
                'type': 'success'
            }
        }
    
    def _group_by_compatibility(self, tasks):
        """Group tasks by product type and color compatibility"""
        groups = {}
        
        for task in tasks:
            # Create compatibility key
            if task.transfer_product_type == 'zero':
                # Zero transfers are always alone
                key = f"zero_{task.id}"
            elif task.transfer_product_type == 'full_colour':
                key = "full_colour_white"  # Can gang with white single colour
            elif task.transfer_product_type == 'single_colour':
                if task.color_variant == 'white':
                    key = "full_colour_white"  # Gang with full colour
                elif task.color_variant == 'silver':
                    key = "metal_silver"  # Can gang with metal
                else:
                    key = f"single_{task.color_variant}"
            elif task.transfer_product_type == 'metal':
                key = "metal_silver"  # Can gang with silver single colour
            else:
                key = f"unknown_{task.id}"
            
            if key not in groups:
                groups[key] = []
            groups[key].append(task)
        
        return groups
    
    def _process_compatibility_group(self, tasks, lay_stages):
        """Process a group of compatible tasks"""
        ganged_count = 0
        unplanned_count = 0
        
        # Sort by priority (deadline urgency + cost effectiveness)
        sorted_tasks = sorted(tasks, key=lambda t: t.gang_priority, reverse=True)
        
        # Try to find optimal ganging combinations
        remaining_tasks = list(sorted_tasks)
        
        while remaining_tasks and lay_stages:
            # Find best combination for one A3 sheet
            best_combination = self._find_best_a3_combination(remaining_tasks)
            
            if not best_combination:
                # No good combinations found, leave remaining unplanned
                unplanned_count += len(remaining_tasks)
                break
            
            # Check if this combination is cost-effective or has urgent deadlines
            should_gang = self._should_gang_combination(best_combination)
            
            if should_gang:
                # Assign to LAY column
                lay_stage = lay_stages.pop(0) if lay_stages else None
                if lay_stage:
                    # Handle new combination format with task and quantity
                    for item in best_combination:
                        if isinstance(item, dict):
                            task = item['task']
                            quantity = item['quantity']
                            # For now, assign the whole task to LAY column
                            # TODO: In future, handle partial quantities by splitting tasks
                            task.stage_id = lay_stage.id
                            if task in remaining_tasks:
                                remaining_tasks.remove(task)
                        else:
                            # Backward compatibility for simple task list
                            item.stage_id = lay_stage.id
                            if item in remaining_tasks:
                                remaining_tasks.remove(item)
                    ganged_count += len(best_combination)
                else:
                    # No more LAY columns available
                    unplanned_count += len(remaining_tasks)
                    break
            else:
                # Not cost-effective, leave unplanned unless deadline critical
                critical_items = []
                for item in best_combination:
                    task = item['task'] if isinstance(item, dict) else item
                    if task.gang_priority >= 100:
                        critical_items.append(item)
                
                if critical_items:
                    # Gang critical tasks even if not cost-effective
                    lay_stage = lay_stages.pop(0) if lay_stages else None
                    if lay_stage:
                        for item in critical_items:
                            if isinstance(item, dict):
                                task = item['task']
                                task.stage_id = lay_stage.id
                                if task in remaining_tasks:
                                    remaining_tasks.remove(task)
                            else:
                                item.stage_id = lay_stage.id
                                if item in remaining_tasks:
                                    remaining_tasks.remove(item)
                        ganged_count += len(critical_items)
                else:
                    # Leave all unplanned
                    unplanned_count += len(remaining_tasks)
                    break
        
        return {'ganged': ganged_count, 'unplanned': unplanned_count}
    
    def _find_best_a3_combination(self, tasks):
        """Find the best mixed-size combination using predefined layout templates"""
        if not tasks:
            return []
        
        # Handle A3 size separately - cannot be ganged
        a3_tasks = [t for t in tasks if t.transfer_size == 'a3']
        if a3_tasks:
            best_a3 = max(a3_tasks, key=lambda t: t.gang_priority)
            return [{'task': best_a3, 'quantity': 1}]
        
        # Create available task inventory
        available_tasks = {}
        for task in tasks:
            if task.transfer_size != 'a3' and task.remaining_quantity > 0:
                size = task.transfer_size
                if size not in available_tasks:
                    available_tasks[size] = []
                available_tasks[size].append({
                    'task': task,
                    'remaining_qty': task.remaining_quantity,
                    'priority': task.gang_priority
                })
        
        if not available_tasks:
            return []
        
        # Define proven mixed-size layout templates (physically verified combinations)
        layout_templates = self._get_mixed_layout_templates()
        
        best_combination = []
        best_score = 0
        
        # Try each template to see which works best with available tasks
        for template in layout_templates:
            combination = []
            total_priority = 0
            total_items = 0
            template_feasible = True
            
            # Check if we have enough tasks for this template
            for size, qty_needed in template['layout'].items():
                if size not in available_tasks:
                    template_feasible = False
                    break
                
                # Sort tasks by priority for this size
                sorted_tasks = sorted(available_tasks[size], key=lambda x: -x['priority'])
                qty_available = sum(t['remaining_qty'] for t in sorted_tasks)
                
                if qty_available < qty_needed:
                    template_feasible = False
                    break
                
                # Allocate from highest priority tasks
                qty_allocated = 0
                for task_item in sorted_tasks:
                    if qty_allocated >= qty_needed:
                        break
                    
                    qty_to_take = min(task_item['remaining_qty'], qty_needed - qty_allocated)
                    if qty_to_take > 0:
                        combination.append({
                            'task': task_item['task'],
                            'quantity': qty_to_take
                        })
                        total_priority += task_item['priority'] * qty_to_take
                        total_items += qty_to_take
                        qty_allocated += qty_to_take
            
            if template_feasible and combination:
                # Score based on template efficiency, priority, and item count
                utilization = template['utilization']
                avg_priority = total_priority / total_items if total_items > 0 else 0
                score = utilization * 1000 + avg_priority * 10 + total_items * 2
                
                if score > best_score:
                    best_combination = combination
                    best_score = score
        
        # Fallback to single-size combinations if no mixed templates work
        if not best_combination:
            return self._find_single_size_combination(available_tasks)
        
        return best_combination
    
    def _get_mixed_layout_templates(self):
        """Define mixed-size layout templates with dynamic utilization calculation"""
        templates = [
            # High-value mixed combinations (user's examples)
            {
                'name': '1×A4 + 1×A5 + 4×100x70',
                'layout': {'a4': 1, 'a5': 1, '100x70': 4},
                'description': 'Optimal for mixed medium sizes'
            },
            {
                'name': '2×A5 + 2×A6 + 4×100x70',
                'layout': {'a5': 2, 'a6': 2, '100x70': 4},
                'description': 'High density small-medium mix'
            },
            {
                'name': '1×A4 + 2×A6 + 8×100x70',
                'layout': {'a4': 1, 'a6': 2, '100x70': 8},
                'description': 'Maximum 100x70 density'
            },
            {
                'name': '1×A5 + 3×A6 + 6×100x70',
                'layout': {'a5': 1, 'a6': 3, '100x70': 6},
                'description': 'Balanced small size mix'
            },
            {
                'name': '1×A4 + 6×95x95',
                'layout': {'a4': 1, '95x95': 6},
                'description': 'A4 with square formats'
            },
            {
                'name': '2×A5 + 8×95x95',
                'layout': {'a5': 2, '95x95': 8},
                'description': 'A5 with square formats'
            },
            {
                'name': '1×295x100 + 1×A6 + 8×60x60',
                'layout': {'295x100': 1, 'a6': 1, '60x60': 8},
                'description': 'Large format with small items'
            },
            # Single-size high-efficiency options  
            {
                'name': '2×A4 only',
                'layout': {'a4': 2},
                'description': 'Pure A4 efficiency'
            },
            {
                'name': '4×A5 only',
                'layout': {'a5': 4},
                'description': 'Pure A5 efficiency'
            },
            {
                'name': 'Max 100x70 only',
                'layout': {'100x70': 40},  # Will be verified by actual fit calculation
                'description': 'Maximum small format density'
            }
        ]
        
        # Calculate dynamic utilization and filter feasible templates
        feasible_templates = []
        for template in templates:
            utilization = self._calculate_template_utilization(template['layout'])
            if utilization > 0 and utilization <= 1.0:  # Must be physically feasible
                template['utilization'] = utilization
                feasible_templates.append(template)
        
        return feasible_templates
    
    def _calculate_template_utilization(self, layout):
        """Calculate utilization using no-rotation bin-packing on 310×438mm sheet"""
        # Use simple shelf packing algorithm (no rotation allowed)
        items_to_place = []
        for size, quantity in layout.items():
            item_w, item_h = get_size_dims_mm(size)
            if item_w <= 0 or item_h <= 0:
                return 0  # Invalid size
            for _ in range(quantity):
                items_to_place.append((item_w, item_h))
        
        # Sort items by height (tallest first) for better shelf packing
        items_to_place.sort(key=lambda x: x[1], reverse=True)
        
        # Shelf packing with gutters
        gutter_x, gutter_y = 2, 2
        shelves = []  # [(current_width, shelf_height)]
        total_used_area = 0
        
        for item_w, item_h in items_to_place:
            placed = False
            
            # Try to place on existing shelf
            for i, (shelf_width, shelf_height) in enumerate(shelves):
                # Check if item fits on this shelf
                if (shelf_width + gutter_x + item_w <= SHEET_W_MM and 
                    item_h <= shelf_height):
                    shelves[i] = (shelf_width + gutter_x + item_w, shelf_height)
                    total_used_area += item_w * item_h
                    placed = True
                    break
            
            if not placed:
                # Create new shelf
                new_shelf_y = sum(s[1] + gutter_y for s in shelves)
                if new_shelf_y + item_h <= SHEET_H_MM and item_w <= SHEET_W_MM:
                    shelves.append((item_w, item_h))
                    total_used_area += item_w * item_h
                    placed = True
            
            if not placed:
                return 0  # Cannot fit all items
        
        # Calculate utilization based on placed area
        utilization = total_used_area / SHEET_AREA_MM2
        return utilization if utilization <= 1.0 else 0
    
    def _find_single_size_combination(self, available_tasks):
        """Fallback to single-size combinations when mixed templates don't work"""
        best_combination = []
        best_score = 0
        
        for size, task_list in available_tasks.items():
            if not task_list:
                continue
            
            # Get max capacity for this size
            max_fit = task_list[0]['task']._get_fits_on_a3(size)
            if max_fit <= 0:
                continue
            
            # Sort by priority
            sorted_tasks = sorted(task_list, key=lambda x: -x['priority'])
            
            combination = []
            qty_allocated = 0
            total_priority = 0
            
            for task_item in sorted_tasks:
                if qty_allocated >= max_fit:
                    break
                
                qty_to_take = min(task_item['remaining_qty'], max_fit - qty_allocated)
                if qty_to_take > 0:
                    combination.append({
                        'task': task_item['task'],
                        'quantity': qty_to_take
                    })
                    total_priority += task_item['priority'] * qty_to_take
                    qty_allocated += qty_to_take
            
            if combination:
                utilization = qty_allocated / max_fit
                avg_priority = total_priority / qty_allocated if qty_allocated > 0 else 0
                score = utilization * 800 + avg_priority * 10 + qty_allocated
                
                if score > best_score:
                    best_combination = combination
                    best_score = score
        
        return best_combination
    
    def _should_gang_combination(self, combination):
        """Determine if a combination should be ganged based on cost and deadlines"""
        if not combination:
            return False
        
        # Extract tasks and calculate quantity-weighted costs
        tasks = []
        total_quantity = 0
        
        for item in combination:
            if isinstance(item, dict):
                task = item['task']
                quantity = item['quantity']
                tasks.append(task)
                total_quantity += quantity
            else:
                tasks.append(item)
                total_quantity += getattr(item, 'remaining_quantity', 1)
        
        # Gang if any task has critical deadline
        if any(t.gang_priority >= 100 for t in tasks):
            return True
        
        # Calculate per-sheet costs
        if not tasks:
            return False
        
        # Use average costs weighted by quantities
        avg_waste_cost = sum(t.estimated_waste_cost for t in tasks) / len(tasks)
        avg_screen_cost = sum(t.estimated_screen_cost for t in tasks) / len(tasks)
        
        # Gang if combination is cost-effective (waste cost < screen setup cost)
        return avg_waste_cost < avg_screen_cost
    
    def _get_lay_stages(self):
        """Get available LAY stages in proper order (LAY-A1 to LAY-Z1, then LAY-A2 to LAY-Z2)"""
        # Look for stages with LAY in the name, ordered properly
        lay_stages = self.env['project.task.type'].search([
            ('name', 'ilike', 'LAY')
        ], order='name')
        
        # Sort stages properly: LAY-A1 to LAY-Z1, then LAY-A2 to LAY-Z2
        def sort_lay_stages(stage):
            name = stage.name or ''
            if 'LAY-' in name:
                parts = name.split('-')
                if len(parts) >= 2:
                    suffix = parts[1]
                    if len(suffix) >= 2:
                        letter = suffix[0]
                        number = suffix[1:]
                        try:
                            return (int(number), ord(letter.upper()))
                        except (ValueError, TypeError):
                            pass
            return (999, 999)  # Sort unknown formats to end
        
        sorted_stages = sorted(lay_stages, key=sort_lay_stages)
        
        # Filter to only available LAY columns (not overloaded)
        available_stages = []
        for stage in sorted_stages:
            task_count = self.env['project.task'].search_count([
                ('stage_id', '=', stage.id)
            ])
            # Allow more tasks per LAY column but still have a reasonable limit
            if task_count < 20:
                available_stages.append(stage)
        
        return available_stages