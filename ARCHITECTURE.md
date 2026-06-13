# Architecture

This project uses small, explicit Django app boundaries. The goal is not to abstract everything, but to keep each kind of decision in the right place.

## App responsibilities

```text
views.py              HTTP orchestration: request, forms, selectors/services, render/redirect
access.py             Route capabilities and app-specific action predicates
selectors.py          Read-side queries, filtering, sorting, annotations, summaries
services.py           Write-side mutations and business operations
forms.py              User input, fields, widgets, validation, normalization
form_viewmodels.py    Template context for create/edit/form pages
list_viewmodels.py    Index page rows, mobile cards, page headers, quick jumps, section links
detail_viewmodels.py  Detail page context, panels, actions, relation rows, mini cards
presentation.py       Reusable UI policy: status, tone, icon, CSS class, display labels
```

Not every app needs every file. A file should exist only when it carries real responsibility.

## Access

`accounts` owns the shared access language and central enforcement:

```text
accounts/roles.py      Capability, RoleSpec and AccountRole
accounts/policies.py   Aggregated route access declarations
accounts/middleware.py Route access enforcement
```

Each app owns the access policy for its own routes in `access.py`.

```text
dashboard/access.py
orders/access.py
inventory/access.py
products/access.py
customers/access.py
```

`access.py` contains route-level capability mappings:

```python
VIEW_CAPABILITIES = {
    "orders:index": Capability.VIEW_ORDERS,
    "orders:create": Capability.CREATE_ORDERS,
    "orders:pack": Capability.PACK_ORDERS,
}
```

It may also contain object/action predicates:

```python
def can_pack_order(*, order: Order, role_spec: RoleSpec) -> bool:
    return (
        order.status == Order.Status.PLACED
        and role_spec.allows(Capability.PACK_ORDERS)
    )
```

Route-level capability mappings answer:

```text
May this role enter this view?
```

Object/action predicates answer:

```text
May this role perform this action on this object now?
```

Views use these predicates when an object-level guard is needed:

```python
if not can_close_batch(batch=batch, role_spec=request.role_spec):
    return redirect(...)
```

Viewmodels use the same predicates when deciding which actions to show:

```python
if can_edit_order(order=order, role_spec=role_spec):
    actions.append(...)
```

Avoid raw capability checks in `list_viewmodels.py` and `detail_viewmodels.py`:

```python
role_spec.allows(Capability.CREATE_PRODUCTS)
```

Prefer app-specific predicates:

```python
can_create_product(role_spec=role_spec)
```

This keeps permission logic out of templates and prevents viewmodels from becoming the owner of access policy.

More detailed identity, role, middleware and deny-by-default rules belong in the accounts architecture documentation.

## Views

Views orchestrate HTTP flow.

A view may:

```text
- read request.GET / request.POST
- bind forms and formsets
- call selectors for read data
- call services for mutations
- call viewmodel builders for template context
- call access predicates for object-level guards
- set messages
- redirect or render
```

A view should avoid:

```text
- business mutations outside services
- large query construction outside selectors
- template presentation logic
- status/tone/icon/class policy
- app-specific action rules that belong in access.py
```

Object lookup helpers stay in `views.py` when they use `get_object_or_404(...)`, because 404 handling is HTTP/view behavior.

Use neutral helper names when the same lookup is shared by detail, edit, cancel, pack, deliver, or close flows:

```python
_get_customer_or_404(...)
_get_batch_or_404(...)
_get_order_or_404(...)
_get_product_or_404(...)
```

## Index pages

Index pages keep request/querystring state in `views.py`.

Typical pattern:

```python
@login_required
def index(request):
    controls = TableControls.from_request_values(...)

    rows = build_x_page_rows(
        list_x(
            filter=controls.active_filter or None,
            sort=controls.active_sort,
        )
    )

    context = {
        "page_header": build_x_page_header(role_spec=request.role_spec),
        "x_rows": rows,
        "filters": controls.build_filter_links(X_FILTERS),
        "table_sorts": controls.build_table_sort_links(X_TABLE_SORTS),
        "mobile_sort_fields": controls.build_mobile_sort_fields(X_TABLE_SORTS),
        "mobile_sort_direction": controls.build_mobile_sort_direction(),
        "table_controls_template": X_TABLE_CONTROLS_TEMPLATE,
        "numeric_table_fields": [...],
    }

    return render(request, "x/index.html", context)
```

`TableControls.from_request_values(...)` stays in `views.py` because it depends on `request.path` and `request.GET`.

`controls.active_filter` and `controls.active_sort` are used by the view when calling selectors. They do not need to be passed separately to templates when filter links, sort links, and mobile sort fields already carry their own active state.

### `list_viewmodels.py`

Index page presentation belongs in `list_viewmodels.py`.

A list viewmodel may build:

```text
- page headers
- header actions
- page rows
- mobile cards
- quick jumps
- section links
- list-specific href decisions
```

Typical pattern:

```text
build_x_page_rows(...)
→ _build_x_page_row(...)
→ _x_card(...)
→ _x_card_rows(...)
→ _x_specific_row(...)
```

For simple cards, the row builder may pass already-computed presentation state into the card builder:

```python
status = product_status_presentation(product)
detail_href = _product_detail_href(product)

return ProductPageRow(
    product=product,
    status=status,
    detail_href=detail_href,
    card=_product_card(
        product=product,
        status=status,
        detail_href=detail_href,
    ),
)
```

