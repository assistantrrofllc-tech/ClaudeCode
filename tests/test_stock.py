"""
Tests for stock routes — CrewInventory module.

Covers:
- Phase 1 parity: dashboard, items CRUD, inventory, shops, checkout/return
- Vendors: CRUD, referential integrity
- Images: upload, delete, serve
- Item detail: JSON response with locations and transactions
- Project inventory: ordered vs on-site tracking, document upload
- Reorder: generate drafts, edit, history
- CrewAsset cross-wire: tool sync to assets table
- Access control: unauthorized users blocked
"""

import io
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

TEST_DB = "/tmp/test_crewledger_stock.db"
os.environ["DATABASE_PATH"] = TEST_DB
os.environ["TWILIO_AUTH_TOKEN"] = ""
os.environ["OPENAI_API_KEY"] = ""
os.environ["RECEIPT_STORAGE_PATH"] = "/tmp/test_receipt_images"
os.environ["STOCK_IMAGE_STORAGE_PATH"] = "/tmp/test_stock_images"
os.environ["INVENTORY_DOC_STORAGE_PATH"] = "/tmp/test_inv_docs"
os.environ["TESTING"] = "1"

import config.settings as _settings
_settings.TWILIO_AUTH_TOKEN = ""
_settings.OPENAI_API_KEY = ""
_settings.RECEIPT_STORAGE_PATH = "/tmp/test_receipt_images"
_settings.STOCK_IMAGE_STORAGE_PATH = "/tmp/test_stock_images"
_settings.INVENTORY_DOC_STORAGE_PATH = "/tmp/test_inv_docs"

from src.app import create_app
from src.database.connection import get_db

SCHEMA_PATH = Path(__file__).resolve().parent.parent / "src" / "database" / "schema.sql"


