"""Render the local AAPL evaluation PDF and latest forecast table."""

import argparse
import csv
from datetime import datetime
from html import escape
import json
from pathlib import Path

from reportlab import rl_config
from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import Image, PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from cwt_quant.submission import display_news_title

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("replay", type=Path, help="Directory of the frozen AAPL replay")
parser.add_argument("output", type=Path, help="Directory for the PDF and latest forecast table")
parser.add_argument("commit", help="Source revision used for the replay")
args = parser.parse_args()
root = args.replay
args.output.mkdir(parents=True, exist_ok=True)
rl_config.invariant = 1
meta = json.loads((root / "manifest.json").read_text())
news = meta["current_news"]
if (meta["ticker"] != "AAPL" or meta["evaluation_end"] != "2026-11-13"
        or meta["x_export_rows_for_ticker"] or meta["x_eligible_rows"]
        or not news.get("articles") or news["collected_at_utc"][:10] <= meta["evaluation_end"]):
    parser.error("Expected the frozen 13 November 2026 AAPL replay with subsequent Tavily context and zero X rows")
with (root / "model_comparison.csv").open() as stream:
    metrics = {(r["model"], int(r["horizon"])): r for r in csv.DictReader(stream)}
with (root / "open-nowcast.csv").open() as stream:
    latest_open = [r for r in csv.DictReader(stream) if r["target_session"] == meta["evaluation_end"]]
with (root / "post-close-forecasts.csv").open() as stream:
    latest_forward = list(csv.DictReader(stream))
fields = ["model", "horizon", "kind", "origin", "target_session", "forecast_close", "actual_close"]
with (args.output / "latest-n0-n5.csv").open("w", newline="") as stream:
    writer = csv.DictWriter(stream, fields, extrasaction="ignore")
    writer.writeheader()
    writer.writerows(latest_open + latest_forward)
blue = colors.HexColor("#163653")
light = colors.HexColor("#eef4f8")
gray = colors.HexColor("#506476")
style = getSampleStyleSheet()
style.add(ParagraphStyle(name="Body", fontName="Helvetica", fontSize=10, leading=14, textColor=blue, spaceAfter=7))
style.add(ParagraphStyle(name="TitleAAPL", fontName="Helvetica-Bold", fontSize=24, leading=29,
                         textColor=blue, spaceAfter=8, alignment=TA_LEFT))
style.add(ParagraphStyle(name="SectionAAPL", fontName="Helvetica-Bold", fontSize=13, leading=17,
                         textColor=blue, spaceBefore=12, spaceAfter=6))
style.add(ParagraphStyle(name="SmallAAPL", fontName="Helvetica", fontSize=8, leading=11, textColor=gray, spaceAfter=5))

story = []
def paragraph(text, name="Body"):
    story.append(Paragraph(text, style[name]))

def table(rows, widths):
    obj = Table(rows, colWidths=widths, hAlign="LEFT", repeatRows=1)
    obj.setStyle(TableStyle([
        ("BACKGROUND", (0,0),(-1,0),blue), ("TEXTCOLOR",(0,0),(-1,0),colors.white),
        ("FONTNAME",(0,0),(-1,0),"Helvetica-Bold"), ("FONTNAME",(0,1),(-1,-1),"Helvetica"),
        ("FONTSIZE",(0,0),(-1,-1),9), ("ROWBACKGROUNDS",(0,1),(-1,-1),[light,colors.white]),
        ("TEXTCOLOR",(0,1),(-1,-1),blue), ("TOPPADDING",(0,0),(-1,-1),6),
        ("BOTTOMPADDING",(0,0),(-1,-1),6), ("ALIGN",(1,0),(-1,-1),"RIGHT"),
    ]))
    story.append(obj)

paragraph("CROWDWISDOMTRADING ASSESSMENT  /  AAPL", "SmallAAPL")
paragraph("Forecast evaluation", "TitleAAPL")
paragraph(f"<b>Partial submission.</b> {meta['evaluation_start']} through {meta['evaluation_end']}. "
          f"{meta['evaluation_sessions']} evaluation sessions and {meta['warmup_sessions']} warm-up sessions.")
paragraph("Price replay uses Yahoo Finance OHLCV. <b>Zero verified historical X posts</b> and zero "
          "covered dates. X sentiment forecasts and retrospective X results are withheld.")
paragraph("Forecast error on matched origins", "SectionAAPL")
rows = [["Horizon","Origins","Baseline MAE","Ridge MAE","Baseline RMSE","Ridge RMSE"]]
n0 = meta["open_nowcast_metrics"]
fmt = lambda x: f"{float(x):.5f}"
rows.append(["n+0",str(n0["price_only"]["n"]),fmt(n0["no_change"]["mae"]),fmt(n0["price_only"]["mae"]),
             fmt(n0["no_change"]["rmse"]),fmt(n0["price_only"]["rmse"])])
