#!/usr/bin/env python3
"""
Standalone Transfer Ganging Combination Analysis Script

This script generates a comprehensive analysis of all possible transfer ganging combinations
using the same geometric validation logic from the Odoo module.
"""

import itertools
import sys

# Transfer size dimensions (from production screenshots)
SHEET_W_MM = 310  # Width in mm
SHEET_H_MM = 440  # Height in mm
SHEET_AREA_MM2 = SHEET_W_MM * SHEET_H_MM  # 136,400 mm²

SIZE_DIMS = {
    'a4': (309, 219.5),       # A4 exact from screenshot
    'a5': (154.5, 219.22),    # A5 exact from screenshot
    'a6': (154.5, 109.75),    # A6 exact from screenshot
    '295x100': (309, 109.75), # 295×100 exact from screenshot
    '95x95': (103, 109.75),   # 95×95 exact from screenshot
    '100x70': (77.25, 109.75),# 100×70 exact from screenshot
    '60x60': (77.25, 73.17),  # 60×60 exact from screenshot
    '290x140': (309, 146),     # 290×140 crop=309×146
}

def get_size_dims_mm(size):
    """Get dimensions (width, height) in mm for any transfer size"""
    return SIZE_DIMS.get(size, (0, 0))

def get_fits_on_a3_single(size):
    """Calculate how many items of given size fit on A3 sheet"""
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

def calculate_template_utilization(layout):
    """Calculate utilization using no-rotation bin-packing on 310×440mm sheet"""
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

