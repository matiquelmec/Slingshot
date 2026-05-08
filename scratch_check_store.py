import asyncio
import json
from engine.core.store import store

async def check_store():
    states = await store.get_market_states()
    print(json.dumps(states, indent=2))

if __name__ == "__main__":
    asyncio.run(check_store())
