"""Render the local AAPL evaluation PDF and latest forecast table."""

import argparse
import csv
from datetime import date, datetime
from html import escape
import json
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import Image, PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from cwt_quant.calendar import XNYSCalendar
from cwt_quant.submission import display_news_title


def render(root: Path, output: Path, commit: str) -> None:
    output.mkdir(parents=True, exist_ok=True)
    meta = json.loads((root / "manifest.json").read_text())
    news = meta["current_news"]
    with (root / "model_comparison.csv").open() as stream:
        metrics = {(r["model"], int(r["horizon"])): r for r in csv.DictReader(stream)}
    with (root / "open-nowcast.csv").open() as stream:
        latest_open = [r for r in csv.DictReader(stream) if r["target_session"] == meta["evaluation_end"]]
    with (root / "post-close-forecasts.csv").open() as stream:
        latest_forward = list(csv.DictReader(stream))
    fields = ["model", "horizon", "kind", "origin", "target_session", "forecast_close", "actual_close"]
    with (output / "latest-n0-n5.csv").open("w", newline="") as stream:
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
    if meta.get("build_mode") == "test-only":
        paragraph("<b>TEST ONLY.</b> Fixture results are software evidence.")
    status = meta["historical_x_status"]
    paragraph(f"Price input: {escape(meta['prices']['provider'])}. Historical X signal: <b>{status}</b>. "
              f"{meta['x_eligible_rows']} cutoff-eligible records. {escape(meta['historical_x_note'])}")
    if not meta["x_export_rows_for_ticker"]:
        paragraph("<b>Zero verified historical X posts.</b>")
    if status == "WITHHELD":
        paragraph("Request a rights-cleared AAPL export with cutoff-time text observations and separately "
                  "timestamped engagement and follower counts.", "SmallAAPL")
    paragraph(f"Observed close on {meta['evaluation_end']}: USD {meta['observed_close']:.2f}.", "SmallAAPL")
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
    paragraph("Errors use log returns. The n+0 baseline uses the opening price and the later baseline uses "
              "the origin close. Ridge uses the opening print and earlier prices for n+0, and close-time data "
              "for later horizons. Expanding folds use matured labels only.", "SmallAAPL")
    paragraph("Chronological hypothetical trading diagnostic", "SectionAAPL")
    def risk_value(value, spec):
        return format(value, spec) if isinstance(value, (float, int)) else "WITHHELD"

    risk = meta["risk"]["price_only"]
    table([["Sessions","Long trades","Cash","Sharpe","Sortino","Max drawdown"],
           [str(risk["n_sessions"]),str(risk["n_trades"]),str(risk["n_cash_sessions"]),
            risk_value(risk["approx_sharpe"], ".2f"), risk_value(risk["approx_sortino"], ".2f"),
            risk_value(risk["max_drawdown"], ".2%")]],
          [70,81,70,70,72,100])
    story.append(Spacer(1,8))
    paragraph("The n+1 forecast targets close-to-close returns. The diagnostic uses positive forecasts "
              "to simulate next-session open-to-close trades, a different return interval. "
              "It charges 10 bps per round trip and assumes zero return on cash. The reported Sharpe describes "
              "one retrospective simulation with approximate fills. Live trading performance remains unvalidated.",
              "SmallAAPL")
    paragraph("Source and reproduction", "SectionAAPL")
    mode = meta.get("build_mode", "replay")
    paragraph(f"Build mode: {mode}. Price snapshot retrieved {meta['prices']['retrieved_at_utc']}.<br/>"
              f"Price snapshot SHA-256: {meta['prices']['sha256']}<br/>"
              f"Replay ID: {meta['run_id']}<br/>"
              f"Replay commit: {escape(commit)}"
              f"{' (local modifications)' if meta.get('source_dirty') else ''}<br/>"
              f"Runtime: Python {meta['runtime_versions']['python']}, NumPy {meta['runtime_versions']['numpy']}, "
              f"pandas {meta['runtime_versions']['pandas']}, Matplotlib {meta['runtime_versions']['matplotlib']}.",
              "SmallAAPL")
    paragraph('<link href="https://github.com/1011K/Trading-X-Sentiment-Price-Prediction-Agent/pull/1" color="#1d5787">Public implementation and replay instructions</link>', "SmallAAPL")

    story.append(PageBreak())
    paragraph(f"{mode.upper()}  /  RESEARCH FIGURE", "SmallAAPL")
    paragraph("Price, forecasts and X coverage", "TitleAAPL")
    story.append(Image(str(root / "research-figure.png"), width=6.1*inch, height=6.1*inch*2/3))
    paragraph("Latest price forecasts (USD)", "SectionAAPL")
    by_horizon = {(int(r["horizon"]), r["model"]): r for r in latest_open + latest_forward}
    values = [["Horizon", "Target session", "Naive baseline", "Price Ridge"]]
    for horizon in range(6):
        baseline = by_horizon[horizon, "no_change"]
        ridge = by_horizon[horizon, "price_only"]
        values.append([f"n+{horizon}", ridge["target_session"],
                       f"{float(baseline['forecast_close']):.2f}", f"{float(ridge['forecast_close']):.2f}"])
    table(values, [65, 124, 136, 122])
    story.append(Spacer(1, 6))
    opened = datetime.fromisoformat(latest_open[0]["origin"])
    closed = datetime.fromisoformat(latest_forward[0]["origin"])
    paragraph(f"n+0 uses the {opened:%H:%M} New York open. n+1 to n+5 use the {closed:%H:%M} "
              f"New York close on {meta['evaluation_end']}. Values are projections as of those cutoffs.", "SmallAAPL")
    paragraph("Current news context", "SectionAAPL")
    if news.get("articles"):
        collected = datetime.fromisoformat(news["collected_at_utc"])
        session_close = XNYSCalendar().session_close_dt(date.fromisoformat(meta["evaluation_end"]))
        timing = " after the forecast evaluation ended" if collected > session_close else ""
        paragraph(f"{escape(news['source'])} context retrieved "
                  f"{collected:%Y-%m-%d %H:%M:%S} UTC{timing}. Excluded from all models.", "SmallAAPL")
        for article in news["articles"]:
            url = escape(article["url"], quote=True)
            host = url.split("/")[2]
            published = escape(article.get("published_date") or "date unavailable")
            paragraph(f'Published {published}  |  <link href="{url}" color="#1d5787">{escape(host)}</link>  |  '
                      f'{escape(display_news_title(article))}', "SmallAAPL")
        paragraph("Provider dates do not establish historical availability.", "SmallAAPL")
    else:
        paragraph(f"<b>News withheld.</b> {escape(news['note'])}")

    def footer(canvas, doc):
        canvas.setStrokeColor(colors.HexColor("#d8e2e9"))
        canvas.line(54,42,558,42)
        canvas.setFillColor(gray)
        canvas.setFont("Helvetica",8)
        canvas.drawString(54,28,"CWT Quant  |  AAPL research submission")
        canvas.drawRightString(558,28,f"{doc.page}")
    SimpleDocTemplate(str(output / "AAPL-evaluation.pdf"), invariant=True, pagesize=(612,792), leftMargin=54, rightMargin=54,
                      topMargin=49, bottomMargin=54, title="AAPL forecast evaluation").build(
                          story, onFirstPage=footer, onLaterPages=footer)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("replay", type=Path, help="Directory of the AAPL replay")
    parser.add_argument("output", type=Path, help="Directory for the PDF and latest forecast table")
    parser.add_argument("commit", help="Source revision used for the replay")
    args = parser.parse_args()
    render(args.replay, args.output, args.commit)
