{
    'name': 'Transfer Ganging Optimization',
    'version': '16.0.1.0.0',
    'category': 'Project',
    'summary': 'Intelligent ganging optimization for transfer printing orders',
    'description': """
        This module adds intelligent ganging capabilities to project tasks for transfer printing.
        Features:
        - Automatic task analysis for optimal A3 sheet utilization
        - Cost-effectiveness calculations comparing screen setup vs paper waste
        - Product type compatibility rules (Full Colour, Single Colour, Metal, Zero)
        - Support for 9 different transfer sizes
        - Deadline-aware planning that prioritizes urgent orders
        - Integration with existing LAY column workflow
    """,
    'author': 'Transfer Printing Solutions',
    'depends': ['base', 'project'],
    'data': [
        'security/ir.model.access.csv',
        'views/project_task_views.xml',
        'data/server_actions.xml',
    ],
    'installable': True,
    'auto_install': False,
    'application': False,
}