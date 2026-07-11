"""Ask every question in examples/demo_corpus/questions.json end-to-end.

Prints status, confidence, evidence coverage, and citations for each answer so
the output can be diffed against examples/demo_corpus/expected_outputs.md.
"""

from __future__ import annotations

import json
from pathlib import Path

QUESTIONS_PATH = Path(__file__).resolve().parent.parent / "examples/demo_corpus/questions.json"


def main() -> None:
    from auralynq.agent.runner import answer_question

    questions = json.loads(QUESTIONS_PATH.read_text())
    for item in questions:
        result = answer_question(item["question"])
        print("=" * 70)
        print(f"[{item['id']}] ({item['category']}) {item['question']}")
        print(
            f"status={result.status} confidence={result.confidence:.2f} "
            f"evidence_coverage={result.evidence_coverage}"
        )
        if result.citations:
            for c in result.citations:
                print(f"  citation: {Path(c.get('source', '?')).name} {c.get('locator', '')}")
        else:
            print("  citation: (none)")


if __name__ == "__main__":
    main()
