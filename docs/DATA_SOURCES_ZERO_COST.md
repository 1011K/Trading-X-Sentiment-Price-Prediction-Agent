# Zero-cost data options

Target is AAPL from 18 May through 13 November 2026, 180 New York calendar days. No paid service was used. Open-source software and permission to collect, analyze, or redistribute data have separate terms.

| Option | What it can support | Target-window result |
| --- | --- | --- |
| [The Community Archive on GitHub](https://github.com/TheExGenesis/community-archive), [opt-in data description](https://arxiv.org/html/2610.30392v1) | The November 2026 public snapshot contains participant-contributed X archives. Public search is free. Suitable for an explicitly retrospective sample if relevant rows are found. | Targeted search did not yield a verified AAPL sample. Search results cannot establish absence across the full export. |
| [StockNet on GitHub](https://github.com/yumoxu/stocknet-dataset) and [ImperialNLP on GitHub](https://github.com/ImperialNLP/stockreturnpred) | Academic datasets and reproducible historical research examples. Check each project's data-specific terms. | Released well before 2026. |
| [Stock Market Tweets Data](https://huggingface.co/datasets/StephanAkkerman/stock-market-tweets-data) and [Tweets About Top Companies](https://www.kaggle.com/datasets/omermetinn/tweets-about-the-top-companies-from-2015-to-2020) | Older X data for isolated retrospective exercises when applicable rights are clear. | Outside the target window. |
| [Exorde GitHub samples](https://github.com/exorde-labs/datasets) | Historical aggregate indicators, including an older AAPL sample. | The sample predates the window and does not provide post-level timestamps. |
| [Twitter Financial News Sentiment](https://huggingface.co/datasets/zeroshot/twitter-financial-news-sentiment) | Open labelled text to validate the lexical classifier independently. | Used for the classification benchmark. It supplies neither 2026 AAPL posts nor forecast-time observations. |
| [SinclairSchneider 2026 sample](https://huggingface.co/datasets/SinclairSchneider/tweets_sample_2026) | Has some dates in the target period. The published card describes collection through Nitter, sampling and field issues. | Excluded. A suitable data license and usable historical coverage were not verified. |
| Employer-provided or participant-donated export | A documented, no-cost grant can support research. Independently documented observation timestamps are needed for strict walk-forward use. | No matching export provided. |
| [StockTwits](https://stocktwits.com/) and [Apple Newsroom](https://www.apple.com/newsroom/archive/?month=11&year=2026) | Possible alternative context under applicable terms. Apple issuer releases were used as manually verified news context. | Neither is an X archive or an X-sentiment substitute. |

## GitHub scraper and API clients

[Twikit](https://github.com/d60/twikit), [twscrape](https://github.com/vladkens/twscrape), [snscrape](https://github.com/JustAnotherArchivist/snscrape) and [TWINT](https://github.com/twintproject/twint) are scraper code repositories. Their software licenses do not grant access rights or prove a historical search works. The project uses authorized export imports and public archive interfaces. X's current terms restrict scraping without permission. [X terms](https://x.com/en/tos)

[Tweepy](https://github.com/tweepy/tweepy), [twarc](https://github.com/DocNow/twarc) and the [official Apify Python client](https://github.com/apify/apify-client-python) are clients. Free code leaves provider access, charges, and data rights separate. X documents a pay-per-use API. [X pricing](https://docs.x.com/x-api/getting-started/pricing)

The existing Tavily integration requires a local `TAVILY_API_KEY`. The Researcher plan offers a no-card free allowance. Leave pay-as-you-go disabled. Use an account you control and keep credentials out of source and submissions. [Tavily free allowance](https://help.tavily.com/articles/8298987937-billing-credits-usage-limits)

The [Community Archive query audit](community-archive-query-audit.json) records four successful date-bounded public semantic-search requests, timestamps, response digests and candidate counts. Counts were 10, 13, 5 and 22. None passed the AAPL relevance review. Eight higher-capacity probes timed out. This does not rule out relevant posts in the full archive. The public export was dated 14 November 2026, and the bulk endpoint could not be reached from this workspace. [Public release](https://github.com/TheExGenesis/community-archive/releases/tag/public-export-2026-11-14T07-06-32Z) · [Archive access documentation](https://www.community-archive.org/docs)

Consenting account holders can also download their own X archives without using an external scraper. These can supply an authorized, limited retrospective sample if contributors grant use. Post creation dates and metrics collected later do not establish forecast-time availability. [X archive instructions](https://help.x.com/en/managing-your-account/how-to-download-your-x-archive)
