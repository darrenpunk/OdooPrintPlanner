# Odoo Transfer Printing Ganging Optimization Module

An intelligent Odoo 16 module that automatically organizes transfer printing tasks with optimal ganging strategies using actual production specifications. The system analyzes incoming orders and groups them into existing LAY-A1 to LAY-Z2 columns with 99.5% sheet utilization, respecting no-rotation constraints and exact crop dimensions.

## 🎯 Features

- **Production-Accurate Ganging**: Uses exact 310×440mm sheet dimensions and real crop sizes from production
- **No-Rotation Constraint**: Respects exact crop orientations without rotation for production accuracy
- **99.5% Sheet Utilization**: Achieves near-perfect efficiency with <1% waste across all combinations
- **Geometric Validation**: Shelf-packing algorithm ensures all combinations are physically feasible
- **100+ Viable Combinations**: Comprehensive analysis of single-size and mixed-size options
- **Product Compatibility Rules**: Handles 4 product types with specific ganging constraints
- **Cost Intelligence**: Only gangs when waste cost < screen setup cost, unless deadline critical
- **Combination Analysis**: Built-in analyzer shows all possible layout combinations
- **LAY Column Integration**: Seamlessly assigns tasks to your existing LAY-A1 through LAY-Z2 workflow

## 📋 Product Types & Compatibility Rules

| Product Type | Compatible With | Notes |
|--------------|-----------------|-------|
| Full Colour | Single Colour White only | Can mix on same sheet |
| Single Colour | Same color only | Red with Red, Blue with Blue, etc. |
| Metal | Silver color only | Metal transfers isolated to silver |
| Zero | None (isolated) | Zero transfers never gang with others |

## 📏 Transfer Sizes & Production Specifications

**Sheet Dimensions**: 310×440mm (136,400 mm²) with no gutters (bleed included in crop dimensions)

| Size | Crop Dimensions | Max per Sheet | Layout | Utilization |
|------|-----------------|---------------|--------|-------------|
| A3 | 297×420mm | 0 | Cannot be ganged | N/A |
| A4 | 309×219.5mm | **2** | 1×2 | 99.5% |
| A5 | 154.5×219.22mm | **4** | 2×2 | 99.3% |
| A6 | 154.5×109.75mm | **8** | 2×4 | 99.5% |
| 295×100 | 309×109.75mm | **4** | 1×4 | 99.5% |
| 290×140 | 309×146mm | **3** | 1×3 | 99.2% |
| 95×95 | 103×109.75mm | **12** | 3×4 | 99.5% |
| 100×70 | 77.25×109.75mm | **16** | 4×4 | 99.5% |
| 60×60 | 77.25×73.17mm | **24** | 4×6 | 99.5% |

**Key Features**:
- ✅ **No Rotation**: Items placed in exact orientation only
- ✅ **Exact Dimensions**: Based on actual production crop sizes with bleed
- ✅ **Geometric Validation**: All layouts physically verified with shelf-packing

## 🚀 Installation

### 1. Install the Module

1. Copy the `custom_addons/transfer_ganging` folder to your Odoo addons directory
2. Restart your Odoo server
3. Go to **Apps** → **Update Apps List**
4. Search for "Transfer Ganging"
5. Click **Install**

### 2. Verify Installation

After installation, you should see:
- New fields in Project Tasks for transfer details
- "Analyze and Gang Tasks" button in task forms
- Enhanced task views with ganging information

## ⚙️ Configuration

### 1. Set Up LAY Columns (Project Stages)

Ensure your project has the following stages configured:
```
LAY-A1, LAY-B1, LAY-C1, ..., LAY-Z1
LAY-A2, LAY-B2, LAY-C2, ..., LAY-Z2
```

The system automatically prioritizes LAY-A1 through LAY-Z1 first, then LAY-A2 through LAY-Z2.

### 2. Configure Task Fields

No additional configuration needed - the module extends existing Project Tasks with:
- **Product Type**: Full Colour, Single Colour, Metal, Zero
- **Transfer Size**: All 9 supported sizes
- **Color Variant**: 29 colors for Single Colour transfers
- **Quantity**: Number of transfers needed
- **Deadline Date**: When order must be completed

## 📝 Usage Workflow

### 1. Task Arrival Process

**Your existing workflow remains unchanged:**
- Tasks arrive in your "New" column with all transfer details already populated
- Product type, size, color, quantity, and deadline are automatically filled
- No manual data entry required

### 2. Ganging Analysis

**Manual Trigger:**
1. Open any project task
2. Click the **"Analyze and Gang Tasks"** button in the header
3. System analyzes all unplanned transfer tasks

**Combination Analysis:**
1. Use the **"Generate Combination Analysis"** button to see all viable layouts
2. View 100+ possible combinations with utilization percentages
3. See optimal mixed-size combinations (e.g., 1×A4 + 4×A6)

**Automatic Analysis:**
- The system can be configured to run automatically via scheduled actions
- Analyzes all tasks not yet in LAY columns

### 3. Ganging Decision Logic

