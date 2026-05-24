import aiosqlite
from datetime import datetime, timedelta
from contextlib import asynccontextmanager

DB_PATH = "database.db"

class DatabaseManager:
    def __init__(self, db_path: str = DB_PATH):
        self.db_path = db_path
        self._db = None

    @asynccontextmanager
    async def get_db(self):
        yield self._db

    async def init_db(self):
        self._db = await aiosqlite.connect(self.db_path)
        await self._db.execute("PRAGMA journal_mode=WAL;")
        self._db.row_factory = aiosqlite.Row
        
        await self._db.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                status TEXT DEFAULT 'user',
                total_downloads INTEGER DEFAULT 0,
                daily_downloads INTEGER DEFAULT 0,
                last_active TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
        """)
        await self._db.execute("""
            CREATE TABLE IF NOT EXISTS global_stats (
                metric TEXT PRIMARY KEY,
                value INTEGER DEFAULT 0
            )
        """)

        await self._db.execute("INSERT OR IGNORE INTO global_stats (metric, value) VALUES ('total_downloaded_tracks', 0)")
        await self._db.execute("INSERT OR IGNORE INTO global_stats (metric, value) VALUES ('critical_errors', 0)")
        await self._db.commit()
    
    async def register_user(self, user_id: int):
        now_dt = datetime.now()
        now_str = now_dt.strftime("%Y-%m-%d %H:%M:%S")
        
        async with self.get_db() as db:
            async with db.execute("SELECT last_active, daily_downloads FROM users WHERE user_id = ?", (user_id,)) as cursor:
                row = await cursor.fetchone()
                
            if row:
                old_last_active = row["last_active"]
                old_daily = row["daily_downloads"]
                
                is_reset_needed = old_last_active[:10] != now_str[:10]
                
                # TEST
                #old_dt = datetime.strptime(old_last_active, "%Y-%m-%d %H:%M:%S")
                #is_reset_needed = (now_dt - old_dt).total_seconds() >= 60
                
                if is_reset_needed:
                    old_daily = 0 
                    
                await db.execute("""
                    UPDATE users 
                    SET daily_downloads = ?, last_active = ? 
                    WHERE user_id = ?
                """, (old_daily, now_str, user_id))
            else:
                await db.execute("""
                    INSERT INTO users (user_id, last_active, created_at)
                    VALUES (?, ?, ?)
                """, (user_id, now_str, now_str))
                
            await db.commit()
    
    async def get_user(self, user_id: int):
        async with self.get_db() as db:
            async with db.execute("SELECT * FROM users WHERE user_id = ?", (user_id,)) as cursor:
                row = await cursor.fetchone()
                return dict(row) if row else None
    
    async def update_user_status(self, user_id: int, status: str):
        async with self.get_db() as db:
            await db.execute("UPDATE users SET status = ? WHERE user_id = ?", (status, user_id))
            await db.commit()
    
    async def track_download(self, user_id: int, track_count: int = 1):
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        async with self.get_db() as db:
            await db.execute("""
                UPDATE users
                SET total_downloads = total_downloads + ?, 
                    daily_downloads = daily_downloads + ?, 
                    last_active = ?
                WHERE user_id = ?
            """, (track_count, track_count, now, user_id))
            
            await db.execute("""
                UPDATE global_stats
                SET value = value + ?
                WHERE metric = 'total_downloaded_tracks'
            """, (track_count,))
            await db.commit()
    
    async def track_error(self):
        async with self.get_db() as db:
            await db.execute("""
                UPDATE global_stats
                SET value = value + 1
                WHERE metric = 'critical_errors'
            """)
            await db.commit()
            
    async def get_active_users_count(self, days: int = 3) -> int:
        threshold_date = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d %H:%M:%S")
        async with self.get_db() as db:
            async with db.execute("SELECT COUNT(*) FROM users WHERE last_active >= ?", (threshold_date,)) as cursor:
                res = await cursor.fetchone()
                return res[0] if res else 0
    
    async def get_global_stats(self) -> dict:
        async with self.get_db() as db:
            async with db.execute("SELECT COUNT(*) FROM users") as cursor:
                res = await cursor.fetchone()
                total_users = res[0] if res else 0
                
            async with db.execute("SELECT value FROM global_stats WHERE metric = 'total_downloaded_tracks'") as cursor:
                res = await cursor.fetchone()
                total_tracks = res[0] if res else 0
                
            async with db.execute("SELECT value FROM global_stats WHERE metric = 'critical_errors'") as cursor:
                res = await cursor.fetchone()
                total_errors = res[0] if res else 0
            
            active_3d = await self.get_active_users_count(days=3)
            
            return {
                "total_users": total_users,
                "active_users_3d": active_3d,
                "total_downloaded_tracks": total_tracks,
                "critical_errors": total_errors
            }

    async def reset_daily_downloads(self):
        async with self.get_db() as db:
            await db.execute("UPDATE users SET daily_downloads = 0")
            await db.commit()

    async def close_db(self):
        if self._db:
            await self._db.close()
            print("[DB] Connection closed cleanly.")


db = DatabaseManager()