def setup_test_db():
    """Create a fresh test database with stock, vendor, and project seed data."""
    os.environ["DATABASE_PATH"] = TEST_DB
    if Path(TEST_DB).exists():
        Path(TEST_DB).unlink()
    db = get_db(TEST_DB)
    db.executescript(SCHEMA_PATH.read_text())

    # Phase 2 tables + columns (simulating migration)
    db.executescript("""
    CREATE TABLE IF NOT EXISTS stock_shops (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL UNIQUE,
        address TEXT,
        qr_code_id TEXT UNIQUE DEFAULT (lower(hex(randomblob(8)))),
        created_at TEXT DEFAULT (datetime('now'))
    );
    CREATE TABLE IF NOT EXISTS stock_items (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        sku TEXT,
        manufacturer TEXT,
        category TEXT DEFAULT 'General',
        unit TEXT DEFAULT 'EACH',
        pieces_per_unit INTEGER DEFAULT 1,
        reorder_point INTEGER DEFAULT 0,
        qr_code_id TEXT UNIQUE DEFAULT (lower(hex(randomblob(8)))),
        vendor_id INTEGER REFERENCES vendors(id),
        image_path TEXT,
        asset_id INTEGER,
        unit_label TEXT DEFAULT 'EA',
        pack_label TEXT DEFAULT 'BOX',
        created_at TEXT DEFAULT (datetime('now')),
        updated_at TEXT DEFAULT (datetime('now'))
    );
    CREATE TABLE IF NOT EXISTS shop_inventory (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        item_id INTEGER NOT NULL REFERENCES stock_items(id),
        shop_id INTEGER NOT NULL REFERENCES stock_shops(id),
        quantity REAL DEFAULT 0,
        section TEXT,
        updated_at TEXT DEFAULT (datetime('now')),
        UNIQUE(item_id, shop_id)
    );
    CREATE TABLE IF NOT EXISTS project_inventory (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        item_id INTEGER NOT NULL REFERENCES stock_items(id),
        project_id INTEGER NOT NULL,
        quantity REAL DEFAULT 0,
        quantity_ordered REAL DEFAULT 0,
        updated_at TEXT DEFAULT (datetime('now')),
        UNIQUE(item_id, project_id)
    );
    CREATE TABLE IF NOT EXISTS stock_transactions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        type TEXT NOT NULL,
        item_id INTEGER NOT NULL REFERENCES stock_items(id),
        shop_id INTEGER REFERENCES stock_shops(id),
        project_id INTEGER,
        employee_id INTEGER,
        quantity REAL NOT NULL,
        notes TEXT,
        created_at TEXT DEFAULT (datetime('now')),
        created_by TEXT
    );
    CREATE TABLE IF NOT EXISTS inventory_documents (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        project_id INTEGER NOT NULL,
        vendor_id INTEGER REFERENCES vendors(id),
        doc_type TEXT DEFAULT 'unknown',
        filename TEXT NOT NULL,
        file_path TEXT NOT NULL,
        status TEXT DEFAULT 'pending',
        notes TEXT,
        uploaded_by TEXT,
        created_at TEXT DEFAULT (datetime('now')),
        updated_at TEXT DEFAULT (datetime('now'))
    );
    CREATE TABLE IF NOT EXISTS inventory_document_items (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        document_id INTEGER NOT NULL REFERENCES inventory_documents(id) ON DELETE CASCADE,
        line_number INTEGER DEFAULT 0,
        description TEXT NOT NULL,
        quantity REAL DEFAULT 0,
        unit_price REAL,
        total_price REAL,
        stock_item_id INTEGER REFERENCES stock_items(id),
        match_status TEXT DEFAULT 'unmatched',
        created_at TEXT DEFAULT (datetime('now'))
    );
    CREATE TABLE IF NOT EXISTS reorder_requests (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        vendor_id INTEGER REFERENCES vendors(id),
        status TEXT DEFAULT 'draft',
        items_json TEXT NOT NULL,
        notes TEXT,
        email_to TEXT,
        email_subject TEXT,
        email_body TEXT,
        sent_at TEXT,
        created_by TEXT,
        created_at TEXT DEFAULT (datetime('now')),
        updated_at TEXT DEFAULT (datetime('now'))
    );
    CREATE TABLE IF NOT EXISTS assets (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        category TEXT DEFAULT 'tool',
        serial_number TEXT,
        stock_item_id INTEGER REFERENCES stock_items(id),
        vendor_id INTEGER REFERENCES vendors(id),
        assigned_to TEXT,
        status TEXT DEFAULT 'available',
        notes TEXT,
        created_at TEXT DEFAULT (datetime('now')),
        updated_at TEXT DEFAULT (datetime('now'))
    );
    CREATE TABLE IF NOT EXISTS vendor_item_map (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        vendor_id INTEGER NOT NULL REFERENCES vendors(id),
        item_id INTEGER NOT NULL REFERENCES stock_items(id),
        vendor_sku TEXT,
        vendor_item_name TEXT,
        vendor_unit TEXT NOT NULL DEFAULT 'EA',
        vendor_unit_quantity REAL NOT NULL DEFAULT 1,
        notes TEXT,
        created_at TEXT NOT NULL DEFAULT (datetime('now')),
        updated_at TEXT NOT NULL DEFAULT (datetime('now')),
        UNIQUE(vendor_id, item_id)
    );
    CREATE TABLE IF NOT EXISTS project_aliases (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        project_id INTEGER NOT NULL REFERENCES projects(id),
        alias TEXT NOT NULL,
        source TEXT,
        created_at TEXT NOT NULL DEFAULT (datetime('now')),
        UNIQUE(alias)
    );
    """)

    # Phase 2 ALTERs for existing tables (vendors from schema.sql)
    for col, col_def in [
        ("contact_email", "TEXT"),
        ("notes", "TEXT"),
        ("updated_at", "TEXT DEFAULT (datetime('now'))"),
    ]:
        try:
            db.execute(f"ALTER TABLE vendors ADD COLUMN {col} {col_def}")
        except Exception:
            pass

    # Seed data
    db.execute(
        "INSERT INTO employees (id, phone_number, first_name, full_name, email) "
        "VALUES (1, '+14075551111', 'Omar', 'Omar Test', 'omar@test.com')"
    )
    db.execute(
        "INSERT INTO projects (id, name, project_code, status) "
        "VALUES (1, 'Test Project', 'TP001', 'active')"
    )
    db.execute("INSERT INTO stock_shops (id, name) VALUES (1, 'Orlando Shop')")
    db.execute("INSERT INTO stock_shops (id, name) VALUES (2, 'Tampa Shop')")
    db.execute(
        "INSERT INTO vendors (id, name, phone, contact_name) "
        "VALUES (1, 'Acme Supply', '407-555-1234', 'John Smith')"
    )
    db.execute(
        "INSERT INTO stock_items (id, name, sku, manufacturer, category, unit, reorder_point, qr_code_id, vendor_id) "
        "VALUES (1, 'PVC Pipe 2in', 'PVC-2', 'Charlotte Pipe', 'Plumbing', 'EACH', 10, 'qr_pvc2in', 1)"
    )
    db.execute(
        "INSERT INTO stock_items (id, name, sku, manufacturer, category, unit, reorder_point, qr_code_id) "
        "VALUES (2, 'Wire Nuts', 'WN-100', '3M', 'Electrical', 'BOX', 5, 'qr_wirenuts')"
    )
    db.execute(
        "INSERT INTO stock_items (id, name, category, unit, qr_code_id) "
        "VALUES (3, 'Dewalt Drill', 'tool', 'EACH', 'qr_drill')"
    )
    db.execute("INSERT INTO shop_inventory (item_id, shop_id, quantity, section) VALUES (1, 1, 50, 'Aisle 2')")
    db.execute("INSERT INTO shop_inventory (item_id, shop_id, quantity) VALUES (2, 1, 3)")
    db.execute("INSERT INTO project_inventory (item_id, project_id, quantity) VALUES (1, 1, 10)")

    db.commit()
    db.close()

    # Create storage dirs
    for d in ("/tmp/test_stock_images", "/tmp/test_inv_docs"):
        Path(d).mkdir(parents=True, exist_ok=True)


