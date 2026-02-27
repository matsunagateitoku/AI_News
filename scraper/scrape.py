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
    # Articles, conjunctions, prepositions
    'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for',
    'of', 'with', 'by', 'from', 'into', 'onto', 'upon', 'about', 'above',
    'below', 'between', 'among', 'through', 'during', 'before', 'after',
    'over', 'under', 'along', 'around', 'off', 'out', 'up', 'down',
    'without', 'within', 'against', 'across', 'behind', 'beyond', 'since',
    'until', 'while', 'than', 'per',

    # Pronouns
    'i', 'me', 'my', 'we', 'us', 'our', 'you', 'your',
    'he', 'him', 'his', 'she', 'her', 'they', 'them', 'their',
    'it', 'its', 'this', 'that', 'these', 'those', 'who', 'whom',
    'which', 'what', 'where', 'when', 'why', 'how',

    # Auxiliary / common verbs
    'is', 'are', 'was', 'were', 'be', 'been', 'being',
    'has', 'have', 'had', 'do', 'did', 'does',
    'will', 'would', 'could', 'should', 'may', 'might', 'can',
    'shall', 'must', 'need', 'dare',
    'say', 'said', 'says', 'saying',
    'get', 'got', 'gets', 'getting',
    'go', 'goes', 'going', 'went', 'gone',
    'come', 'comes', 'coming', 'came',
    'make', 'made', 'makes', 'making',
    'take', 'took', 'taken', 'takes', 'taking',
    'know', 'known', 'knows', 'knew', 'knowing',
    'see', 'seen', 'sees', 'saw', 'seeing',
    'use', 'used', 'uses', 'using',
    'give', 'gave', 'given', 'gives',
    'put', 'puts', 'putting',
    'let', 'lets', 'letting',
    'keep', 'kept', 'keeps',
    'continue', 'continued', 'continues',
    'call', 'called', 'calls', 'calling',
    'show', 'showed', 'shown', 'shows',
    'think', 'thought', 'thinks', 'thinking',
    'want', 'wants', 'wanted', 'wanting',
    'find', 'found', 'finds', 'finding',
    'tell', 'told', 'tells', 'telling',
    'move', 'moved', 'moves', 'moving',
    'end', 'ends', 'ended', 'ending',
    'help', 'helped', 'helps', 'helping',
    'ask', 'asked', 'asks', 'asking',
    'hit', 'hits', 'hitting',
    'look', 'looks', 'looked', 'looking',
    'turn', 'turns', 'turned', 'turning',

    # Common adjectives / adverbs — too generic for news signal
    'new', 'old', 'big', 'best', 'good', 'bad', 'great', 'large', 'small',
    'long', 'short', 'high', 'low', 'right', 'left', 'next', 'last', 'first',
    'more', 'most', 'much', 'many', 'some', 'any', 'other', 'another',
    'such', 'same', 'few', 'less', 'even', 'still', 'just', 'only',
    'also', 'too', 'very', 'well', 'ever', 'never', 'now', 'back',
    'here', 'there', 'then', 'not', 'no', 'nor', 'so', 'yet',
    'away', 'better', 'top', 'amid', 'once', 'own',

    # Common nouns — too generic or ubiquitous on news sites
    'time', 'times', 'year', 'years', 'day', 'days', 'week', 'weeks',
    'month', 'months', 'home', 'life', 'world', 'way', 'part', 'things',
    'thing', 'moment', 'age', 'story', 'stories', 'news', 'address',
    'work', 'stage', 'sign', 'reading', 'man', 'men', 'woman', 'women',
    'people', 'person', 'group',

    # Cardinal / ordinal numbers (words)
    'one', 'two', 'three', 'four', 'five', 'six', 'seven', 'eight',
    'nine', 'ten', 'second', 'third', 'half',

    # Days of the week
    'monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday', 'sunday',

    # Months
    'january', 'february', 'march', 'april', 'june', 'july', 'august',
    'september', 'october', 'november', 'december',

    # Journalistic boilerplate / UI artifacts
    'report', 'reports', 'reported', 'reporting',
    'newsletter', 'subscribe', 'read', 'click', 'share', 'follow',
    'according', 'including', 'amid', 'via',

    # HTML entity fragments that slip through (&amp; → amp, &nbsp; → nbsp, etc.)
    'nbsp', 'quot', 'apos', 'amp', 'lt', 'gt',

    # Source names that bleed into word counts
    'guardian',

    # Short tokens that pass the 3-char filter but are meaningless
    's', 'n', 't', 're', 've', 'll', 'd',
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


def named_entities(articles, top_n=10):
    """
    Extract named entities using spaCy, processing articles in batches.
    Returns dict of category → [{name, count, url, source}, ...].

    After counting, partial-name variants are merged into their longest
    canonical form before ranking.  E.g. 'Trump' and 'Donald Trump' both
    seen in the corpus → all counts roll up into 'Donald Trump'.

    Merge rule (per label bucket): for every pair (long, short) where
    short's tokens are a prefix OR suffix of long's tokens, redirect
    short → long and add its count.
    """
    print("  Loading spaCy model...")
    nlp = spacy.load("en_core_web_sm")

    LABELS = {"PERSON", "ORG", "GPE", "EVENT"}
    buckets     = {lbl: Counter() for lbl in LABELS}
    entity_meta = {}   # normalised name → {url, source} of first occurrence

    texts = [art['text'] for art in articles]

    for doc, art in zip(nlp.pipe(texts, batch_size=50, disable=["parser"]), articles):
        for ent in doc.ents:
            if ent.label_ not in LABELS:
                continue
            name = ent.text.strip().title()
            if len(name) < 2:
                continue
            buckets[ent.label_][name] += 1
            if name not in entity_meta:
                entity_meta[name] = {'url': art['url'], 'source': art['source']}

    # ── Disambiguation: merge partial-name variants into canonical form ──
    for label, counter in buckets.items():
        # Longest names first → they become the canonical target
        names = sorted(counter.keys(), key=len, reverse=True)
        redirects = {}
        for i, long_name in enumerate(names):
            long_parts = long_name.lower().split()
            for short_name in names[i + 1:]:
                if short_name in redirects:
                    continue
                short_parts = short_name.lower().split()
                if not short_parts:
                    continue
                m = len(short_parts)
                # Accept if short_name is a leading or trailing token-sequence
                # of long_name (e.g. "Trump" is suffix of "Donald Trump")
                if m < len(long_parts) and (
                    long_parts[:m] == short_parts or long_parts[-m:] == short_parts
                ):
                    redirects[short_name] = long_name
        for short_name, canonical in redirects.items():
            buckets[label][canonical] += buckets[label].pop(short_name, 0)

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
