# Architecture

SwedeSweets uses explicit boundaries between actor-facing interfaces,
domain/application code, shared capabilities, and application-wide composition.

The primary dependency rule is:

```text
actor-facing UI
        ↓
domain / application code
```

Core domain and application code must not depend on the interface through which
it is used.

## Dependency direction

The main actor-facing applications are:

```text
business_portal
storefront
ops_portal
        ↓
domain / application apps
```

The dependency direction points inward.

Actor-facing applications may depend on domain and application code.

Domain and application code must not depend on actor-facing applications.

For example:

```text
business_portal
    ↓
orders
products
customers
business

ops_portal
    ↓
orders
inventory
products
customers
accounts

storefront
    ↓
retail
payments
products
```

The reverse direction is not allowed:

```text
orders
    ✗→ business_portal

products
    ✗→ storefront

customers
    ✗→ ops_portal
```

This keeps business behavior independent of the HTTP interface that happens to
invoke it.

## Core code outside HTTP

Domain and application functionality should remain usable outside web requests.

Examples:

```text
manage.py shell
management commands
workers
scheduled jobs
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

HTTP concerns belong at the edge of the system.

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

For example:

```text
ops_portal/products/
    staff-facing product management

products/
    product state
    product queries
    product mutations
```

The portal owns:

```text
views
forms
actor-specific presentation
view models
templates
routes
navigation
HTTP orchestration
```

The domain or application capability owns:

```text
persistent state
business invariants
domain queries
mutations
transactions
```

## Portal organization

Actor-facing applications may be organized internally around stable actor use
cases.

For example:

```text
business_portal/
    orders/
        forms.py
        selectors.py
        services.py
        views.py
        presentation.py
        *_viewmodels.py

    profile/
        forms.py
        services.py
        views.py

    selectors.py
        portal-level actor scope

    views.py
        portal home and simple portal-level pages
```

This is not a second domain model.

`business_portal/orders` owns the B2B customer's order interface and
portal-specific orchestration.

The underlying order domain remains owned by:

```text
orders/
```

Likewise:

```text
ops_portal/orders
    staff order interface

orders
    order domain
```

Portal package structure should follow useful actor-facing use cases rather than
mechanically mirror every domain application.

## Domain and application apps

Domain and application apps own business behavior and persistence knowledge.

Typical responsibilities include:

```text
models.py
    persistent state and model-level invariants

selectors.py
    read-only queries and read models

services.py
    mutations, workflows and transactional invariants

errors.py
    domain/application failures

datatypes.py
    explicit input or result structures
```

Not every application needs every module.

A useful distinction is:

```text
selector
    asks the system something

service
    changes the system

view
    translates HTTP into application operations
```

Selectors should not mutate persistent state.

Services should own mutations and transactional business behavior.

Views should remain thin HTTP orchestration.

## Read ownership

Persistence knowledge belongs to the application that owns the model.

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

Other applications may call these selectors.

They should not duplicate their ORM knowledge.

For example:

```text
accounts/activity_selectors.py
        ↓
orders/selectors.py
products/selectors.py
inventory/selectors.py
customers/selectors.py
```

The composing module owns the cross-domain use case.

Each domain retains ownership of how its own persistence is queried.

## Actor and object scope

A portal may add actor-specific scoping on top of domain selectors.

For example:

```text
business_portal/selectors.py
    resolve logged-in user
        ↓
    CustomerMembership
        ↓
    Customer
```

An order-specific portal selector may then compose that actor scope with
domain-owned order queries:

```text
business_portal/orders/selectors.py
        ↓
business_portal/selectors.py
orders/selectors.py
```

This keeps two responsibilities separate:

```text
domain selector
    how orders are queried

portal selector
    which orders this actor may address
```

Portal selectors should compose domain queries rather than reproduce their ORM
implementation.

## Write ownership

Mutations belong to the domain or application capability that owns the behavior
being changed.

Examples:

```text
orders/services.py
    generic order lifecycle mutations

inventory/services.py
    inventory mutations and invariants

