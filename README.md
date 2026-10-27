# POS - Item, Customer & Sale Order (Python / Flask / SQLite)

A small point-of-sale app with three forms. Each form supports full CRUD
(Create, Read, Update, Delete).

| Form      | Fields                                                                    |
| --------- | ------------------------------------------------------------------------- |
| Item      | Code, Description, Price, BarCode                                         |
| Customer  | Code, Name, CustomerType (Cash / Credit)                                  |
| SaleOrder | VoucherNo, CustomerCode, ItemCode, Quantity, Unit Price, Sub Total, Total |

## Run it

Requires Python 3.9+.

```bash
# 1. create an isolated environment (once)
python -m venv .venv

# 2. activate it
#    Windows (PowerShell):  .venv\Scripts\Activate.ps1
#    macOS / Linux:         source .venv/bin/activate

# 3. install dependencies (once)
pip install -r requirements.txt

# 4. start the app
python app.py
```

Open http://127.0.0.1:5000. The database file `pos.db` is created automatically on first run.

## How to use it

- **Save** creates a new record, or updates it when you came from **Edit**.
- **Clear** resets the form to a blank one.
- **Edit** (in the list) loads a record into the form. Its code is locked, because changing the code would make it a different record.
- **Delete** asks for confirmation first.
- In **SaleOrder**, picking an Item Code fills in its price, and Sub Total / Total update as you type.
  The server recalculates them again on save, so they can't be faked from the browser.
- A customer or item that already has sale orders can't be deleted (the database protects the link).

## Project layout

```
app.py            Web layer: routes (URLs) and the config describing each form
database.py       Database layer: tables, validation, create/read/update/delete
templates/        HTML pages (Jinja): base.html (menu), crud.html (form + list)
static/           style.css, sales.js (auto price and totals)
```

## Design decisions

- **Flask + SQLite**: small, readable, and zero database setup. Swapping to MySQL/PostgreSQL only touches `database.py`.
- **Parameterized SQL everywhere**, so SQL injection isn't possible. Templates auto-escape output, which prevents XSS.
- **Money uses `Decimal`**, never floats, so `0.1 + 0.2` style rounding errors can't appear.
- **Validation lives in the database layer**, so the rules hold whichever interface calls it.
- **One generic page for all three forms**, driven by the `ENTITIES` config in `app.py`.

## Possible improvements

Multiple items per sale order (a separate order-lines table), search and paging in lists,
login and user roles, tax and discount, a JSON API.
