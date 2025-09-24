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
        1. Group tasks by compatibility (product type and color) - NOT by deadline
        2. For each group, calculate optimal A3 utilization (mixed deadlines allowed)
        3. Only gang if cost-effective OR any task has critical deadline
        4. Assign to LAY columns based on optimization with proper quantity tracking
        
        Note: Tasks with different deadlines CAN be ganged together for better sheet utilization.
        Deadlines only affect priority ordering, not grouping constraints.
        """
        if not tasks:
            return {'type': 'ir.actions.client', 'tag': 'display_notification',
                   'params': {'message': 'No tasks to analyze', 'type': 'warning'}}
        
        # Initialize per-run allocation tracking
        self.run_allocations = {}  # task.id -> total_allocated_qty
        for task in tasks:
            self.run_allocations[task.id] = 0
        
        total_allocated_qty = 0
        total_remaining_qty = sum(task.get_remaining_quantity() for task in tasks)
        
        # Group tasks by compatibility
        compatibility_groups = self._group_by_compatibility(tasks)
        
        # Find available LAY columns
        lay_stages = self._get_lay_stages()
        
        # Process primary compatibility groups first (like-with-like)
        unprocessed_groups = {}
        for group_key, group_tasks in compatibility_groups.items():
            result = self._process_compatibility_group(group_tasks, lay_stages)
            total_allocated_qty += result['allocated_qty']
            
            # Keep track of groups with remaining unprocessed tasks
            if result['remaining_tasks']:
                unprocessed_groups[group_key] = result['remaining_tasks']
        
        # Try cross-compatibility ganging for remaining unprocessed tasks
        if unprocessed_groups and lay_stages:
            cross_result = self._process_cross_compatibility(unprocessed_groups, lay_stages)
            total_allocated_qty += cross_result['allocated_qty']
        
        # Final cleanup: move fully consumed tasks to LAY stages
        fully_ganged_count = self._finalize_task_assignments()
        
        remaining_qty = total_remaining_qty - total_allocated_qty
        message = f"Analysis complete: {total_allocated_qty} items allocated across {fully_ganged_count} tasks, {remaining_qty} items left for future opportunities"
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'message': message,
                'type': 'success'
            }
        }
    
    def _group_by_compatibility(self, tasks):
        """Group tasks by product type and color compatibility - prioritize like-with-like first"""
        groups = {}
        
        for task in tasks:
            # Use parsing methods instead of custom fields
            product_type = task.get_parsed_product_type()
            color_variant = task.get_parsed_color_variant()
            
            # Create primary compatibility key - prioritize like-with-like
            if product_type == 'zero':
                # Zero transfers are always alone
                key = f"zero_{task.id}"
            elif product_type == 'full_colour':
                # Full colour gets its own primary group
                key = "full_colour"
            elif product_type == 'single_colour':
                # Single colour jobs grouped by their specific color
                key = f"single_{color_variant or 'unknown'}"
            elif product_type == 'metal':
                # Metal gets its own group
                key = "metal"
            else:
                key = f"unknown_{task.id}"
            
            if key not in groups:
                groups[key] = []
            groups[key].append(task)
        
        return groups
    
    def _process_compatibility_group(self, tasks, lay_stages):
        """Process a group of compatible tasks"""
        allocated_qty = 0
        ganged_count = 0
        unplanned_count = 0
        
        # Sort by priority (deadline urgency + cost effectiveness)
        # Note: Mixed deadlines are allowed - priority is just for processing order
        sorted_tasks = sorted(tasks, key=lambda t: t.get_gang_priority(), reverse=True)
        
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
                    tasks_to_remove = []
                    allocated_in_template = 0
                    for item in best_combination:
                        if isinstance(item, dict):
                            task = item['task']
                            quantity = item['quantity']
                            
                            # Track allocated quantity
                            self.run_allocations[task.id] += quantity
                            allocated_in_template += quantity
                            
                            # Mark for removal if fully consumed, but don't set stage yet
                            if self.run_allocations[task.id] >= task.get_remaining_quantity():
                                if task in remaining_tasks:
                                    tasks_to_remove.append(task)
                        else:
                            # Backward compatibility for simple task list - don't set stage directly!
                            # Just track the task for removal and let finalization handle stage assignment
                            if item in remaining_tasks:
                                # Mark as fully consumed since it's in backward compatibility mode
                                self.run_allocations[item.id] = item.get_remaining_quantity()
                                allocated_in_template += item.get_remaining_quantity()
                                tasks_to_remove.append(item)
                    
                    # Remove tasks that were fully consumed
                    for task in tasks_to_remove:
                        remaining_tasks.remove(task)
                    
                    # Update tracking totals
                    allocated_qty += allocated_in_template
                    ganged_count += len(tasks_to_remove)
                else:
                    # No more LAY columns available
                    break
            else:
                # Not cost-effective, leave unplanned unless deadline critical
                critical_items = []
                for item in best_combination:
                    task = item['task'] if isinstance(item, dict) else item
                    if task.get_gang_priority() >= 100:
                        critical_items.append(item)
                
                if critical_items:
                    # Gang critical tasks even if not cost-effective
                    lay_stage = lay_stages.pop(0) if lay_stages else None
                    if lay_stage:
                        tasks_to_remove = []
                        allocated_in_critical = 0
                        for item in critical_items:
                            if isinstance(item, dict):
                                task = item['task']
                                quantity = item['quantity']
                                # Track allocation but don't set stage yet - finalize will handle it
                                self.run_allocations[task.id] += quantity
                                allocated_in_critical += quantity
                                if self.run_allocations[task.id] >= task.get_remaining_quantity():
                                    if task in remaining_tasks:
                                        tasks_to_remove.append(task)
                            else:
                                # Don't set stage directly - let finalization handle it
                                if item in remaining_tasks:
                                    # Mark as fully consumed since it's in backward compatibility mode
                                    self.run_allocations[item.id] = item.get_remaining_quantity()
                                    allocated_in_critical += item.get_remaining_quantity()
                                    tasks_to_remove.append(item)
                        
                        # Remove tasks that were fully consumed
                        for task in tasks_to_remove:
                            remaining_tasks.remove(task)
                        
                        # Update tracking totals
                        allocated_qty += allocated_in_critical
                        ganged_count += len(tasks_to_remove)
                else:
                    # Leave all unplanned
                    unplanned_count += len(remaining_tasks)
                    break
        
        return {
            'allocated_qty': allocated_qty,
            'remaining_tasks': remaining_tasks
        }
    
    def _process_cross_compatibility(self, unprocessed_groups, lay_stages):
        """Process cross-compatibility ganging for remaining tasks - prioritize size optimization"""
        allocated_qty = 0
        ganged_count = 0
        
        # Create a pool of cross-compatible tasks
        compatible_pools = self._create_cross_compatibility_pools(unprocessed_groups)
        
        for pool_tasks in compatible_pools:
            if not pool_tasks or not lay_stages:
                break
                
            # Find best cross-compatibility combination focusing on size optimization
            best_combination = self._find_best_cross_compatible_combination(pool_tasks)
            
            if best_combination and self._should_gang_combination(best_combination):
                # Assign to LAY column
                lay_stage = lay_stages.pop(0) if lay_stages else None
                if lay_stage:
                    tasks_to_remove = []
                    allocated_in_template = 0
                    for item in best_combination:
                        if isinstance(item, dict):
                            task = item['task']
                            quantity = item['quantity']
                            
                            # Track allocated quantity
                            self.run_allocations[task.id] += quantity
                            allocated_in_template += quantity
                            
                            # Don't set stage directly - let finalization handle it
                            if self.run_allocations[task.id] >= task.get_remaining_quantity():
                                tasks_to_remove.append(task)
                        else:
                            # Backward compatibility - don't set stage directly
                            # Mark as fully consumed since it's in backward compatibility mode
                            self.run_allocations[item.id] = item.get_remaining_quantity()
                            allocated_in_template += item.get_remaining_quantity()
                            tasks_to_remove.append(item)
                    
                    # Remove tasks that were fully consumed from original groups
                    for task in tasks_to_remove:
                        for group_tasks in unprocessed_groups.values():
                            if task in group_tasks:
                                group_tasks.remove(task)
                    
                    # Update tracking totals
                    allocated_qty += allocated_in_template
                    ganged_count += len(tasks_to_remove)
                else:
                    break
        
        return {
            'allocated_qty': allocated_qty,
            'ganged_count': ganged_count
        }
    
    def _create_cross_compatibility_pools(self, unprocessed_groups):
        """Create pools of tasks that can gang across compatibility boundaries"""
        pools = []
        
        # Pool 1: Full colour + Single colour white
        full_colour_tasks = unprocessed_groups.get('full_colour', [])
        single_white_tasks = unprocessed_groups.get('single_white', [])
        if full_colour_tasks or single_white_tasks:
            pools.append(full_colour_tasks + single_white_tasks)
        
        # Pool 2: Metal + Single colour silver
        metal_tasks = unprocessed_groups.get('metal', [])
        single_silver_tasks = unprocessed_groups.get('single_silver', [])
        if metal_tasks or single_silver_tasks:
            pools.append(metal_tasks + single_silver_tasks)
        
        return pools
    
    def _find_best_cross_compatible_combination(self, tasks):
        """Find best combination across compatible task types focusing on size optimization"""
        if not tasks:
            return []
            
        # Use the same logic as regular combination finding but with cross-compatible tasks
        return self._find_best_a3_combination(tasks)
    
    def _find_best_a3_combination(self, tasks):
        """Find the best mixed-size combination using predefined layout templates"""
        if not tasks:
            return []
        
        # Handle A3 size separately - cannot be ganged
        a3_tasks = [t for t in tasks if t.get_parsed_transfer_size() == 'a3']
        if a3_tasks:
            best_a3 = max(a3_tasks, key=lambda t: t.get_gang_priority())
            return [{'task': best_a3, 'quantity': 1}]
        
        # Create available task inventory
        available_tasks = {}
        for task in tasks:
            size = task.get_parsed_transfer_size()
            remaining_qty = task.get_remaining_quantity()
            if size != 'a3' and remaining_qty > 0:
                if size not in available_tasks:
                    available_tasks[size] = []
                available_tasks[size].append({
                    'task': task,
                    'remaining_qty': remaining_qty,
                    'priority': task.get_gang_priority()
                })
        
        if not available_tasks:
            return []
        
        # Define proven mixed-size layout templates (physically verified combinations)
        layout_templates = self._get_mixed_layout_templates()
        
        best_combination = []
        best_score = 0
        
        # Sort templates by priority first, then try them
        sorted_templates = sorted(layout_templates, key=lambda t: t.get('priority', 0), reverse=True)
        
        # Try each template starting with highest priority
        for template in sorted_templates:
            combination = []
            total_task_priority = 0
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
                        total_task_priority += task_item['priority'] * qty_to_take
                        total_items += qty_to_take
                        qty_allocated += qty_to_take
            
            if template_feasible and combination:
                # Enhanced scoring: template priority, utilization, task priority, and completeness
                utilization = template.get('utilization', 0.0)  # Defensive coding for missing utilization
                template_priority = template.get('priority', 1)
                avg_task_priority = total_task_priority / total_items if total_items > 0 else 0
                
                # Weighted scoring system
                score = (template_priority * 500 +           # Template efficiency priority
                        utilization * 1000 +                # Sheet utilization
                        avg_task_priority * 15 +             # Task urgency priority  
                        total_items * 3)                     # Item count bonus
                
                if score > best_score:
                    best_combination = combination
                    best_score = score
        
        # Fallback to single-size combinations if no mixed templates work
        if not best_combination:
            return self._find_single_size_combination(available_tasks)
        
        return best_combination
    
    def _get_mixed_layout_templates(self):
        """Define comprehensive mixed-size layout templates prioritizing sheet utilization"""
        templates = [
            # Ultra high-efficiency combinations (90%+ utilization)
            {
                'name': '1×A4 + 1×A5 + 4×100x70',
                'layout': {'a4': 1, 'a5': 1, '100x70': 4},
                'description': 'Optimal mixed medium sizes',
                'priority': 10
            },
            {
                'name': '2×A5 + 2×A6 + 4×100x70',
                'layout': {'a5': 2, 'a6': 2, '100x70': 4},
                'description': 'High density small-medium mix',
                'priority': 10
            },
            {
                'name': '1×A4 + 2×A6 + 8×100x70',
                'layout': {'a4': 1, 'a6': 2, '100x70': 8},
                'description': 'Maximum 100x70 density with A4',
                'priority': 9
            },
            
            # High-efficiency single size runs (85%+ utilization)
            {
                'name': '2×A4 only',
                'layout': {'a4': 2},
                'description': 'Pure A4 efficiency',
                'priority': 8
            },
            {
                'name': '4×A5 only',
                'layout': {'a5': 4},
                'description': 'Pure A5 efficiency',
                'priority': 8
            },
            {
                'name': '8×A6 only',
                'layout': {'a6': 8},
                'description': 'Pure A6 efficiency',
                'priority': 8
            },
            
            # Medium efficiency mixed combinations (70-85% utilization)
            {
                'name': '1×A5 + 3×A6 + 6×100x70',
                'layout': {'a5': 1, 'a6': 3, '100x70': 6},
                'description': 'Balanced small size mix',
                'priority': 7
            },
            {
                'name': '1×A4 + 6×95x95',
                'layout': {'a4': 1, '95x95': 6},
                'description': 'A4 with square formats',
                'priority': 7
            },
            {
                'name': '2×A5 + 8×95x95',
                'layout': {'a5': 2, '95x95': 8},
                'description': 'A5 with square formats',
                'priority': 7
            },
            {
                'name': '1×295x100 + 2×A6 + 6×60x60',
                'layout': {'295x100': 1, 'a6': 2, '60x60': 6},
                'description': 'Large format with small items',
                'priority': 6
            },
            {
                'name': '1×290x140 + 1×A6 + 4×100x70',
                'layout': {'290x140': 1, 'a6': 1, '100x70': 4},
                'description': 'Large format mixed',
                'priority': 6
            },
            
            # Small format high-density options
            {
                'name': 'Max 100x70 only',
                'layout': {'100x70': 40},  # Will be calculated by fit algorithm
                'description': 'Maximum small format density',
                'priority': 7
            },
            {
                'name': 'Max 95x95 only',
                'layout': {'95x95': 28},  # Will be calculated by fit algorithm  
                'description': 'Maximum square format density',
                'priority': 7
            },
            {
                'name': 'Max 60x60 only',
                'layout': {'60x60': 72},  # Will be calculated by fit algorithm
                'description': 'Maximum tiny format density',
                'priority': 6
            },
            
            # Specialty combinations for unusual mixes
            {
                'name': '2×295x100 only',
                'layout': {'295x100': 2},
                'description': 'Large format pair',
                'priority': 5
            },
            {
                'name': '1×A4 + 1×A6 + 2×295x100',
                'layout': {'a4': 1, 'a6': 1, '295x100': 2},
                'description': 'Mixed with large formats',
                'priority': 5
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
        
        # Shelf packing without gutters (bleed included in crop dimensions)
        gutter_x, gutter_y = 0, 0
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
                total_quantity += item.get_remaining_quantity()
        
        # Gang if any task has critical deadline
        if any(t.get_gang_priority() >= 100 for t in tasks):
            return True
        
        # Calculate per-sheet costs
        if not tasks:
            return False
        
        # Use project cost settings for cost effectiveness
        first_task = tasks[0]
        project = first_task.project_id
        
        # Calculate if this combination is cost effective
        cost_effective_count = 0
        for task in tasks:
            size = task.get_parsed_transfer_size()
            quantity = task.get_parsed_quantity()
            if task.is_cost_effective_to_gang(size, quantity):
                cost_effective_count += 1
        
        # Gang if majority of tasks are cost effective
        return cost_effective_count >= len(tasks) / 2
    
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
    
    def _finalize_task_assignments(self):
        """Move fully consumed tasks to LAY stages and return count"""
        fully_ganged_count = 0
        
        # Get available LAY stages for assignment
        lay_stages = self._get_lay_stages()
        lay_stage_index = 0
        
        # Ensure run_allocations exists before accessing
        if not hasattr(self, 'run_allocations') or not self.run_allocations:
            return 0
            
        for task_id, allocated_qty in self.run_allocations.items():
            if allocated_qty > 0:
                task = self.env['project.task'].browse(task_id)
                remaining_qty = task.get_remaining_quantity()
                
                # If task is fully consumed, move to LAY stage
                if allocated_qty >= remaining_qty:
                    # Only assign to LAY stage if not already in one
                    current_stage_name = task.stage_id.name or '' if task.stage_id else ''
                    if 'LAY' not in current_stage_name:
                        # Assign to next available LAY stage
                        if lay_stage_index < len(lay_stages):
                            task.stage_id = lay_stages[lay_stage_index].id
                            lay_stage_index += 1
                            _logger.info(f"Task {task.name} moved to LAY stage {lay_stages[lay_stage_index-1].name}")
                    
                    fully_ganged_count += 1
        
        return fully_ganged_count