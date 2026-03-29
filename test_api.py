"""
Test script to try the FastAPI streaming endpoints.

Run the server first:   python server.py
Then run this:          python test_api.py

This demonstrates how a client (frontend/mobile app) would interact
with the SSE streaming API.
"""
import httpx
import json


BASE_URL = "http://localhost:8000"


def stream_sse(response):
    """
    Parse SSE events from an httpx streaming response.

    SSE format is:
        event: event_name\n
        data: json_payload\n
        \n

    Each event has a type (event:) and payload (data:).
    """
    event_type = None
    for line in response.iter_lines():
        if line.startswith("event:"):
            event_type = line[len("event:"):].strip()
        elif line.startswith("data:"):
            data = json.loads(line[len("data:"):].strip())
            yield event_type, data
            event_type = None


def main():
    thread_id = None

    # ── Phase 1: Start analysis ──
    print("=" * 60)
    print("PHASE 1: Starting analysis (streaming portfolio + news)...")
    print("=" * 60)

    with httpx.stream("GET", f"{BASE_URL}/analyze", timeout=120) as response:
        for event_type, data in stream_sse(response):

            if event_type == "thread_id":
                thread_id = data["thread_id"]
                print(f"\nSession started: {thread_id}\n")

            elif event_type == "portfolio":
                print("── PORTFOLIO ──")
                for h in data["holdings"]:
                    print(f"  {h['symbol']} ({h['name']}): {h['quantity']} units @ ₹{h['current_price']:.2f}")
                print(f"  Total: ₹{data['total_portfolio_value']:.2f}\n")

            elif event_type == "news":
                print("── NEWS & SENTIMENT ──")
                for sn in data["stock_news"]:
                    print(f"  {sn['symbol']} — {sn['sentiment'].upper()}: {sn['sentiment_reasoning']}")
                    for a in sn["articles"]:
                        print(f"    • [{a['date']}] {a['title']}")
                print(f"  Overall: {data['overall_market_sentiment']}\n")

            elif event_type == "human_review_needed":
                print(f"── REVIEW NEEDED ──")
                print(f"  {data['message']}\n")

    # ── Human decision ──
    user_input = input("Is the news relevant for analysis? (y/n): ")
    is_relevant = user_input.strip().lower() == "y"

    # ── Phase 2: Continue with analysis ──
    print("\n" + "=" * 60)
    print("PHASE 2: Running technical analysis + recommendations...")
    print("=" * 60)

    with httpx.stream(
        "POST",
        f"{BASE_URL}/continue",
        json={"thread_id": thread_id, "is_relevant": is_relevant},
        timeout=300,  # Analysis can take a while with multiple tool calls
    ) as response:
        for event_type, data in stream_sse(response):

            if event_type == "analysis":
                print("\n── TECHNICAL ANALYSIS ──")
                for sa in data["stock_analyses"]:
                    ind = sa["indicators"]
                    print(f"  {sa['symbol']} — Risk: {sa['risk_score']}/10 — {sa['signal'].upper()}")
                    print(f"    RSI: {ind['rsi']} ({ind['rsi_signal']})")
                    print(f"    MACD: histogram={ind['macd_histogram']} ({ind['macd_signal']})")
                    print(f"    Bollinger: {ind['bollinger_position']}")
                    if ind["candlestick_patterns"]:
                        print(f"    Patterns: {', '.join(ind['candlestick_patterns'])}")
                print(f"  Portfolio Risk: {data['portfolio_risk_score']}/10")
                print(f"  Summary: {data['summary']}\n")

            elif event_type == "recommendations":
                print("── RECOMMENDATIONS ──")
                print("  Rebalancing:")
                for r in data["rebalancing"]:
                    print(f"    {r['symbol']}: {r['action'].upper()} {r['quantity']} shares — {r['reasoning']}")
                print("  Hedging:")
                for h in data["hedging"]:
                    print(f"    {h['strategy']} → {', '.join(h['instruments'])}")
                print("  Exits:")
                for e in data["exits"]:
                    status = "EXIT" if e["should_exit"] else "HOLD"
                    print(f"    {e['symbol']}: {status} — {e['reasoning']}")
                print(f"  Summary: {data['summary']}\n")

            elif event_type == "done":
                print("── COMPLETE ──")

    print("\nDone!")


if __name__ == "__main__":
    main()
