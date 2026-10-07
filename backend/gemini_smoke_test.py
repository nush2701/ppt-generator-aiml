"""Run a single Gemini structured-output request for development verification."""

import json
import sys

from app.llm.gemini_provider import GeminiProvider, GeminiProviderError


def main() -> int:
    try:
        result = GeminiProvider().generate_smoke_test()
    except GeminiProviderError as exc:
        print(f"Gemini smoke test failed: {exc}", file=sys.stderr)
        return 1

    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