customers/services.py
    customer mutations

accounts/services.py
    account lifecycle mutations
```

Actor-facing portals may provide small application adapters around these
operations when an actor-specific use case requires orchestration.

For example:

```text
business_portal/orders/services.py
    B2B draft-order use case
        ↓
business/services.py
orders/services.py
```

or:

```text
business_portal/profile/services.py
    B2B profile-update use case
        ↓
customers/services.py
```

Portal services must not become a second implementation of domain business
rules.

Their role is actor-specific application orchestration.

## Transactions

Transactional writes belong as close as practical to the mutation whose
invariants they protect.

For example, locking and lifecycle checks used by order mutation services belong
with the order application behavior rather than with a particular portal.

HTTP views should not be responsible for maintaining database consistency.

Conceptually:

```text
HTTP request
    ↓
portal view
    ↓
application/domain service
    ↓
transaction
    ↓
database
```

## Accounts and authorization

`accounts` owns shared account identity and the capability language used across
the project.

Examples:

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

Authentication, account identity, authorization, sales channel and UI routing
are related but separate concepts.

## Shared account UI

Not every HTTP view belongs in an actor portal.

Shared authentication and self-account behavior may remain in `accounts` when
it is not specific to B2B customers, staff operations or retail storefront
behavior.

Examples include shared login/self-account routing.

Actor-specific account administration belongs to the actor-facing portal.

For example:

```text
ops_portal/accounts
    staff-facing account management

accounts
    shared identity, permissions, lifecycle and self/account behavior
```

## Route authorization

Route access declarations live close to the routes they describe.

Application-wide access-policy composition belongs in:

```text
config/policies.py
```

Authorization is fail-closed.

Navigation is UX, not authorization.

A link being hidden or visible must never be treated as the security boundary.

The destination route must enforce its own access policy.

## Object scope

Capabilities answer:

> May this actor access this kind of operation?

Scoped selectors answer:

> May this actor access this specific object?

Both may be required.

For example:

```text
capability
    may view own orders

object scope
    this order belongs to the current customer's membership
```

Capability checks without object scoping are insufficient for actor-owned data.

## Navigation

Navigation is actor-specific presentation.

Generic navigation primitives may live in shared code:

```text
common/navigation.py
```

Actor-specific navigation belongs with the actor:

```text
business_portal/navigation.py
ops_portal/navigation.py
```

Application-wide selection and composition of navigation belongs in:

```text
config/context_processors.py
```

Navigation should express what the UI offers.

It must not become an authorization mechanism.

## Composition root

`config` owns application-wide composition.

Examples:

```text
config/settings.py
    installed applications
    middleware
    global Django configuration

config/policies.py
    aggregate route access declarations

config/login_routing.py
    choose the appropriate destination after login

config/context_processors.py
    compose actor-specific navigation

config/middleware.py
    global request/session behavior

config/urls.py
    top-level URL composition
```

`config` may know about multiple applications because wiring the whole
application together is its responsibility.

Domain applications should not become composition roots for unrelated
applications.

## Presentation

Presentation code belongs to the actor-facing application when it is
actor-specific.

Examples:

```text
business_portal
    B2B-specific status labels
    order cards
    B2B catalog labels
    page context
    B2B links and actions

ops_portal
    staff-specific actions
    operational labels
    staff routes
    staff page context

storefront
    public retail presentation
```

Neutral helpers may remain near a domain when they do not know about a specific
actor or portal.

For example:

```text
products/localization.py
    channel-neutral product-name localization
```

while:

```text
business_portal/orders/product_presentation.py
    B2B-specific product presentation
```

belongs to the portal.

Prefer small duplication over premature cross-portal abstractions.

Similar HTML or labels do not automatically represent the same abstraction.

## Shared UI primitives

Reusable actor-neutral UI primitives may live in:

```text
common/
```

Examples include:

```text
table controls
detail cards
page headers
generic UI dataclasses
form-layout helpers
navigation primitives
```

Shared primitives should describe mechanics or neutral presentation structure.

Actor-specific:

```text
copy
labels
URLs
actions
workflow
authorization meaning
```

should remain in the owning portal.

## Sales channels

Authentication and sales channel are separate concepts.

Being logged in does not by itself determine:

```text
catalog
pricing
payment behavior
reservation behavior
fulfillment policy
```

Those decisions belong to channel policy and channel-specific application
behavior.

The current actor-facing channel entry points are:

```text
business_portal
    authenticated B2B customer experience