def get_app():
    app = create_app()
    app.config["TESTING"] = True
    return app


def make_client(system_role="super_admin", email="rob.rrofllc@gmail.com"):
    client = get_app().test_client()
    with client.session_transaction() as sess:
        sess["user"] = {
            "email": email,
            "name": "Test User",
            "picture": "",
            "role": "admin",
            "system_role": system_role,
        }
        sess["employee_id"] = 1
    return client


# ══════════════════════════════════════════════════════════════
# Phase 1 parity tests
# ══════════════════════════════════════════════════════════════


def test_dashboard_page_loads():
    setup_test_db()
    client = make_client()
    resp = client.get("/stock/")
    assert resp.status_code == 200


def test_dashboard_api_returns_stats():
    setup_test_db()
    client = make_client()
    resp = client.get("/stock/api/dashboard")
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["total_items"] == 3
    assert data["total_qty"] == 53  # 50 + 3
    assert "shops" in data
    assert "projects_with_inventory" in data


def test_inventory_api_returns_items():
    setup_test_db()
    client = make_client()
    resp = client.get("/stock/api/inventory")
    assert resp.status_code == 200
    data = resp.get_json()
    assert len(data["items"]) >= 2


def test_inventory_filter_by_shop():
    setup_test_db()
    client = make_client()
    resp = client.get("/stock/api/inventory?shop_id=1")
    assert resp.status_code == 200
    data = resp.get_json()
    for item in data["items"]:
        assert item["shop_id"] == 1


def test_items_list():
    setup_test_db()
    client = make_client()
    resp = client.get("/stock/api/items")
    assert resp.status_code == 200
    data = resp.get_json()
    assert len(data["items"]) == 3


def test_items_search():
    setup_test_db()
    client = make_client()
    resp = client.get("/stock/api/items?search=PVC")
    assert resp.status_code == 200
    data = resp.get_json()
    assert len(data["items"]) == 1
    assert "PVC" in data["items"][0]["name"]


