/*
 * Financial Agent Frontend
 *
 * This file handles the two-phase SSE flow:
 *
 * Phase 1: GET /analyze
 *   - Opens an SSE connection (EventSource)
 *   - Receives: thread_id → portfolio → news → human_review_needed
 *   - Each event triggers a render function that builds the UI
 *
 * Phase 2: POST /continue (after human review)
 *   - SSE via fetch() + ReadableStream (EventSource doesn't support POST)
 *   - Receives: analysis → recommendations → done
 *
 * Why two different SSE approaches?
 *   EventSource (Phase 1): Simple, built-in browser API, but only supports GET
 *   fetch + reader (Phase 2): More code, but supports POST with a JSON body
 */

const API_BASE = "";  // same origin since FastAPI serves the frontend

let threadId = null;

// ── Phase 1: Start analysis ──

function startAnalysis() {
    // Disable button and show progress
    document.getElementById("start-btn").disabled = true;
    document.getElementById("start-btn").textContent = "Analyzing...";
    show("progress");
    show("loading");
    setLoadingText("Fetching portfolio...");
    setStep("portfolio", "active");

    // Reset any previous results
    ["portfolio", "news", "review", "analysis", "recommendations"].forEach(s => {
        hide(s + "-section");
    });

    /*
     * EventSource opens a persistent connection to GET /analyze.
     * The server sends SSE events as each agent node completes.
     * We listen for specific event types and render them.
     */
    const source = new EventSource(`${API_BASE}/analyze`);

    source.addEventListener("thread_id", (e) => {
        const data = JSON.parse(e.data);
        threadId = data.thread_id;
    });

    source.addEventListener("portfolio", (e) => {
        const data = JSON.parse(e.data);
        renderPortfolio(data);
        setStep("portfolio", "done");
        setStep("news", "active");
        setLoadingText("Searching for news...");
    });

    source.addEventListener("news", (e) => {
        const data = JSON.parse(e.data);
        renderNews(data);
        setStep("news", "done");
        setStep("review", "active");
        hide("loading");
    });

    source.addEventListener("human_review_needed", (e) => {
        show("review-section");
        source.close();  // Close SSE — we'll open a new one for Phase 2
    });

    source.onerror = () => {
        source.close();
        hide("loading");
        setLoadingText("Connection error. Please try again.");
        show("loading");
    };
}


// ── Phase 2: Continue after human review ──

async function continueAnalysis(isRelevant) {
    hide("review-section");
    setStep("review", "done");
    setStep("analysis", "active");
    show("loading");
    setLoadingText("Running technical analysis (this may take a minute)...");

    /*
     * We can't use EventSource for POST requests (it only supports GET).
     * Instead, we use fetch() with a ReadableStream to parse SSE manually.
     *
     * The pattern:
     * 1. fetch() with POST body
     * 2. Get a reader from response.body
     * 3. Read chunks, split by newlines
     * 4. Parse "event:" and "data:" lines (same format as EventSource)
     */
    const response = await fetch(`${API_BASE}/continue`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ thread_id: threadId, is_relevant: isRelevant }),
    });

    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let buffer = "";

    while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });

        // SSE events are separated by double newlines
        const parts = buffer.split("\n\n");
        buffer = parts.pop();  // Keep incomplete chunk in buffer

        for (const part of parts) {
            const lines = part.trim().split("\n");
            let eventType = null;
            let eventData = null;

            for (const line of lines) {
                if (line.startsWith("event:")) {
                    eventType = line.slice(6).trim();
                } else if (line.startsWith("data:")) {
                    eventData = line.slice(5).trim();
                }
            }

            if (!eventType || !eventData) continue;

            const data = JSON.parse(eventData);

            if (eventType === "analysis") {
                renderAnalysis(data);
                setStep("analysis", "done");
                setStep("recommendations", "active");
                setLoadingText("Generating recommendations...");
            } else if (eventType === "recommendations") {
                renderRecommendations(data);
                setStep("recommendations", "done");
                hide("loading");
            } else if (eventType === "done") {
                hide("loading");
                document.getElementById("start-btn").disabled = false;
                document.getElementById("start-btn").textContent = "Run Again";
            }
        }
    }
}


// ── Render Functions ──

function renderPortfolio(data) {
    const html = `
        <table class="holdings-table">
            <thead>
                <tr>
                    <th>Symbol</th>
                    <th>Name</th>
                    <th>Qty</th>
                    <th>Price</th>
                    <th>Value</th>
                </tr>
            </thead>
            <tbody>
                ${data.holdings.map(h => `
                    <tr>
                        <td><strong>${h.symbol}</strong></td>
                        <td>${h.name}</td>
                        <td>${h.quantity}</td>
                        <td>${currency(h.current_price)}</td>
                        <td>${currency(h.total_value)}</td>
                    </tr>
                `).join("")}
            </tbody>
        </table>
        <div class="portfolio-total">Total: ${currency(data.total_portfolio_value)}</div>
    `;
    document.getElementById("portfolio-content").innerHTML = html;
    show("portfolio-section");
}

