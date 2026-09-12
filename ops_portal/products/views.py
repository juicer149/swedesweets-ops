from __future__ import annotations

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.shortcuts import (
    get_object_or_404,
    redirect,
    render,
)
from django.urls import reverse

from common.table_controls import (
    TableControls,
    TableControlsTemplate,
    TableFilter,
    TableSortField,
)
from inventory.selectors import (
    available_quantity_by_product,
    list_available_batches_for_product,
)
from ops_portal.products.detail_viewmodels import (
    build_product_detail_context,
)
from ops_portal.products.form_viewmodels import (
    build_create_product_form_context,
    build_edit_product_form_context,
)
from ops_portal.products.forms import (
    ProductEditForm,
    ProductForm,
    build_product_edit_initial_data,
)
from ops_portal.products.list_viewmodels import (
    build_product_page_rows,
    build_product_quick_jump_search,
    build_products_page_header,
)
from ops_portal.products.pricing_forms import (
    ProductPricingForm,
    build_product_pricing_initial_data,
)
from ops_portal.products.pricing_services import (
    update_product_standard_pricing,
)
from pricing.errors import (
    InvalidCommercialPrice,
)
from pricing.models import CommercialPrice
from pricing.selectors import (
    get_product_commercial_price,
)
from products.errors import (
    InvalidProductData,
)
from products.image_services import (
    ProductImageChange,
    change_product_image,
)
from products.models import Product
from products.selectors import (
    DEFAULT_PRODUCT_SORT,
    PRODUCT_FILTER_ACTIVE,
    PRODUCT_FILTER_ALL,
    PRODUCT_FILTER_INACTIVE,
    PRODUCT_SORTS,
    get_product_delivered_demand_summary,
    list_products,
)
from products.services import (
    create_product,
    update_product,
)


PRODUCT_FILTERS = [
    TableFilter(
        PRODUCT_FILTER_ALL,
        "All",
    ),
    TableFilter(
        PRODUCT_FILTER_ACTIVE,
        "Active",
    ),
    TableFilter(
        PRODUCT_FILTER_INACTIVE,
        "Inactive",
    ),
]

PRODUCT_TABLE_SORTS = [
    TableSortField(
        "number",
        "#",
    ),
    TableSortField(
        "product",
        "Product",
    ),
    TableSortField(
        "brand",
        "Brand",
    ),
    TableSortField(
        "manufacturer",
        "Manufacturer",
    ),
    TableSortField(
        "weight",
        "Weight",
    ),
    TableSortField(
        "unit",
        "Unit",
    ),
    TableSortField(
        "vegan",
        "Vegan",
    ),
    TableSortField(
        "status",
        "Status",
    ),
]

PRODUCTS_LIST_ANCHOR = (
    "products-list"
)
PRODUCT_FILTER_QUERY_KEY = (
    "status"
)

PRODUCT_TABLE_CONTROLS_TEMPLATE = (
    TableControlsTemplate(
        filters_title_id=(
            "products-filters-title"
        ),
        filters_aria_label=(
            "Product filters"
        ),
        sort_title_id=(
            "products-sort-title"
        ),
        sort_select_id=(
            "mobile-product-sort"
        ),
    )
)


@login_required
def index(request):
    controls = (
        TableControls
        .from_request_values(
            base_path=request.path,
            anchor=(
                PRODUCTS_LIST_ANCHOR
            ),
            requested_filter=(
                request.GET.get(
                    PRODUCT_FILTER_QUERY_KEY,
                    "",
                )
            ),
            requested_sort=(
                request.GET.get(
                    "sort",
                    "",
                )
            ),
            filters=PRODUCT_FILTERS,
            allowed_sorts=PRODUCT_SORTS,
            default_sort=(
                DEFAULT_PRODUCT_SORT
            ),
            filter_query_key=(
                PRODUCT_FILTER_QUERY_KEY
            ),
        )
    )

    products = list(
        list_products(
            status=(
                controls.active_filter
            ),
            sort=(
                controls.active_sort
            ),
        )
    )

    product_rows = (
        build_product_page_rows(
            products
        )
    )

    context = {
        "page_header": (
            build_products_page_header(
                role_spec=(
                    request.role_spec
                ),
            )
        ),
        "product_rows": (
            product_rows
        ),
        "quick_jump_search": (
            build_product_quick_jump_search(
                product_rows
            )
        ),
        "filters": (
            controls
            .build_filter_links(
                PRODUCT_FILTERS
            )
        ),
        "table_sorts": (
            controls
            .build_table_sort_links(
                PRODUCT_TABLE_SORTS
            )
        ),
        "mobile_sort_fields": (
            controls
            .build_mobile_sort_fields(
                PRODUCT_TABLE_SORTS
            )
        ),
        "mobile_sort_direction": (
            controls
            .build_mobile_sort_direction()
        ),
        "table_controls_template": (
            PRODUCT_TABLE_CONTROLS_TEMPLATE
        ),
        "numeric_table_fields": [
            "number",
            "weight",
        ],
    }

    return render(
        request,
        "ops_portal/products/index.html",
        context,
    )


