"""
sentiment_engine.py
===================
Module 2 – Rule Checker and Scorer
------------------------------------
Implements:
  • Comprehensive rule-based sentiment scoring  (no ML/AI required)
  • Pattern matching via Python re module
  • Keyword tagging by domain
  • Negation handling  (e.g. "not good" → negative)
  • Intensifier / diminisher weighting (e.g. "very good" → +2)
  • Compound score → label mapping
"""

import re
import logging
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
# WORD DICTIONARIES
# ─────────────────────────────────────────────────────────────────────────────

# Each word maps to a base score (+1 = mildly positive, +2 = strongly positive)
POSITIVE_WORDS: dict[str, float] = {
    # General positive
    "good": 1, "great": 2, "excellent": 2, "outstanding": 3, "superb": 3,
    "wonderful": 2, "fantastic": 2, "amazing": 2, "awesome": 2, "brilliant": 2,
    "perfect": 3, "best": 2, "better": 1, "superior": 2, "exceptional": 3,
    "happy": 2, "joy": 2, "joyful": 2, "pleased": 1, "delighted": 2,
    "satisfied": 1, "impressed": 1, "love": 2, "like": 1, "enjoy": 1,
    "appreciate": 1, "grateful": 2, "thankful": 1, "blessed": 2,
    "positive": 1, "optimistic": 1, "hopeful": 1, "confident": 1,
    "successful": 2, "success": 2, "achieve": 1, "win": 2, "winner": 2,
    "innovative": 1, "creative": 1, "efficient": 1, "effective": 1,
    "reliable": 1, "trustworthy": 1, "honest": 1, "fair": 1,
    "helpful": 1, "supportive": 1, "friendly": 1, "kind": 1, "generous": 2,
    "strong": 1, "powerful": 1, "capable": 1, "skilled": 1, "expert": 1,
    "fast": 1, "quick": 1, "easy": 1, "simple": 1, "smooth": 1,
    "clean": 1, "clear": 1, "accurate": 1, "precise": 1,
    "profit": 1, "growth": 1, "improve": 1, "improvement": 1,
    "benefit": 1, "advantage": 1, "opportunity": 1, "progress": 1,
    "safe": 1, "secure": 1, "stable": 1, "healthy": 1,
}

NEGATIVE_WORDS: dict[str, float] = {
    # General negative
    "bad": 1, "terrible": 2, "horrible": 2, "awful": 2, "dreadful": 2,
    "poor": 1, "worst": 3, "worse": 1, "inferior": 2, "disappointing": 2,
    "sad": 1, "unhappy": 1, "miserable": 2, "depressed": 2, "upset": 1,
    "angry": 2, "frustrated": 1, "annoyed": 1, "furious": 3, "rage": 3,
    "hate": 2, "dislike": 1, "despise": 2, "loathe": 3,
    "failure": 2, "fail": 1, "failed": 1, "lose": 1, "lost": 1, "loser": 2,
    "wrong": 1, "incorrect": 1, "inaccurate": 1, "false": 1, "lie": 2,
    "problem": 1, "issue": 1, "error": 1, "bug": 1, "fault": 1, "mistake": 1,
    "slow": 1, "difficult": 1, "hard": 1, "complicated": 1, "confusing": 1,
    "broken": 2, "damage": 2, "damaged": 2, "destroy": 3, "destroyed": 3,
    "danger": 2, "dangerous": 2, "harmful": 2, "toxic": 2, "risk": 1,
    "expensive": 1, "costly": 1, "overpriced": 2,
    "waste": 1, "wasteful": 1, "inefficient": 1, "useless": 2,
    "corrupt": 2, "dishonest": 2, "fraud": 3, "scam": 3, "fake": 2,
    "violent": 2, "abuse": 3, "abusive": 3, "harassment": 3,
    "sick": 1, "ill": 1, "disease": 2, "pain": 1, "suffer": 2, "suffering": 2,
    "loss": 1, "deficit": 1, "decline": 1, "decrease": 1, "drop": 1,
    "concern": 1, "worried": 1, "anxiety": 1, "fear": 1, "scared": 1,
    "ugly": 2, "dirty": 1, "messy": 1, "chaotic": 2,
    "boring": 1, "tedious": 1, "monotonous": 1, "dull": 1,
    "weak": 1, "fragile": 1, "unstable": 1,
}

# Words that amplify the next sentiment word's score
INTENSIFIERS: dict[str, float] = {
    "very": 1.5, "extremely": 2.0, "incredibly": 2.0, "absolutely": 2.0,
    "totally": 1.5, "completely": 1.5, "utterly": 2.0, "highly": 1.5,
    "really": 1.3, "super": 1.5, "so": 1.2, "quite": 1.1,
    "deeply": 1.5, "strongly": 1.5, "remarkably": 1.5, "exceptionally": 2.0,
}

