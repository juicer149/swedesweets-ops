# Accounts architecture

The accounts app owns business identity, roles, capabilities and route access
enforcement.

Django authentication answers:

    Who is logged in?

The accounts app answers:

    What business identity does this user represent?
    What is this identity allowed to do?

## Main pieces

```text
models.py
  Persistent account identity links:
    User -> StaffAccount
    User -> CustomerMembership

roles.py
  AccountRole, StaffAccessLevel, Capability and RoleSpec.
  Owns stable role metadata such as role labels, role ranks and
  staff access-level labels.

permissions.py
  Resolves user -> AccountRole -> RoleSpec.
  Provides require_capability(...) for explicit checks when needed.

access.py
  Declares accounts-owned route access:
    protected account views -> required Capability
    auth-exempt views -> allowed through custom middleware

policies.py
  Aggregates app-level access declarations into one route policy map.
  Views are denied by default unless listed in aggregated VIEW_CAPABILITIES
  or AUTH_EXEMPT_VIEWS.

middleware.py
  Attaches request.account_role and request.role_spec.
  Enforces route access using policies.py.

navigation.py
  Builds role-aware primary navigation.
  Navigation is UX, not authorization.

context_processors.py
  Exposes navigation viewmodels to templates.

selectors.py
  Read-side account queries and view rows:
    account list rows
    account identity summaries
    account activity rows

services.py
  Account management use cases:
    create internal account
    update internal account
    create customer account

forms.py
  Validates account management form input.

form_viewmodels.py
  Builds form page context for account management views.

detail_viewmodels.py
  Builds account detail page context and actions.
```

Other apps own their own route access declarations:

```text
dashboard/access.py
orders/access.py
inventory/access.py
products/access.py
customers/access.py
```

Each app that owns views should declare the access policy for those views in its
own `access.py` module.

## Business identity

A user may be linked to one business identity type:

```text
User -> StaffAccount
or
User -> CustomerMembership
or
no business identity yet
```

A user must not be linked to both staff and customer identity. If that happens,
`resolve_account_role(...)` raises `InvalidAccountIdentity`.

Superusers resolve to `AccountRole.OWNER`.

Account identity resolution belongs in `accounts/permissions.py`, not
`accounts/roles.py`, because it depends on Django `User` state and related
database rows.

`accounts/roles.py` should remain a pure role/capability module. It should know
what roles exist and what those roles can do, but it should not know which
specific `User`, `StaffAccount` or `CustomerMembership` carries a role.

## Access model

The access model has three layers:

```text
AccountRole
  broad business identity:
    OWNER, FULL_STAFF, RESTRICTED_STAFF, CUSTOMER, UNKNOWN

Capability
  one named permission, such as:
    Capability.PACK_ORDERS
    Capability.CREATE_BATCHES
    Capability.VIEW_CUSTOMERS

RoleSpec
  immutable set of Capability values describing what a role can do
```

Code should ask:

```python
role_spec.allows(Capability.PACK_ORDERS)
```

instead of checking raw strings or internal storage directly.

`RoleSpec` currently stores capabilities as a `frozenset[Capability]`. Other
modules should not depend on that representation. They should use
`role_spec.allows(...)`.

## Role metadata

Stable role metadata lives in `accounts/roles.py`.

Examples:

```text
role label
  AccountRole.FULL_STAFF -> "Full staff"

role rank
  OWNER before FULL_STAFF before RESTRICTED_STAFF before CUSTOMER before UNKNOWN

staff access-level label
  StaffAccessLevel.FULL -> "Full access"
```

Use helper functions instead of duplicating maps in selectors, navigation or
templates:

```python
get_role_label(AccountRole.FULL_STAFF)
get_role_rank(AccountRole.FULL_STAFF)
get_staff_access_level_label(StaffAccessLevel.FULL)
```

This keeps the stable role language in one place.

User-specific identity labels do not belong in `roles.py`.

