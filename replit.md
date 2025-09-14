# Overview

This repository contains an Odoo 16 ERP system with a custom module for transfer printing ganging optimization. The main application is the "Transfer Ganging Optimization Module" which intelligently organizes transfer printing tasks to maximize A3 sheet utilization while considering product compatibility rules, cost-effectiveness, and deadline constraints.

The custom module analyzes incoming printing orders and groups them into existing LAY-A1 to LAY-Z2 columns using smart algorithms that only gang orders when waste cost is less than screen setup cost, unless deadline pressures require immediate processing.

# User Preferences

Preferred communication style: Simple, everyday language.

# System Architecture

## Core Framework
- **Platform**: Odoo 16 - Open source ERP framework built on Python
- **Web Framework**: Built on Werkzeug WSGI with custom HTTP layer for request handling
- **Database ORM**: Custom ORM with PostgreSQL backend for data persistence
- **Module Architecture**: Modular addon system allowing custom business logic extensions

## Transfer Ganging Module Design
- **Location**: `custom_addons/transfer_ganging/` - Custom addon following Odoo's module structure
- **Core Engine**: `models/ganging_engine.py` - Main optimization algorithm for task grouping
- **Data Models**: Extends `project.task` model with transfer-specific fields (product type, size, color)
- **Business Logic**: Implements compatibility rules for 4 product types (Full Colour, Single Colour, Metal, Zero)
- **Size Support**: Handles 9 different transfer sizes with precise A3 sheet fitting calculations

## Product Compatibility Rules
- **Full Colour**: Can mix with Single Colour White only
- **Single Colour**: Same color grouping only (Red with Red, Blue with Blue)
- **Metal**: Isolated to silver color only  
- **Zero**: Never gangs with other products (completely isolated)

## Cost Optimization Logic
- **Primary Rule**: Only gang when paper waste cost < screen setup cost
- **Exception**: Deadline-critical orders override cost considerations
- **Sheet Utilization**: Calculates optimal placement on 438×310mm A3 sheets
- **LAY Integration**: Assigns optimized groups to existing LAY-A1 through LAY-Z2 workflow columns

## Data Structure
- **Sheet Dimensions**: 438mm × 310mm production A3 sheets (135,780 mm² total area)
- **Size Mapping**: Dictionary-based size definitions with precise crop dimensions including bleed
- **Task Extensions**: Additional fields on project tasks for transfer product type, size, and color

# External Dependencies

## Python Dependencies
- **Core Odoo Requirements**: As defined in `odoo/requirements.txt` including PostgreSQL adapter, XML processing, web framework components
- **Essential Libraries**: psycopg2 for database connectivity, lxml for XML processing, Pillow for image handling
- **Web Stack**: Werkzeug WSGI framework, Jinja2 templating, gevent for async processing

## Database System
- **Primary Database**: PostgreSQL (psycopg2 adapter with connection pooling)
- **ORM Layer**: Custom Odoo ORM with advanced field types and relationship management
- **Migration System**: Built-in database migration and module upgrade handling

## Web Technologies
- **Frontend**: Odoo's web client built on JavaScript with custom components
- **Templates**: Jinja2 templating system for dynamic content generation
- **Assets**: SCSS/CSS compilation and JavaScript bundling system

## Authentication & Security
- **Multi-factor Auth**: TOTP support with optional mail-based 2FA
- **OAuth Integration**: Support for external OAuth providers
- **LDAP Integration**: Enterprise directory authentication
- **Password Policies**: Configurable password strength requirements

## Business Integrations
- **Email Processing**: SMTP/IMAP integration for automated email handling
- **Calendar Systems**: iCal/CalDAV support for scheduling integration
- **Payment Processing**: Extensible payment provider framework
- **Barcode Support**: GS1 barcode nomenclature and scanning capabilities