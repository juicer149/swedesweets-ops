# SwedeSweets

SwedeSweets is a Django application for managing wholesale and retail candy
operations.

The project currently includes:

- internal operations workflows
- B2B customer ordering
- public retail checkout
- products and inventory
- orders and fulfillment
- reservations
- payments
- account and access management

The application is under active development.

## Tech stack

- Python 3.12
- Django
- PostgreSQL in production
- SQLite for local development
- Vanilla JavaScript
- Custom CSS

## Local development

Clone the repository:

```bash
git clone git@github.com:juicer149/swedesweets-ops.git
cd swedesweets-ops
```

Create the virtual environment, install dependencies and run migrations:

```bash
make setup
```

Create a local superuser:

```bash
make superuser
```

Load demo data:

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
make setup
make run
make check
make test
make migrate
make makemigrations
make seed
make reset-demo
make superuser
make shell
make clean
```

## Project structure

```text
accounts/
    account identity, roles, capabilities and account lifecycle

business_portal/
    authenticated B2B customer UI

storefront/
    public retail UI

ops_portal/
    internal staff UI

products/
    product domain

inventory/
    physical inventory and stock reads

orders/
    order domain and lifecycle

customers/
    customer domain

reservations/
    stock reservation capability

payments/
    payment capability

fulfillment/
    shared fulfillment workflows

retail/
    retail application rules and checkout workflows

business/
    B2B application rules and workflows

config/
    Django configuration and cross-application composition

common/
    stable shared UI/application primitives
```

See `ARCHITECTURE.md` for dependency rules and architectural boundaries.

## Authentication and access

The project uses Django authentication together with application-specific
account roles and capabilities.

Account identity and capabilities live in `accounts`.

Cross-application route policy composition lives in `config`.

Authorization is deny-by-default for protected application routes.

For more detail, see:

```text
accounts/README.md
ARCHITECTURE.md
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

## Demo data

The demo seed creates representative customers, products, inventory batches and
orders for local development.

Reset the local database and seed demo data with:

```bash
make reset-demo
```

## Configuration

Development uses environment variables for settings that may differ between
machines or deployment environments.

Important variables include:

```text
DJANGO_SECRET_KEY
DJANGO_DEBUG
DJANGO_ALLOWED_HOSTS
DJANGO_CSRF_TRUSTED_ORIGINS

PGHOST
PGDATABASE
PGUSER
PGPASSWORD
PGPORT

EMAIL_BACKEND
DEFAULT_FROM_EMAIL
SERVER_EMAIL

SUMUP_API_KEY
SUMUP_MERCHANT_CODE
```

See `config/settings.py` for the current configuration contract.

## Email

Local development can use Django's console email backend.

Production email requires SMTP configuration through environment variables.

## Deployment

The project is configured for deployment on Railway.

Production should use:

* PostgreSQL
* environment-based secrets
* `DEBUG=False`
* configured `ALLOWED_HOSTS`
* configured CSRF trusted origins
* production email settings
* migrations before serving application traffic

## Documentation

* `ARCHITECTURE.md` — system-level architecture and dependency rules
* `accounts/README.md` — account identity and capability responsibilities

Additional app-local README files should only be added when an app has
non-obvious boundaries or invariants worth documenting.
