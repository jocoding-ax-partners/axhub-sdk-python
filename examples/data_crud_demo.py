"""Ergonomic data layer demo (mirrors node examples/data-crud-demo.ts +
data-projection.ts + data-discover-demo.ts).

Run against a live AX Hub backend:

    AX_HUB_BASE_URL=https://api.axhub.ai \
    AX_HUB_PAT=pat_xxx \
    AX_HUB_TENANT=acme AX_HUB_APP=crm \
    PYTHONPATH=src python examples/data_crud_demo.py
"""
import os

from axhub_sdk import AxHubClient
from axhub_sdk.data import and_, define_schema, where


def main() -> None:
    sdk = AxHubClient(
        base_url=os.environ.get("AX_HUB_BASE_URL", "https://api.axhub.ai"),
        token=os.environ.get("AX_HUB_PAT", "demo"),
        token_type="pat",
    )

    tenant = os.environ.get("AX_HUB_TENANT", "acme")
    app = os.environ.get("AX_HUB_APP", "crm")

    # 1. Static schema + fluent table client (node: sdk.tenant().app().data.table()).
    orders = define_schema(
        "orders",
        {
            "id": "uuid",
            "total": "number",
            "status": {"type": "enum", "values": ["paid", "pending"]},
        },
    )
    table = sdk.tenant(tenant).app(app).data.table(orders)

    # 2. count() with a pushable predicate.
    print("paid order count:", table.count(where=where(orders.cols["status"]).eq("paid")))

    # 3. list() with where + order_by + select + offset pagination.
    page1 = table.list(
        where=and_(where("status").eq("paid"), where("total").gte(10)),
        order_by="-total",
        select=["id", "total"],
        page=1,
        page_size=10,
    )
    print("page 1 items:", page1.items, "next_cursor:", page1.next_cursor)

    # 4. insert / get / update / delete round-trip.
    created = table.insert({"total": 42, "status": "pending"})
    fetched = table.get(created["id"])
    table.update(created["id"], {"status": "paid"})
    table.delete(created["id"])
    print("round-trip id:", fetched.get("id"))

    # 5. Runtime schema discovery (node: data.discover()).
    discovered = sdk.tenant(tenant).app(app).data.discover("orders")
    print("discovered columns:", list((discovered.schema.columns if discovered.schema else {}).keys()))

    # 6. list_all() drains every page; emits a drift marker if the backend grows.
    for entry in table.list_all(where=where("status").eq("paid"), page_size=50):
        if entry.type == "item":
            pass  # use(entry.value)
        elif entry.type == "drift":
            print("backend grew mid-scan by", entry.added_since)


if __name__ == "__main__":
    main()
