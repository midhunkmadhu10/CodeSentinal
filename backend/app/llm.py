import json
import os
from typing import List, Optional

from openai import OpenAI

from .models import Finding


def build_analysis_prompt(diff: str, rules_chunks: List[str]) -> str:
    """Build the system + user prompt for the LLM."""
    rules_context = "\n\n---\n\n".join(
        [f"Rule Chunk {i+1}:\n{chunk}" for i, chunk in enumerate(rules_chunks)]
    )

    system_prompt = """You are a security code reviewer. Analyze the provided code diff against the given security rules.

Return your analysis as a JSON array of objects. Each object must have exactly these fields:
- "severity": "High", "Medium", or "Low"
- "file_line": the file path and line number where the issue is found (e.g. "src/auth.ts:42")
- "risk": a clear description of what the security risk is
- "rule_violation": which rule is violated and why
- "safer_code": a code snippet showing how to fix the issue
- "source_chunk": the exact text from the rule chunks that applies to this finding

If no issues are found, return an empty array [].

IMPORTANT: You MUST output ONLY valid JSON. No extra text, no markdown formatting, no explanation outside the JSON."""

    user_prompt = f"""## Code Diff to Review
```
{diff}
```

## Relevant Security Rules
{rules_context}

Analyze the diff against these rules and return findings as a JSON array."""

    return system_prompt, user_prompt


def call_llm(
    diff: str,
    rules_chunks: List[str],
    endpoint: Optional[str] = None,
    model: Optional[str] = None,
    api_key: Optional[str] = None,
) -> List[Finding]:
    """Call the OpenAI-compatible API and parse the response into Finding objects."""
    if endpoint is None:
        endpoint = os.getenv("LLM_ENDPOINT", "https://api.example.com/v1/chat/completions")
    if model is None:
        model = os.getenv("LLM_MODEL", "gpt-4o-mini")
    if api_key is None:
        api_key = os.getenv("LLM_API_KEY", "")

    if not api_key:
        raise ValueError("LLM_API_KEY is not configured")

    client = OpenAI(base_url=endpoint, api_key=api_key)

    system_prompt, user_prompt = build_analysis_prompt(diff, rules_chunks)

    response = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        temperature=0.1,
        max_tokens=4096,
    )

    content = response.choices[0].message.content.strip()

    # Try to parse the JSON response
    # Handle markdown code blocks if present
    if content.startswith("```"):
        # Extract JSON from the outermost markdown code block
        first_newline = content.find("\n")
        last_backticks = content.rfind("```")
        if last_backticks > first_newline:
            content = content[first_newline:last_backticks].strip()
        else:
            # Fallback: remove first line and last line if they have backticks
            lines = content.split("\n")
            if lines[0].startswith("```"):
                lines = lines[1:]
            if lines and lines[-1].startswith("```"):
                lines = lines[:-1]
            content = "\n".join(lines).strip()

    content = content.strip()

    try:
        data = json.loads(content)
    except json.JSONDecodeError as err:
        # Try to find JSON array in the text
        start = content.find("[")
        end = content.rfind("]") + 1
        if start >= 0 and end > start:
            try:
                data = json.loads(content[start:end])
            except json.JSONDecodeError as sub_err:
                print("=== JSON Parsing Failure ===")
                print(f"Error: {sub_err}")
                print("Raw Content:")
                print(content)
                print("============================")
                raise ValueError(f"Failed to parse LLM response as JSON: {content[:200]}...")
        else:
            print("=== JSON Parsing Failure (No array markers found) ===")
            print(f"Error: {err}")
            print("Raw Content:")
            print(content)
            print("=====================================================")
            raise ValueError(f"Failed to parse LLM response as JSON: {content[:200]}...")

    findings = []
    for item in data:
        findings.append(
            Finding(
                severity=item.get("severity", "Low"),
                file_line=item.get("file_line", "unknown"),
                risk=item.get("risk", "No description"),
                rule_violation=item.get("rule_violation", "No rule reference"),
                safer_code=item.get("safer_code", "No suggestion"),
                source_chunk=item.get("source_chunk", "No source"),
            )
        )

    return findings