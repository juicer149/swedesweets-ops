# Architecture

SwedeSweets uses explicit boundaries between actor-facing interfaces, domain/application code, and application-wide composition.

The architecture is organized around one primary dependency rule:

```text
actor-facing UI
        ↓
domain / application code
```

Core domain and application code must not depend on the interface through which it is used.

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

Domain and application functionality should remain usable outside HTTP flows, for example from:

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

UI ownership follows the actor using the interface, not the domain being manipulated.

```text
business_portal
    authenticated B2B customer UI

storefront
    public retail UI

ops_portal
    internal staff UI
```

This means that a page used by staff belongs to `ops_portal` even when the page manipulates data owned by another domain.

For example:

```text
ops_portal/products/
    staff-facing product management

products/
    product state, queries and mutations
```

The portal owns the HTTP and presentation concerns.

The domain owns the underlying business behavior.

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

A useful distinction is:

```text
selector
    asks the system something

service
    changes the system

view
    translates HTTP into those operations
```

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

Other applications may use these selectors.

They should not recreate the same ORM knowledge themselves.

Cross-domain read use cases may compose domain-owned selectors:

```text
accounts/activity_selectors.py
        ↓
orders/selectors.py
products/selectors.py
inventory/selectors.py
customers/selectors.py
```

The composing module owns the use case.

The individual domains retain ownership of how their persistence is queried.

## Write ownership

Mutations belong to the domain or application capability that owns the behavior being changed.

For example:

```text
orders/services.py
    order lifecycle mutations

inventory/services.py
    inventory mutations and invariants

accounts/services.py
    account lifecycle mutations
```

Actor-facing portals may initiate these operations, but should not become the owner of their business rules.

```text
ops_portal
    HTTP request
        ↓
orders/services.py
    business mutation
        ↓
database
```

This keeps the same operation usable from another interface without reproducing its business logic.

## Accounts and authorization

`accounts` owns shared account identity and the capability language used across the project.

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

and:

> What capabilities does that identity have?

Authentication, account identity, authorization and UI routing are related but separate concerns.

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

For example, a business customer may have the capability to view orders while still being restricted to orders belonging to their own membership.

Conceptually:

```text
capability
    may view orders

scope
    may view these orders
```

Authorization without object scope is insufficient when data belongs to a specific customer, account or actor.

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

`config` may know about multiple applications because composing the application is its responsibility.

Domain apps should not become composition roots for unrelated applications.

A domain may know about its own dependencies.

It should not wire together the application as a whole.

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

This includes view models and presentation helpers that only make sense within a particular interface.

Neutral presentation helpers may remain close to a domain or shared capability when they do not know about a specific portal.

Prefer small duplication over premature cross-portal abstractions.

Two interfaces displaying similar information does not automatically mean they share the same presentation concept.

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

For example:

```text
business_portal
    B2B sales channel

storefront
    retail sales channel
```

A persistent `Customer` represents a business/customer entity.

Anonymous retail checkout does not require creating a `Customer`.

This keeps business identity separate from the mechanics of an individual retail purchase.

## Shared capabilities

Capabilities that are meaningful across channels should remain separate from actor-facing portals.

Examples:

```text
reservations
    stock reservation capability

payments
    payment capability

fulfillment
    shared fulfillment application workflows
```

A portal may use these capabilities without owning them.

```text
storefront ───────┐
business_portal ──┼──> reservations
ops_portal ───────┘
```

The same principle applies to future application capabilities.

Billing and invoicing, for example, should remain conceptually separate from payment processing even if a particular workflow uses both.

## Dependency tests

When deciding where code belongs, ask which direction the dependency points.

Good:

```text
ops_portal
    ↓
customers

business_portal
    ↓
orders

storefront
    ↓
products

config
    ↓
multiple applications
```

Suspicious:

```text
customers
    ↓
ops_portal

orders
    ↓
business_portal

products
    ↓
storefront
```

A core application importing an actor-facing portal is usually evidence that an interface concern has leaked into the domain.

Another useful test is:

> Could this domain operation still work if the current web interface disappeared?

If not, HTTP or presentation concerns may have moved too far inward.

## Design rules

Prefer:

```text
explicit dependencies
domain-owned persistence knowledge
selector-owned reads
service-owned mutations
thin HTTP orchestration
actor-owned presentation
fail-closed authorization
explicit object scope
small modules with one clear responsibility
```

Avoid:

```text
portal imports from core domain/application modules
business rules in templates
business rules in views
ORM knowledge duplicated across apps
navigation used as authorization
actor-specific presentation in domain modules
domain apps acting as global composition roots
generic abstractions created only to remove small duplication
```

## Current structure

The main interface boundaries are:

```text
business_portal
    authenticated B2B customer interface

storefront
    public retail interface

ops_portal
    internal staff interface
```

Application-wide composition lives in:

```text
config
```

Domain and application behavior remains in the applications that own the corresponding state or capability.

Examples of boundaries established during the architecture migration include:

```text
B2B customer UI
    -> business_portal

public retail UI
    -> storefront

staff account-management UI
    -> ops_portal/accounts

staff customer-management UI
    -> ops_portal/customers

cross-app policy composition
    -> config

post-login destination composition
    -> config

domain ORM queries
    -> owning domain selectors
```

These boundaries should be preserved as new functionality is added.

When introducing a new feature, first determine whether it represents:

```text
an actor-facing interface concern
a domain concern
an application capability
or application-wide composition
```

Its location should follow from that responsibility rather than from whichever existing module is easiest to modify.
