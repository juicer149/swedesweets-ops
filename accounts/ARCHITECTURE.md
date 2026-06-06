# Accounts architecture

The accounts app owns business identity, roles, capabilities and route access
policy.

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

policies.py
  Maps Django view names to required capabilities.
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
  immutable set of booleans describing what a role can do
```

Code should ask:

```python
role_spec.allows(Capability.PACK_ORDERS)
```

instead of checking raw strings directly.

## Route policy

Route access is declared in `accounts/policies.py`.

Protected views are mapped by Django `resolver_match.view_name`:

```python
VIEW_CAPABILITIES = {
    "orders:pack": Capability.PACK_ORDERS,
    "inventory:create": Capability.CREATE_BATCHES,
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

This means new protected views must be added to `VIEW_CAPABILITIES`.

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

2. Add a matching field to `RoleSpec`.

```python
@dataclass(frozen=True, slots=True)
class RoleSpec:
    can_export_orders: bool = False
```

3. Enable it for the roles that should have it.

```python
FULL_STAFF_SPEC = RoleSpec(
    ...
    can_export_orders=True,
)
```

4. Map any protected views that require it in `accounts/policies.py`.

```python
VIEW_CAPABILITIES = {
    ...
    "orders:export": Capability.EXPORT_ORDERS,
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
    can_view_staff_ops=True,
    can_view_orders=True,
    can_pack_orders=True,
    can_deliver_orders=True,
    can_view_inventory=True,
    can_create_batches=True,
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
2. Add the view name to `VIEW_CAPABILITIES`.
3. Add the required `Capability` if it does not already exist.
4. Add UI links/actions only where appropriate.
5. Run tests.

If a view is intentionally public, add it to `PUBLIC_VIEWS` instead.

Protected views missing from both `VIEW_CAPABILITIES` and `PUBLIC_VIEWS` are
denied by default.

## Design rule

Keep these responsibilities separate:

```text
roles.py
  What can each role do?

policies.py
  What capability is required to reach each route?

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
