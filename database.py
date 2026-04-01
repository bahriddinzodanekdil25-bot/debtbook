import aiosqlite
from datetime import date

DB_PATH = "debtors.db"

async def init_db():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS debtors (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                phone TEXT NOT NULL,
                product TEXT NOT NULL,
                amount REAL NOT NULL,
                due_date TEXT NOT NULL,
                notified INTEGER DEFAULT 0,
                paid INTEGER DEFAULT 0,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)
        await db.commit()
    print("✅ База данных готова")

async def add_debtor(name, phone, product, amount, due_date):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT INTO debtors (name, phone, product, amount, due_date) VALUES (?, ?, ?, ?, ?)",
            (name, phone, product, amount, due_date)
        )
        await db.commit()

async def get_all_debtors():
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM debtors WHERE paid = 0 ORDER BY due_date"
        ) as cursor:
            return await cursor.fetchall()

async def get_due_today():
    today = date.today().isoformat()
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM debtors WHERE due_date = ? AND paid = 0 AND notified = 0",
            (today,)
        ) as cursor:
            return await cursor.fetchall()

async def mark_notified(debtor_id):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("UPDATE debtors SET notified = 1 WHERE id = ?", (debtor_id,))
        await db.commit()

async def mark_paid(debtor_id):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("UPDATE debtors SET paid = 1 WHERE id = ?", (debtor_id,))
        await db.commit()

async def delete_debtor(debtor_id):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("DELETE FROM debtors WHERE id = ?", (debtor_id,))
        await db.commit()