The system evaluates each potential combination:

**✅ Tasks Will Be Ganged When:**
- Products are compatible (follow compatibility rules above)
- Combination fits on one A3 sheet
- Waste cost < Screen setup cost **OR** deadline is critical (≤1 day)
- Available LAY column exists

**❌ Tasks Remain Unplanned When:**
- Products incompatible
- Not cost-effective and deadline not critical
- No available LAY columns

### 4. Results

**Successful Ganging:**
- Compatible tasks move to appropriate LAY column (LAY-A1, LAY-B1, etc.)
- Tasks grouped for optimal A3 sheet utilization
- Cost-effective combinations prioritized

**Critical Deadlines:**
- Tasks with deadlines ≤1 day get ganged even if not cost-effective
- Ensures urgent orders are never delayed

## 🎛️ Understanding the Fields

### Task Fields Added:

| Field | Purpose | Options |
|-------|---------|---------|
| **Product Type** | Determines compatibility rules | Full Colour, Single Colour, Metal, Zero |
| **Transfer Size** | Calculates A3 sheet capacity | A3, A4, A5, A6, 295x100, 95x95, 100x70, 60x60, 290x140 |
| **Color Variant** | For Single Colour compatibility | 29 color options (Red, Blue, Green, etc.) |
| **Quantity** | Number of transfers needed | Integer (used for capacity calculations) |
| **Deadline Date** | Urgency calculation | Date/Time (critical if ≤1 day) |

### Computed Fields:

| Field | Purpose |
|-------|---------|
| **Gang Priority** | Calculated urgency score (0-100+) |
| **Cost Effective** | Boolean - waste cost vs screen cost |
| **Estimated Waste Cost** | Cost of unused A3 sheet space |
| **Estimated Screen Cost** | Setup cost for separate screen |

## 🔍 Monitoring and Troubleshooting

### View Ganging Status

1. **Task List View**: See gang priority and cost effectiveness
2. **Task Form**: View detailed ganging calculations
3. **LAY Columns**: Monitor ganged task distribution

### Common Scenarios

**Why wasn't my task ganged?**
- Check product compatibility rules
- Verify cost-effectiveness (waste < screen cost)
- Ensure deadline isn't forcing immediate ganging
- Check if LAY columns are available

**Task has critical deadline but not ganged?**
- Verify deadline date is set and ≤1 day away
- Check if compatible LAY column space available
- Ensure product type allows ganging

**How to force ganging?**
- Set deadline date to today or earlier
- System will gang critical tasks even if not cost-effective

## 🎯 Production Optimization

### 1. Top Mixed-Size Combinations (99.5% Utilization)

**Most Practical for Production:**
- **1×A4 + 4×A6** (5 items total) - Perfect for mixed medium/small orders
- **2×295×100 + 1×A4** (3 items total) - Efficient banner + standard mix
- **6×95×95 + 1×A4** (7 items total) - Good for square format needs
- **12×60×60 + 1×A4** (13 items total) - High-density small format mix
- **12×100×70 + 2×A6** (14 items total) - Maximum small format density

**High-Volume Options:**
- **24×60×60** - Maximum single-size density
- **16×100×70** - High rectangular format density
- **12×95×95** - Good square format volume

### 2. Deadline Management
- Set realistic deadline dates on incoming tasks
- Use deadline urgency to override cost decisions when needed
- Monitor critical tasks to ensure timely processing

### 3. LAY Column Capacity
- System limits 20 tasks per LAY column by default
- Monitor column capacity during peak periods
- Consider adding more LAY columns if needed consistently

### 4. Utilization Monitoring
- All optimal combinations achieve 99.5% sheet utilization
- Waste typically <750mm² per sheet (less than 1%)
- Use combination analysis to find best layouts for your order mix

## 🔧 Advanced Configuration

### Modify Cost Calculations
Edit `models/project_task.py` to adjust:
- Waste cost per unit area
- Screen setup cost estimates
- Priority scoring weights

### Adjust LAY Column Limits
Edit `models/ganging_engine.py` to modify:
- Maximum tasks per LAY column (default: 20)
- LAY column selection priority
- Ganging combination scoring

### Custom Compatibility Rules
Modify `_are_products_compatible()` method to add:
- New product types
- Modified compatibility logic
- Special customer requirements

## 📞 Support

For technical issues or customization requests, refer to the module's code documentation in:
- `models/project_task.py` - Task model extensions
- `models/ganging_engine.py` - Core ganging algorithm
- `views/project_task_views.xml` - User interface modifications

---

## 📊 System Performance

- **Sheet Utilization**: 99.5% average across optimal combinations
- **Waste Per Sheet**: 743-1058mm² (less than 1%)
- **Viable Combinations**: 100+ validated mixed-size options
- **Production Accuracy**: Exact crop dimensions with no-rotation constraint
- **Geometric Validation**: All combinations physically verified

---

**Version**: 2.0.0 - Production Ready  
**Compatible**: Odoo 16  
**License**: LGPL-3  
**Author**: Transfer Ganging Optimization Module