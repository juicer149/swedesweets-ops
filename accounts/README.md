# Accounts

`accounts` owns authentication-adjacent business identity, roles,
capabilities and account lifecycle use cases.

Django authentication answers:

> Who is logged in?

`accounts` answers:

> What account identity does this user represent?
> What capabilities does that identity have?

## Responsibilities

```text
models.py
    Persistent identity links:
    User -> StaffAccount
    User -> CustomerMembership

roles.py
    AccountRole
    StaffAccessLevel
    Capability
    RoleSpec
    stable role metadata

permissions.py
    Resolve Django User -> AccountRole -> RoleSpec.

access.py
    Access declarations for accounts-owned routes.

selectors.py
    Account identity/read queries.

services.py
    Account mutations and invariants.

activity.py
    Shared account activity read model.

activity_selectors.py
    Aggregates actor activity from domain-owned selectors.

presentation.py
activity_viewmodels.py
    Neutral account/activity presentation.

self_viewmodels.py
self_activity_links.py
    Presentation and navigation for the signed-in user's own account.

middleware.py
    Attach account role context and enforce capability policy.

navigation.py
    Shared account navigation helpers.
```

## Boundaries

`accounts` does not own staff account-management UI.
That belongs to `ops_portal/accounts`.

`accounts` does not own business customer UI.
That belongs to `business_portal`.

Domain-specific activity queries belong to their owning domains:

```text
orders/selectors.py
products/selectors.py
inventory/selectors.py
customers/selectors.py
```

`accounts/activity_selectors.py` only aggregates those results.

Cross-application composition belongs in `config`.

Examples:

```text
config/policies.py
config/login_routing.py
config/context_processors.py
```

## Design rules

Use capabilities rather than checking role/storage values directly:

```python
role_spec.allows(Capability.PACK_ORDERS)
```

Use selectors for reads and services for mutations.

Account services own invariants and database writes.
Views and portals orchestrate HTTP/UI concerns.

Navigation is UX, not authorization.
Route authorization remains fail-closed at the destination.
