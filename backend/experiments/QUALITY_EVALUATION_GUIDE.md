# Human Quality Evaluation Guide

## Purpose

Compare the observed presentation quality of selective and full regeneration for the ten localized modification cases. Both versions in a pair use the same original presentation, requirements, and modification request.

## What to review

Use the blinded evaluator packet at `results/quality_evaluator_packet.json`. For each evaluation ID, review the named original presentation, the modification request, and the modified deck labeled Version A or Version B. Enter one row per presentation and evaluator in `results/quality_ratings_template.csv`.

The packet and rating template do not identify the regeneration method. Keep `quality_evaluation_cases.json` and `quality_evaluation_mapping.json` with the experiment coordinator; those files contain the actual method mapping. Do not share the mapping with evaluators.

## Rating instructions

1. Read the original modification request.
2. Review the generated presentation (and original deck where helpful for consistency).
3. Score each of the six dimensions from 1 to 5.
4. Do not consider which regeneration method was used.
5. Evaluate the result itself and apply the same criteria to every deck.

| Score | Meaning |
| --- | --- |
| 1 | Poor |
| 2 | Below average |
| 3 | Acceptable |
| 4 | Good |
| 5 | Excellent |

Dimensions:

- **Relevance:** Does the modified slide/deck address the requested change?
- **Completeness:** Does it contain enough appropriate information to satisfy the request?
- **Consistency:** Does the modified result remain consistent with the rest of the presentation?
- **Readability:** Is the text clear, concise, and easy to read?
- **Layout suitability:** Is the selected layout appropriate for the content?
- **Requirement adherence:** Does the output follow the original presentation requirements and modification request?

The overall score is the arithmetic mean of these six ratings. Comments are optional.

## Update the summary

After entering human scores, run from the backend directory:

```text
python -m app.services.quality_evaluation
```

The service validates scores, evaluator IDs, duplicate entries, and blinded labels before updating `results/quality_summary.json`. Blank template rows remain unrated. No quality score is generated automatically.

The report shows observed mean differences, including the absolute difference. A difference within 0.5 points is described only as “within a 0.5-point observed difference”; it is not a statistical-equivalence or significance claim.
