import math
import re
from datetime import datetime, timezone

from backend.parsing.normalize import CORE_AI_SKILLS, normalize_skill

CONSULTING_COMPANIES = {
    "accenture", "capgemini", "cognizant", "genpact ai", "hcl", "infosys", "mindtree", 
    "mphasis", "tcs", "tech mahindra", "wipro", "ltimindtree", "lti", "birlasoft",
    "persistent systems", "hexaware", "ust", "virtusa", "zensar", "niit technologies",
    "coforge", "cgi", "deloitte", "pwc", "ey", "kpmg", "ibm consulting"
}

PRODUCT_COMPANIES = {
    "google", "meta", "microsoft", "netflix", "amazon", "apple", "salesforce", 
    "adobe", "linkedin", "uber", "cred", "phonepe", "flipkart", "swiggy", "zomato",
    "razorpay", "meesho", "inmobi", "freshworks", "sarvam ai", "krutrim",
    "observe.ai", "zoho", "postman", "browserstack", "atlan", "chargebee",
    "clevertap", "whatfix", "dream11", "makemytrip", "goibibo", "ola",
    "zerodha", "groww", "paytm", "navi", "slice", "acko", "policybazaar",
    "urban company", "bigbasket", "dunzo", "udaan", "sharechat", "dailyhunt",
    "thoughtspot", "sprinklr", "servicenow", "intuit", "atlassian", "oracle",
    "vmware", "snowflake", "databricks", "elastic", "confluent", "mongodb",
    "cisco", "nvidia", "airbnb", "booking", "expedia"
}

TECHNICAL_TITLE_TERMS = {
    "engineer", "developer", "scientist", "researcher", "architect", "ml",
    "ai", "machine learning", "data", "backend", "platform", "search",
    "ranking", "recommendation", "nlp", "applied scientist", "relevance",
    "personalization", "search quality", "staff software", "sde", "swe",
    "technical lead", "tech lead", "principal software", "mlops"
}

RESEARCH_ONLY_TERMS = {
    "research intern", "research assistant", "academic lab", "phd researcher",
    "postdoctoral", "post-doc", "university lab"
}

DISQUALIFIER_TERMS = {
    "marketing manager", "product marketing", "sales manager", "growth manager",
    "business development", "recruiter", "talent acquisition", "graphic designer",
    "content writer"
}

MUST_HAVE_TERMS = {
    "embedding": 14.0,
    "sentence-transformer": 14.0,
    "retrieval": 16.0,
    "semantic search": 16.0,
    "hybrid search": 16.0,
    "vector search": 16.0,
    "vector database": 16.0,
    "pinecone": 14.0,
    "weaviate": 14.0,
    "qdrant": 14.0,
    "milvus": 14.0,
    "opensearch": 12.0,
    "elasticsearch": 12.0,
    "faiss": 12.0,
    "bm25": 10.0,
    "ranking": 14.0,
    "relevance": 12.0,
    "search quality": 12.0,
    "candidate matching": 12.0,
    "matching system": 12.0,
    "learning-to-rank": 14.0,
    "learning to rank": 14.0,
    "lambdamart": 12.0,
    "xgboost ranker": 12.0,
    "rerank": 10.0,
    "re-rank": 10.0,
    "cross-encoder": 10.0,
    "recommendation system": 12.0,
    "recommender": 12.0,
    "personalization": 10.0,
    "llm": 10.0,
    "fine-tuning": 8.0,
    "lora": 8.0,
    "qlora": 8.0,
    "python": 10.0,
}

PRODUCTION_TERMS = {
    "production": 14.0,
    "deployed": 12.0,
    "real users": 12.0,
    "scale": 8.0,
    "latency": 6.0,
    "on-call": 6.0,
    "index refresh": 8.0,
    "drift": 8.0,
    "regression": 8.0,
    "pipeline": 5.0,
    "owned": 5.0,
    "shipped": 10.0,
    "launched": 8.0,
    "owned end-to-end": 8.0,
    "customer-facing": 8.0,
    "online serving": 8.0,
    "serving": 5.0,
    "sla": 5.0,
    "observability": 5.0,
    "monitoring": 5.0,
}

EVALUATION_TERMS = {
    "ndcg": 14.0,
    "mrr": 12.0,
    "map": 10.0,
    "a/b test": 12.0,
    "ab test": 12.0,
    "offline evaluation": 12.0,
    "benchmark": 8.0,
    "feedback loop": 8.0,
    "ranking quality": 10.0,
    "precision": 6.0,
    "recall": 6.0,
    "ctr": 8.0,
    "conversion": 6.0,
    "click-through": 8.0,
    "experiment": 6.0,
}


def _norm(value):
    return str(value or "").lower()


def _contains_company(company, company_set):
    comp = _norm(company)
    return any(name in comp for name in company_set)


def _candidate_text(cand):
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
    parts.extend(s.get("name", "") for s in skills)
    return " ".join(str(part) for part in parts if part).lower()


