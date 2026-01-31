"""
Search Utility Functions
Provides fuzzy matching, deduplication, and relevance scoring for log search results
"""

import re
from difflib import SequenceMatcher
from typing import List, Dict, Any, Set
from datetime import datetime
import hashlib


# Fuzzy Matching
def fuzzy_match(text: str, pattern: str, threshold: float = 0.75) -> bool:
    """
    Check if text matches pattern using fuzzy matching

    Args:
        text: Text to search in
        pattern: Pattern to search for
        threshold: Similarity threshold (0.0 to 1.0)

    Returns:
        True if similarity >= threshold
    """
    text_lower = text.lower()
    pattern_lower = pattern.lower()

    # Exact match (fast path)
    if pattern_lower in text_lower:
        return True

    # Fuzzy match using SequenceMatcher
    similarity = SequenceMatcher(None, text_lower, pattern_lower).ratio()

    if similarity >= threshold:
        return True

    # Check word-level similarity for phrases
    text_words = set(text_lower.split())
    pattern_words = set(pattern_lower.split())

    # If any pattern word fuzzy matches any text word
    for p_word in pattern_words:
        for t_word in text_words:
            word_similarity = SequenceMatcher(None, t_word, p_word).ratio()
            if word_similarity >= threshold:
                return True

    return False


def expand_pattern_with_variations(pattern: str) -> List[str]:
    """
    Expand a pattern with common variations

    Args:
        pattern: Original pattern

    Returns:
        List of pattern variations
    """
    variations = [pattern]
    pattern_lower = pattern.lower()

    # Common error term variations
    ERROR_VARIATIONS = {
        'timeout': ['timeout', 'timed out', 'time-out', 'time out', 'timeout exceeded'],
        'database': ['database', 'db', 'db connection', 'database connection'],
        'connection': ['connection', 'conn', 'connect', 'connecting'],
        'error': ['error', 'err', 'exception', 'failure', 'failed'],
        'authentication': ['authentication', 'auth', 'unauthorized', 'forbidden'],
        'null': ['null', 'undefined', 'nil', 'none'],
        'payment': ['payment', 'pay', 'transaction', 'txn'],
        'order': ['order', 'ord', 'purchase'],
    }

    # Check if pattern matches any key
    for key, vars in ERROR_VARIATIONS.items():
        if key in pattern_lower:
            variations.extend(vars)
            break

    return list(set(variations))  # Remove duplicates


# Deduplication (Exact duplicates only: same message + same timestamp)
def deduplicate_results(results: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Remove exact duplicate log entries (same message + same timestamp)

    Args:
        results: List of log result dictionaries

    Returns:
        Deduplicated list of results
    """
    seen_hashes: Set[str] = set()
    unique_results = []

    for result in results:
        # Create hash from message + timestamp
        message = result.get('@message', '')
        timestamp = result.get('@timestamp', '')

        # Generate unique hash
        unique_key = f"{message}|{timestamp}"
        hash_key = hashlib.md5(unique_key.encode()).hexdigest()

        if hash_key not in seen_hashes:
            seen_hashes.add(hash_key)
            unique_results.append(result)

    return unique_results


# Relevance Scoring
def calculate_relevance_score(
    result: Dict[str, Any],
    keywords: List[str],
    question: str = ""
) -> float:
    """
    Calculate relevance score for a log result

    Args:
        result: Log result dictionary
        keywords: List of search keywords
        question: Original user question

    Returns:
        Relevance score (0.0 to 100.0)
    """
    score = 0.0
    message = result.get('@message', '').lower()

    # 1. Keyword frequency scoring (up to 30 points)
    keyword_score = 0
    for keyword in keywords:
        keyword_lower = keyword.lower()

        # Exact keyword match: +5 points per occurrence
        exact_count = message.count(keyword_lower)
        keyword_score += exact_count * 5

        # Fuzzy match: +2 points if fuzzy matches
        if exact_count == 0 and fuzzy_match(message, keyword_lower, threshold=0.8):
            keyword_score += 2

    score += min(keyword_score, 30)  # Cap at 30

    # 2. Severity level scoring (up to 30 points)
    if 'ERROR' in message or 'FATAL' in message:
        score += 30
    elif 'WARN' in message or 'WARNING' in message:
        score += 15
    elif 'INFO' in message:
        score += 5

    # 3. Exception/Stack trace presence (up to 20 points)
    if 'exception' in message or 'stack trace' in message or 'at line' in message:
        score += 20
    elif 'error' in message:
        score += 10

    # 4. Recency scoring (up to 10 points)
    # More recent logs get higher scores
    timestamp_str = result.get('@timestamp', '')
    if timestamp_str:
        try:
            # Parse timestamp
            timestamp = datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
            now = datetime.utcnow()

            # Calculate age in hours
            age_hours = (now - timestamp).total_seconds() / 3600

            # Score: 10 points for logs < 1 hour, declining to 0 at 24 hours
            if age_hours < 1:
                score += 10
            elif age_hours < 6:
                score += 7
            elif age_hours < 24:
                score += 3
        except:
            pass  # Ignore timestamp parsing errors

    # 5. Question relevance (up to 10 points)
    if question:
        question_lower = question.lower()
        question_words = set(question_lower.split())
        message_words = set(message.split())

        # Count matching words
        matching_words = question_words.intersection(message_words)
        score += min(len(matching_words) * 2, 10)

    return min(score, 100.0)  # Cap at 100


def rank_results_by_relevance(
    results: List[Dict[str, Any]],
    keywords: List[str],
    question: str = ""
) -> List[Dict[str, Any]]:
    """
    Rank results by relevance score

    Args:
        results: List of log results
        keywords: Search keywords
        question: Original user question

    Returns:
        Sorted list of results (highest score first)
    """
    # Calculate score for each result
    scored_results = []
    for result in results:
        score = calculate_relevance_score(result, keywords, question)
        result_with_score = result.copy()
        result_with_score['_relevance_score'] = score
        scored_results.append(result_with_score)

    # Sort by score (descending)
    sorted_results = sorted(
        scored_results,
        key=lambda x: x.get('_relevance_score', 0),
        reverse=True
    )

    return sorted_results


def extract_keywords_from_question(question: str) -> List[str]:
    """
    Extract search keywords from user question

    Args:
        question: User question

    Returns:
        List of keywords
    """
    # Remove common stop words
    STOP_WORDS = {
        'what', 'when', 'where', 'why', 'how', 'is', 'are', 'was', 'were',
        'the', 'a', 'an', 'in', 'on', 'at', 'to', 'for', 'of', 'with',
        'show', 'me', 'find', 'get', 'tell', 'display', 'list', 'give'
    }

    # Extract words
    words = re.findall(r'\b\w+\b', question.lower())

    # Filter stop words and short words
    keywords = [w for w in words if w not in STOP_WORDS and len(w) > 2]

    return keywords


# Combined function for applying all improvements
def improve_search_results(
    results: List[Dict[str, Any]],
    question: str,
    keywords: List[str] = None
) -> List[Dict[str, Any]]:
    """
    Apply all search improvements: deduplication + relevance ranking

    Args:
        results: Raw search results
        question: User question
        keywords: Search keywords (auto-extracted if not provided)

    Returns:
        Improved and ranked results
    """
    if not results:
        return []

    # Extract keywords if not provided
    if keywords is None:
        keywords = extract_keywords_from_question(question)

    # Step 1: Remove exact duplicates
    unique_results = deduplicate_results(results)

    # Step 2: Calculate relevance and rank
    ranked_results = rank_results_by_relevance(unique_results, keywords, question)

    return ranked_results