def test_items_create():
    setup_test_db()
    client = make_client()
    resp = client.post("/stock/api/items", json={
        "name": "New Item",
        "category": "General",
        "unit": "EACH",
    })
    assert resp.status_code == 201
    data = resp.get_json()
    assert "id" in data
    assert "qr_code_id" in data


def test_items_create_missing_name():
    setup_test_db()
    client = make_client()
    resp = client.post("/stock/api/items", json={"category": "General"})
    assert resp.status_code == 400


def test_items_update():
    setup_test_db()
    client = make_client()
    resp = client.put("/stock/api/items/1", json={"name": "PVC Pipe 3in"})
    assert resp.status_code == 200


def test_items_delete():
    setup_test_db()
    client = make_client()
    resp = client.delete("/stock/api/items/2")
    assert resp.status_code == 200
    # Verify deleted
    resp2 = client.get("/stock/api/items")
    names = [i["name"] for i in resp2.get_json()["items"]]
    assert "Wire Nuts" not in names


def test_shops_list():
    setup_test_db()
    client = make_client()
    resp = client.get("/stock/api/shops")
    assert resp.status_code == 200
    data = resp.get_json()
    assert len(data["shops"]) == 2


# ══════════════════════════════════════════════════════════════
# Vendor tests
# ══════════════════════════════════════════════════════════════


def test_vendors_list():
    setup_test_db()
    client = make_client()
    resp = client.get("/stock/api/vendors")
    assert resp.status_code == 200
    data = resp.get_json()
    assert len(data["vendors"]) >= 1


def test_vendors_create():
    setup_test_db()
    client = make_client()
    resp = client.post("/stock/api/vendors", json={
        "name": "Home Depot",
        "phone": "800-555-0000",
        "contact_email": "orders@homedepot.test",
    })
    assert resp.status_code == 201
    data = resp.get_json()
    assert "id" in data


def test_vendors_create_missing_name():
    setup_test_db()
    client = make_client()
    resp = client.post("/stock/api/vendors", json={"phone": "555-1234"})
    assert resp.status_code == 400


def test_vendors_update():
    setup_test_db()
    client = make_client()
    resp = client.put("/stock/api/vendors/1", json={"contact_email": "new@acme.test"})
    assert resp.status_code == 200


def test_vendors_update_404():
    setup_test_db()
    client = make_client()
    resp = client.put("/stock/api/vendors/999", json={"name": "Ghost"})
    assert resp.status_code == 404


def test_vendors_delete():
    setup_test_db()
    client = make_client()
    # Create a vendor with no items
    resp = client.post("/stock/api/vendors", json={"name": "Temp Vendor"})
    vendor_id = resp.get_json()["id"]
    resp = client.delete(f"/stock/api/vendors/{vendor_id}")
    assert resp.status_code == 200


def test_vendors_delete_with_items_fails():
    setup_test_db()
    client = make_client()
    # Vendor 1 has items referencing it
    resp = client.delete("/stock/api/vendors/1")
    assert resp.status_code == 409


def test_vendors_search():
    setup_test_db()
    client = make_client()
    resp = client.get("/stock/api/vendors?search=Acme")
    assert resp.status_code == 200
    data = resp.get_json()
    assert len(data["vendors"]) == 1


# ══════════════════════════════════════════════════════════════
# Image tests
# ══════════════════════════════════════════════════════════════


def test_image_upload():
    setup_test_db()
    client = make_client()
    data = {"image": (io.BytesIO(b"\x89PNG\r\n\x1a\n" + b"\x00" * 100), "test.png")}
    resp = client.post(
        "/stock/api/items/1/image",
        content_type="multipart/form-data",
        data=data,
    )
    assert resp.status_code == 200
    result = resp.get_json()
    assert "image_path" in result


def test_image_upload_bad_type():
    setup_test_db()
    client = make_client()
    data = {"image": (io.BytesIO(b"not a real file"), "test.txt")}
    resp = client.post(
        "/stock/api/items/1/image",
        content_type="multipart/form-data",
        data=data,
    )
    assert resp.status_code == 400