For example, these are selector/viewmodel concerns:

```text
"Superuser"
"Internal staff · Full access"
"Eva Sandelgård / Le Salon"
```

They depend on a concrete `User` and its linked identity rows.

## Account management use cases

Internal account management is handled through explicit service functions.

Managers may create and edit internal staff accounts through accounts views. The
service layer owns invariants such as:

```text
a manager cannot deactivate their own account
a full staff user cannot remove their own account management access
user email and username stay aligned
staff access level changes are saved atomically with User changes
```

Account creation and update logic should stay in `accounts/services.py`, not in
views or forms.

Forms validate user input. Services apply business rules and write to the
database. Views coordinate the HTTP flow.

Customer account creation is also an account-management use case. A customer
login should be linked through `CustomerMembership`.

Customer portal access must still be scoped through customer membership. A
customer user must only see records belonging to their linked `Customer`.

## Inactive users

Inactive users are not allowed to continue through the custom middleware.

If an authenticated inactive user reaches the application, the login middleware
logs the user out and redirects to the inactive account page. This keeps inactive
state as a login/session concern instead of scattering `is_active` checks across
views.

Deactivating a user disables login access. It does not delete the user or remove
historical audit references.

## Route policy

Route access is declared app-locally and enforced centrally.

Each app declares the policy for the views it owns:

```text
accounts/access.py
dashboard/access.py
orders/access.py
inventory/access.py
products/access.py
customers/access.py
```

Protected views are mapped by Django `resolver_match.view_name`:

```python
from accounts.roles import Capability


VIEW_CAPABILITIES = {
    "orders:pack": Capability.PACK_ORDERS,
    "orders:deliver": Capability.DELIVER_ORDERS,
}
```

Auth-exempt views are declared in `accounts/access.py`.

These views are allowed through the custom login/access middleware because
Django's built-in auth views own their own access flow, or because the view must
be reachable before login.

Auth-exempt does not always mean public. For example, `password_change` is
auth-exempt from the custom middleware, but Django still requires an
authenticated user.

```python
AUTH_EXEMPT_VIEWS = frozenset(
    {
        "login",
        "logout",
        "password_change",
        "password_change_done",
        "password_reset",
        "password_reset_done",
        "password_reset_confirm",
        "password_reset_complete",
        "accounts:inactive",
    }
)
```

`accounts/policies.py` aggregates app-level declarations:

```python
VIEW_CAPABILITIES = {
    **ACCOUNT_VIEW_CAPABILITIES,
    **DASHBOARD_VIEW_CAPABILITIES,
    **ORDER_VIEW_CAPABILITIES,
    **INVENTORY_VIEW_CAPABILITIES,
    **PRODUCT_VIEW_CAPABILITIES,
    **CUSTOMER_VIEW_CAPABILITIES,
}
```

Rules:

```text
auth-exempt view -> allowed through custom middleware
protected view   -> requires mapped capability
unknown view     -> denied
anonymous user   -> redirected to login for protected views
authenticated user without capability -> 403
```

This means new protected views must be added to the owning app's `access.py`.
They become enforceable when `accounts/policies.py` aggregates that app's
declarations.

Protected views missing from both aggregated `VIEW_CAPABILITIES` and
`AUTH_EXEMPT_VIEWS` are denied by default.

## Navigation is not authorization

`accounts/navigation.py` decides which top-level links a role should see.

It does not decide what a user may reach. Route access is still enforced by
`ViewCapabilityMiddleware`.

A role may have read access to a route without seeing it in the navbar.

Example:

```text
restricted staff may open a customer detail page from an order,
but does not need Customers as a top-level navigation item.
```

Avoid putting role/capability `if` logic directly in templates when it can be
built in Python and tested.

## Selectors and viewmodels

Selectors are read-side code.

They may:

```text
query the database
select/prefetch related rows
build immutable rows for presentation
return ready-to-render labels and URLs
```

They should not:

