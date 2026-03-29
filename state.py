import asyncio
import os
import json
import base64
from dotenv import load_dotenv
from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client

load_dotenv()

config = {"apiKey": os.environ["GROWW_API_KEY"], "debug": True}
encoded = base64.urlsafe_b64encode(json.dumps(config).encode()).decode()
SERVER_URL = f"http://localhost:8181/mcp?config={encoded}"

async def main():
    async with streamablehttp_client(SERVER_URL) as (r, w, _):
        async with ClientSession(r, w) as session:
            await session.initialize()
            result = await session.call_tool("get_holdings", {})
            print("Raw client result:", result.content[0].text)

asyncio.run(main())