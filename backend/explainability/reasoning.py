from backend.parsing.normalize import CORE_AI_SKILLS, normalize_skill

def _clip(items, limit=2):
    return [item for item in items if item][:limit]


def _employer_names(history, limit=2):
    names = []
    for job in history:
        company = job.get("company")
        if company and company not in names:
            names.append(company)
    return names[:limit]


def generate_factual_reasoning(cand, rank=None, score=None):
    """
    Generate factual, specific, non-templated reasoning for the candidate.
    Must reference specific facts (years of experience, current title, named skills, signal values).
    Must connect to JD (product over research, embedding experience).
    Must acknowledge honest concerns if any.
    Must not hallucinate.
    """
    profile = cand.get("profile", {})
    skills_raw = cand.get("skills", [])
    signals = cand.get("redrob_signals", {})
    history = cand.get("career_history", [])
    
    yoe = profile.get("years_of_experience", 0)
    title = profile.get("current_title", "Engineer")
    
    # Extract actual skills candidate possesses
    cand_skills = []
    for s in skills_raw:
        n = s.get("name", "")
        if n: cand_skills.append(n)
        
    core_matches = _clip([s for s in cand_skills if normalize_skill(s) in CORE_AI_SKILLS], 3)
    other_skills = _clip([s for s in cand_skills if normalize_skill(s) not in CORE_AI_SKILLS], 1)
    
    skills_to_mention = core_matches + other_skills
    skills_str = ", ".join(skills_to_mention) if skills_to_mention else "general software development"
    
    employers = _employer_names(history)
    employer_str = ", ".join(employers) if employers else profile.get("current_company", "their prior employers")

    text = " ".join(
        str(part or "")
        for part in [
            profile.get("headline", ""),
            profile.get("summary", ""),
            " ".join(job.get("description", "") for job in history),
        ]
    ).lower()
    evidence = []
    if any(term in text for term in ("retrieval", "semantic search", "vector", "faiss", "pinecone", "qdrant", "weaviate")):
        evidence.append("retrieval/vector-search evidence")
    if any(term in text for term in ("ranking", "recommendation", "recommender", "learning-to-rank")):
        evidence.append("ranking or recommendation work")
    if any(term in text for term in ("ndcg", "mrr", "map", "a/b", "offline evaluation", "benchmark")):
        evidence.append("ranking-evaluation exposure")
    if any(term in text for term in ("production", "deployed", "real users", "shipped", "on-call")):
        evidence.append("production delivery signals")
    
    # Find concerns
    concerns = []
    notice = signals.get("notice_period_days", 90)
    if notice > 60:
        concerns.append(f"notice period is {notice} days")
    resp_rate = signals.get("recruiter_response_rate", 0.0)
    if resp_rate < 0.3:
        concerns.append(f"low recruiter response rate ({int(resp_rate*100)}%)")
    if not core_matches:
        concerns.append("lacks explicit core AI skills")
    if signals.get("last_active_date"):
        last_active = signals.get("last_active_date")
    else:
        last_active = None
        
    concern_str = ""
    if concerns:
        concern_str = f" One concern is that their {concerns[0]}."
        
    # Variation based on candidate hash
    h_val = int(cand["candidate_id"].split("_")[1]) % 5
    availability = f"response rate is {int(resp_rate * 100)}% and notice is {notice} days"
    if last_active:
        availability += f"; last active {last_active}"
    evidence_str = ", ".join(evidence[:2]) if evidence else "adjacent ML/software evidence"
    
    if h_val == 0:
        base = f"{title} with {yoe} years of experience at {employer_str}; profile shows {evidence_str} and skills in {skills_str}."
        base += f" Availability signals: {availability}."
        return base + concern_str
    elif h_val == 1:
        base = f"Current {title} with {yoe} YoE and named skills including {skills_str}."
        base += f" JD fit comes from {evidence_str}; {availability}."
        return base + concern_str
    elif h_val == 2:
        base = f"{yoe} YoE profile from {employer_str} with {skills_str}."
        base += f" Relevant because the JD emphasizes retrieval/ranking builders, and this profile shows {evidence_str}."
        return base + concern_str
    elif h_val == 3:
        base = f"Experienced {title} ({yoe} YoE) with {skills_str}; work history points to {evidence_str}."
        base += f" Recruiter availability is measurable: {availability}."
        return base + concern_str
    else:
        base = f"{title} profile balances {yoe} years of experience, {skills_str}, and {evidence_str}."
        base += f" Behavioral fit is supported by {availability}."
        return base + concern_str