```text
write to the database
enforce business mutations
decide route authorization
hide missing capability checks
```

Account list rows are built in `accounts/selectors.py`.

Account detail page context is built in `accounts/detail_viewmodels.py`.

Account form page context is built in `accounts/form_viewmodels.py`.

Templates should receive ready-to-display values where practical. They should
not know how to resolve account roles, inspect capabilities or derive business
identity labels.

## Account activity

Account activity is currently read from existing audit fields on domain models.

Examples:

```text
Order.placed_by / Order.placed_at
Order.cancelled_by / Order.cancelled_at
Product.created_by / Product.created_at
InventoryBatch.closed_by / InventoryBatch.closed_at
Customer.edited_by / Customer.edited_at
```

`accounts/selectors.py` defines dataclass-based activity specs that describe:

```text
which model to query
which actor field to filter by
which timestamp field to sort by
which route the activity links to
which label and tone the UI should show
```

This is intentionally a small dispatch table, not a full activity framework.

The current approach is acceptable for MVP account detail pages:

```text
read recent rows per activity type
combine them in Python
sort by occurred_at
return the latest ACCOUNT_ACTIVITY_LIMIT rows
```

If activity becomes a central product feature, consider adding a persistent
`ActivityEvent` model written from service-layer use cases.

Avoid using Django signals for core audit/activity creation unless there is a
strong reason. Service-layer writes are more explicit and easier to reason about.

## Customer portal query scope

Customer portal access must be scoped at the query level.

A customer user must never fetch records only by primary key:

```python
Order.objects.get(pk=order_id)
```

Instead, customer-facing selectors must scope through the linked customer:

```python
Order.objects.get(
    pk=order_id,
    customer=request.user.customer_membership.customer,
)
```

or through a dedicated selector:

```python
get_customer_portal_order(
    user=request.user,
    order_id=order_id,
)
```

Capability checks answer:

```text
May this role access this kind of page?
```

Scoped queries answer:

```text
Does this specific row belong to this specific customer?
```

Both are required.

## Adding a new capability

1. Add the capability in `accounts/roles.py`.

```python
class Capability(StrEnum):
    EXPORT_ORDERS = "can_export_orders"
```

2. Enable it for the roles that should have it.

If the role uses a shared capability set, add the new capability there:

```python
STAFF_CAPABILITIES = frozenset(
    {
        ...
        Capability.EXPORT_ORDERS,
    }
)
```

If the role spec is defined directly, add it to that role's capability set:

```python
EXPORT_STAFF_SPEC = RoleSpec(
    capabilities=frozenset(
        {
            ...
            Capability.EXPORT_ORDERS,
        }
    )
)
```

3. Map any protected views that require it in the owning app's `access.py`.

```python
# orders/access.py

VIEW_CAPABILITIES = {
    ...
    "orders:export": Capability.EXPORT_ORDERS,
}
```

4. Make sure `accounts/policies.py` aggregates that app's `VIEW_CAPABILITIES`.

```python
from orders.access import VIEW_CAPABILITIES as ORDER_VIEW_CAPABILITIES


VIEW_CAPABILITIES = {
    ...
    **ORDER_VIEW_CAPABILITIES,
}
```

5. Use it in UX builders if the capability should affect visible UI.

```python
role_spec.allows(Capability.EXPORT_ORDERS)
```

6. Add or update tests.

At minimum, policy tests should prove:

```text
the view can be reversed
the capability exists
roles with the capability can reach the view
roles without it receive 403
anonymous users are redirected to login
```

## Adding a new account role

1. Add the role in `accounts/roles.py`.

```python
class AccountRole(StrEnum):
    WAREHOUSE_MANAGER = "warehouse_manager"
```

2. Add stable role metadata.

```python
ROLE_LABELS = {
    ...
    AccountRole.WAREHOUSE_MANAGER: "Warehouse manager",
}

ROLE_RANKS = {
    ...
    AccountRole.WAREHOUSE_MANAGER: 2,
}
```