def test_image_delete():
    setup_test_db()
    client = make_client()
    # Upload first
    data = {"image": (io.BytesIO(b"\x89PNG\r\n\x1a\n" + b"\x00" * 100), "test.png")}
    client.post("/stock/api/items/1/image", content_type="multipart/form-data", data=data)
    # Delete
    resp = client.delete("/stock/api/items/1/image")
    assert resp.status_code == 200


def test_image_upload_missing_item():
    setup_test_db()
    client = make_client()
    data = {"image": (io.BytesIO(b"\x89PNG\r\n\x1a\n" + b"\x00" * 100), "test.png")}
    resp = client.post(
        "/stock/api/items/999/image",
        content_type="multipart/form-data",
        data=data,
    )
    assert resp.status_code == 404


# ══════════════════════════════════════════════════════════════
# Item detail tests
# ══════════════════════════════════════════════════════════════


def test_item_detail_page_loads():
    setup_test_db()
    client = make_client()
    resp = client.get("/stock/items/1")
    assert resp.status_code == 200


def test_item_detail_api():
    setup_test_db()
    client = make_client()
    resp = client.get("/stock/api/items/1/detail")
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["item"]["name"] == "PVC Pipe 2in"
    assert data["item"]["vendor_name"] == "Acme Supply"
    assert len(data["shop_inventory"]) >= 1
    assert len(data["project_inventory"]) >= 1
    assert data["total_shop_qty"] == 50
    assert data["total_project_qty"] == 10


def test_item_detail_404():
    setup_test_db()
    client = make_client()
    resp = client.get("/stock/api/items/999/detail")
    assert resp.status_code == 404


def test_item_detail_page_404():
    setup_test_db()
    client = make_client()
    resp = client.get("/stock/items/999")
    assert resp.status_code == 404


# ══════════════════════════════════════════════════════════════
# Project inventory tests
# ══════════════════════════════════════════════════════════════


def test_project_inventory_includes_vendor():
    setup_test_db()
    client = make_client()
    resp = client.get("/stock/api/project/1/inventory")
    assert resp.status_code == 200
    data = resp.get_json()
    items = data["items"]
    assert len(items) >= 1
    pvc = next((i for i in items if i["name"] == "PVC Pipe 2in"), None)
    assert pvc is not None
    assert pvc["vendor_name"] == "Acme Supply"


def test_project_page_loads():
    setup_test_db()
    client = make_client()
    resp = client.get("/stock/project/1")
    assert resp.status_code == 200


def test_project_upload_page_loads():
    setup_test_db()
    client = make_client()
    resp = client.get("/stock/project/1/upload")
    assert resp.status_code == 200


def test_project_doc_upload():
    setup_test_db()
    client = make_client()
    data = {
        "document": (io.BytesIO(b"%PDF-1.4 test"), "test_po.pdf"),
        "doc_type": "po",
        "vendor_id": "1",
    }
    resp = client.post(
        "/stock/api/project/1/documents",
        content_type="multipart/form-data",
        data=data,
    )
    assert resp.status_code == 201
    result = resp.get_json()
    assert "id" in result


def test_project_docs_list():
    setup_test_db()
    client = make_client()
    # Upload a doc first
    data = {"document": (io.BytesIO(b"%PDF-1.4 test"), "test.pdf"), "doc_type": "invoice"}
    client.post("/stock/api/project/1/documents", content_type="multipart/form-data", data=data)

    resp = client.get("/stock/api/project/1/documents")
    assert resp.status_code == 200
    result = resp.get_json()
    assert len(result["documents"]) >= 1


# ══════════════════════════════════════════════════════════════
# Reorder tests
# ══════════════════════════════════════════════════════════════


def test_reorder_generate():
    setup_test_db()
    client = make_client()
    resp = client.post("/stock/api/reorder/generate", json={
        "items": [
            {"item_id": 1, "quantity": 20},
            {"item_id": 2, "quantity": 50},
        ],
    })
    assert resp.status_code == 201
    data = resp.get_json()
    assert len(data["ids"]) >= 1


