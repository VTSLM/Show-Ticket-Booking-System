"""AI review summarization and cache helpers for TicketFlow."""

import json
import os
from typing import Any, Dict, List

from openai import AsyncOpenAI

MODEL_NAME = os.getenv("OPENAI_REVIEW_MODEL", "gpt-6-luna")
CACHE_DAYS = int(os.getenv("AI_REVIEW_CACHE_DAYS", "7"))
REVIEWS_PER_CHUNK = int(os.getenv("AI_REVIEW_CHUNK_SIZE", "40"))
MAX_REVIEW_CHARS = int(os.getenv("AI_REVIEW_MAX_REVIEW_CHARS", "1500"))

_client = None


def _client_or_raise() -> AsyncOpenAI:
    global _client
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY is not configured")
    if _client is None:
        _client = AsyncOpenAI(api_key=api_key)
    return _client


async def _call_json(instructions: str, payload: str) -> Dict[str, Any]:
    client = _client_or_raise()
    response = await client.responses.create(
        model=MODEL_NAME,
        instructions=instructions,
        input=payload,
    )
    raw = response.output_text.strip()
    try:
        return json.loads(raw)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"AI returned invalid JSON: {raw[:500]}") from exc


async def summarize_chunk(reviews: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Summarize one review chunk. Ratings are supplied as data, not invented by AI."""
    serialized = []
    for r in reviews:
        serialized.append({
            "type": r["review_type"],
            "rating": float(r["rating"]),
            "headline": r["headline"],
            "content": r["content"][:MAX_REVIEW_CHARS],
        })

    instructions = """
You are a movie/show review analyst.
Analyze the supplied audience and critic reviews and return ONLY valid JSON.
Do not invent facts, reviews, ratings, people, or opinions.
Do not reveal plot twists, endings, or other specific spoilers. Discuss themes such as
acting, direction, writing, pacing, visuals, music, humour, emotional impact, etc.
Separate audience and critic observations when the evidence supports it.
Use concise, evidence-grounded language.
The output schema is:
{
  "audience_summary": "string",
  "critic_summary": "string",
  "overall_summary": "string",
  "audience_liked": ["string"],
  "audience_disliked": ["string"],
  "critic_liked": ["string"],
  "critic_disliked": ["string"]
}
"""
    return await _call_json(instructions, json.dumps(serialized, ensure_ascii=False))


async def synthesize_summaries(partials: List[Dict[str, Any]]) -> Dict[str, Any]:
    instructions = """
You are producing the final AI review overview for a movie/show booking website.
Combine the supplied evidence summaries into one concise, balanced result.
Return ONLY valid JSON using exactly this schema:
{
  "audience_summary": "string",
  "critic_summary": "string",
  "overall_summary": "string",
  "audience_liked": ["string"],
  "audience_disliked": ["string"],
  "critic_liked": ["string"],
  "critic_disliked": ["string"]
}
Do not invent information. Do not reveal plot twists, endings, or other specific spoilers.
If one group has no reviews, say so rather than fabricating an opinion.
Keep each summary to 2-4 sentences and each bullet list to at most 5 items.
"""
    return await _call_json(instructions, json.dumps(partials, ensure_ascii=False))


async def generate_summary(reviews: List[Dict[str, Any]]) -> Dict[str, Any]:
    if not reviews:
        return {
            "audience_summary": "No audience reviews are available yet.",
            "critic_summary": "No critic reviews are available yet.",
            "overall_summary": "There are not enough published reviews to generate an AI overview.",
            "audience_liked": [],
            "audience_disliked": [],
            "critic_liked": [],
            "critic_disliked": [],
        }

    chunks = [reviews[i:i + REVIEWS_PER_CHUNK] for i in range(0, len(reviews), REVIEWS_PER_CHUNK)]
    partials = []
    for chunk in chunks:
        partials.append(await summarize_chunk(chunk))

    return await synthesize_summaries(partials) if len(partials) > 1 else partials[0]