3. Add a `RoleSpec`.

```python
WAREHOUSE_MANAGER_SPEC = RoleSpec(
    capabilities=frozenset(
        {
            Capability.VIEW_STAFF_OPS,

            Capability.VIEW_ORDERS,
            Capability.PACK_ORDERS,
            Capability.DELIVER_ORDERS,

            Capability.VIEW_INVENTORY,
            Capability.CREATE_BATCHES,
        }
    )
)
```

4. Register it in `ROLE_SPECS`.

```python
ROLE_SPECS = {
    ...
    AccountRole.WAREHOUSE_MANAGER: WAREHOUSE_MANAGER_SPEC,
}
```

5. Update account role resolution in `permissions.py`.

For staff users this may mean adding a new `StaffAccessLevel`, or adding a new
identity model if the role is a different kind of business identity.

6. Add navigation/dashboard UX mappings if the role needs custom UI.

```python
NAV_ITEMS_BY_ROLE[AccountRole.WAREHOUSE_MANAGER] = (...)
DASHBOARD_ACTIONS_BY_ROLE[AccountRole.WAREHOUSE_MANAGER] = (...)
DASHBOARD_QUEUES_BY_ROLE[AccountRole.WAREHOUSE_MANAGER] = (...)
```

7. Add tests for:

```text
role resolution
route access
navigation
dashboard actions/queues
```

## Adding a new protected view

1. Add the URL and view normally.
2. Add the view name to the owning app's `access.py`.
3. Map it to the required `Capability`.
4. Add the required `Capability` in `accounts/roles.py` if it does not already exist.
5. Make sure the app's access declarations are aggregated by `accounts/policies.py`.
6. Add UI links/actions only where appropriate.
7. Run tests.

If a view is intentionally auth-exempt, add it to `AUTH_EXEMPT_VIEWS` instead.

Protected views missing from both aggregated `VIEW_CAPABILITIES` and
`AUTH_EXEMPT_VIEWS` are denied by default.

## Adding an account management use case

Use this flow for new account-management mutations:

```text
form
  validate user input shape and field-level constraints

view
  coordinate HTTP request/response
  call service function
  show messages and redirect

service
  enforce business invariants
  perform database writes atomically
  return the changed object

selector/viewmodel
  build read-side data for pages
```

Example:

```text
create internal staff account
edit internal staff account
create customer login
deactivate customer login
```

Keep mutation rules out of templates and selectors.

## App access module convention

Each app with protected views should have an `access.py` module.

Example:

```text
orders/
  urls.py
  views.py
  access.py
```

The app owns:

```text
urls.py
  Which routes exist?

views.py
  What does each route do?

access.py
  What capability does each route require?
```

This keeps route ownership and route access declaration close together.

`accounts` still owns the central language and enforcement:

```text
accounts/roles.py
  Capability, RoleSpec and AccountRole.

accounts/policies.py
  Aggregated VIEW_CAPABILITIES and AUTH_EXEMPT_VIEWS.

accounts/middleware.py
  ViewCapabilityMiddleware enforcement.
```

## Design rule

Keep these responsibilities separate:

```text
roles.py
  What can each role do?
  What stable metadata describes each role?

permissions.py
  Which AccountRole does this Django User resolve to?

*/access.py
  What capability is required to reach each app-owned route?

policies.py
  Aggregate app access declarations into one enforcement policy.

middleware.py
  Enforce login/session and route access.

navigation.py
  Which top-level links should each role see?

dashboard/*
  Which dashboard actions and queues should each role see?

services.py
  Business mutations and invariants.

selectors.py
  Read-side queries and immutable rows.

viewmodels.py
  Page-specific presentation context.

templates
  Render ready-to-display viewmodels.
```

Prefer explicit service calls over hidden side effects. Prefer scoped selectors
over broad queries filtered later in templates. Keep templates simple.