@login_required
def detail(
    request,
    product_pk: int,
):
    product = _get_product_or_404(
        product_pk
    )

    business_price = (
        get_product_commercial_price(
            product=product,
            channel=(
                CommercialPrice
                .Channel
                .BUSINESS
            ),
        )
    )

    retail_price = (
        get_product_commercial_price(
            product=product,
            channel=(
                CommercialPrice
                .Channel
                .RETAIL
            ),
        )
    )

    context = (
        build_product_detail_context(
            product=product,
            stock_row=(
                _get_stock_row_for_product(
                    product
                )
            ),
            active_batches=list(
                list_available_batches_for_product(
                    product=product,
                )
            ),
            demand_summary=(
                get_product_delivered_demand_summary(
                    product=product,
                )
            ),
            business_price=business_price,
            retail_price=retail_price,
            role_spec=request.role_spec,
            cancel_url=reverse(
                "ops_products:index"
            ),
        )
        .as_dict()
    )

    return render(
        request,
        (
            "ops_portal/products/"
            "detail.html"
        ),
        context,
    )


@login_required
def edit(
    request,
    product_pk: int,
):
    product = _get_product_or_404(
        product_pk
    )

    business_price = (
        get_product_commercial_price(
            product=product,
            channel=(
                CommercialPrice
                .Channel
                .BUSINESS
            ),
        )
    )

    retail_price = (
        get_product_commercial_price(
            product=product,
            channel=(
                CommercialPrice
                .Channel
                .RETAIL
            ),
        )
    )

    if request.method == "POST":
        form = ProductEditForm(
            request.POST,
            request.FILES,
            product=product,
        )

        pricing_form = (
            ProductPricingForm(
                request.POST,
            )
        )

        product_form_is_valid = (
            form.is_valid()
        )
        pricing_form_is_valid = (
            pricing_form.is_valid()
        )

        if (
            product_form_is_valid
            and pricing_form_is_valid
        ):
            image_change = (
                ProductImageChange
                .empty()
            )

            try:
                with transaction.atomic():
                    updated_product = (
                        update_product(
                            product=product,
                            internal_number=(
                                form.cleaned_data[
                                    "internal_number"
                                ]
                            ),
                            manufacturer=(
                                form.cleaned_data[
                                    "manufacturer"
                                ]
                            ),
                            brand=(
                                form.cleaned_data[
                                    "brand"
                                ]
                            ),
                            name=(
                                form.cleaned_data[
                                    "name"
                                ]
                            ),
                            active=(
                                form.active_value
                            ),
                            vegan=(
                                form.cleaned_data[
                                    "vegan"
                                ]
                            ),
                            customer_facing_name_fr=(
                                form.cleaned_data[
                                    "customer_facing_name_fr"
                                ]
                            ),
                            category=(
                                form.cleaned_data[
                                    "category"
                                ]
                            ),
                            description=(
                                form.cleaned_data[
                                    "description"
                                ]
                            ),
                            ingredients=(
                                form.cleaned_data[
                                    "ingredients"
                                ]
                            ),
                            user=request.user,
                        )
                    )

                    (
                        update_product_standard_pricing(
                            product=(
                                updated_product
                            ),
                            **(
                                pricing_form
                                .pricing_values()
                            ),
                        )
                    )

                    image_change = (
                        change_product_image(
                            product=(
                                updated_product
                            ),
                            uploaded_image=(
                                form.cleaned_data[
                                    "image"
                                ]
                            ),
                            remove_image=(
                                form.cleaned_data[
                                    "remove_image"
                                ]
                            ),
                        )
                    )

            except InvalidProductData as error:
                image_change.rollback()

                form.add_error(
                    None,
                    str(error),
                )

            except InvalidCommercialPrice as error:
                image_change.rollback()

                pricing_form.add_error(
                    None,
                    str(error),
                )

            except Exception:
                image_change.rollback()
                raise

            else:
                image_change.commit()

                messages.success(
                    request,
                    (
                        "Product "
                        f"{updated_product.sku} "
                        "updated."
                    ),
                )

                return redirect(
                    "ops_products:detail",
                    product_pk=(
                        updated_product.pk
                    ),
                )

    else:
        form = ProductEditForm(
            initial=(
                build_product_edit_initial_data(
                    product
                )
            ),
            product=product,
        )

        pricing_form = (
            ProductPricingForm(
                initial=(
                    build_product_pricing_initial_data(
                        business_price=(
                            business_price
                        ),
                        retail_price=(
                            retail_price
                        ),
                    )
                )
            )
        )

    context = (
        build_edit_product_form_context(
            form=form,
            pricing_form=pricing_form,
            product=product,
        )
        .as_dict()
    )

    return render(
        request,
        (
            "ops_portal/products/"
            "product_form.html"
        ),
        context,
    )


