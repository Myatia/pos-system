"""
app.py - the web layer (Flask).

One generic page handles all three forms (Item, Customer, SaleOrder).
Each form is described by a small config dict in ENTITIES below, so adding a
field or a form later means editing config, not copy-pasting code.

Run:   python app.py      then open  http://127.0.0.1:5000
"""
import os

from flask import Flask, abort, flash, g, redirect, render_template, request, url_for

import database
from database import CUSTOMER_TYPES, Customers, Items, SaleOrders, ValidationError


def field(name, label, kind="text", **extra):
    """Describe one input box. kind: text | decimal | integer | select | readonly"""
    return {"name": name, "label": label, "kind": kind, **extra}


# slug -> description of the form. The slug is used in the URL (/items, /customers...).
ENTITIES = {
    "items": {
        "title": "Item", "table": Items, "pk": "code",
        "fields": [
            field("code", "Code"),
            field("description", "Description"),
            field("price", "Price", "decimal"),
            field("barcode", "BarCode", required=False),
        ],
    },
    "customers": {
        "title": "Customer", "table": Customers, "pk": "code",
        "fields": [
            field("code", "Code"),
            field("name", "Name"),
            field("customer_type", "CustomerType", "select", options=CUSTOMER_TYPES),
        ],
    },
    "sales": {
        "title": "SaleOrder", "table": SaleOrders, "pk": "voucher_no",
        "fields": [
            field("voucher_no", "VoucherNo"),
            field("customer_code", "CustomerCode", datalist="customer-codes"),
            field("item_code", "ItemCode", datalist="item-codes"),
            field("quantity", "Quantity", "integer"),
            field("unit_price", "Unit Price", "decimal"),
            field("sub_total", "Sub Total", "readonly"),
            field("total", "Total", "readonly"),
        ],
    },
}


def create_app(db_path=None):
    app = Flask(__name__)
    # Needed by flash() messages. Set SECRET_KEY in the environment for real deployments.
    app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "dev-only-change-me")
    app.config["DB_PATH"] = db_path or database.DB_FILE

    # ---- one database connection per request, closed automatically afterwards
    def get_db():
        if "db" not in g:
            g.db = database.connect(app.config["DB_PATH"])
        return g.db

    @app.teardown_appcontext
    def close_db(_error):
        db = g.pop("db", None)
        if db is not None:
            db.close()

    def entity_or_404(slug):
        if slug not in ENTITIES:
            abort(404)
        return ENTITIES[slug]

    def render_page(slug, form_values, editing):
        """Draw the page: the form on top, the table of saved records below."""
        cfg = entity_or_404(slug)
        db = get_db()
        extra = {}
        if slug == "sales":  # helpers for the Sale Order form (dropdown suggestions + auto price)
            extra["customer_codes"] = [c["code"] for c in Customers(db).all()]
            items = Items(db).all()
            extra["item_codes"] = [i["code"] for i in items]
            extra["prices"] = {i["code"]: i["price"] for i in items}
        return render_template(
            "crud.html", slug=slug, cfg=cfg, rows=cfg["table"](db).all(),
            values=form_values, editing=editing, entities=ENTITIES, **extra,
        )

    def blank_values(slug):
        cfg = ENTITIES[slug]
        values = {f["name"]: "" for f in cfg["fields"]}
        if slug == "customers":
            values["customer_type"] = CUSTOMER_TYPES[0]
        if slug == "sales":
            values["voucher_no"] = SaleOrders(get_db()).next_voucher_no()
            values["quantity"] = "1"
        return values

    # ------------------------------------------------------------- routes
    @app.route("/")
    def home():
        return redirect(url_for("crud_page", slug="items"))

    @app.route("/<slug>/")
    def crud_page(slug):
        """READ: list all records. With ?edit=<key>, also load that record into the form."""
        cfg = entity_or_404(slug)
        key = request.args.get("edit")
        if key:
            record = cfg["table"](get_db()).get(key)
            if record is None:
                flash(f"'{key}' was not found.", "error")
                return redirect(url_for("crud_page", slug=slug))
            return render_page(slug, {k: ("" if v is None else v) for k, v in record.items()}, True)
        return render_page(slug, blank_values(slug), False)

    @app.post("/<slug>/save")
    def save(slug):
        """CREATE or UPDATE, depending on the hidden 'editing' field."""
        cfg = entity_or_404(slug)
        table = cfg["table"](get_db())
        submitted = {f["name"]: request.form.get(f["name"], "") for f in cfg["fields"]}
        editing = request.form.get("editing") == "1"
        try:
            row = table.update(submitted) if editing else table.create(submitted)
        except ValidationError as exc:
            flash(str(exc), "error")
            return render_page(slug, submitted, editing)  # keep what the user typed
        flash(f"{cfg['title']} '{row[cfg['pk']]}' {'updated' if editing else 'created'}.", "ok")
        return redirect(url_for("crud_page", slug=slug))

    @app.post("/<slug>/delete")
    def delete(slug):
        """DELETE one record."""
        cfg = entity_or_404(slug)
        key = request.form.get("key", "")
        try:
            cfg["table"](get_db()).delete(key)
        except ValidationError as exc:
            flash(str(exc), "error")
        else:
            flash(f"{cfg['title']} '{key}' deleted.", "ok")
        return redirect(url_for("crud_page", slug=slug))

    return app


if __name__ == "__main__":
    # debug=True auto-reloads on code changes. Fine for a demo, never for production.
    create_app().run(debug=True)
