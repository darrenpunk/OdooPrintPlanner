from odoo import models, fields, api
import logging

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
        """Find the best combination of tasks/quantities that fit on one A3 sheet using bin-packing"""
        if not tasks:
            return []
        
        # Handle A3 size separately - cannot be ganged
        a3_tasks = [t for t in tasks if t.transfer_size == 'a3']
        if a3_tasks:
            # Return highest priority A3 task with quantity 1 (one A3 per sheet)
            best_a3 = max(a3_tasks, key=lambda t: t.gang_priority)
            return [{'task': best_a3, 'quantity': 1}]
        
        # Group tasks by size and create work items with remaining quantities
        work_items = []
        for task in tasks:
            if task.transfer_size != 'a3' and task.remaining_quantity > 0:
                fits_on_a3 = task._get_fits_on_a3(task.transfer_size)
                if fits_on_a3 > 0:
                    work_items.append({
                        'task': task,
                        'size': task.transfer_size,
                        'remaining_qty': task.remaining_quantity,
                        'fits_on_a3': fits_on_a3,
                        'priority': task.gang_priority
                    })
        
        if not work_items:
            return []
        
        # Sort by priority (highest first) then by efficiency (larger sizes first)
        work_items.sort(key=lambda x: (-x['priority'], -x['fits_on_a3']))
        
        # Try different combinations to maximize A3 utilization
        best_combination = []
        best_score = 0
        
        # Simple greedy approach: try to fill A3 with highest priority items
        for primary_item in work_items:
            combination = []
            used_slots = 0
            remaining_items = work_items.copy()
            
            # Start with primary item
            slots_for_primary = primary_item['fits_on_a3']
            qty_to_take = min(primary_item['remaining_qty'], slots_for_primary - used_slots)
            if qty_to_take > 0:
                combination.append({
                    'task': primary_item['task'],
                    'quantity': qty_to_take
                })
                used_slots += qty_to_take
                remaining_items.remove(primary_item)
            
            # Try to fill remaining slots with compatible items of same size
            for item in remaining_items:
                if (item['size'] == primary_item['size'] and 
                    item['fits_on_a3'] == primary_item['fits_on_a3']):
                    
                    available_slots = slots_for_primary - used_slots
                    qty_to_take = min(item['remaining_qty'], available_slots)
                    
                    if qty_to_take > 0:
                        combination.append({
                            'task': item['task'],
                            'quantity': qty_to_take
                        })
                        used_slots += qty_to_take
                        
                        if used_slots >= slots_for_primary:
                            break
            
            # Calculate score (utilization * priority_weight)
            if combination:
                utilization = used_slots / slots_for_primary if slots_for_primary > 0 else 0
                avg_priority = sum(c['task'].gang_priority * c['quantity'] for c in combination) / used_slots if used_slots > 0 else 0
                score = utilization * 100 + avg_priority
                
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