List viewmodels may call app-specific access predicates when deciding whether to show actions:

```python
if not can_create_product(role_spec=role_spec):
    return None
```

The list viewmodel should express the UI decision, not own the access policy.

## Multi-section index pages

If an index page has multiple sections, such as inventory batches and product stock, the section switch stays in `views.py`:

```python
@login_required
def index(request):
    active_view = _active_inventory_view(
        request.GET.get(INVENTORY_VIEW_QUERY_KEY, "")
    )

    if active_view == INVENTORY_VIEW_PRODUCTS:
        context = _build_products_index_context(request)
    else:
        context = _build_batches_index_context(request)

    return render(request, "inventory/index.html", context)
```

Section navigation itself belongs in `list_viewmodels.py`.

If all sections share the same row shape and table structure, keep one index flow and switch only the selector or data source.

If sections have different row shapes, filters, table sorts, quick jumps, or template keys, split them into private `_build_*_index_context(...)` helpers in `views.py`.

## Detail pages

Detail pages fetch one main object, load related read data through selectors, and delegate render context construction to `detail_viewmodels.py`.

Typical pattern:

```python
@login_required
def detail(request, object_pk: int):
    obj = _get_object_or_404(object_pk)

    context = build_object_detail_context(
        obj=obj,
        related_data=list_related_data(obj=obj),
        role_spec=request.role_spec,
        cancel_url=reverse("objects:index"),
    ).as_dict()

    return render(request, "objects/detail.html", context)
```

### `detail_viewmodels.py`

Detail page presentation belongs in `detail_viewmodels.py`.

A detail viewmodel may build:

```text
- detail context dataclasses
- detail cards
- headers
- panels
- primary actions
- secondary actions
- relation rows
- mini cards
- page title and cancel URL
- detail-specific hrefs
```

Detail pages often use context dataclasses with `.as_dict()` because they combine domain data and presentation state into one coherent page object.

Typical pattern:

```text
build_x_detail_context(...)
→ _build_x_header(...)
→ _build_x_detail_panels(...)
→ build_x_primary_action(...)
→ build_x_secondary_actions(...)
```

Detail viewmodels may call app-specific access predicates when deciding which actions to show:

```python
if can_edit_order(order=order, role_spec=role_spec):
    actions.append(...)
```

Detail viewmodels should not define access predicates themselves. Rules such as `can_edit_order`, `can_close_batch`, `can_cancel_order`, or `can_pack_order` belong in the app's `access.py`.

Small single-use action builders may be inlined when they only wrap a generic helper:

```python
build_secondary_get_action(
    label="Edit order",
    href=order_edit_href(order),
)
```

More semantic or specialized actions may remain as named builders when they encode meaningful UI behavior:

```python
build_pack_action(...)
build_deliver_action()
build_go_to_pack_action(...)
build_go_to_deliver_action(...)
```

## Href helpers

Repeated `reverse(...)` calls may be hidden behind small local href helpers.

```python
def order_pack_href(order: Order) -> str:
    return reverse("orders:pack", kwargs={"order_id": order.pk})
```

Use helpers when the same route is used in several places, or when the helper name makes navigation intent clearer.

Keep href helpers local to the module that uses them. Avoid importing helpers from `detail_viewmodels.py` into `list_viewmodels.py` just to remove duplication.

A little duplication is acceptable when it keeps presentation modules independent.

## Card navigation

Cards without inner links may use card-level navigation:

```python
UiCard(
    href=detail_href,
    footer_hint="Open details →",
    rows=...,
)
```

Cards with inner interactive links should not also make the entire card clickable. In that case, use an explicit action link instead:

```python
UiCard(
    rows=...,
    action=UiText(
        text="View customer →",
        href=detail_href,
    ),
)
```

This avoids nested interactive elements and keeps mobile cards semantically clear.

## Form pages

Form pages follow their own create/edit pattern.

The view keeps GET/POST orchestration:

```text
- bind form or formset
- validate input
- call services
- handle domain errors
- set messages
- redirect or render
```

Form page context belongs in `form_viewmodels.py`.

This section should be expanded when the create/edit form views have been standardized.

## Constants

Keep constants when they define a stable contract:

```text
X_LIST_ANCHOR
X_FILTER_QUERY_KEY
X_VIEW_QUERY_KEY
ORDER_LINE_FORMSET_PREFIX
INVENTORY_VIEW_PRODUCTS
INVENTORY_VIEW_BATCHES
X_FILTERS
X_TABLE_SORTS
X_TABLE_CONTROLS_TEMPLATE
```

Avoid constants that merely hide a one-off label, icon, or CSS class without adding meaning.

## Rule of thumb

```text
views.py              decides the HTTP flow
access.py             decides route and action permissions
selectors.py          decides how data is read
services.py           decides how data changes
forms.py              decides how input is validated
form_viewmodels.py    decides what form templates receive
list_viewmodels.py    decides what index templates receive
detail_viewmodels.py  decides what detail templates receive
presentation.py       decides reusable UI policy
common/               contains stable primitives, not app-specific shortcuts
```

Prefer local, explicit, domain-named helpers over premature shared abstractions.

Good:

```python
can_pack_order(...)
order_pack_href(...)
build_order_detail_primary_action(...)
```

Avoid too early:

```python
can_edit_object(...)
build_generic_action(...)
common_href(...)
```
