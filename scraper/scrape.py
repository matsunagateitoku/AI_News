#!/usr/bin/env python3
"""
Scrapes RSS feeds from major national newspapers.
Computes word frequency and extracts named entities via spaCy.
Writes data/wordcloud.js and data/entities.js for the static site.
"""

import json
import os
import re
import sys
from collections import Counter
from datetime import datetime, timezone

import feedparser
import spacy

# ---------------------------------------------------------------------------
# RSS feeds — add or remove sources here
# ---------------------------------------------------------------------------
RSS_FEEDS = [
    ("NY Times",         "https://rss.nytimes.com/services/xml/rss/nyt/HomePage.xml"),
    ("Washington Post",  "https://feeds.washingtonpost.com/rss/national"),
    ("Wall St. Journal", "https://feeds.a.dj.com/rss/RSSWorldNews.xml"),
    ("The Guardian",     "https://www.theguardian.com/us/rss"),
    ("LA Times",         "https://www.latimes.com/rss2.0.xml"),
    ("NPR",              "https://feeds.npr.org/1001/rss.xml"),
    ("CNN",              "https://rss.cnn.com/rss/edition.rss"),
    ("Fox News",         "https://feeds.foxnews.com/foxnews/latest"),
    ("CBS News",         "https://www.cbsnews.com/latest/rss/main"),
    ("NBC News",         "https://feeds.nbcnews.com/nbcnews/public/news"),
    ("USA Today",        "http://rssfeeds.usatoday.com/usatoday-NewsTopStories"),
    ("Chicago Tribune",  "https://www.chicagotribune.com/arcio/rss/"),
    ("Politico",         "https://rss.politico.com/politics-news.xml"),
    ("The Hill",         "https://thehill.com/rss/syndicator/19110"),
    ("Reuters",          "https://feeds.reuters.com/reuters/topNews"),
]

# ---------------------------------------------------------------------------
# Common English words to exclude from the word cloud
# ---------------------------------------------------------------------------
STOPWORDS = {
    'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for',
    'of', 'with', 'by', 'from', 'is', 'it', 'its', 'as', 'be', 'are',
    'was', 'were', 'has', 'have', 'had', 'that', 'this', 'will', 'would',
    'could', 'should', 'may', 'can', 'do', 'did', 'not', 'no', 'up',
    'out', 'after', 'over', 'into', 'about', 'more', 'new', 'than',
    'says', 'said', 'say', 'get', 'their', 'he', 'she', 'his', 'her',
    'they', 'them', 'we', 'us', 'you', 'your', 'who', 'what', 'how',
    'when', 'where', 'why', 'all', 'also', 'i', 'me', 'my', 'two',
    'first', 'last', 'year', 'years', 'time', 'people', 's', 'been',
    'one', 'just', 'report', 'reports', 'reported', 'amid', 'still',
    'now', 'back', 'off', 'here', 'there', 'then', 'are', 'our',
    'make', 'made', 'take', 'taken', 'goes', 'going', 'come', 'coming',
    'know', 'known', 'see', 'seen', 'use', 'used', 'against', 'plan',
}


def scrape_feeds():
    """Fetch all RSS feeds and return a list of headline + summary strings."""
    texts = []
    for name, url in RSS_FEEDS:
        try:
            feed = feedparser.parse(url)
            count = 0
            for entry in feed.entries:
                title = entry.get('title', '').strip()
                summary = re.sub(r'<[^>]+>', ' ', entry.get('summary', ''))
                if title:
                    texts.append(f"{title}. {summary}")
                    count += 1
            print(f"  ✓ {name}: {count} entries")
        except Exception as exc:
            print(f"  ✗ {name}: {exc}", file=sys.stderr)
    return texts


def word_frequency(texts, top_n=150):
    """Return [[word, count], ...] sorted by frequency, stopwords excluded."""
    counter = Counter()
    for text in texts:
        for word in re.findall(r"[a-zA-Z']{3,}", text.lower()):
            word = word.strip("'")
            if word not in STOPWORDS and len(word) >= 3:
                counter[word] += 1
    return [[word, count] for word, count in counter.most_common(top_n)]


def named_entities(texts, top_n=15):
    """Return top named entities per category using spaCy NER."""
    print("  Loading spaCy model...")
    nlp = spacy.load("en_core_web_sm")

    # Combine texts; spaCy has a character limit so we cap it
    combined = " ".join(texts)[:500_000]
    doc = nlp(combined)

    buckets = {
        "PERSON": Counter(),
        "ORG":    Counter(),
        "GPE":    Counter(),   # countries, cities, states
        "EVENT":  Counter(),
    }
    for ent in doc.ents:
        label = ent.label_
        if label not in buckets:
            continue
        name = ent.text.strip()
        if len(name) < 2:
            continue
        # Normalise to title case to merge e.g. "TRUMP" and "Trump"
        buckets[label][name.title()] += 1

    return {
        label: [{"name": name, "count": ct}
                for name, ct in counter.most_common(top_n)]
        for label, counter in buckets.items()
    }


def write_js(path, var_name, data):
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    with open(path, 'w', encoding='utf-8') as fh:
        fh.write(
            f"(window.newsData=window.newsData||{{}}).{var_name}="
            f"{json.dumps(data, indent=2, ensure_ascii=False)};\n"
        )
    print(f"  Wrote {path}")


if __name__ == '__main__':
    # Change to repo root so relative paths work from any CWD
    os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

    print("Fetching RSS feeds...")
    texts = scrape_feeds()
    print(f"Total: {len(texts)} articles\n")

    print("Computing word frequency...")
    wc_data = word_frequency(texts)

    print("Extracting named entities...")
    ent_data = named_entities(texts)
    ent_data['updated'] = datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')

    print("\nWriting data files...")
    write_js('data/wordcloud.js', 'wordcloud', wc_data)
    write_js('data/entities.js',  'entities',  ent_data)
    print("\nDone.")
