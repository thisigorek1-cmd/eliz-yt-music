import asyncio
from datetime import datetime, timedelta
from database import get_sql

TOP_LIMIT = 4

async def fetch_top_tracks():
    """
    Считаем топ скачиваний за последние 24 часа
    """

    print("🔥 Calculating daily top tracks...")

    conn = get_sql()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT track_query, COUNT(*) as cnt
        FROM downloads_log
        WHERE downloaded_at >= datetime('now', '-1 day')
        GROUP BY track_query
        ORDER BY cnt DESC
        LIMIT ?
    """, (TOP_LIMIT,))

    top_tracks = cursor.fetchall()
    conn.close()

    if not top_tracks:
        print("❌ No downloads in last 24h")
        return

    print("🔥 TOP TODAY:")
    for track, count in top_tracks:
        print(f"{track} — {count} downloads")

async def scheduler():
    """
    Ждём до 00:00 и запускаем ежедневно
    """

    while True:
        now = datetime.now()
        next_run = datetime.combine(now.date(), datetime.min.time()) + timedelta(days=1)

        sleep_seconds = (next_run - now).total_seconds()

        print(f"⏳ Next auto update in {int(sleep_seconds)} sec")

        await asyncio.sleep(sleep_seconds)

        await fetch_top_tracks()