def test_reorder_generate_empty():
    setup_test_db()
    client = make_client()
    resp = client.post("/stock/api/reorder/generate", json={"items": []})
    assert resp.status_code == 400


def test_reorder_detail():
    setup_test_db()
    client = make_client()
    # Generate first
    resp = client.post("/stock/api/reorder/generate", json={
        "items": [{"item_id": 1, "quantity": 10}],
    })
    rid = resp.get_json()["ids"][0]
    resp = client.get(f"/stock/api/reorder/{rid}")
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["reorder"]["status"] == "draft"
    assert len(data["reorder"]["items"]) == 1


def test_reorder_update():
    setup_test_db()
    client = make_client()
    resp = client.post("/stock/api/reorder/generate", json={
        "items": [{"item_id": 1, "quantity": 10}],
    })
    rid = resp.get_json()["ids"][0]
    resp = client.put(f"/stock/api/reorder/{rid}", json={
        "notes": "Rush order",
        "email_to": "vendor@test.com",
    })
    assert resp.status_code == 200


def test_reorder_history():
    setup_test_db()
    client = make_client()
    # Generate a draft
    client.post("/stock/api/reorder/generate", json={
        "items": [{"item_id": 1, "quantity": 10}],
    })
    resp = client.get("/stock/api/reorder/history")
    assert resp.status_code == 200
    data = resp.get_json()
    assert len(data["orders"]) >= 1


def test_reorder_send_no_email():
    setup_test_db()
    client = make_client()
    resp = client.post("/stock/api/reorder/generate", json={
        "items": [{"item_id": 2, "quantity": 10}],  # Item 2 has no vendor
    })
    rid = resp.get_json()["ids"][0]
    resp = client.post(f"/stock/api/reorder/{rid}/send")
    assert resp.status_code == 400  # No email configured


# ══════════════════════════════════════════════════════════════
# CrewAsset cross-wire tests
# ══════════════════════════════════════════════════════════════


def test_tool_item_syncs_to_assets():
    setup_test_db()
    client = make_client()
    # Item 3 is category 'tool' — creating via API should sync
    resp = client.post("/stock/api/items", json={
        "name": "Milwaukee Saw",
        "category": "tool",
        "vendor_id": 1,
    })
    assert resp.status_code == 201
    item_id = resp.get_json()["id"]

    # Check assets table
    db = get_db(TEST_DB)
    try:
        asset = db.execute(
            "SELECT * FROM assets WHERE stock_item_id = ?", (item_id,)
        ).fetchone()
        assert asset is not None
        assert asset["name"] == "Milwaukee Saw"
        assert asset["vendor_id"] == 1
    finally:
        db.close()


def test_non_tool_item_not_synced():
    setup_test_db()
    client = make_client()
    resp = client.post("/stock/api/items", json={
        "name": "Copper Fitting",
        "category": "Plumbing",
    })
    assert resp.status_code == 201
    item_id = resp.get_json()["id"]

    db = get_db(TEST_DB)
    try:
        asset = db.execute(
            "SELECT * FROM assets WHERE stock_item_id = ?", (item_id,)
        ).fetchone()
        assert asset is None
    finally:
        db.close()


def test_fleet_tools_page():
    setup_test_db()
    client = make_client()
    resp = client.get("/fleet/tools")
    assert resp.status_code == 200


# ══════════════════════════════════════════════════════════════
# Access control tests
# ══════════════════════════════════════════════════════════════


def test_unauthorized_user_blocked():
    setup_test_db()
    client = make_client(email="nobody@example.com")
    resp = client.get("/stock/")
    assert resp.status_code == 403


def test_unauthorized_api_blocked():
    setup_test_db()
    client = make_client(email="nobody@example.com")
    resp = client.get("/stock/api/dashboard")
    assert resp.status_code == 403


def test_no_session_blocked():
    setup_test_db()
    app = create_app()
    app.config["TESTING"] = True
    client = app.test_client()
    resp = client.get("/stock/")
    # Should redirect to login or return 302/403
    assert resp.status_code in (302, 403)


