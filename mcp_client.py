import asyncio
from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client
import json
import base64

config = {"apiKey": "eyJraWQiOiJaTUtjVXciLCJhbGciOiJFUzI1NiJ9.eyJleHAiOjI1NjMxNjE2MzMsImlhdCI6MTc3NDc2MTYzMywibmJmIjoxNzc0NzYxNjMzLCJzdWIiOiJ7XCJ0b2tlblJlZklkXCI6XCIxMDhiZWViYy05YWQxLTQ0MjMtYmE2ZC0yYTkwMGUwYTk5ZGFcIixcInZlbmRvckludGVncmF0aW9uS2V5XCI6XCJlMzFmZjIzYjA4NmI0MDZjODg3NGIyZjZkODQ5NTMxM1wiLFwidXNlckFjY291bnRJZFwiOlwiNmY4ODg0MGItMzllMS00ZjY4LWIxMmItMjVmNDgxYWQwZmJjXCIsXCJkZXZpY2VJZFwiOlwiMzYxYzI1YjItMmJlZC01ZjEwLTlmYjgtODA5ZThiMWY1NTZlXCIsXCJzZXNzaW9uSWRcIjpcImI0NWExZGY3LWE4N2UtNDVkMy04ODJiLTRlMjBlYzE1MmMyY1wiLFwiYWRkaXRpb25hbERhdGFcIjpcIno1NC9NZzltdjE2WXdmb0gvS0EwYklBSlU2K01BQTRhS3U1TE1QWEVaQkpSTkczdTlLa2pWZDNoWjU1ZStNZERhWXBOVi9UOUxIRmtQejFFQisybTdRPT1cIixcInJvbGVcIjpcImF1dGgtdG90cFwiLFwic291cmNlSXBBZGRyZXNzXCI6XCIyNDAyOmUyODA6M2UwNjplYjpmOTE2OjE5ODA6OWRlZTo0NDdiLDE3Mi42OS4xMjkuMjAwLDM1LjI0MS4yMy4xMjNcIixcInR3b0ZhRXhwaXJ5VHNcIjoyNTYzMTYxNjMzNTI3LFwidmVuZG9yTmFtZVwiOlwiZ3Jvd3dBcGlcIn0iLCJpc3MiOiJhcGV4LWF1dGgtcHJvZC1hcHAifQ.-w-HD2nNSncYDlBp0bKz37MCHuWBlswQHCYbYlMoI8Bosm7fe8G73h1cNSPOtbhQ5sGMTVHssve4KDVwzhba9A", "debug": True}

encoded = base64.urlsafe_b64encode(json.dumps(config).encode()).decode()
SERVER_URL = f"http://localhost:8181/mcp?config={encoded}"

async def main():

    async with streamable_http_client(SERVER_URL) as (read_stream, write_stream, _):
        async with ClientSession(read_stream, write_stream) as session:
            await session.initialize()

            tools = await session.list_tools()

            # for tool in tools.tools:
            #     print(f"\n\n{tool}\n\n")

            print("\n=== Downloading Instruments ===")
            result = await session.call_tool(
                "download_instruments_csv",
                {}
            )
            print(result.content[0].text)

            print("\n=== Calling search_instruments ===")
            result = await session.call_tool(
                "search_instruments",
                {"query": "reliance", "exchange": "NSE", "limit": 3}
            )
            print(result.content[0].text)

asyncio.run(main())
