# Odoo Transfer Printing Ganging Optimization Module

An intelligent Odoo 16 module that automatically organizes transfer printing tasks with optimal ganging strategies. The system analyzes incoming orders and groups them into existing LAY-A1 to LAY-Z2 columns based on cost-effectiveness, product compatibility, and deadline urgency.

## 🎯 Features

- **Smart Ganging Algorithm**: Automatically groups compatible tasks for optimal A3 sheet utilization
- **Product Compatibility Rules**: Handles 4 product types with specific ganging constraints
- **Cost Intelligence**: Only gangs when waste cost < screen setup cost, unless deadline critical
- **Size Support**: All 9 document sizes with precise A3 sheet fitting calculations
- **Deadline Management**: Prioritizes urgent orders even if not immediately cost-effective
- **LAY Column Integration**: Seamlessly assigns tasks to your existing LAY-A1 through LAY-Z2 workflow

## 📋 Product Types & Compatibility Rules

| Product Type | Compatible With | Notes |
|--------------|-----------------|-------|
| Full Colour | Single Colour White only | Can mix on same sheet |
| Single Colour | Same color only | Red with Red, Blue with Blue, etc. |
| Metal | Silver color only | Metal transfers isolated to silver |
| Zero | None (isolated) | Zero transfers never gang with others |

## 📏 Supported Transfer Sizes

| Size | Fits per A3 Sheet | Notes |
|------|-------------------|-------|
| A3 | 1 | Cannot be ganged |
| A4 | 1-2 | Optimal ganging size |
| A5 | 1-4 | High efficiency potential |
| A6 | 1-8 | 2 across x 4 down (154x109mm crop) |
| 295x100 | 1-2 | 1 across x 2 down (309x109mm crop) |
| 95x95 | 1-18 | 3 across x 6 down (103x109mm crop) |
| 100x70 | 1-32 | 4 across x 8 down (77x109mm crop) |
| 60x60 | 1-12 | 4 across x 3 down (77x63mm crop) |
| 290x140 | 1-2 | Wide format |

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

## 🎯 Best Practices

### 1. Deadline Management
- Set realistic deadline dates on incoming tasks
- Use deadline urgency to override cost decisions when needed
- Monitor critical tasks to ensure timely processing

### 2. LAY Column Capacity
- System limits 20 tasks per LAY column by default
- Monitor column capacity during peak periods
- Consider adding more LAY columns if needed consistently

### 3. Cost Optimization
- Review waste vs screen cost calculations periodically
- Adjust cost parameters if ganging behavior needs tuning
- Balance cost efficiency with production speed

### 4. Regular Analysis
- Run ganging analysis regularly throughout the day
- Consider scheduling automatic analysis every hour
- Monitor for tasks waiting too long for ganging opportunities

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

**Version**: 1.0.0  
**Compatible**: Odoo 16  
**License**: LGPL-3  
**Author**: Transfer Ganging Module