def test_vendor_pages_load():
    setup_test_db()
    client = make_client()
    resp = client.get("/stock/vendors")
    assert resp.status_code == 200


def test_reorder_page_loads():
    setup_test_db()
    client = make_client()
    resp = client.get("/stock/reorder")
    assert resp.status_code == 200


# ══════════════════════════════════════════════════════════════
# Items with vendor_id tests
# ══════════════════════════════════════════════════════════════


def test_create_item_with_vendor():
    setup_test_db()
    client = make_client()
    resp = client.post("/stock/api/items", json={
        "name": "Vendor Item",
        "vendor_id": 1,
    })
    assert resp.status_code == 201

    # Verify vendor shows in listing
    resp2 = client.get("/stock/api/items?search=Vendor+Item")
    items = resp2.get_json()["items"]
    assert len(items) == 1
    assert items[0]["vendor_name"] == "Acme Supply"


def test_update_item_vendor():
    setup_test_db()
    client = make_client()
    resp = client.put("/stock/api/items/2", json={"vendor_id": 1})
    assert resp.status_code == 200

    resp2 = client.get("/stock/api/items/2/detail")
    assert resp2.get_json()["item"]["vendor_name"] == "Acme Supply"


# ══════════════════════════════════════════════════════════════
# Vendor-Item Mapping tests
# ══════════════════════════════════════════════════════════════


def test_vendor_map_crud():
    """Create, list, update, delete vendor-item mappings."""
    setup_test_db()
    client = make_client()

    # Create
    resp = client.post("/stock/api/items/1/vendor-maps", json={
        "vendor_id": 1,
        "vendor_sku": "APS500SBZ130",
        "vendor_item_name": "APS500 Dark Bronze",
        "vendor_unit": "BOX",
        "vendor_unit_quantity": 24,
        "notes": "Lead time 3 days",
    })
    assert resp.status_code == 201
    map_id = resp.get_json()["id"]

    # List
    resp = client.get("/stock/api/items/1/vendor-maps")
    assert resp.status_code == 200
    maps = resp.get_json()["maps"]
    assert len(maps) == 1
    assert maps[0]["vendor_sku"] == "APS500SBZ130"
    assert maps[0]["vendor_unit"] == "BOX"
    assert maps[0]["vendor_unit_quantity"] == 24
    assert maps[0]["vendor_name"] == "Acme Supply"

    # Update
    resp = client.put(f"/stock/api/items/1/vendor-maps/{map_id}", json={
        "vendor_sku": "APS500-NEW",
        "vendor_unit_quantity": 48,
    })
    assert resp.status_code == 200

    # Verify update
    resp = client.get("/stock/api/items/1/vendor-maps")
    maps = resp.get_json()["maps"]
    assert maps[0]["vendor_sku"] == "APS500-NEW"
    assert maps[0]["vendor_unit_quantity"] == 48

    # Delete
    resp = client.delete(f"/stock/api/items/1/vendor-maps/{map_id}")
    assert resp.status_code == 200

    resp = client.get("/stock/api/items/1/vendor-maps")
    assert len(resp.get_json()["maps"]) == 0


def test_vendor_map_duplicate_rejected():
    """Cannot create two mappings for same vendor+item."""
    setup_test_db()
    client = make_client()
    client.post("/stock/api/items/1/vendor-maps", json={"vendor_id": 1})
    resp = client.post("/stock/api/items/1/vendor-maps", json={"vendor_id": 1})
    assert resp.status_code == 409


def test_vendor_map_requires_vendor():
    """vendor_id is required."""
    setup_test_db()
    client = make_client()
    resp = client.post("/stock/api/items/1/vendor-maps", json={"vendor_sku": "X"})
    assert resp.status_code == 400


def test_vendor_map_nonexistent_item():
    """404 for non-existent item."""
    setup_test_db()
    client = make_client()
    resp = client.post("/stock/api/items/999/vendor-maps", json={"vendor_id": 1})
    assert resp.status_code == 404


