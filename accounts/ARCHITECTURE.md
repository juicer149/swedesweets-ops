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

permissions.py
  Resolves user -> AccountRole -> RoleSpec.
  Provides require_capability(...) for explicit checks when needed.

access.py
  Declares accounts-owned public/auth views.

policies.py
  Aggregates app-level access declarations into one route policy map.
  Views are denied by default unless listed here or marked public.

middleware.py
  Attaches request.account_role and request.role_spec.
  Enforces route access using policies.py.

navigation.py
  Builds role-aware primary navigation.
  Navigation is UX, not authorization.

context_processors.py
  Exposes navigation viewmodels to templates.

services.py
  Account creation use cases.
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

## Route policy

Route access is declared app-locally and enforced centrally.

Each app declares the policy for the views it owns:

```text
orders/access.py
inventory/access.py
products/access.py
customers/access.py
dashboard/access.py
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
        "password_reset",
    }
)
```

`accounts/policies.py` aggregates those app-level declarations:

```python
VIEW_CAPABILITIES = {
    **DASHBOARD_VIEW_CAPABILITIES,
    **ORDER_VIEW_CAPABILITIES,
    **INVENTORY_VIEW_CAPABILITIES,
    **PRODUCT_VIEW_CAPABILITIES,
    **CUSTOMER_VIEW_CAPABILITIES,
}
```

Rules:

```text
public view       -> allowed
protected view    -> requires mapped capability
unknown view      -> denied
anonymous user    -> redirected to login for protected views
authenticated user without capability -> 403
```

This means new protected views must be added to the owning app's `access.py`.
They become enforceable when `accounts/policies.py` aggregates that app's
declarations.

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

2. Add a `RoleSpec`.

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

3. Register it in `ROLE_SPECS`.

```python
ROLE_SPECS = {
    ...
    AccountRole.WAREHOUSE_MANAGER: WAREHOUSE_MANAGER_SPEC,
}
```

4. Update account role resolution in `permissions.py`.

For staff users this may mean adding a new `StaffAccessLevel`, or adding a new
identity model if the role is a different kind of business identity.

5. Add navigation/dashboard UX mappings if the role needs custom UI.

```python
NAV_ITEMS_BY_ROLE[AccountRole.WAREHOUSE_MANAGER] = (...)
DASHBOARD_ACTIONS_BY_ROLE[AccountRole.WAREHOUSE_MANAGER] = (...)
DASHBOARD_QUEUES_BY_ROLE[AccountRole.WAREHOUSE_MANAGER] = (...)
```

6. Add tests for:

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

*/access.py
  What capability is required to reach each app-owned route?

policies.py
  Aggregate app access declarations into one enforcement policy.

middleware.py
  Enforce route access.

navigation.py
  Which top-level links should each role see?

dashboard/*
  Which dashboard actions and queues should each role see?

templates
  Render ready-to-display viewmodels.
```

Avoid putting role/capability `if` logic directly in templates when it can be
built in Python and tested.
