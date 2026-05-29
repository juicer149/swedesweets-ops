# Seed demo data

This seed data uses real historical inventory and sales data for the MVP demo.

## Current seed state

Seed command:

```bash
python manage.py seed_demo_data --reset --with-orders
```

Creates:

* products
* customers
* inbound inventory batches
* historical delivered orders
* consumed allocations

## Skipped historical orders

The following orders are intentionally skipped for now:

### 2025-12-01_super_u_les_houches_2025-0002

Skipped because this large order currently consumes more stock than the known
inbound batches support. It also contains unmapped items:

* BRIO CARAMEL
* JÄTTEBANAN CHOKLAD

Re-enable after verifying additional inbound stock or correcting product mapping.

### 2026-02-29_miss_money_penny_2025-0004

Skipped because the invoice only says "Lösgodis 10" and does not provide a
product-level split.

### unknown_date_unknown_customer_unknown_invoice

Skipped because the source text is missing invoice number, customer and order date.

```

## Nästa bra tekniska förbättring

Seed räknar ordern som skapad innan/efter vissa skips lite otydligt. senare justera rapporteringen så den skriver:

```text id="qcqwhd"
Historical orders created: 7
Skipped orders: 3
Unmapped inventory lines ignored: 3
```
