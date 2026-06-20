from datetime import datetime, timezone

FOUNDING_YEARS = {
    "sarvam ai": 2023, "krutrim": 2023, "cred": 2018, "phonepe": 2015,
    "observe.ai": 2017, "swiggy": 2014, "meesho": 2015, "zomato": 2008,
    "razorpay": 2014, "freshworks": 2010, "inmobi": 2007
}


def _parse_date(date_str):
    if not date_str:
        return None
    try:
        return datetime.strptime(date_str[:10], "%Y-%m-%d").replace(tzinfo=timezone.utc)
    except (TypeError, ValueError):
        return None


def _company_founding_year(company):
    name = str(company or "").lower()
    for known, year in FOUNDING_YEARS.items():
        if known in name:
            return year
    return None


def is_honeypot(cand):
    skills = cand.get("skills", [])
    history = cand.get("career_history", [])
    profile = cand.get("profile", {})
    
    # Check 1: Expert in 8+ skills with 0 months duration
    zero_dur_expert = sum(1 for s in skills if s.get("proficiency") in ["advanced", "expert"] and s.get("duration_months", 0) <= 0)
    if zero_dur_expert >= 8:
        return True

    # Check 1b: many "expert" claims with implausibly short aggregate usage
    expert_skills = [s for s in skills if s.get("proficiency") == "expert"]
    if len(expert_skills) >= 10:
        expert_months = sum(max(0, int(s.get("duration_months", 0) or 0)) for s in expert_skills)
        if expert_months < 60:
            return True
        
    # Check 2: Total experience exceeds stated years
    total_exp = profile.get("years_of_experience", 0)
    intervals = []
    summed_months = 0
    now = datetime.now(timezone.utc)
    for job in history:
        dur_months = job.get("duration_months", 0)
        summed_months += max(0, dur_months or 0)
        if dur_months / 12 > total_exp + 0.1:
            return True
            
        # Check 3: Started working before company existed
        comp = job.get("company")
        start_str = job.get("start_date")
        founding_year = _company_founding_year(comp)
        if founding_year and start_str:
            try:
                start_year = int(start_str.split("-")[0])
                if start_year < founding_year:
                    return True
            except Exception:
                pass

        # Check 4: End date before start date
        end_str = job.get("end_date")
        start = _parse_date(start_str)
        end = _parse_date(end_str) or now
        if start and end:
            if (end - start).days < 0:
                return True
            if start > now:
                return True
            intervals.append((start, end))

    # Check 5: summed job duration is far beyond stated experience.
    if total_exp and summed_months > (total_exp * 12) + 36:
        return True

    # Check 6: several substantial overlapping jobs are suspicious for full-time histories.
    intervals.sort(key=lambda item: item[0])
    overlap_months = 0
    for prev, current in zip(intervals, intervals[1:]):
        overlap_days = (prev[1] - current[0]).days
        if overlap_days > 45:
            overlap_months += overlap_days / 30.0
    if overlap_months > 12:
        return True
                
    return False