# Words that reduce the next sentiment word's score
DIMINISHERS: dict[str, float] = {
    "somewhat": 0.6, "slightly": 0.5, "a bit": 0.6, "a little": 0.5,
    "kind of": 0.5, "sort of": 0.5, "rather": 0.7, "fairly": 0.7,
    "barely": 0.3, "hardly": 0.3, "scarcely": 0.3,
}

# Negation words – flip the polarity of the following word
NEGATIONS = {
    "not", "no", "never", "neither", "nor", "none", "nobody",
    "nothing", "nowhere", "isn't", "aren't", "wasn't", "weren't",
    "don't", "doesn't", "didn't", "won't", "wouldn't", "can't",
    "cannot", "couldn't", "shouldn't", "without", "lack", "lacking",
}

# ── Domain-specific keyword tags ─────────────────────────────────────────────
DOMAIN_TAGS: dict[str, list[str]] = {
    "technology": [
        "software", "hardware", "algorithm", "database", "server", "cloud",
        "api", "machine learning", "ai", "data", "network", "security",
        "code", "programming", "developer", "app", "application",
    ],
    "finance": [
        "revenue", "profit", "loss", "market", "stock", "investment",
        "budget", "cost", "price", "financial", "economy", "bank",
        "fund", "asset", "debt", "growth", "gdp",
    ],
    "health": [
        "patient", "hospital", "doctor", "medicine", "treatment", "disease",
        "health", "clinical", "drug", "symptom", "diagnosis", "surgery",
        "vaccine", "therapy", "mental health", "wellness",
    ],
    "education": [
        "student", "teacher", "school", "university", "learning", "course",
        "research", "study", "academic", "curriculum", "degree",
    ],
    "social": [
        "community", "society", "people", "culture", "diversity",
        "inclusion", "human rights", "social", "welfare",
    ],
    "environment": [
        "climate", "pollution", "energy", "renewable", "carbon",
        "sustainability", "environment", "ecology", "nature",
    ],
}

# ── Regex patterns for structural / entity detection ─────────────────────────
PATTERNS: dict[str, str] = {
    "email":        r"\b[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}\b",
    "url":          r"https?://[^\s]+",
    "phone":        r"\b(?:\+?\d[\d\-\s().]{7,14}\d)\b",
    "date":         r"\b\d{1,2}[/-]\d{1,2}[/-]\d{2,4}\b",
    "currency":     r"\$[\d,]+(?:\.\d{2})?|\b\d+(?:\.\d{2})?\s*(?:USD|EUR|GBP|INR)\b",
    "percentage":   r"\b\d+(?:\.\d+)?%",
    "hashtag":      r"#\w+",
    "mention":      r"@\w+",
    "number":       r"\b\d+(?:,\d{3})*(?:\.\d+)?\b",
    "question":     r"\?",
    "exclamation":  r"!",
    "all_caps_word": r"\b[A-Z]{2,}\b",
}


# ─────────────────────────────────────────────────────────────────────────────
# RESULT DATACLASS
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class SentimentResult:
    raw_score:       float        = 0.0
    sentiment_score: float        = 0.0   # normalised to [-1, +1]
    sentiment_label: str          = "neutral"
    positive_words:  list[str]    = field(default_factory=list)
    negative_words:  list[str]    = field(default_factory=list)
    negated_words:   list[str]    = field(default_factory=list)
    tags:            list[str]    = field(default_factory=list)
    pattern_matches: list[str]    = field(default_factory=list)
    word_count:      int          = 0
    char_count:      int          = 0


# ─────────────────────────────────────────────────────────────────────────────
# CORE ANALYSER
# ─────────────────────────────────────────────────────────────────────────────