storefront
    public retail experience
```

The domain should not infer sales-channel behavior merely from whether a Django
user is authenticated.

## Customer identity

A persistent:

```text
Customer
```

represents a business/customer entity.

It is not synonymous with:

```text
Django User
shopping session
anonymous retail buyer
individual order
```

An anonymous retail checkout does not require creating a persistent `Customer`.

Retail orders may instead preserve the buyer information required by the order
through an order snapshot.

This keeps persistent business identity separate from a single retail purchase.

## Products and inventory

A product and physical stock are separate concepts.

```text
Product
    stable sellable product / SKU identity

InventoryBatch
    physical stock
    quantity
    expiry
    location
```

Product identity should not encode individual stock batches.

Inventory behavior belongs to `inventory`.

Product identity and catalog-level product behavior belong to `products`.

## Orders

`orders` owns the shared order model and generic order behavior.

It is not the owner of one specific actor interface.

The same order domain may be used by:

```text
business_portal
ops_portal
retail
fulfillment
payments
```

Actor-specific presentation and HTTP behavior stay outside `orders`.

For example:

```text
business_portal/orders
    customer order UI

ops_portal/orders
    staff order UI

orders
    order state
    selectors
    lifecycle services
    datatypes
```

## Business channel

The `business` application owns B2B-specific application behavior that is not
merely presentation.

For example, B2B order preparation or draft workflows may compose generic order
services while applying business-channel policy.

The dependency direction remains:

```text
business_portal
        ↓
business
        ↓
orders / inventory / other capabilities
```

The B2B portal should not make generic `orders` responsible for B2B-only
interface behavior.

## Retail channel

`retail` owns retail-specific application behavior and policy.

Examples include retail checkout and payment-related retail workflows.

The public HTTP interface belongs to:

```text
storefront
```

Conceptually:

```text
storefront
    public HTTP/UI
        ↓
retail
    retail application behavior
        ↓
orders
payments
reservations
products
inventory-related capabilities
```

Retail domain/application behavior should remain usable without requiring a
browser request.

## Shared capabilities

Capabilities meaningful across channels remain separate from actor-facing
portals.

Current examples include:

```text
reservations
    stock reservation capability

payments
    payment capability

fulfillment
    shared fulfillment application workflows
```

Portals and channel applications may use these capabilities without owning them.

For example:

```text
storefront ───────┐
business_portal ──┼──> shared capabilities
ops_portal ───────┘
```

A shared capability should exist because it represents a stable application
concept, not merely because two callers currently contain similar code.

## Payments

Payment processing is a capability separate from retail presentation.

```text
payments
    payment records
    provider integration
    payment services
    provider callbacks/webhooks where appropriate

retail
    retail payment workflow and policy

storefront
    public retail payment-return UI
```

Not all HTTP endpoints are actor-facing pages.

Provider callbacks and webhooks may legitimately live with the capability they
serve when they represent machine-to-machine integration rather than an actor
portal.

## Billing

Payment processing and billing/invoicing are different concepts.

Future billing behavior should not be added to `payments` merely because money
is involved.

Conceptually:

```text
payments
    payment execution and provider state

billing
    invoices
    billing snapshots
    accounting-facing billing concepts
```

A `billing` application should only be introduced when that capability actually
exists.

## Fulfillment

`fulfillment` is a shared application capability.

It may compose:

```text
orders
inventory
reservations
```

to perform fulfillment workflows.

It should not own actor-specific staff pages.

Staff fulfillment UI belongs in `ops_portal`.

## Avoid synthetic symmetry

Applications should not be created only to make the package tree look
symmetrical.

For example, `ops_portal` does not require a generic `ops` domain layer merely
because:

```text
business_portal
    uses business
