# Architecture

SwedeSweets uses explicit Django application boundaries.

This document describes the stable architectural direction of the project.
Some staff-facing HTTP/UI code is still being migrated toward these boundaries,
so the rules below describe the intended dependency direction rather than the
current location of every view.

## Dependency direction

Actor-facing UI depends on domain/application code.

```text
business_portal
storefront
ops_portal
        ↓
domain / application apps
```

Core domain/application code must not depend on actor-facing portals.

Domain and application functionality should remain usable outside HTTP flows,
for example from:

```text
manage.py shell
management commands
workers
tests
```

Core logic should therefore not require:

```text
HttpRequest
templates
messages
URL routing
browser state
```

Cross-application composition belongs in `config`.

## Actor-facing UI

UI ownership follows the actor using the interface, not the domain being
manipulated.

```text
business_portal
    authenticated B2B customer UI

storefront
    public retail UI

ops_portal
    internal staff UI
```

For example, staff product-management pages belong to `ops_portal`, while
product state, queries and mutations remain owned by `products`.

The project is still migrating some existing staff-facing views toward this
boundary.

## Domain and application apps

Domain apps own their persistence and business behavior.

Typical responsibilities:

```text
models.py
    persistent state

selectors.py
    read-only queries and read models

services.py
    mutations, workflows and invariants

access.py
    capability declarations for routes owned by the app
```

Not every app needs every module.

Selectors should not mutate state.

Services should own transactional writes and business invariants.

Views should remain thin orchestration around HTTP concerns.

## Read ownership

Persistence knowledge belongs to the domain that owns the model.

For example:

```text
orders/selectors.py
    knows how orders are queried

inventory/selectors.py
    knows how inventory batches are queried

products/selectors.py
    knows how products are queried

customers/selectors.py
    knows how customers are queried
```

Cross-domain read use cases may compose those selectors, but should not duplicate
their ORM knowledge.

Example:

```text
accounts/activity_selectors.py
        ↓
orders/selectors.py
products/selectors.py
inventory/selectors.py
customers/selectors.py
```

## Accounts and authorization

`accounts` owns the shared account identity and capability language.

```text
accounts/models.py
    StaffAccount
    CustomerMembership

accounts/roles.py
    AccountRole
    StaffAccessLevel
    Capability
    RoleSpec

accounts/permissions.py
    resolve Django User -> AccountRole -> RoleSpec

accounts/services.py
    account lifecycle mutations and invariants
```

Django authentication answers:

> Who is logged in?

`accounts` answers:

> What account identity does this user represent?
> What capabilities does that identity have?

Route access declarations live close to the routes they describe.

Global access-policy composition belongs in:

```text
config/policies.py
```

Authorization is fail-closed.

Navigation is UX, not authorization.

A visible or hidden link must never be treated as the security boundary.

## Object scope

Capabilities answer:

> May this actor access this kind of operation?

Scoped selectors answer:

> May this actor access this specific object?

Both may be required.

For example, a business customer may have permission to view their own orders,
but the order query must still be scoped through that customer's membership.

## Composition root

`config` owns application-wide composition.

Examples:

```text
config/policies.py
    aggregate route access declarations

config/login_routing.py
    choose the correct destination after login

config/context_processors.py
    compose actor-specific navigation

config/middleware.py
    global login/session behavior

config/settings.py
    wire installed apps and middleware
```

Domain apps should not become composition roots for unrelated applications.

## Presentation

Presentation code belongs to the actor-facing UI when it is actor-specific.

Examples:

```text
business_portal/
    B2B-specific labels, links and page context

ops_portal/
    staff-specific labels, actions, routes and page context

storefront/
    public retail presentation
```

Neutral presentation helpers may remain close to the domain or shared capability
when they do not know about a specific portal.

Prefer small duplication over premature cross-portal abstractions.

## Sales channels

Authentication and sales channel are separate concepts.

A user being authenticated does not by itself determine:

```text
catalog
pricing
payment behavior
reservation behavior
```

Those decisions belong to channel policy.

A persistent `Customer` represents a business/customer entity.

Anonymous retail checkout does not require creating a `Customer`.

## Shared capabilities

Capabilities that are meaningful across channels should remain separate from
actor-facing portals.

Examples:

```text
reservations
    stock reservation capability

payments
    payment capability

fulfillment
    shared fulfillment application workflows
```

Future billing/invoice behavior should remain separate from payment processing.

## Design rules

Prefer:

```text
explicit dependencies
domain-owned queries
service-owned mutations
thin HTTP orchestration
fail-closed authorization
small modules with one clear responsibility
```

Avoid:

```text
portal imports from core domain/application modules
business rules in templates
ORM knowledge duplicated across apps
navigation used as authorization
generic abstractions created only to remove small duplication
```

## Migration status

The project is currently being aligned with these boundaries.

Completed examples:

```text
B2B customer UI
    -> business_portal

public retail UI
    -> storefront

staff account-management UI
    -> ops_portal/accounts

cross-app policy composition
    -> config

post-login destination composition
    -> config

account activity ORM queries
    -> owning domain selectors
```

Some remaining staff-facing views in domain apps may still move into
`ops_portal`.

Update this section as those migrations are completed.