@login_required
def create(request):
    if request.method == "POST":
        form = ProductForm(
            request.POST,
            request.FILES,
        )

        pricing_form = (
            ProductPricingForm(
                request.POST,
            )
        )

        product_form_is_valid = (
            form.is_valid()
        )
        pricing_form_is_valid = (
            pricing_form.is_valid()
        )

        if (
            product_form_is_valid
            and pricing_form_is_valid
        ):
            image_change = (
                ProductImageChange
                .empty()
            )

            try:
                with transaction.atomic():
                    result = create_product(
                        internal_number=(
                            form.cleaned_data[
                                "internal_number"
                            ]
                        ),
                        manufacturer=(
                            form.cleaned_data[
                                "manufacturer"
                            ]
                        ),
                        brand=(
                            form.cleaned_data[
                                "brand"
                            ]
                        ),
                        name=(
                            form.cleaned_data[
                                "name"
                            ]
                        ),
                        weight_per_unit=(
                            form.cleaned_data[
                                "weight_per_unit"
                            ]
                        ),
                        stock_unit=(
                            form.cleaned_data[
                                "stock_unit"
                            ]
                        ),
                        vegan=(
                            form.cleaned_data[
                                "vegan"
                            ]
                        ),
                        customer_facing_name_fr=(
                            form.cleaned_data[
                                "customer_facing_name_fr"
                            ]
                        ),
                        category=(
                            form.cleaned_data[
                                "category"
                            ]
                        ),
                        description=(
                            form.cleaned_data[
                                "description"
                            ]
                        ),
                        ingredients=(
                            form.cleaned_data[
                                "ingredients"
                            ]
                        ),
                        user=request.user,
                    )

                    if result.created:
                        (
                            update_product_standard_pricing(
                                product=(
                                    result.item
                                ),
                                **(
                                    pricing_form
                                    .pricing_values()
                                ),
                            )
                        )

                        image_change = (
                            change_product_image(
                                product=(
                                    result.item
                                ),
                                uploaded_image=(
                                    form.cleaned_data[
                                        "image"
                                    ]
                                ),
                            )
                        )

            except InvalidProductData as error:
                image_change.rollback()

                form.add_error(
                    None,
                    str(error),
                )

            except InvalidCommercialPrice as error:
                image_change.rollback()

                pricing_form.add_error(
                    None,
                    str(error),
                )

            except Exception:
                image_change.rollback()
                raise

            else:
                image_change.commit()

                if result.created:
                    messages.success(
                        request,
                        result.message,
                    )
                else:
                    messages.info(
                        request,
                        result.message,
                    )

                return redirect(
                    "ops_products:index"
                )

    else:
        form = ProductForm()
        pricing_form = (
            ProductPricingForm()
        )

    context = (
        build_create_product_form_context(
            form=form,
            pricing_form=pricing_form,
        )
        .as_dict()
    )

    return render(
        request,
        (
            "ops_portal/products/"
            "product_form.html"
        ),
        context,
    )


def _get_product_or_404(
    product_pk: int,
) -> Product:
    return get_object_or_404(
        Product.objects.select_related(
            "profile"
        ),
        pk=product_pk,
    )


def _get_stock_row_for_product(
    product: Product,
):
    for row in (
        available_quantity_by_product()
    ):
        if (
            row.product_id
            == product.pk
        ):
            return row

    return None
