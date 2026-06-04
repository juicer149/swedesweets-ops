# SwedeSweets Ops

Internal operations MVP for SwedeSweets.

The app helps manage customers, products, inventory batches, orders and account access from one small Django system.

## Features

- Operations dashboard with current work queues and inventory signals
- Customer management with active/inactive customer lifecycle
- Product catalog with internal product codes, SKU, vegan flag and active status
- Inventory batches with physical, reserved, available and orderable stock
- Expiry-aware stock reservation so expired batches cannot be ordered
- Order placement, packing, delivery, cancellation and edit flow
- Batch-level FEFO allocation and reservation tracking
- Historical customer snapshots on orders
- Account roles for owner, full staff, restricted staff and customer users
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

## Authentication and accounts

All application pages require login.

The project uses Django's built-in `User` model for authentication. Business identity is modeled separately in the `accounts` app.

Current account roles:

* Owner
* Full staff
* Restricted staff
* Customer
* Unknown/unconfigured user

The `accounts` app owns:

* Staff accounts
* Customer memberships
* Role resolution
* Role capabilities
* Account creation services

A Django user should represent exactly one business identity:

```text
owner/superuser
or staff account
or customer membership
or unknown/unconfigured
```

A user must not be linked to both staff and customer identities.

For local development, create a Django superuser with:

```bash
make superuser
```

## Customers

Customers are the operational business entities that orders belong to.

Customers are not hard-deleted as part of normal application use. Instead, customers can be deactivated with `is_active=False`.

This keeps historical orders intact while allowing old customers to be hidden from new workflows later.

Current customer data includes:

* Name
* Email
* Phone number
* Country
* City
* Address line
* Active status

## Products

Products are stable operational objects used by orders and inventory.

Product identity includes:

* SKU
* Stock unit
* Weight per unit

These identity fields are intentionally protected after creation because historical orders, inventory and stock conversions depend on them.

Editable product/catalog data includes:

* Internal number
* Manufacturer
* Brand
* Name
* Vegan flag
* Active status
* Optional profile data such as description, ingredients and image URL

Inactive products are kept for history but should not be offered as normal order choices.

## Inventory

Inventory is represented through physical batches.

Inventory batches track:

* Product
* Batch ID
* Quantity
* Best-before date
* Location
* Status

Batch statuses:

* Active
* Depleted
* Closed

Stock reservation is order-aware and expiry-aware. Expired batches are not orderable, even if they still have physical quantity and have not been manually closed.

Order allocation uses FEFO:

```text
first-expired, first-out
```

Physical stock is reduced when an order is packed.

## Orders

Orders own the order lifecycle.

Order statuses:

* Draft
* Placed
* Packed
* Delivered
* Cancelled

Order flow:

```text
draft -> placed -> packed -> delivered
draft -> cancelled
placed -> cancelled
```

Order lines store normalized quantities in product stock units.

Placed orders reserve inventory through batch-level allocations. Packed orders consume those allocations and reduce physical stock.

Orders keep protected foreign keys to customers, products, inventory batches and audit users where historical integrity matters.

Orders also store customer snapshots when created:

* Customer name
* Customer email
* Customer phone number
* Customer country
* Customer city
* Customer address line

This allows historical order views to keep showing the customer data that was true when the order was placed, even if the live customer profile changes later.

## Data retention and deletion policy

Normal application behavior should prefer lifecycle state over hard deletion.

General rules:

```text
Customers:
  deactivate, do not hard-delete

Users:
  deactivate, do not hard-delete

Products:
  mark inactive, do not hard-delete

Inventory batches:
  deplete or close, do not hard-delete

Orders:
  preserve historical data
```

Important historical relations use `PROTECT` so data cannot accidentally disappear through cascading deletes.

Examples:

* Orders protect their customer relation
* Order lines protect their product relation
* Allocations protect their inventory batch relation
* Order audit fields protect the user relation
* Customer memberships protect their customer relation

If anonymization is needed later, it should be implemented as explicit service-layer use cases:

```text
customers/services.py
  anonymize_customer(...)

accounts/services.py
  anonymize_user_account(...)
```

Anonymization should not live in `common`, because the rules are domain-specific.

## Demo data

The demo seed creates sample customers, products, inventory batches and orders so the MVP can be reviewed with realistic operational data.

## Project structure

```text
accounts/    Account identity, roles, memberships and account creation services
customers/   Customer models, views, forms, selectors and services
products/    Product catalog, product detail views and product services
inventory/   Batch, stock, expiry and reservation-related inventory logic
orders/      Order placement, packing, delivery, cancellation and allocation flow
common/      Shared UI, viewmodel, table and dashboard helpers
templates/   Shared and app-specific templates
static/      CSS, JavaScript and assets
config/      Django settings, URLs and dashboard/root views
```

## Tests

Run the full test suite:

```bash
make test
```

Run Django system checks:

```bash
make check
```

The test suite currently covers:

* Products
* Inventory
* Orders
* Customers
* Accounts

## Deployment notes

This project is prepared for deployment work on Railway.

Important production concerns:

* Move secrets to environment variables
* Use PostgreSQL in production
* Configure static file serving
* Configure production `ALLOWED_HOSTS`
* Configure production CSRF trusted origins
* Run migrations before serving traffic
* Keep debug mode disabled in production

## Status

MVP operations system under active development.

Current focus areas:

* Account role middleware
* Permission checks for staff/customer capabilities
* Role-aware dashboard and navigation
* Customer-facing catalog/portal later