function renderNews(data) {
    const html = data.stock_news.map(sn => `
        <div class="news-stock">
            <div class="news-stock-header">
                <h3>${sn.symbol}</h3>
                <span class="sentiment-badge sentiment-${sn.sentiment.toLowerCase()}">${sn.sentiment}</span>
            </div>
            <div class="news-reason">${sn.sentiment_reasoning}</div>
            ${sn.articles.map(a => `
                <div class="article">
                    <div class="article-title">${a.url ? `<a href="${a.url}" target="_blank" rel="noopener">${a.title}</a>` : a.title}</div>
                    <div class="article-meta">${a.source} &middot; ${a.date}</div>
                </div>
            `).join("")}
        </div>
    `).join("");
    document.getElementById("news-content").innerHTML = html;
    show("news-section");
}

function renderAnalysis(data) {
    const stocksHtml = data.stock_analyses.map(sa => {
        const ind = sa.indicators;
        const riskClass = sa.risk_score <= 3 ? "risk-low" : sa.risk_score <= 6 ? "risk-medium" : "risk-high";

        return `
            <div class="stock-analysis">
                <div class="stock-analysis-header">
                    <h3>${sa.symbol} &mdash; ${sa.signal.toUpperCase()}</h3>
                    <span class="risk-badge ${riskClass}">Risk ${sa.risk_score}/10</span>
                </div>
                <div class="indicators-grid">
                    <div class="indicator">
                        <div class="indicator-label">RSI</div>
                        <div class="indicator-value">${ind.rsi ?? "N/A"} ${ind.rsi_signal ? `(${ind.rsi_signal})` : ""}</div>
                    </div>
                    <div class="indicator">
                        <div class="indicator-label">MACD</div>
                        <div class="indicator-value">H: ${ind.macd_histogram ?? "N/A"} ${ind.macd_signal ? `(${ind.macd_signal})` : ""}</div>
                    </div>
                    <div class="indicator">
                        <div class="indicator-label">Bollinger</div>
                        <div class="indicator-value">${ind.bollinger_position ?? "N/A"}</div>
                    </div>
                    <div class="indicator">
                        <div class="indicator-label">Patterns</div>
                        <div class="indicator-value">${ind.candlestick_patterns?.length ? ind.candlestick_patterns.join(", ") : "None"}</div>
                    </div>
                </div>
                <div class="analysis-reasoning">${sa.reasoning}</div>
            </div>
        `;
    }).join("");

    const summaryHtml = `
        <div class="portfolio-risk-summary">
            <h3>Portfolio Risk: ${data.portfolio_risk_score}/10</h3>
            <p style="color: #7d8590; font-size: 0.85rem; margin-top: 6px;">${data.sector_concentration_risk}</p>
            <p style="color: #e1e4e8; font-size: 0.9rem; margin-top: 8px;">${data.summary}</p>
        </div>
    `;

    document.getElementById("analysis-content").innerHTML = stocksHtml + summaryHtml;
    show("analysis-section");
}

function renderRecommendations(data) {
    let html = "";

    // Rebalancing
    html += `<div class="rec-group"><h3>Rebalancing</h3>`;
    for (const r of data.rebalancing) {
        const actionClass = r.action === "buy" ? "action-buy" : r.action === "sell" ? "action-sell" : "action-hold";
        html += `
            <div class="rec-item">
                <span class="rec-action ${actionClass}">${r.action}</span>
                <strong>${r.symbol}</strong> &mdash; ${r.quantity} shares
                <br><span style="color: #7d8590;">${r.reasoning}</span>
            </div>`;
    }
    html += `</div>`;

    // Hedging
    html += `<div class="rec-group"><h3>Hedging Strategies</h3>`;
    for (const h of data.hedging) {
        html += `
            <div class="rec-item">
                <strong>${h.strategy}</strong>
                <br><span style="color: #58a6ff;">${h.instruments.join(", ")}</span>
                <br><span style="color: #7d8590;">${h.reasoning}</span>
            </div>`;
    }
    html += `</div>`;

    // Exits
    html += `<div class="rec-group"><h3>Exit Recommendations</h3>`;
    for (const e of data.exits) {
        const actionClass = e.should_exit ? "action-exit" : "action-hold";
        const label = e.should_exit ? "EXIT" : "HOLD";
        html += `
            <div class="rec-item">
                <span class="rec-action ${actionClass}">${label}</span>
                <strong>${e.symbol}</strong>
                <br><span style="color: #7d8590;">${e.reasoning}</span>
            </div>`;
    }
    html += `</div>`;

    // Summary
    html += `<div class="rec-summary">${data.summary}</div>`;

    document.getElementById("recommendations-content").innerHTML = html;
    show("recommendations-section");
}


// ── Helpers ──

function currency(val) {
    return new Intl.NumberFormat("en-IN", {
        style: "currency",
        currency: "INR",
        maximumFractionDigits: 2,
    }).format(val);
}

function show(id) {
    document.getElementById(id).classList.remove("hidden");
}

function hide(id) {
    document.getElementById(id).classList.add("hidden");
}

function setLoadingText(text) {
    document.getElementById("loading-text").textContent = text;
}

function setStep(name, state) {
    const el = document.getElementById(`step-${name}`);
    el.classList.remove("active", "done");
    if (state) el.classList.add(state);
}
