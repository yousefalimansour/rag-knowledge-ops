"""Query-rewriter prompt.

Asks Gemini to expand a conversational question into 1–3 short search
queries. The output format is a single JSON array of strings — easy to
parse and self-correcting if the model adds prose around it.
"""

QUERY_REWRITE_SYSTEM = """You convert a user's natural-language question into 1–3 short, focused search queries
that maximize recall against a knowledge base. Each query should be a few keywords or
a short phrase; do not write a sentence.

Output ONLY a JSON array of 1 to 3 strings. No prose, no markdown, no commentary.

Example:
Question: What did we decide about pricing for enterprise customers last week?
Output: ["pricing decision enterprise customers", "enterprise pricing tiers", "pricing meeting last week"]
"""


def build_rewrite_prompt(question: str) -> str:
    return f"Question: {question.strip()}\nOutput:"
