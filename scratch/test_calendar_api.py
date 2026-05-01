
import asyncio
import httpx

async def check_calendar():
    async with httpx.AsyncClient() as client:
        try:
            response = await client.get("http://localhost:8000/api/v1/calendar")
            print(f"Status: {response.status_code}")
            if response.status_code == 200:
                data = response.json()
                print(f"Count: {len(data)}")
                if len(data) > 0:
                    print("First event:", data[0]['title'])
                else:
                    print("No events found in API.")
        except Exception as e:
            print(f"Error connecting to API: {e}")

if __name__ == "__main__":
    asyncio.run(check_calendar())