for h in range(1,6):
    b, r = metrics["no_change",h], metrics["price_only",h]
    rows.append([f"n+{h}",r["n"],fmt(b["mae"]),fmt(r["mae"]),fmt(b["rmse"]),fmt(r["rmse"])])
table(rows, [55,48,90,84,96,90])
story.append(Spacer(1,8))
paragraph("Errors use log returns. n+0 targets the open-to-close return and uses the opening quote. "
          "Later forecasts target close-to-close returns. Expanding folds use prior mature labels.", "SmallAAPL")
paragraph("Chronological hypothetical trading diagnostic", "SectionAAPL")
risk = meta["risk"]["price_only"]
table([["Sessions","Long trades","Cash","Sharpe","Sortino","Max drawdown"],
       [str(risk["n_sessions"]),str(risk["n_trades"]),str(risk["n_cash_sessions"]),
        f"{risk['approx_sharpe']:.2f}",f"{risk['approx_sortino']:.2f}",f"{risk['max_drawdown']:.2%}"]],
      [70,81,70,70,72,100])
story.append(Spacer(1,8))
paragraph("The n+1 forecast targets close-to-close returns. The diagnostic uses positive forecasts "
          "to simulate next-session open-to-close trades, a different return interval. "
          "It charges 10 bps per round trip and assumes zero return on cash. The reported Sharpe describes "
          "one retrospective simulation with approximate fills. Live trading performance remains unvalidated.",
          "SmallAAPL")
paragraph("Source and reproduction", "SectionAAPL")
paragraph(f"Price snapshot SHA-256: {meta['prices']['sha256']}<br/>"
          f"Replay ID: {meta['run_id']}<br/>"
          f"Replay commit: {escape(args.commit)}<br/>"
          f"Runtime: Python {meta['runtime_versions']['python']}, NumPy {meta['runtime_versions']['numpy']}, "
          f"pandas {meta['runtime_versions']['pandas']}, Matplotlib {meta['runtime_versions']['matplotlib']}.",
          "SmallAAPL")
paragraph('<link href="https://github.com/1011K/Trading-X-Sentiment-Price-Prediction-Agent/pull/1" color="#1d5787">Public implementation and replay instructions</link>', "SmallAAPL")

story.append(PageBreak())
paragraph("FROZEN REPLAY  /  RESEARCH FIGURE", "SmallAAPL")
paragraph("Price, forecasts and X coverage", "TitleAAPL")
story.append(Image(str(root / "research-figure.png"), width=6.8*inch, height=6.8*inch*2/3))
paragraph("X panels show missing evidence explicitly. The n+0 opening forecasts and observed close are "
          "separate markers. Other horizons use the 13 November close as their origin.", "SmallAAPL")
paragraph("Current news context", "SectionAAPL")
collected = datetime.fromisoformat(news["collected_at_utc"])
paragraph(f"Tavily collected {len(news['articles'])} dated results at "
          f"{collected:%Y-%m-%d %H:%M:%S} UTC, after the forecast evaluation ended on "
          f"{meta['evaluation_end']}. Both forecast models excluded all Tavily news.")
for article in news["articles"]:
    url = escape(article["url"], quote=True)
    host = url.split("/")[2]
    date = escape((article.get("published_date") or "date unavailable"))
    paragraph(f'{date}  |  <link href="{url}" color="#1d5787">{escape(host)}</link>  |  '
              f'{escape(display_news_title(article))}', "SmallAAPL")
paragraph("Dates in the news capture reflect provider metadata and do not establish historical availability.", "SmallAAPL")
paragraph("Delivery status", "SectionAAPL")
paragraph("The assessment's historical dataset index does not establish eligible AAPL X coverage for "
          "May to November 2026. An authorized archive with documented forecast-time observation is still required.",
          "SmallAAPL")

def footer(canvas, doc):
    canvas.setStrokeColor(colors.HexColor("#d8e2e9"))
    canvas.line(54,42,558,42)
    canvas.setFillColor(gray)
    canvas.setFont("Helvetica",8)
    canvas.drawString(54,28,"CWT Quant  |  AAPL research submission")
    canvas.drawRightString(558,28,f"{doc.page}")
SimpleDocTemplate(str(args.output / "AAPL-evaluation.pdf"), pagesize=(612,792), leftMargin=54, rightMargin=54,
                  topMargin=49, bottomMargin=54, title="AAPL forecast evaluation").build(
                      story, onFirstPage=footer, onLaterPages=footer)