# ══════════════════════════════════════════════════════════════
# Project Aliases tests
# ══════════════════════════════════════════════════════════════


def test_project_alias_crud():
    """Create, list, delete project aliases."""
    setup_test_db()
    client = make_client()

    # Create
    resp = client.post("/stock/api/projects/1/aliases", json={
        "alias": "SPERROW",
        "source": "Triangle Fastener packing slip",
    })
    assert resp.status_code == 201
    alias_id = resp.get_json()["id"]

    # List
    resp = client.get("/stock/api/projects/1/aliases")
    assert resp.status_code == 200
    aliases = resp.get_json()["aliases"]
    assert len(aliases) == 1
    assert aliases[0]["alias"] == "SPERROW"

    # Delete
    resp = client.delete(f"/stock/api/projects/1/aliases/{alias_id}")
    assert resp.status_code == 200

    resp = client.get("/stock/api/projects/1/aliases")
    assert len(resp.get_json()["aliases"]) == 0


def test_project_alias_unique():
    """Cannot reuse the same alias for another project."""
    setup_test_db()
    client = make_client()
    client.post("/stock/api/projects/1/aliases", json={"alias": "SPERROW"})
    resp = client.post("/stock/api/projects/1/aliases", json={"alias": "SPERROW"})
    assert resp.status_code == 409


def test_project_match_exact_name():
    """Match by exact project name."""
    setup_test_db()
    client = make_client()
    resp = client.post("/stock/api/projects/match", json={"query": "Test Project"})
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["match"]["id"] == 1
    assert data["match_type"] == "exact_name"


def test_project_match_by_alias():
    """Match by alias."""
    setup_test_db()
    client = make_client()
    client.post("/stock/api/projects/1/aliases", json={"alias": "SPERROW"})
    resp = client.post("/stock/api/projects/match", json={"query": "SPERROW"})
    data = resp.get_json()
    assert data["match"]["id"] == 1
    assert data["match_type"] == "alias"


def test_project_match_fuzzy():
    """Fuzzy match with high enough score."""
    setup_test_db()
    client = make_client()
    resp = client.post("/stock/api/projects/match", json={"query": "Test Projct"})
    data = resp.get_json()
    # Should fuzzy match or return candidates
    assert data["match_type"] in ("fuzzy", "none")
    if data["match_type"] == "fuzzy":
        assert data["match"]["id"] == 1


# ══════════════════════════════════════════════════════════════
# Dual Unit Display tests
# ══════════════════════════════════════════════════════════════


def test_item_unit_label_saved():
    """unit_label and pack_label are persisted."""
    setup_test_db()
    client = make_client()
    resp = client.put("/stock/api/items/1", json={
        "unit_label": "TUBE",
        "pack_label": "CASE",
        "pieces_per_unit": 24,
    })
    assert resp.status_code == 200

    resp = client.get("/stock/api/items/1/detail")
    item = resp.get_json()["item"]
    assert item["unit_label"] == "TUBE"
    assert item["pack_label"] == "CASE"
    assert item["pieces_per_unit"] == 24


def test_inventory_api_returns_unit_fields():
    """Inventory API returns unit_label and pack_label."""
    setup_test_db()
    client = make_client()
    resp = client.get("/stock/api/inventory")
    items = resp.get_json()["items"]
    assert len(items) > 0
    # Default values
    assert "unit_label" in items[0]
    assert "pack_label" in items[0]


def test_create_item_with_unit_labels():
    """Create item with unit_label and pack_label."""
    setup_test_db()
    client = make_client()
    resp = client.post("/stock/api/items", json={
        "name": "Sealant Tubes",
        "unit_label": "TUBE",
        "pack_label": "BOX",
        "pieces_per_unit": 24,
    })
    assert resp.status_code == 201
    item_id = resp.get_json()["id"]

    resp = client.get(f"/stock/api/items/{item_id}/detail")
    item = resp.get_json()["item"]
    assert item["unit_label"] == "TUBE"
    assert item["pack_label"] == "BOX"
