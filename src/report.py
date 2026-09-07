"""Generate a self-contained local MarketPulse recruiter report."""
from html import escape
from pathlib import Path

import pandas as pd
import plotly.express as px


def generate_report(root):
    root, processed = Path(root), Path(root) / "data" / "processed"
    names = {"coverage": "dataset_coverage.csv", "events": "event_study_aggregate.csv",
             "walk": "walk_forward_results.csv", "ic": "information_coefficients.csv",
             "metrics": "strategy_metrics.csv", "significance": "sentiment_significance.csv",
             "monte": "monte_carlo_results.csv", "windows": "event_study_windows.csv",
             "news_events": "news_events.csv"}
    data = {name: pd.read_csv(processed / file) for name, file in names.items()}
    coverage = data["coverage"].query("RelevantArticles > 0")
    market_rows = pd.read_csv(root / "data" / "raw" / "market_data.csv", usecols=["Ticker"]).shape[0]
    articles = int(coverage["RelevantArticles"].sum())
    events = int(data["events"].groupby("EventType")["Events"].max().sum())

    coverage_chart = px.bar(coverage, x="Ticker", y=["RelevantArticles", "StrongEvents"],
                            barmode="group", title="News coverage and strong events")
    event_chart = px.line(data["events"], x="Offset", y=data["events"]["MeanCAR"] * 100,
                          color="EventType", markers=True,
                          labels={"y": "Mean QQQ-adjusted CAR (%)"}, title="Event study")
    walk = data["walk"].copy(); walk["ReturnPercent"] = walk["StrategyReturn"] * 100
    walk_chart = px.bar(walk, x="TestYear", y="ReturnPercent", color="Strategy", barmode="group",
                        title="Out-of-sample net returns")
    ic = data["ic"].set_index("Feature")[["IC_1D", "IC_3D", "IC_5D", "IC_10D"]]
    ic_chart = px.imshow(ic, color_continuous_scale="RdBu", zmin=-.3, zmax=.3,
                         labels={"color": "Spearman IC"}, title="Feature information coefficients")
    charts = "".join(chart.to_html(full_html=False, include_plotlyjs="inline" if index == 0 else False)
                     for index, chart in enumerate([coverage_chart, event_chart, walk_chart, ic_chart]))
    table = lambda frame: frame.to_html(index=False, border=0, float_format=lambda value: f"{value:.4f}")
    company_sections = []
    for ticker in coverage["Ticker"]:
        row = coverage[coverage["Ticker"] == ticker].iloc[0]
        window = data["windows"][data["windows"]["Ticker"] == ticker]
        event_curve = (window.groupby(["EventType", "Offset"], as_index=False)["CAR"].mean()
                       if len(window) else pd.DataFrame(columns=["EventType", "Offset", "CAR"]))
        company_chart = px.line(event_curve, x="Offset", y=event_curve["CAR"] * 100,
                                color="EventType", markers=True,
                                labels={"y": "Mean CAR (%)"}, title=f"{ticker} event response")
        categories = (data["news_events"].query("Ticker == @ticker").groupby("EventCategory").size()
                      .rename("Events").sort_values(ascending=False).reset_index())
        company_sections.append(f"""<section class="company" id="company-{ticker}">
<h2>{ticker} research profile</h2><div class="cards"><div class="card"><b>{int(row.RelevantArticles):,}</b><br>articles</div>
<div class="card"><b>{int(row.NewsDays):,}</b><br>news days</div><div class="card"><b>{int(row.StrongEvents):,}</b><br>strong events</div>
<div class="card"><b>{row.CoverageScore:.1f}/100</b><br>{row.CoverageLabel}</div></div>
{company_chart.to_html(full_html=False, include_plotlyjs=False)}
<h3>Event categories</h3>{table(categories)}</section>""")
    p_value = data["significance"].iloc[0].PValue
    html = f"""<!doctype html><html><head><meta charset="utf-8"><title>MarketPulse Research Report</title>
<style>body{{font-family:Arial,sans-serif;max-width:1100px;margin:40px auto;color:#172033;line-height:1.5}}
h1,h2{{color:#0f3d75}}.cards{{display:flex;gap:16px;flex-wrap:wrap}}.card{{background:#eef5ff;padding:16px 22px;border-radius:8px}}
table{{border-collapse:collapse;width:100%;font-size:13px}}th,td{{border:1px solid #ddd;padding:7px;text-align:right}}th:first-child,td:first-child{{text-align:left}}</style></head><body>
<h1>MarketPulse</h1><p><strong>Technology Stocks and Financial-News Quantitative Research</strong></p>
<p>I investigated whether financial-news sentiment combined with momentum and volume contains useful information for short-horizon market movements.</p>
<div class="cards"><div class="card"><b>{market_rows:,}</b><br>market observations</div><div class="card"><b>{articles:,}</b><br>relevant articles</div>
<div class="card"><b>{events:,}</b><br>strong events</div><div class="card"><b>10</b><br>news companies</div></div>
{charts}
<h2>Company explorer</h2><label for="ticker"><strong>Select company: </strong></label>
<select id="ticker" onchange="showCompany(this.value)">{''.join(f'<option value="{ticker}">{ticker}</option>' for ticker in coverage['Ticker'])}</select>
{''.join(company_sections)}
<h2>Coverage quality</h2>{table(coverage[["Ticker","RelevantArticles","MatchedArticles","NewsDays","StrongEvents","CoverageScore","CoverageLabel"]])}
<h2>Walk-forward validation</h2><p>Signals are lagged one session. Net results include 10 bps transaction cost and 5 bps slippage.</p>
{table(data["walk"][["Strategy","TestYear","StrategyReturn","SharpeRatio","MaximumDrawdown","NumberOfTrades","NewsDays"]])}
<h2>Full-period benchmark</h2>{table(data["metrics"])}
<h2>Monte Carlo robustness</h2>{table(data["monte"])}
<h2>Conclusion</h2><p>{escape(f'The positive-versus-negative sentiment test has p={p_value:.3f}; the current evidence is not statistically significant. Momentum is more stable than sentiment, but varies by year and regime.')}</p>
<h2>Limitations</h2><ul><li>Historical news collection currently covers 2022 H1 and recent 2026 data; the resumable collector will fill 2022 H2–2026.</li>
<li>Stock-day observations are correlated and are not independent samples.</li><li>Backtests are research evidence, not live-trading forecasts.</li></ul>
<script>function showCompany(ticker){{document.querySelectorAll('.company').forEach(x=>x.style.display='none');document.getElementById('company-'+ticker).style.display='block'}}showCompany(document.getElementById('ticker').value);</script>
</body></html>"""
    output = root / "report" / "index.html"
    output.parent.mkdir(exist_ok=True)
    output.write_text(html, encoding="utf-8")
    return output


if __name__ == "__main__":
    print(f"Saved local report to {generate_report(Path(__file__).parents[1])}")
