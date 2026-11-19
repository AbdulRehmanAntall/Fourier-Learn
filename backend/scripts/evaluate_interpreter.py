"""Run the Prompt Interpreter over a query set and report how often it is right (§5.9.1).

Needs a language model configured in backend/.env (LLM_PROVIDER, LLM_MODEL, LLM_API_KEY):

    python scripts/evaluate_interpreter.py [--queries evaluation/dev_queries.json]

A query counts as right when the interpreter names the expected concept, or, for an expected
null, answers out of scope. Every request and reply also goes to the LLM log (LLM_LOG_PATH).
Exits with 1 if any query fails.
"""

import argparse
import json
import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))

from app.content import content  # noqa: E402
from app.llm import LLMError, LLMNotConfiguredError, get_client  # noqa: E402
from app.prompt_interpreter.interpreter import InterpretationError, interpret  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--queries", type=Path, default=BACKEND / "evaluation" / "dev_queries.json")
    args = parser.parse_args()

    queries = json.loads(args.queries.read_text(encoding="utf-8"))["queries"]
    try:
        client = get_client()
    except LLMNotConfiguredError as error:
        print(error)
        return 2
    taxonomy = content()
    names = {c.id: c.name for c in taxonomy.taxonomy.concepts}

    right = invalid = 0
    for case in queries:
        expected = case["expected"]
        try:
            result = interpret(case["query"], taxonomy, client)
        except (InterpretationError, LLMError) as error:
            invalid += 1
            print(f"ERROR  {case['query']!r}: {error}")
            continue
        got = result.target_concept_id if result.in_scope else None
        ok = got == expected
        right += ok
        label = names.get(got, "out of scope") if got else "out of scope"
        want = names.get(expected, "out of scope") if expected else "out of scope"
        print(f"{'ok' if ok else 'WRONG':6} {case['query']!r}: {label} (expected {want})")

    total = len(queries)
    print(f"\n{right}/{total} right ({100 * right / total:.1f}%), {invalid} without a valid answer")
    return 0 if right == total else 1


if __name__ == "__main__":
    sys.exit(main())
