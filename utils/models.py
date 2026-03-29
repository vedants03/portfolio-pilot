from typing import TypedDict, Optional
from pydantic import BaseModel, Field


# ── Portfolio Agent Output ──

class StockHolding(BaseModel):
    symbol: str = Field(description="Trading symbol e.g. GOLDBETA, RELIANCE")
    name: str = Field(description="Full name of the instrument e.g. UTI Gold ETF")
    quantity: int = Field(description="Number of shares/units held")
    current_price: float = Field(description="Current market price in INR")
    total_value: float = Field(description="quantity * current_price")


class PortfolioData(BaseModel):
    holdings: list[StockHolding] = Field(description="List of all stock holdings")
    total_portfolio_value: float = Field(description="Sum of all holdings' total_value")


# ── News Agent Output ──

class NewsArticle(BaseModel):
    title: str = Field(description="Article headline")
    source: str = Field(description="News source name")
    date: str = Field(description="Publication date YYYY-MM-DD")
    summary: str = Field(description="Brief article summary")
    url: str = Field(default="", description="Link to the full article")


class StockNews(BaseModel):
    symbol: str = Field(description="Trading symbol this news relates to")
    articles: list[NewsArticle] = Field(description="Relevant news articles found")
    sentiment: str = Field(description="Overall sentiment: bullish, bearish, or neutral")
    sentiment_reasoning: str = Field(description="Brief explanation for the sentiment rating")


class NewsData(BaseModel):
    stock_news: list[StockNews] = Field(description="News and sentiment per stock")
    overall_market_sentiment: str = Field(description="Overall market sentiment across all holdings")


# ── Analysis Agent Output ──

class TechnicalIndicators(BaseModel):
    rsi: Optional[float] = Field(default=None, description="RSI value (0-100)")
    rsi_signal: Optional[str] = Field(default=None, description="overbought / oversold / neutral")
    macd_line: Optional[float] = Field(default=None, description="MACD line value")
    macd_signal_line: Optional[float] = Field(default=None, description="MACD signal line value")
    macd_histogram: Optional[float] = Field(default=None, description="MACD histogram value")
    macd_signal: Optional[str] = Field(default=None, description="bullish_crossover / bearish_crossover / neutral")
    bollinger_upper: Optional[float] = Field(default=None, description="Upper Bollinger Band")
    bollinger_middle: Optional[float] = Field(default=None, description="Middle Bollinger Band (SMA)")
    bollinger_lower: Optional[float] = Field(default=None, description="Lower Bollinger Band")
    bollinger_position: Optional[str] = Field(default=None, description="near_upper / near_lower / middle")
    candlestick_patterns: list[str] = Field(default_factory=list, description="Detected candlestick patterns")


class StockAnalysis(BaseModel):
    symbol: str = Field(description="Trading symbol")
    indicators: TechnicalIndicators = Field(description="Technical indicator values")
    risk_score: int = Field(description="Risk score 1-10, where 10 is highest risk")
    signal: str = Field(description="Overall signal: bullish / bearish / neutral")
    reasoning: str = Field(description="Brief explanation combining indicators and news")


class AnalysisData(BaseModel):
    stock_analyses: list[StockAnalysis] = Field(description="Per-stock technical analysis")
    portfolio_risk_score: int = Field(description="Overall portfolio risk score 1-10")
    sector_concentration_risk: str = Field(description="Assessment of sector concentration")
    summary: str = Field(description="Brief overall portfolio risk summary")


# ── Mitigation Agent Output ──

class RebalanceAction(BaseModel):
    symbol: str = Field(description="Trading symbol")
    action: str = Field(description="buy / sell / hold")
    quantity: int = Field(description="Number of shares to buy/sell, 0 for hold")
    reasoning: str = Field(description="Why this action is recommended")


class HedgingStrategy(BaseModel):
    strategy: str = Field(description="Description of the hedging strategy")
    instruments: list[str] = Field(description="Specific instruments or ETFs to use")
    reasoning: str = Field(description="Why this hedge is appropriate")


class ExitRecommendation(BaseModel):
    symbol: str = Field(description="Trading symbol")
    should_exit: bool = Field(description="Whether to fully exit this position")
    reasoning: str = Field(description="Why exit or stay")


class RecommendationsData(BaseModel):
    rebalancing: list[RebalanceAction] = Field(description="Rebalancing actions per stock")
    hedging: list[HedgingStrategy] = Field(description="Hedging strategies")
    exits: list[ExitRecommendation] = Field(description="Exit recommendations per stock")
    summary: str = Field(description="Brief overall recommendation summary")


# ── Graph State ──

class AgentState(TypedDict):
    portfolio: PortfolioData
    news: NewsData
    analysis: AnalysisData
    recommendations: RecommendationsData
    messages: list
    is_relevant: bool