```

Operational use cases should live in the domain or shared capability whose
business meaning they represent.

A new domain/application package should be introduced only when a stable concept
emerges.

## Avoid premature catalog abstraction

A separate `catalog` application should not be introduced merely because more
than one sales channel displays products.

Today:

```text
products
    owns product data and neutral product behavior

business_portal
    owns B2B product presentation

storefront
    owns retail product presentation
```

A shared catalog application would only be justified if a stable,
channel-neutral catalog read model or application capability emerges.

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
retail

business
    ↓
orders

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

retail
    ↓
storefront
```

A core or application module importing an actor-facing portal usually means an
interface concern has leaked inward.

Another useful test is:

> Could this domain or application operation still work if the current web
> interface disappeared?

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
actor-specific object scoping at the edge
fail-closed authorization
explicit channel policy
small modules with one clear responsibility
stable shared capabilities
```

Avoid:

```text
core domain/application imports from actor-facing portals
business rules in templates
business rules in HTTP views
ORM knowledge duplicated across applications
navigation used as authorization
actor-specific presentation in core domain modules
domain applications acting as global composition roots
sales-channel policy inferred only from authentication
generic abstractions created only to remove small duplication
new applications created only for structural symmetry
```

## Current application boundaries

The main actor-facing interfaces are:

```text
business_portal
    authenticated B2B customer interface

storefront
    public retail interface

ops_portal
    internal staff interface
```

Internal staff UI currently follows these ownership boundaries:

```text
ops_portal/accounts
    staff account management

ops_portal/customers
    staff customer management

ops_portal/products
    staff product management

ops_portal/inventory
    staff inventory management

ops_portal/orders
    staff order management
```

The corresponding state and business behavior remain in:

```text
accounts
customers
products
inventory
orders
```

The B2B customer interface is organized around customer-facing use cases:

```text
business_portal/orders
    order placement
    draft handling
    order history
    order detail
    B2B order presentation

business_portal/profile
    customer profile editing

business_portal
    portal home
    shared B2B navigation
    portal-level actor scope
```

The retail interface is:

```text
storefront
```

while retail-specific application behavior remains in:

```text
retail
```

Application-wide composition remains in:

```text
config
```

## Architecture migration status

The main architecture migration is complete.

Established boundaries include:

```text
B2B customer UI
    -> business_portal

B2B order UI
    -> business_portal/orders

B2B profile UI
    -> business_portal/profile

public retail UI
    -> storefront

staff account-management UI
    -> ops_portal/accounts

staff customer-management UI
    -> ops_portal/customers

staff product-management UI
    -> ops_portal/products

staff inventory-management UI
    -> ops_portal/inventory

staff order-management UI
    -> ops_portal/orders

cross-application access-policy composition
    -> config

post-login destination composition
    -> config

actor-specific navigation composition
    -> config + owning portal

domain ORM queries
    -> owning domain selectors
```

This document now describes the current intended structure rather than a
temporary migration state.

## Adding new functionality

When introducing a new feature, first determine what kind of responsibility it
represents.

Ask:

```text
Is this actor-facing HTTP or presentation?
    -> owning portal / storefront

Is this persistent domain state or invariant?
    -> owning domain application

Is this a read of domain-owned persistence?
    -> owning domain selector

Is this a mutation or workflow?
    -> owning domain/application service

Is this channel-specific business behavior?
    -> channel application such as business or retail

Is this a capability shared across channels?
    -> shared application capability

Is this application-wide wiring?
    -> config
```

The location should follow from the responsibility.

It should not be chosen merely because a nearby module is convenient to edit.

## Guiding principle

The architecture should make the common dependency direction obvious:

```text
HTTP / presentation
        ↓
application use case
        ↓
domain behavior
        ↓
persistence
```

The purpose of these boundaries is not to maximize the number of modules.

The purpose is to make change local, dependencies explicit, business rules
reusable, and incorrect coupling difficult.
