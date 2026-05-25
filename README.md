# SwedeSweets Ops

Internal operations MVP for SwedeSweets.

The app helps manage customers, products, inventory batches and orders from one small Django system.

## Features

- Dashboard for operational overview
- Customer management
- Product catalog with internal product codes, SKU, vegan flag and active status
- Inventory batches with physical, reserved and available stock
- Order placement, packing and delivery flow
- Login-protected internal pages
- Responsive UI for desktop and mobile

## Tech stack

- Python
- Django
- SQLite for local MVP development
- Vanilla JavaScript
- Tom Select for searchable select inputs
- Custom CSS

## Local setup

Clone the repository:

```bash
git clone git@github.com:juicer149/swedesweets-ops.git
cd swedesweets-ops
```

Create the virtual environment, install dependencies and run migrations:

```bash
make setup
```

Create an admin user:

```bash
make superuser
```

Seed demo data:

```bash
make reset-demo
```

Run the development server:

```bash
make run
```

Open:

```text
http://localhost:8000/
```

## Useful commands

```bash
make check
make migrate
make makemigrations
make seed
make reset-demo
make shell
make test
make clean
```

## Authentication

All application pages require login.

Use the Django superuser created with:

```bash
make superuser
```

## Demo data

The demo seed creates sample customers, products, inventory batches and orders so the MVP can be reviewed with realistic operational data.

## Project structure

```text
customers/   Customer models, views and forms
products/    Product catalog and product detail views
inventory/   Batch and stock management
orders/      Order placement, packing and delivery flow
common/      Shared UI/viewmodel helpers and middleware
templates/   Shared and app-specific templates
static/      CSS, JavaScript and assets
config/      Django settings, URLs and dashboard view
```

## Deployment notes

This project is currently prepared as a local Django MVP using SQLite.

Planned deployment work:

* Move secrets to environment variables
* Switch production database to PostgreSQL
* Configure static file serving
* Configure Railway deployment
* Add production `ALLOWED_HOSTS` and CSRF settings

## Status

MVP demo version.
