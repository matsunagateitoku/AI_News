#!/usr/bin/env python3
"""
Scrapes RSS feeds from major national newspapers.
Computes word frequency and extracts named entities via spaCy.
Each word and entity carries the URL of the article it first appeared in.
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
# Common words to exclude from the word cloud
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
    """Fetch all RSS feeds, return list of {text, url, source} dicts."""
    articles = []
    for name, feed_url in RSS_FEEDS:
        try:
            feed = feedparser.parse(feed_url)
            count = 0
            for entry in feed.entries:
                title   = entry.get('title', '').strip()
                summary = re.sub(r'<[^>]+>', ' ', entry.get('summary', ''))
                link    = entry.get('link', '')
                if title:
                    articles.append({'text': f"{title}. {summary}",
                                     'url': link, 'source': name})
                    count += 1
            print(f"  ✓ {name}: {count} entries")
        except Exception as exc:
            print(f"  ✗ {name}: {exc}", file=sys.stderr)
    return articles


def word_frequency(articles, top_n=150):
    """
    Return [[word, count, url], ...] sorted by frequency.
    url is the first article the word appeared in.
    """
    counter  = Counter()
    word_url = {}          # word → first article url
    for art in articles:
        for word in re.findall(r"[a-zA-Z']{3,}", art['text'].lower()):
            word = word.strip("'")
            if word not in STOPWORDS and len(word) >= 3:
                counter[word] += 1
                if word not in word_url:
                    word_url[word] = art['url']
    return [[w, c, word_url.get(w, '')] for w, c in counter.most_common(top_n)]


def named_entities(articles, top_n=15):
    """
    Extract named entities using spaCy, processing articles in batches.
    Returns dict of category → [{name, count, url, source}, ...].
    """
    print("  Loading spaCy model...")
    nlp = spacy.load("en_core_web_sm")

    LABELS = {"PERSON", "ORG", "GPE", "EVENT"}
    buckets    = {lbl: Counter() for lbl in LABELS}
    entity_meta = {}   # normalised name → {url, source} of first occurrence

    texts = [art['text'] for art in articles]
    metas = articles

    for doc, art in zip(nlp.pipe(texts, batch_size=50, disable=["parser"]), metas):
        for ent in doc.ents:
            if ent.label_ not in LABELS:
                continue
            name = ent.text.strip().title()
            if len(name) < 2:
                continue
            buckets[ent.label_][name] += 1
            if name not in entity_meta:
                entity_meta[name] = {'url': art['url'], 'source': art['source']}

    return {
        label: [
            {"name": name, "count": ct,
             "url":    entity_meta.get(name, {}).get('url', ''),
             "source": entity_meta.get(name, {}).get('source', '')}
            for name, ct in counter.most_common(top_n)
        ]
        for label, counter in buckets.items()
    }


def write_js(path, var_name, data):
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    with open(path, 'w', encoding='utf-8') as fh:
        fh.write(
            f"// Auto-generated by scraper/scrape.py — do not edit by hand.\n"
            f"(window.newsData=window.newsData||{{}}).{var_name}="
            f"{json.dumps(data, indent=2, ensure_ascii=False)};\n"
        )
    print(f"  Wrote {path}")


if __name__ == '__main__':
    os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

    print("Fetching RSS feeds...")
    articles = scrape_feeds()
    print(f"Total: {len(articles)} articles\n")

    print("Computing word frequency...")
    wc_data = word_frequency(articles)

    print("Extracting named entities...")
    ent_data = named_entities(articles)
    ent_data['updated'] = datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')

    print("\nWriting data files...")
    write_js('data/wordcloud.js', 'wordcloud', wc_data)
    write_js('data/entities.js',  'entities',  ent_data)
    print("\nDone.")
