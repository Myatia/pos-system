"""
database.py - everything that talks to the SQLite database.

Rules of the road:
  * SQL values are ALWAYS passed as parameters (?, :name) - never pasted into
    the SQL string - so SQL injection is not possible.
  * All validation lives here (not in the web layer), so the rules apply no
    matter who calls these classes (web page, tests, a future API...).
"""
import sqlite3
from decimal import Decimal, InvalidOperation
from pathlib import Path

DB_FILE = Path(__file__).with_name("pos.db")
CUSTOMER_TYPES = ("Cash", "Credit")

SCHEMA = """
CREATE TABLE IF NOT EXISTS items (
    code        TEXT PRIMARY KEY,
    description TEXT NOT NULL,
    price       TEXT NOT NULL,            -- decimal stored as text, e.g. '12.50'
    barcode     TEXT UNIQUE               -- NULL allowed (many items without one)
);

CREATE TABLE IF NOT EXISTS customers (
    code          TEXT PRIMARY KEY,
    name          TEXT NOT NULL,
    customer_type TEXT NOT NULL CHECK (customer_type IN ('Cash', 'Credit'))
);

CREATE TABLE IF NOT EXISTS sale_orders (
    voucher_no    TEXT PRIMARY KEY,
    customer_code TEXT NOT NULL REFERENCES customers(code),
    item_code     TEXT NOT NULL REFERENCES items(code),
    quantity      INTEGER NOT NULL CHECK (quantity > 0),
    unit_price    TEXT NOT NULL,
    sub_total     TEXT NOT NULL,
    total         TEXT NOT NULL
);
"""


class ValidationError(Exception):
    """Raised with a human-friendly message when user input is not acceptable."""


def connect(path=DB_FILE):
    """Open the database (creating tables on first run)."""
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")  # SQLite ignores foreign keys unless asked
    conn.executescript(SCHEMA)
    return conn


# ----------------------------------------------------------------- helpers
def _required(data, field, label):
    value = str(data.get(field) or "").strip()
    if not value:
        raise ValidationError(f"{label} is required.")
    return value


def _money(text, label):
    """'12.5' -> Decimal('12.50'). Rejects blanks, letters and negatives."""
    try:
        value = Decimal(str(text).strip())
    except InvalidOperation:
        raise ValidationError(f"{label} must be a number, e.g. 12.50.") from None
    if not value.is_finite() or value < 0:
        raise ValidationError(f"{label} must be zero or more.")
    return value.quantize(Decimal("0.01"))


# --------------------------------------------------------- generic CRUD base
class Table:
    """
    Generic Create / Read / Update / Delete for one table.
    A subclass only says its table name, key column and columns, and (if
    needed) overrides clean() to validate input.
    NOTE: table/column names come from class constants below, never from users,
    so building them into the SQL text with f-strings is safe here.
    """
    name = ""
    key = ""
    columns = ()  # key column first

    def __init__(self, conn):
        self.conn = conn

    def clean(self, data):
        """Validate + tidy a dict of form values. Return the cleaned dict."""
        raise NotImplementedError

    # ---- Read
    def all(self):
        cols = ", ".join(self.columns)
        sql = f"SELECT {cols} FROM {self.name} ORDER BY {self.key}"
        return [dict(row) for row in self.conn.execute(sql)]

    def get(self, key):
        cols = ", ".join(self.columns)
        row = self.conn.execute(
            f"SELECT {cols} FROM {self.name} WHERE {self.key} = ?", (key,)
        ).fetchone()
        return dict(row) if row else None

    # ---- Create
    def create(self, data):
        row = self.clean(data)
        if self.get(row[self.key]) is not None:
            raise ValidationError(f"'{row[self.key]}' already exists. Use Edit to change it.")
        cols = ", ".join(self.columns)
        marks = ", ".join(f":{c}" for c in self.columns)
        self._write(f"INSERT INTO {self.name} ({cols}) VALUES ({marks})", row)
        return row

    # ---- Update
    def update(self, data):
        row = self.clean(data)
        if self.get(row[self.key]) is None:
            raise ValidationError(f"'{row[self.key]}' does not exist.")
        assignments = ", ".join(f"{c} = :{c}" for c in self.columns[1:])
        self._write(f"UPDATE {self.name} SET {assignments} WHERE {self.key} = :{self.key}", row)
        return row

    # ---- Delete
    def delete(self, key):
        if self.get(key) is None:
            raise ValidationError(f"'{key}' does not exist.")
        self._write(f"DELETE FROM {self.name} WHERE {self.key} = :key", {"key": key})

    def _write(self, sql, params):
        try:
            with self.conn:  # commits on success, rolls back on error
                self.conn.execute(sql, params)
        except sqlite3.IntegrityError as exc:
            message = str(exc)
            if "FOREIGN KEY" in message:
                raise ValidationError(
                    "This record is linked to other records (e.g. a sale order) "
                    "and cannot be changed that way. Delete the linked records first."
                ) from None
            if "UNIQUE" in message:
                raise ValidationError("That code or barcode is already used by another record.") from None
            raise ValidationError(f"Database rejected the data: {message}") from None


# ------------------------------------------------------------------ the 3 forms
class Items(Table):
    name = "items"
    key = "code"
    columns = ("code", "description", "price", "barcode")

    def clean(self, data):
        return {
            "code": _required(data, "code", "Code"),
            "description": _required(data, "description", "Description"),
            "price": str(_money(data.get("price"), "Price")),
            "barcode": str(data.get("barcode") or "").strip() or None,
        }


class Customers(Table):
    name = "customers"
    key = "code"
    columns = ("code", "name", "customer_type")

    def clean(self, data):
        customer_type = str(data.get("customer_type") or "").strip()
        if customer_type not in CUSTOMER_TYPES:
            raise ValidationError("Customer type must be Cash or Credit.")
        return {
            "code": _required(data, "code", "Code"),
            "name": _required(data, "name", "Name"),
            "customer_type": customer_type,
        }


class SaleOrders(Table):
    name = "sale_orders"
    key = "voucher_no"
    columns = ("voucher_no", "customer_code", "item_code", "quantity",
               "unit_price", "sub_total", "total")

    def clean(self, data):
        voucher_no = _required(data, "voucher_no", "Voucher No")
        customer_code = _required(data, "customer_code", "Customer Code")
        item_code = _required(data, "item_code", "Item Code")

        if Customers(self.conn).get(customer_code) is None:
            raise ValidationError(f"Customer '{customer_code}' does not exist. Create it first.")
        if Items(self.conn).get(item_code) is None:
            raise ValidationError(f"Item '{item_code}' does not exist. Create it first.")

        try:
            quantity = int(str(data.get("quantity")).strip())
        except ValueError:
            raise ValidationError("Quantity must be a whole number.") from None
        if quantity <= 0:
            raise ValidationError("Quantity must be at least 1.")

        unit_price = _money(data.get("unit_price"), "Unit Price")
        
        sub_total = (unit_price * quantity).quantize(Decimal("0.01"))
        total = sub_total  
        return {
            "voucher_no": voucher_no,
            "customer_code": customer_code,
            "item_code": item_code,
            "quantity": quantity,
            "unit_price": str(unit_price),
            "sub_total": str(sub_total),
            "total": str(total),
        }

    def next_voucher_no(self):
        """Suggest V0001, V0002, ... (one more than the highest existing number)."""
        numbers = [int(v[1:]) for (v,) in self.conn.execute("SELECT voucher_no FROM sale_orders")
                   if v[:1] == "V" and v[1:].isdigit()]
        return f"V{(max(numbers) + 1 if numbers else 1):04d}"
