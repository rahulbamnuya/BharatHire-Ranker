import argparse
import gzip
import json
import csv
import sys
from pathlib import Path

# Add the current directory to sys.path to enable imports of local backend packages
sys.path.insert(0, str(Path(__file__).resolve().parent))

# Import the newly developed, comprehensive logic modules
from backend.ranking.honeypot import is_honeypot
from backend.ranking.scorer import calculate_heuristic_score
from backend.explainability.reasoning import generate_factual_reasoning

JD_TEXT = """
We need deep technical depth in modern ML systems — embeddings, retrieval, ranking, LLMs, fine-tuning.
Production experience with embeddings-based retrieval systems deployed to real users.
Production experience with vector databases or hybrid search infrastructure.
Strong Python. Experience designing evaluation frameworks for ranking systems.
"""

def parse_args():
    parser = argparse.ArgumentParser(description="Run Comprehensive Candidate Ranking")
    parser.add_argument("--candidates", default="data/candidates.jsonl", help="Path to candidates.jsonl")
    parser.add_argument("--out", default="submission.csv", help="Path for submission CSV")
    parser.add_argument(
        "--use-embeddings",
        action="store_true",
        help="Optionally add local SentenceTransformer scoring if the model is already installed/cached.",
    )
    return parser.parse_args()


def open_candidate_file(path):
    if path.suffix == ".gz":
        return gzip.open(path, "rt", encoding="utf-8")
    return open(path, "r", encoding="utf-8")


def iter_candidates(path):
    with open_candidate_file(path) as f:
        first_char = f.read(1)
        f.seek(0)

        if first_char == "[":
            try:
                raw_cands = json.load(f)
            except Exception as e:
                raise ValueError(f"Failed to parse JSON array: {e}") from e
            for cand in raw_cands:
                yield cand
        else:
            for line in f:
                if not line.strip():
                    continue
                try:
                    yield json.loads(line)
                except json.JSONDecodeError:
                    continue


def candidate_text(cand):
    profile = cand.get("profile", {})
    history = cand.get("career_history", [])
    skills = cand.get("skills", [])
    parts = [
        profile.get("headline", ""),
        profile.get("summary", ""),
        profile.get("current_title", ""),
        profile.get("current_company", ""),
        profile.get("current_industry", ""),
    ]
    for job in history:
        parts.extend([
            job.get("title", ""),
            job.get("company", ""),
            job.get("industry", ""),
            job.get("description", ""),
        ])
    parts.extend(skill.get("name", "") for skill in skills)
    return " ".join(str(part) for part in parts if part)


def main():
    args = parse_args()
    cand_path = Path(args.candidates)
    
    if not cand_path.exists():
        print(f"Error: {cand_path} does not exist.")
        sys.exit(1)
        
    print("Loading candidates and applying comprehensive heuristic filtering...")
    candidates = []
    
    try:
        for cand in iter_candidates(cand_path):
            if is_honeypot(cand):
                continue
            h_score = calculate_heuristic_score(cand)
            if h_score > -500.0:
                candidates.append({"cand": cand, "h_score": h_score})
    except ValueError as e:
        print(e)
        sys.exit(1)
                    
    # Sort by heuristic score and take top 5000 to save embedding time
    candidates.sort(key=lambda x: x["h_score"], reverse=True)
    top_candidates = candidates[:5000]
    
    print(f"Filtered down to {len(top_candidates)} candidates.")
    
    final_results = []
    
    if args.use_embeddings:
        print("Loading SentenceTransformer model for semantic scoring...")
        try:
            from sentence_transformers import SentenceTransformer, util
        except ImportError:
            print("SentenceTransformers not installed, falling back to pure heuristic score...")
            SentenceTransformer = None
            util = None
        if SentenceTransformer is None:
            for item in top_candidates:
                final_results.append((item["cand"], item["h_score"]))
        else:
            try:
                model = SentenceTransformer('all-MiniLM-L6-v2', device='cpu', local_files_only=True)
            except TypeError:
                model = SentenceTransformer('all-MiniLM-L6-v2', device='cpu')
            jd_emb = model.encode(JD_TEXT, convert_to_tensor=True)
        
            texts = [candidate_text(item["cand"]) for item in top_candidates]
            
            print("Embedding candidate profiles...")
            cand_embs = model.encode(texts, convert_to_tensor=True, show_progress_bar=True)
            cosine_scores = util.cos_sim(jd_emb, cand_embs)[0]
        
            for i, item in enumerate(top_candidates):
                semantic_score = float(cosine_scores[i]) * 100.0  # Heavy weight on semantic fit
                total_score = item["h_score"] + semantic_score
                final_results.append((item["cand"], total_score))
    else:
        print("Using deterministic heuristic score. Add --use-embeddings only when the local model is cached.")
        for item in top_candidates:
            final_results.append((item["cand"], item["h_score"]))
            
    # Sort by rounded final score descending, break ties with candidate_id ascending
    final_results.sort(key=lambda x: (-round(x[1], 4), x[0]["candidate_id"]))
    top_100 = final_results[:100]
    
    out_path = Path(args.out)
    with open(out_path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(["candidate_id", "rank", "score", "reasoning"])
        for i, (cand, score) in enumerate(top_100):
            writer.writerow([cand["candidate_id"], i+1, round(score, 4), generate_factual_reasoning(cand, rank=i+1, score=score)])
            
    print(f"Done! Wrote {len(top_100)} ranked rows to {out_path}")

if __name__ == "__main__":
    main()