def analyse_chunk(text: str) -> SentimentResult:
    """
    Analyse a single text chunk and return a SentimentResult.

    Steps
    -----
    1. Tokenise
    2. Walk tokens applying negation / intensifier / diminisher windows
    3. Sum weighted scores
    4. Detect patterns
    5. Assign domain tags
    6. Normalise score
    7. Assign label
    """
    if not text or not text.strip():
        return SentimentResult()

    result = SentimentResult()
    result.char_count = len(text)

    tokens = _tokenise(text)
    result.word_count = len(tokens)

    raw_score      = 0.0
    pos_found      = []
    neg_found      = []
    negated_found  = []

    i = 0
    while i < len(tokens):
        token = tokens[i]

        # ── Check for multi-word diminisher ("a bit", "kind of") ─────────────
        modifier = 1.0
        two_word = f"{token} {tokens[i+1]}" if i + 1 < len(tokens) else ""

        if two_word.lower() in DIMINISHERS:
            modifier = DIMINISHERS[two_word.lower()]
            i += 2
            if i < len(tokens):
                token = tokens[i]
            else:
                break
        elif token.lower() in INTENSIFIERS:
            modifier = INTENSIFIERS[token.lower()]
            i += 1
            if i < len(tokens):
                token = tokens[i]
            else:
                break
        elif token.lower() in DIMINISHERS:
            modifier = DIMINISHERS[token.lower()]
            i += 1
            if i < len(tokens):
                token = tokens[i]
            else:
                break

        # ── Check negation window (up to 3 words back) ───────────────────────
        negated = _is_negated(tokens, i)

        # ── Score positive words ──────────────────────────────────────────────
        if token.lower() in POSITIVE_WORDS:
            score = POSITIVE_WORDS[token.lower()] * modifier
            if negated:
                raw_score -= score
                negated_found.append(token.lower())
                neg_found.append(token.lower())
            else:
                raw_score += score
                pos_found.append(token.lower())

        # ── Score negative words ──────────────────────────────────────────────
        elif token.lower() in NEGATIVE_WORDS:
            score = NEGATIVE_WORDS[token.lower()] * modifier
            if negated:
                raw_score += score    # double negative → positive
                negated_found.append(token.lower())
                pos_found.append(token.lower())
            else:
                raw_score -= score
                neg_found.append(token.lower())

        i += 1

    result.raw_score      = raw_score
    result.positive_words = list(set(pos_found))
    result.negative_words = list(set(neg_found))
    result.negated_words  = list(set(negated_found))

    # ── Normalise to [-1, +1] ─────────────────────────────────────────────────
    result.sentiment_score = _normalise(raw_score, result.word_count)

    # ── Assign label ──────────────────────────────────────────────────────────
    result.sentiment_label = _label(result.sentiment_score)

    # ── Pattern detection ─────────────────────────────────────────────────────
    result.pattern_matches = _detect_patterns(text)

    # ── Domain tagging ────────────────────────────────────────────────────────
    result.tags = _detect_tags(text.lower())

    return result


# ─────────────────────────────────────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────────────────────────────────────

def _tokenise(text: str) -> list[str]:
    """Lowercase-aware word tokeniser (keeps apostrophes for contractions)."""
    return re.findall(r"\b\w+(?:'\w+)?\b", text)


def _is_negated(tokens: list[str], pos: int, window: int = 3) -> bool:
    """Return True if any of the `window` tokens before `pos` is a negation."""
    start = max(0, pos - window)
    for j in range(start, pos):
        if tokens[j].lower() in NEGATIONS:
            return True
    return False


def _normalise(raw: float, word_count: int) -> float:
    """
    Normalise raw score to [-1, +1].
    Uses a sigmoid-style squashing to handle extreme values gracefully.
    """
    if word_count == 0:
        return 0.0
    # Scale by word count to make long texts comparable
    ratio = raw / (word_count ** 0.5 + 1)
    # Squash to [-1, +1]
    import math
    return max(-1.0, min(1.0, math.tanh(ratio)))


def _label(score: float) -> str:
    if score > 0.15:
        return "positive"
    if score < -0.15:
        return "negative"
    return "neutral"


def _detect_patterns(text: str) -> list[str]:
    """Return a list of pattern-type labels found in the text."""
    found = []
    for name, pattern in PATTERNS.items():
        if re.search(pattern, text, re.IGNORECASE):
            found.append(name)
    return found


def _detect_tags(lower_text: str) -> list[str]:
    """Return domain tags whose keywords appear in the text."""
    tags = []
    for domain, keywords in DOMAIN_TAGS.items():
        for kw in keywords:
            if kw in lower_text:
                tags.append(domain)
                break   # one hit per domain is enough
    return tags


# ─────────────────────────────────────────────────────────────────────────────
# BATCH SUMMARY
# ─────────────────────────────────────────────────────────────────────────────

def summarise_results(results: list[SentimentResult]) -> dict:
    """Aggregate multiple SentimentResult objects into a summary dict."""
    if not results:
        return {}

    scores = [r.sentiment_score for r in results]
    labels = [r.sentiment_label for r in results]

    pos_count = labels.count("positive")
    neg_count = labels.count("negative")
    neu_count = labels.count("neutral")
    total     = len(results)

    from collections import Counter
    all_pos   = [w for r in results for w in r.positive_words]
    all_neg   = [w for r in results for w in r.negative_words]
    all_tags  = [t for r in results for t in r.tags]

    return {
        "total_chunks":      total,
        "avg_score":         round(sum(scores) / total, 4),
        "max_score":         round(max(scores), 4),
        "min_score":         round(min(scores), 4),
        "positive_count":    pos_count,
        "negative_count":    neg_count,
        "neutral_count":     neu_count,
        "positive_pct":      round(pos_count / total * 100, 1),
        "negative_pct":      round(neg_count / total * 100, 1),
        "neutral_pct":       round(neu_count / total * 100, 1),
        "top_positive_words": Counter(all_pos).most_common(10),
        "top_negative_words": Counter(all_neg).most_common(10),
        "top_domains":        Counter(all_tags).most_common(5),
    }