def _keyword_score(text, terms, cap):
    score = 0.0
    matched = 0
    for term, weight in terms.items():
        if term in text:
            score += weight
            matched += 1
    if matched >= 3:
        score += min(20.0, matched * 2.5)
    return min(cap, score)


def _parse_date(date_str):
    if not date_str:
        return None
    try:
        return datetime.strptime(date_str[:10], "%Y-%m-%d").replace(tzinfo=timezone.utc)
    except (TypeError, ValueError):
        return None


def _days_since(date_str, default=365):
    dt = _parse_date(date_str)
    if not dt:
        return default
    return max(0, (datetime.now(timezone.utc) - dt).days)


def _salary_midpoint(signals):
    salary = signals.get("expected_salary_range_inr_lpa", {}) or {}
    low = salary.get("min")
    high = salary.get("max")
    if isinstance(low, (int, float)) and isinstance(high, (int, float)) and high >= low:
        return (low + high) / 2.0
    return None


def calculate_heuristic_score(cand, weights=None):
    """
    Calculate a dense heuristic score using profile, career history, skills,
    and all 23 Redrob behavioral signals. Supports custom scoring weights.
    """
    if weights is None:
        weights = {}

    # Default weights
    w_yoe_sweet = weights.get("yoe_sweet_spot", 50.0)
    w_yoe_sec = weights.get("yoe_secondary_spot", 25.0)
    w_yoe_pen = weights.get("yoe_penalty", -20.0)
    w_skill = weights.get("skill_match", 15.0)
    w_cv_speech_pen = weights.get("cv_speech_penalty", -30.0)
    w_consulting_pen = weights.get("consulting_penalty", -80.0)
    w_product = weights.get("product_bonus", 40.0)
    w_comp_high = weights.get("completeness_high", 10.0)
    w_comp_low = weights.get("completeness_low", -15.0)
    w_open_work = weights.get("open_to_work", 15.0)
    w_resp_rate_fac = weights.get("response_rate_factor", 30.0)
    w_resp_rate_pen = weights.get("response_rate_penalty", -50.0)
    w_resp_time_fast = weights.get("response_time_fast", 10.0)
    w_resp_time_slow = weights.get("response_time_slow", -10.0)
    w_loc_relocate = weights.get("location_relocate", 20.0)
    w_github_high = weights.get("github_high", 20.0)
    w_github_med = weights.get("github_med", 10.0)
    w_notice_short = weights.get("notice_short", 25.0)
    w_notice_long = weights.get("notice_long", -25.0)
    
    profile = cand.get("profile", {})
    history = cand.get("career_history", [])
    skills_raw = cand.get("skills", [])
    signals = cand.get("redrob_signals", {})
    
    score = 0.0
    
    text = _candidate_text(cand)

    # 1. Experience Check (Target: 5-9 years, with room for strong adjacent profiles)
    yoe = profile.get("years_of_experience", 0)
    if yoe < 3.0:
        score -= 1000.0  # Massive penalty for too little experience
    elif 5.0 <= yoe <= 9.0:
        score += w_yoe_sweet  # Sweet spot
    elif 4.0 <= yoe < 5.0 or 9.0 < yoe <= 12.0:
        score += w_yoe_sec
    else:
        score += w_yoe_pen  # Too senior or too junior

    if 6.0 <= yoe <= 8.5:
        score += 12.0
        
    # 2. Skill Matching (Normalized)
    candidate_skills = {normalize_skill(s.get("name")) for s in skills_raw}
    matched_core = candidate_skills.intersection(CORE_AI_SKILLS)
    score += len(matched_core) * w_skill  # points per core skill matched

    skill_months = 0
    verified_skill_quality = 0.0
    for skill in skills_raw:
        normalized = normalize_skill(skill.get("name"))
        if normalized in CORE_AI_SKILLS:
            skill_months += max(0, int(skill.get("duration_months", 0) or 0))
            endorsements = max(0, int(skill.get("endorsements", 0) or 0))
            proficiency = _norm(skill.get("proficiency"))
            verified_skill_quality += min(10.0, endorsements / 4.0)
            if proficiency == "expert":
                verified_skill_quality += 6.0
            elif proficiency == "advanced":
                verified_skill_quality += 4.0
    score += min(35.0, skill_months / 10.0)
    score += min(35.0, verified_skill_quality)

    score += _keyword_score(text, MUST_HAVE_TERMS, cap=95.0)
    score += _keyword_score(text, PRODUCTION_TERMS, cap=55.0)
    score += _keyword_score(text, EVALUATION_TERMS, cap=45.0)
    
    # Check for CV/Speech without NLP (as specified in JD)
    cv_speech = {"computer vision", "image classification", "speech recognition", "tts"}
    if candidate_skills.intersection(cv_speech) and not matched_core:
        score += w_cv_speech_pen  # "People whose primary expertise is computer vision... without NLP"
        
    # 3. Trap Check: Non-engineering titles
    title = profile.get("current_title", "").lower()
    if not any(term in title for term in TECHNICAL_TITLE_TERMS):
        score -= 500.0  # e.g., "Marketing Manager" with AI keywords
    if any(term in text for term in DISQUALIFIER_TERMS):
        score -= 350.0
    if any(term in text for term in RESEARCH_ONLY_TERMS) and "production" not in text and "deployed" not in text:
        score -= 180.0
        
    # 4. Consulting vs Product Company
    employers = [j.get("company", "") for j in history]
    named_employers = [emp for emp in employers if emp]
    only_consulting = bool(named_employers) and all(_contains_company(comp, CONSULTING_COMPANIES) for comp in named_employers)
    has_product = any(_contains_company(comp, PRODUCT_COMPANIES) for comp in named_employers)
    product_industry_jobs = sum(
        1 for job in history
        if any(term in _norm(job.get("industry")) for term in {"software", "internet", "fintech", "marketplace", "saas", "ai"})
    )
    
    if only_consulting:
        score += w_consulting_pen  # JD: "People who have only worked at consulting firms... explicitly do NOT want"
    if has_product:
        score += w_product  # JD prefers product company experience
    score += min(25.0, product_industry_jobs * 8.0)
        
    # 5. Redrob Behavioral Signals (23 Signals)
    # completeness
    completeness = signals.get("profile_completeness_score", 0)
    if completeness > 80: score += w_comp_high
    elif completeness < 50: score += w_comp_low

    days_inactive = _days_since(signals.get("last_active_date"))
    if days_inactive <= 14:
        score += 18.0
    elif days_inactive <= 45:
        score += 8.0
    elif days_inactive > 120:
        score -= 30.0
    
    # open_to_work
    if signals.get("open_to_work_flag", False):
        score += w_open_work

    applications = signals.get("applications_submitted_30d", 0) or 0
    if 1 <= applications <= 10:
        score += min(12.0, applications * 1.5)
    elif applications > 25:
        score -= 8.0
        
    # recruiter_response_rate (0.0 to 1.0)
    resp_rate = signals.get("recruiter_response_rate", 0.0)
    score += resp_rate * w_resp_rate_fac  # Up to w_resp_rate_fac points for high response rate
    if resp_rate < 0.1:
        score += w_resp_rate_pen  # Penalize severely if ghosting recruiters
        
    # avg_response_time_hours
    resp_time = signals.get("avg_response_time_hours", 999)
    if resp_time < 24: score += w_resp_time_fast
    elif resp_time > 168: score += w_resp_time_slow  # Over a week
        
    # assessments
    assessments = signals.get("skill_assessment_scores", {})
    if assessments:
        avg_assessment = sum(assessments.values()) / len(assessments)
        score += min(18.0, avg_assessment / 5.0)
        
    # network / visibility
    views = signals.get("profile_views_received_30d", 0)
    saves = signals.get("saved_by_recruiters_30d", 0)
    search_appearances = signals.get("search_appearance_30d", 0)
    connections = signals.get("connection_count", 0)
    endorsements = signals.get("endorsements_received", 0)
    score += min(22.0, (views * 0.08) + (saves * 1.8) + (search_appearances * 0.03))
    score += min(12.0, math.log1p(max(0, connections)) * 2.0 + math.log1p(max(0, endorsements)))
    
    # notice_period_days
    notice = signals.get("notice_period_days", 90)
    if notice <= 30: score += w_notice_short
    elif notice > 60: score += w_notice_long
    
    # location / relocation
    target_locations = {"pune", "noida"}
    loc = profile.get("location", "").lower()
    in_target = any(t in loc for t in target_locations)
    will_relocate = signals.get("willing_to_relocate", False)
    if in_target or will_relocate:
        score += w_loc_relocate
    if signals.get("preferred_work_mode") in {"hybrid", "flexible"}:
        score += 6.0
        
    # github_activity_score (-1 to 100)
    github = signals.get("github_activity_score", -1)
    if github > 50: score += w_github_high
    elif github > 10: score += w_github_med
    elif github == -1 and "open-source" in text:
        score += 8.0
    
    # interview / offers
    interview_rate = signals.get("interview_completion_rate", 0.0)
    if interview_rate > 0.8: score += 15.0
    elif interview_rate < 0.3: score -= 20.0

    offer_rate = signals.get("offer_acceptance_rate", -1)
    if offer_rate >= 0.7:
        score += 10.0
    elif offer_rate == 0:
        score -= 5.0
    
    # verification
    if signals.get("verified_email", False) and signals.get("verified_phone", False):
        score += 5.0
    if signals.get("linkedin_connected", False):
        score += 4.0

    salary_mid = _salary_midpoint(signals)
    if salary_mid is not None:
        if 25 <= salary_mid <= 65:
            score += 8.0
        elif salary_mid > 100:
            score -= 8.0

    if re.search(r"\b(langchain|llamaindex)\b", text) and not any(
        term in text for term in ("production", "deployed", "retrieval", "ranking", "vector")
    ):
        score -= 45.0
        
    return score