def analyze_single_size_combinations():
    """Analyze maximum quantities for each size individually"""
    single_combinations = []
    
    # Get all available sizes
    available_sizes = list(SIZE_DIMS.keys())
    
    for size in available_sizes:
        max_qty = get_fits_on_a3_single(size)
        item_w, item_h = get_size_dims_mm(size)
        item_area = item_w * item_h
        total_area = max_qty * item_area
        utilization = total_area / SHEET_AREA_MM2 if max_qty > 0 else 0
        
        # Calculate layout pattern
        across = max(1, int(SHEET_W_MM // item_w)) if item_w > 0 else 0
        down = max(1, int(max_qty / across)) if across > 0 else 0
        layout_pattern = f"{across}×{down}" if across * down == max_qty else f"~{across}×{down}"
        
        combination = {
            'size': size,
            'dimensions': f"{item_w}×{item_h}mm",
            'max_quantity': max_qty,
            'total_area_used': total_area,
            'utilization_percent': round(utilization * 100, 1),
            'waste_area': SHEET_AREA_MM2 - total_area,
            'layout_pattern': layout_pattern if max_qty > 0 else "N/A"
        }
        
        single_combinations.append(combination)
    
    # Sort by utilization descending
    single_combinations.sort(key=lambda x: x['utilization_percent'], reverse=True)
    
    return single_combinations

def generate_mixed_combinations():
    """Generate and test mixed-size combinations"""
    mixed_combinations = []
    available_sizes = list(SIZE_DIMS.keys())
    
    # Test combinations with 2-4 different sizes
    for num_sizes in range(2, 5):
        size_combinations = list(itertools.combinations(available_sizes, num_sizes))
        
        for size_combo in size_combinations:
            # Generate reasonable quantity combinations
            max_quantities = {}
            for size in size_combo:
                max_quantities[size] = min(12, get_fits_on_a3_single(size))
            
            # Create quantity ranges
            quantity_ranges = []
            for size in size_combo:
                max_for_size = max_quantities[size]
                if max_for_size <= 2:
                    ranges = [1, 2] if max_for_size >= 2 else [1]
                elif max_for_size <= 8:
                    ranges = [1, 2, max_for_size//2, max_for_size]
                else:
                    ranges = [1, 2, 4, max_for_size//2, max_for_size]
                quantity_ranges.append(ranges)
            
            # Generate all combinations
            for quantities in itertools.product(*quantity_ranges):
                layout = dict(zip(size_combo, quantities))
                
                # Test feasibility
                utilization = calculate_template_utilization(layout)
                if utilization > 0:
                    total_items = sum(layout.values())
                    total_area_used = sum(
                        get_size_dims_mm(size)[0] * get_size_dims_mm(size)[1] * qty
                        for size, qty in layout.items()
                    )
                    
                    # Format description
                    parts = []
                    for size, qty in sorted(layout.items()):
                        size_display = size.upper() if size.startswith('a') else size.replace('x', '×')
                        parts.append(f"{qty}×{size_display}")
                    description = " + ".join(parts)
                    
                    combination = {
                        'layout': layout.copy(),
                        'description': description,
                        'total_items': total_items,
                        'total_area_used': total_area_used,
                        'utilization_percent': round(utilization * 100, 1),
                        'waste_area': SHEET_AREA_MM2 - total_area_used,
                    }
                    
                    mixed_combinations.append(combination)
    
    # Filter to combinations with >70% utilization and sort by utilization
    high_util = [c for c in mixed_combinations if c['utilization_percent'] >= 70]
    high_util.sort(key=lambda x: x['utilization_percent'], reverse=True)
    
    return high_util[:100]  # Top 100 combinations

def generate_report():
    """Generate comprehensive combination analysis report"""
    print("=" * 80)
    print("TRANSFER GANGING COMBINATION ANALYSIS REPORT")
    print("=" * 80)
    print(f"Sheet Dimensions: {SHEET_W_MM}×{SHEET_H_MM}mm ({SHEET_AREA_MM2:,} mm²)")
    print("")
    
    # Analyze single-size combinations
    single_combos = analyze_single_size_combinations()
    
    # Analyze mixed-size combinations
    mixed_combos = generate_mixed_combinations()
    
    # Summary Statistics
    single_utilizations = [c['utilization_percent'] for c in single_combos if c['max_quantity'] > 0]
    mixed_utilizations = [c['utilization_percent'] for c in mixed_combos]
    
    print("SUMMARY STATISTICS")
    print("-" * 40)
    print(f"Total Single-Size Combinations: {len(single_combos)}")
    print(f"Total Mixed-Size Combinations: {len(mixed_combos)}")
    print(f"Highest Single Utilization: {max(single_utilizations):.1f}%" if single_utilizations else "N/A")
    print(f"Highest Mixed Utilization: {max(mixed_utilizations):.1f}%" if mixed_utilizations else "N/A")
    print(f"Average Single Utilization: {sum(single_utilizations)/len(single_utilizations):.1f}%" if single_utilizations else "N/A")
    print(f"Average Mixed Utilization: {sum(mixed_utilizations)/len(mixed_utilizations):.1f}%" if mixed_utilizations else "N/A")
    print(f"Combinations >90% Utilization: {len([c for c in mixed_combos if c['utilization_percent'] >= 90])}")
    print(f"Combinations >95% Utilization: {len([c for c in mixed_combos if c['utilization_percent'] >= 95])}")
    print("")
    
    # Single-Size Combinations
    print("SINGLE-SIZE COMBINATIONS")
    print("-" * 80)
    print(f"{'Size':<12} {'Dimensions':<15} {'Max Qty':<8} {'Layout':<10} {'Utilization':<12} {'Waste Area'}")
    print("-" * 80)
    
    for combo in single_combos:
        print(f"{combo['size'].upper():<12} {combo['dimensions']:<15} "
              f"{combo['max_quantity']:<8} {combo['layout_pattern']:<10} "
              f"{combo['utilization_percent']:>6.1f}%     {combo['waste_area']:>8.0f}mm²")
    
    print("")
    
    # Top Mixed-Size Combinations
    print("TOP MIXED-SIZE COMBINATIONS (>95% Utilization)")
    print("-" * 80)
    print(f"{'Combination':<40} {'Items':<6} {'Utilization':<12} {'Waste Area'}")
    print("-" * 80)
    
    top_95 = [c for c in mixed_combos if c['utilization_percent'] >= 95][:20]
    for combo in top_95:
        print(f"{combo['description']:<40} {combo['total_items']:<6} "
              f"{combo['utilization_percent']:>6.1f}%     {combo['waste_area']:>8.0f}mm²")
    
    print("")
    print("HIGH-EFFICIENCY MIXED COMBINATIONS (90-95% Utilization)")
    print("-" * 80)
    
    high_90 = [c for c in mixed_combos if 90 <= c['utilization_percent'] < 95][:25]
    for combo in high_90:
        print(f"{combo['description']:<40} {combo['total_items']:<6} "
              f"{combo['utilization_percent']:>6.1f}%     {combo['waste_area']:>8.0f}mm²")
    
    print("")
    print("GOOD-EFFICIENCY MIXED COMBINATIONS (80-90% Utilization)")
    print("-" * 80)
    
    good_80 = [c for c in mixed_combos if 80 <= c['utilization_percent'] < 90][:30]
    for combo in good_80:
        print(f"{combo['description']:<40} {combo['total_items']:<6} "
              f"{combo['utilization_percent']:>6.1f}%     {combo['waste_area']:>8.0f}mm²")
    
    print("")
    print("=" * 80)

if __name__ == "__main__":
    generate_report()