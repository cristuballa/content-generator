import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.calendar_manager import calendar_manager
from core.social_dispatcher import social_dispatcher

async def main():
    print("Testing execute_due_posts...")
    res = await calendar_manager.execute_due_posts(social_dispatcher)
    print(f"Executed {len(res)} due posts.")
    for item in res:
        print(f"Post {item.get('id')}: status={item.get('status')}, error={item.get('error')}, retries={item.get('retry_count')}, next_retry={item.get('next_retry_at')}")

if __name__ == "__main__":
    asyncio.run(main())
