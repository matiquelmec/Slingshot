
import asyncio
import httpx
from engine.workers.calendar_worker import CalendarWorker
from engine.core.store import store

async def test_calendar():
    worker = CalendarWorker()
    await worker.fetch_and_process_calendar()
    events = await store.get_economic_events()
    print(f"Events found: {len(events)}")
    for ev in events:
        print(f"[{ev['impact']}] {ev['country']}: {ev['title']}")

if __name__ == "__main__":
    asyncio.run(test_calendar())
