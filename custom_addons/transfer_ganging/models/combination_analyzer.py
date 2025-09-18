from odoo import models, fields, api
import itertools
import logging
from .project_task import SHEET_W_MM, SHEET_H_MM, SHEET_AREA_MM2, get_size_dims_mm, SIZE_DIMS

_logger = logging.getLogger(__name__)

class CombinationAnalyzer(models.Model):
    _name = 'transfer.combination.analyzer'
    _description = 'Transfer Ganging Combination Analysis Tool'
    
    def analyze_all_combinations(self):
        """Generate comprehensive analysis of all possible transfer ganging combinations"""
        result = {
            'sheet_dimensions': f"{SHEET_W_MM}×{SHEET_H_MM}mm ({SHEET_AREA_MM2:,} mm²)",
            'single_size_combinations': self._analyze_single_size_combinations(),
            'mixed_size_combinations': self._analyze_mixed_size_combinations(),
            'summary_statistics': {}
        }
        
        # Calculate summary statistics
        result['summary_statistics'] = self._calculate_summary_statistics(result)
        
        return result
    
    def _analyze_single_size_combinations(self):
        """Analyze maximum quantities for each size individually"""
        single_combinations = []
        
        # Get all available sizes except A3 (which cannot be ganged)
        available_sizes = [size for size in SIZE_DIMS.keys() if size != 'a3']
        
        for size in available_sizes:
            max_qty = self._get_fits_on_a3_single(size)
            item_w, item_h = get_size_dims_mm(size)
            item_area = item_w * item_h
            total_area = max_qty * item_area
            utilization = total_area / SHEET_AREA_MM2 if max_qty > 0 else 0
            
            combination = {
                'size': size,
                'dimensions': f"{item_w}×{item_h}mm",
                'max_quantity': max_qty,
                'total_area_used': total_area,
                'utilization_percent': round(utilization * 100, 1),
                'waste_area': SHEET_AREA_MM2 - total_area,
                'layout_pattern': self._get_layout_pattern(size, max_qty)
            }
            
            single_combinations.append(combination)
        
        # Sort by utilization descending
        single_combinations.sort(key=lambda x: x['utilization_percent'], reverse=True)
        
        return single_combinations
    
    def _analyze_mixed_size_combinations(self):
        """Systematically generate and test mixed-size combinations"""
        mixed_combinations = []
        
        # Get all sizes except A3
        available_sizes = [size for size in SIZE_DIMS.keys() if size != 'a3']
        
        # Test combinations with different numbers of sizes (2-4 different sizes)
        for num_sizes in range(2, 5):  # 2, 3, 4 different sizes
            combinations = list(itertools.combinations(available_sizes, num_sizes))
            
            for size_combo in combinations:
                mixed_combinations.extend(self._generate_quantity_combinations(size_combo))
        
        # Filter to high-utilization combinations (>70%) and sort by utilization
        high_util_combinations = [c for c in mixed_combinations if c['utilization_percent'] >= 70]
        high_util_combinations.sort(key=lambda x: x['utilization_percent'], reverse=True)
        
        return high_util_combinations[:50]  # Top 50 combinations
    
    def _generate_quantity_combinations(self, sizes):
        """Generate different quantity combinations for a set of sizes"""
        combinations = []
        
        # Get reasonable maximum quantities for each size
        max_quantities = {}
        for size in sizes:
            max_quantities[size] = min(20, self._get_fits_on_a3_single(size))
        
        # Generate combinations with different quantity distributions
        # Use limited ranges to avoid explosion of combinations
        quantity_ranges = {}
        for size in sizes:
            max_for_size = max_quantities[size]
            if max_for_size <= 2:
                quantity_ranges[size] = [1, 2] if max_for_size >= 2 else [1]
            elif max_for_size <= 8:
                quantity_ranges[size] = [1, 2, max_for_size//2, max_for_size]
            else:
                quantity_ranges[size] = [1, 2, 4, 8, max_for_size//2, max_for_size]
        
        # Generate all combinations of quantities
        size_qty_combinations = list(itertools.product(*[
            [(size, qty) for qty in quantity_ranges[size]] for size in sizes
        ]))
        
        for combo in size_qty_combinations[:200]:  # Limit to avoid too many combinations
            layout = {}
            for size, qty in combo:
                layout[size] = qty
            
            # Test if this layout is feasible
            utilization = self._calculate_template_utilization(layout)
            if utilization > 0:  # Feasible combination
                total_items = sum(layout.values())
                total_area_used = sum(
                    get_size_dims_mm(size)[0] * get_size_dims_mm(size)[1] * qty
                    for size, qty in layout.items()
                )
                
                combination = {
                    'layout': layout.copy(),
                    'description': self._format_layout_description(layout),
                    'total_items': total_items,
                    'total_area_used': total_area_used,
                    'utilization_percent': round(utilization * 100, 1),
                    'waste_area': SHEET_AREA_MM2 - total_area_used,
                    'layout_efficiency': self._calculate_layout_efficiency(layout)
                }
                
                combinations.append(combination)
        
        return combinations
    
    def _get_fits_on_a3_single(self, size):
        """Calculate how many items of given size fit on A3 sheet"""
        if size == 'a3':
            return 0  # A3 cannot be ganged
        
        item_w, item_h = get_size_dims_mm(size)
        if item_w <= 0 or item_h <= 0:
            return 0
        
        # Check if item fits at all
        if item_w > SHEET_W_MM or item_h > SHEET_H_MM:
            return 0
        
        # Calculate fit count - NO ROTATION, exact orientation only, no gutters
        across = max(0, int(SHEET_W_MM // item_w))
        down = max(0, int(SHEET_H_MM // item_h))
        
        return across * down
    
    def _calculate_template_utilization(self, layout):
        """Calculate utilization using no-rotation bin-packing - reuse from ganging engine"""
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
    
    def _get_layout_pattern(self, size, quantity):
        """Determine the layout pattern (e.g., '2×2', '4×1')"""
        item_w, item_h = get_size_dims_mm(size)
        if item_w <= 0 or item_h <= 0 or quantity <= 0:
            return "N/A"
        
        across = max(1, int(SHEET_W_MM // item_w))
        down = max(1, quantity // across if across > 0 else 0)
        
        if across * down == quantity:
            return f"{across}×{down}"
        else:
            return f"~{across}×{down}"
    
    def _format_layout_description(self, layout):
        """Format layout as readable description"""
        parts = []
        for size, qty in sorted(layout.items()):
            size_display = size.upper() if size.startswith('a') else size.replace('x', '×')
            parts.append(f"{qty}×{size_display}")
        return " + ".join(parts)
    
    def _calculate_layout_efficiency(self, layout):
        """Calculate layout efficiency score based on size diversity and balance"""
        total_items = sum(layout.values())
        num_different_sizes = len(layout)
        
        # Efficiency increases with more diverse sizes and balanced quantities
        size_diversity_bonus = num_different_sizes * 10
        
        # Balance bonus: lower variance in quantities is better
        quantities = list(layout.values())
        avg_qty = sum(quantities) / len(quantities)
        variance = sum((q - avg_qty) ** 2 for q in quantities) / len(quantities)
        balance_bonus = max(0, 50 - variance)  # Lower variance = higher bonus
        
        return round(size_diversity_bonus + balance_bonus + total_items, 1)
    
    def _calculate_summary_statistics(self, result):
        """Calculate summary statistics from the analysis"""
        single_combinations = result['single_size_combinations']
        mixed_combinations = result['mixed_size_combinations']
        
        # Single size stats
        single_utilizations = [c['utilization_percent'] for c in single_combinations if c['max_quantity'] > 0]
        
        # Mixed size stats
        mixed_utilizations = [c['utilization_percent'] for c in mixed_combinations]
        
        stats = {
            'total_single_combinations': len(single_combinations),
            'total_mixed_combinations': len(mixed_combinations),
            'highest_single_utilization': max(single_utilizations) if single_utilizations else 0,
            'highest_mixed_utilization': max(mixed_utilizations) if mixed_utilizations else 0,
            'average_single_utilization': round(sum(single_utilizations) / len(single_utilizations), 1) if single_utilizations else 0,
            'average_mixed_utilization': round(sum(mixed_utilizations) / len(mixed_utilizations), 1) if mixed_utilizations else 0,
            'combinations_over_90_percent': len([c for c in mixed_combinations if c['utilization_percent'] >= 90]),
            'combinations_over_95_percent': len([c for c in mixed_combinations if c['utilization_percent'] >= 95])
        }
        
        return stats
    
    def display_analysis_report(self):
        """Generate and display a comprehensive analysis report"""
        analysis = self.analyze_all_combinations()
        
        # Create and display the report wizard instead of just logging
        report_wizard = self.env['transfer.combination.report.wizard']
        return report_wizard.create_report(analysis)