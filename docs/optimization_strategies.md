# Optimization Strategy And Improvement Notes

This document explains the ranking choices, why they were made, and what can still be improved before a final hackathon submission.

## Current Strategy

The current ranker prioritizes:

- fast CPU execution
- no network during ranking
- no hidden model dependency
- low honeypot risk
- factual reasoning
- clear interview defensibility

The full 100k run completed locally in about 23 seconds, well below the 5-minute limit.

## Why Not Use Hosted LLMs

Hosted LLM calls are not allowed during the official ranking step. Even if they were allowed, calling an LLM for 100k profiles would be slow, expensive, and difficult to reproduce.

The project uses deterministic scoring instead.

## Why Not Depend On Embeddings By Default

Embeddings can help semantic matching, but they create reproduction risk:

- model weights may not exist in the judging sandbox
- first-run downloads require network access
- CPU inference over thousands of candidates can add latency
- embedding-only approaches can over-rank keyword-stuffed traps

The default submission avoids this. Optional local embedding scoring is available through:

```bash
python3 rank.py --candidates ./data/candidates.jsonl --out ./submission.csv --use-embeddings
```

Use that only if model artifacts are already available offline.

## Quality Optimizations Already Implemented

### 1. JD-Specific Evidence Scoring

The ranker rewards specific evidence from the JD:

- retrieval
- embeddings
- vector databases
- hybrid search
- BM25
- ranking systems
- recommendation systems
- learning to rank
- LLMs and fine-tuning
- Python
- production deployment
- evaluation frameworks

This improves over simple skill counting.

### 2. Career History Text

The scorer reads job descriptions, not only skills. This matters because the JD says strong candidates may describe the work as recommendation, ranking, search, or product infrastructure rather than using the latest AI buzzwords.

### 3. Behavioral Signal Weighting

Redrob behavioral signals affect the final score. Candidates are rewarded for:

- recent activity
- high response rate
- fast response time
- short notice
- open-to-work status
- relocation willingness
- recruiter saves
- profile views
- GitHub activity
- skill assessments
- interview completion
- offer acceptance

This aligns with actual hiring utility, not only technical fit.

### 4. Honeypot Avoidance

The honeypot detector checks impossible or suspicious data patterns before ranking. This lowers disqualification risk.

### 5. Factual Reasoning

Reasoning is generated from structured candidate facts. This avoids hallucination and helps Stage 4 manual review.

## Performance Optimizations Already Implemented

### Streaming Input

JSONL and JSONL.GZ files are read line by line. The ranker does not need to load the entire candidate pool as a single JSON object.

### Standard-Library Default Path

The official CLI path avoids heavy ML dependencies. This keeps setup and Docker builds faster.

### Top-K Funnel

The ranker scores all candidates heuristically, sorts by score, then keeps the strongest candidates for final output. Optional embedding mode only processes the top candidate pool.

### Simple Deterministic Sort

Tie-breaking is deterministic and validator-friendly:

1. score descending
2. candidate ID ascending

## What Could Still Improve Hidden Score

These are optional improvements if there is time and the team can test carefully.

### 1. Build A Small Local Validation Set

Manually label 100-300 sample candidates into tiers:

- strong fit
- possible fit
- weak fit
- reject
- honeypot/trap

Then tune weights against NDCG@10 and NDCG@50 locally.

### 2. Add More Company Intelligence

The product-company and consulting-company lists are useful but incomplete. Add more Indian product companies, AI startups, SaaS companies, HR-tech companies, and marketplace companies from the dataset.

### 3. Tune Weights From Real Samples

Current weights are hand-designed from the JD. They can improve if tuned against manually labeled profiles.

High-impact weights:

- retrieval/vector evidence
- ranking/recommendation evidence
- production evidence
- evaluation evidence
- response rate
- notice period
- last active date
- consulting-only penalty
- research-only penalty

### 4. Add Better Title Taxonomy

Some good candidates may have titles like:

- Applied Scientist
- Search Engineer
- Relevance Engineer
- ML Platform Engineer
- Data Scientist

The current code handles many of these, but title matching can be expanded.

### 5. Add Negative Pattern Checks

Add stronger penalties for:

- only tutorial/demo project language
- no production verbs
- no career-history AI evidence
- management-only roles
- job hopping every 12-18 months
- closed-source-only profiles with no validation

### 6. Optional Offline Embedding Artifact

If using embeddings, commit or document the offline artifact clearly. The official ranking step must not require network.

Potential local models:

- `all-MiniLM-L6-v2`
- `bge-small-en-v1.5`
- `e5-small-v2`

Do not add this to the default path unless it is fully reproducible.

## Pre-Submission Checklist

Before uploading:

- Run `python3 rank.py --candidates ./data/candidates.jsonl --out ./submission.csv`.
- Run `python3 validate_submission.py submission.csv`.
- Confirm exactly 100 data rows.
- Confirm no duplicate candidate IDs.
- Confirm scores are non-increasing by rank.
- Check 10 random reasoning rows for hallucinations.
- Check top 10 manually against the JD.
- Replace placeholder values in `submission_metadata.yaml`.
- Confirm GitHub repo URL is real and accessible.
- Confirm sandbox/demo link works.
- Rename CSV to the registered participant/team ID if required by portal.

## Risk Notes

The project is compliant and defensible, but hidden leaderboard performance is not guaranteed. The biggest remaining risk is weight calibration against the hidden relevance labels. The best practical improvement is manual labeling and tuning, not adding more technology.
