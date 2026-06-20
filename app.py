import streamlit as st
import pandas as pd
import json
import gzip
import plotly.express as px
from datetime import datetime, timezone
from backend.ranking.honeypot import is_honeypot, _company_founding_year, _parse_date
from backend.ranking.scorer import calculate_heuristic_score
from backend.explainability.reasoning import generate_factual_reasoning
from backend.parsing.normalize import CORE_AI_SKILLS, normalize_skill

# Page setup
st.set_page_config(page_title="BharatHire Ranker UI", layout="wide", page_icon="🏆")

# Custom CSS for Premium Design Look
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@300;400;500;600;700&display=swap');
    
    html, body, [class*="css"] {
        font-family: 'Plus Jakarta Sans', sans-serif;
    }
    
    .main-title {
        font-weight: 800;
        font-size: 2.5rem;
        background: linear-gradient(135deg, #4f46e5 0%, #0ea5e9 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        margin-bottom: 0.2rem;
    }
    
    .sub-title {
        color: #64748b;
        font-size: 1rem;
        margin-bottom: 1.5rem;
    }
    
    /* Metrics Layout */
    .metric-container {
        display: flex;
        gap: 1rem;
        margin-bottom: 1.5rem;
    }
    
    .metric-card {
        flex: 1;
        background-color: #ffffff;
        border: 1px solid #e2e8f0;
        border-radius: 12px;
        padding: 1.2rem;
        box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.05);
        text-align: center;
        transition: transform 0.2s ease, box-shadow 0.2s ease;
    }
    .metric-card:hover {
        transform: translateY(-2px);
        box-shadow: 0 10px 15px -3px rgba(0, 0, 0, 0.08);
    }
    .metric-value {
        font-size: 1.8rem;
        font-weight: 700;
        color: #1e293b;
        margin-bottom: 0.1rem;
    }
    .metric-label {
        font-size: 0.8rem;
        color: #64748b;
        font-weight: 600;
        text-transform: uppercase;
        letter-spacing: 0.05em;
    }
    
    /* Candidate Deep Dive card */
    .resume-card {
        background-color: #ffffff;
        border: 1px solid #e2e8f0;
        border-radius: 16px;
        padding: 1.5rem;
        box-shadow: 0 4px 20px -2px rgba(0, 0, 0, 0.05);
        margin-top: 1rem;
    }
    
    .card-header {
        border-bottom: 1px solid #f1f5f9;
        padding-bottom: 1rem;
        margin-bottom: 1rem;
        display: flex;
        justify-content: space-between;
        align-items: flex-start;
    }
    
    .candidate-title {
        font-size: 1.6rem;
        font-weight: 700;
        color: #0f172a;
    }
    
    .candidate-subtitle {
        font-size: 1rem;
        color: #4f46e5;
        font-weight: 600;
        margin-top: 0.2rem;
    }
    
    .section-title {
        font-size: 0.95rem;
        font-weight: 700;
        color: #1e293b;
        text-transform: uppercase;
        letter-spacing: 0.05em;
        margin-bottom: 0.8rem;
        border-left: 4px solid #4f46e5;
        padding-left: 0.6rem;
    }
    
    .signal-item {
        display: flex;
        justify-content: space-between;
        padding: 0.4rem 0;
        border-bottom: 1px dashed #f1f5f9;
        font-size: 0.9rem;
    }
    .signal-label {
        color: #64748b;
        font-weight: 500;
    }
    .signal-value {
        color: #0f172a;
        font-weight: 600;
    }
    
    .badge {
        display: inline-block;
        padding: 4px 10px;
        border-radius: 9999px;
        font-size: 0.75rem;
        font-weight: 600;
        margin-right: 6px;
        margin-bottom: 6px;
    }
    .badge-core { background-color: #e0f2fe; color: #0369a1; border: 1px solid #bae6fd; }
    .badge-other { background-color: #f1f5f9; color: #475569; border: 1px solid #e2e8f0; }
    .badge-alert { background-color: #fef2f2; color: #991b1b; border: 1px solid #fecaca; }
    .badge-warning { background-color: #fffbeb; color: #92400e; border: 1px solid #fef3c7; }
    .badge-success { background-color: #f0fdf4; color: #166534; border: 1px solid #bbf7d0; }
    
    .job-item {
        position: relative;
        padding-left: 1.2rem;
        border-left: 2px solid #e2e8f0;
        padding-bottom: 1rem;
    }
    .job-item::before {
        content: '';
        position: absolute;
        left: -5px;
        top: 4px;
        width: 8px;
        height: 8px;
        border-radius: 50%;
        background-color: #4f46e5;
        border: 2px solid #ffffff;
    }
    .job-title {
        font-size: 0.95rem;
        font-weight: 600;
        color: #0f172a;
    }
    .job-meta {
        font-size: 0.8rem;
        color: #64748b;
        margin-bottom: 0.3rem;
    }
    .job-desc {
        font-size: 0.85rem;
        color: #334155;
        line-height: 1.4;
    }
</style>
""", unsafe_allow_html=True)

# Helper function to audit honeypot reason
def get_honeypot_reason(cand):
    skills = cand.get("skills", [])
    history = cand.get("career_history", [])
    profile = cand.get("profile", {})
    
    # 1. Expert in 8+ skills with 0 months duration
    zero_dur_expert = sum(1 for s in skills if s.get("proficiency") in ["advanced", "expert"] and s.get("duration_months", 0) <= 0)
    if zero_dur_expert >= 8:
        return f"Suspicious skills profile: {zero_dur_expert} expert/advanced skills claimed with 0 months duration."

    # 1b. many "expert" claims with implausibly short aggregate usage
    expert_skills = [s for s in skills if s.get("proficiency") == "expert"]
    if len(expert_skills) >= 10:
        expert_months = sum(max(0, int(s.get("duration_months", 0) or 0)) for s in expert_skills)
        if expert_months < 60:
            return f"Suspicious skills profile: {len(expert_skills)} expert skills claimed but with only {expert_months} months total usage."
        
    # 2. Total experience exceeds stated years
    total_exp = profile.get("years_of_experience", 0)
    intervals = []
    summed_months = 0
    now = datetime.now(timezone.utc)
    for job in history:
        dur_months = job.get("duration_months", 0)
        summed_months += max(0, dur_months or 0)
        if dur_months / 12 > total_exp + 0.1:
            return f"Experience anomaly: Individual job duration ({round(dur_months/12, 1)} years) exceeds total profile experience ({total_exp} years)."
            
        # 3. Started working before company existed
        comp = job.get("company")
        start_str = job.get("start_date")
        founding_year = _company_founding_year(comp)
        if founding_year and start_str:
            try:
                start_year = int(start_str.split("-")[0])
                if start_year < founding_year:
                    return f"Chronological inconsistency: Job at '{comp}' started in {start_year}, which is before the company was founded in {founding_year}."
            except Exception:
                pass

        # 4. End date before start date
        end_str = job.get("end_date")
        start = _parse_date(start_str)
        end = _parse_date(end_str) or now
        if start and end:
            if (end - start).days < 0:
                return f"Date anomaly: Job start date ({start_str}) is after end date ({end_str or 'present'})."
            if start > now:
                return f"Date anomaly: Job start date ({start_str}) is in the future."
            intervals.append((start, end))

    # 5. summed job duration is far beyond stated experience.
    if total_exp and summed_months > (total_exp * 12) + 36:
        return f"Experience anomaly: Cumulative job duration ({round(summed_months/12, 1)} years) is far beyond stated total experience ({total_exp} years)."

    # 6. several substantial overlapping jobs are suspicious for full-time histories.
    intervals.sort(key=lambda item: item[0])
    overlap_months = 0
    for prev, current in zip(intervals, intervals[1:]):
        overlap_days = (prev[1] - current[0]).days
        if overlap_days > 45:
            overlap_months += overlap_days / 30.0
    if overlap_months > 12:
        return f"Timeline anomaly: Cumulative job overlaps total {round(overlap_months, 1)} months, which is suspicious for full-time work histories."
                
    return "Flagged as inconsistent/potential honeypot profile."

# Render main header
st.markdown("<div class='main-title'>🏆 BharatHire AI Ranker</div>", unsafe_allow_html=True)
st.markdown("<div class='sub-title'>High-performance offline candidate discovery & ranking engine</div>", unsafe_allow_html=True)

# Context collapse banner for judges
with st.expander("🎯 Target Job Description & Challenge Scope", expanded=False):
    st.markdown("""
    This ranker evaluates candidates against the **Senior AI Engineer (Founding Role)** JD under strict compute constraints:
    * **Experience Sweet Spot**: Preferred 5-9 years of experience.
    * **Technical Domain**: Production embeddings, search ranking, vector databases, and metric-driven evaluation (NDCG, MRR, MAP, A/B Testing).
    * **Behavioral Modifiers**: Availability, response rate, Github score, and notice period are integrated directly.
    * **Exclusions**: Suspicious honeypot profiles, non-engineering keywords, or purely consulting-only experience.
    """)

# Sidebar Controls
st.sidebar.title("Configuration Panel")
st.sidebar.markdown("Upload candidate dataset below:")
uploaded_file = st.sidebar.file_uploader("Upload candidates (.json, .jsonl, .gz)", type=["jsonl", "gz", "json"])
st.sidebar.markdown("---")

st.sidebar.subheader("Scoring Presets")
preset = st.sidebar.selectbox(
    "Choose a Weight Preset",
    ["Standard Balanced", "Technical Heavyweight", "Fast Hire (Short Notice)", "High Active Engagement"]
)

# Preset configs mapping
if preset == "Standard Balanced":
    d_yoe, d_skill, d_github, d_notice, d_resp = 50, 15, 20, 25, 30
elif preset == "Technical Heavyweight":
    d_yoe, d_skill, d_github, d_notice, d_resp = 75, 35, 40, 10, 15
elif preset == "Fast Hire (Short Notice)":
    d_yoe, d_skill, d_github, d_notice, d_resp = 30, 10, 10, 50, 50
else:  # High Active Engagement
    d_yoe, d_skill, d_github, d_notice, d_resp = 40, 20, 45, 35, 40

st.sidebar.subheader("Adjustable Weights")
yoe_sweet_spot = st.sidebar.slider("YoE Sweet Spot Bonus", 0, 100, d_yoe)
skill_match = st.sidebar.slider("Core Skill Match Bonus", 0, 50, d_skill)
github_high = st.sidebar.slider("GitHub High Activity Bonus", 0, 50, d_github)
notice_short = st.sidebar.slider("Short Notice Period (<=30d) Bonus", 0, 50, d_notice)
response_rate_factor = st.sidebar.slider("Response Rate Weight", 0, 100, d_resp)

weights = {
    "yoe_sweet_spot": float(yoe_sweet_spot),
    "skill_match": float(skill_match),
    "github_high": float(github_high),
    "notice_short": float(notice_short),
    "response_rate_factor": float(response_rate_factor),
}

# Function to parse uploaded file
def parse_uploaded_candidates(uploaded):
    raw = uploaded.getvalue()
    if uploaded.name.endswith(".gz"):
        text = gzip.decompress(raw).decode("utf-8")
    else:
        text = raw.decode("utf-8")

    stripped = text.lstrip()
    if not stripped:
        return []
    if stripped[0] == "[":
        return json.loads(stripped)
    
    candidates = []
    for line in text.splitlines():
        if not line.strip():
            continue
        try:
            candidates.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return candidates

import os

# Helper to read from local file
def parse_local_candidates(file_path):
    try:
        if str(file_path).endswith(".gz"):
            with gzip.open(file_path, "rt", encoding="utf-8") as f:
                content = f.read()
        else:
            with open(file_path, "r", encoding="utf-8") as f:
                content = f.read()
        
        stripped = content.lstrip()
        if not stripped:
            return []
        if stripped[0] == "[":
            return json.loads(stripped)
        
        candidates = []
        for line in content.splitlines():
            if not line.strip():
                continue
            try:
                candidates.append(json.loads(line))
            except json.JSONDecodeError:
                continue
        return candidates
    except Exception as e:
        st.error(f"Error reading local file {file_path}: {e}")
        return []

# Check input source
parsed_list = []
source_name = ""

if uploaded_file is not None:
    st.info("Parsing uploaded candidates using official heuristic ranking modules...")
    try:
        parsed_list = parse_uploaded_candidates(uploaded_file)
        source_name = uploaded_file.name
    except Exception as exc:
        st.error(f"Failed to parse uploaded candidate file: {exc}")
elif os.path.exists("sample_candidates.json"):
    st.info("💡 Running dashboard on default 'sample_candidates.json' dataset. Upload your own candidate file in the sidebar to inspect another dataset.")
    parsed_list = parse_local_candidates("sample_candidates.json")
    source_name = "sample_candidates.json"

total = len(parsed_list)

if total == 0:
    if uploaded_file is not None or os.path.exists("sample_candidates.json"):
        st.warning("No valid candidates found in the dataset.")
    else:
        st.info("👈 Please upload your candidate dataset in the sidebar to get started.")
else:
        candidates = []
        honeypots = []
        
        progress_bar = st.progress(0, text="Evaluating profiles...")
        
        for i, cand in enumerate(parsed_list):
            if i % max(1, total // 50) == 0:
                progress_bar.progress(i / total, text=f"Scored {i}/{total} candidates...")
            
            # Check for honeypot
            if is_honeypot(cand):
                honeypots.append({
                    "candidate_id": cand.get("candidate_id"),
                    "title": cand.get("profile", {}).get("current_title", "N/A"),
                    "yoe": cand.get("profile", {}).get("years_of_experience", 0),
                    "reason": get_honeypot_reason(cand),
                    "raw": cand
                })
                continue
                
            h_score = calculate_heuristic_score(cand, weights=weights)
            candidates.append({"cand": cand, "score": h_score})
            
        progress_bar.empty()
        
        # Sort and filter top 100
        candidates.sort(key=lambda x: (-round(x["score"], 4), x["cand"]["candidate_id"]))
        top_candidates = candidates[:100]
        
        # Render Metrics Banner
        avg_yoe = sum([c["cand"].get("profile", {}).get("years_of_experience", 0) for c in top_candidates]) / max(1, len(top_candidates))
        avg_score = sum([c["score"] for c in top_candidates]) / max(1, len(top_candidates))
        
        st.markdown(f"""
        <div class="metric-container">
            <div class="metric-card">
                <div class="metric-value">{total}</div>
                <div class="metric-label">Processed Candidates</div>
            </div>
            <div class="metric-card" style="border-top: 3px solid #ef4444;">
                <div class="metric-value" style="color: #ef4444;">{len(honeypots)}</div>
                <div class="metric-label">Honeypots Removed</div>
            </div>
            <div class="metric-card">
                <div class="metric-value">{avg_yoe:.1f} yrs</div>
                <div class="metric-label">Avg YoE (Top 100)</div>
            </div>
            <div class="metric-card" style="border-top: 3px solid #10b981;">
                <div class="metric-value" style="color: #10b981;">{avg_score:.2f}</div>
                <div class="metric-label">Avg Rank Score (Top 100)</div>
            </div>
        </div>
        """, unsafe_allow_html=True)
        
        # Prepare Dataframe for Tab 1
        data = []
        all_skills = []
        for i, item in enumerate(top_candidates):
            c = item["cand"]
            prof = c.get("profile", {})
            reasoning = generate_factual_reasoning(c, rank=i + 1, score=item["score"])
            all_skills.extend([s.get("name", "") for s in c.get("skills", [])])
            
            data.append({
                "candidate_id": c.get("candidate_id"),
                "rank": i + 1,
                "score": round(item["score"], 4),
                "title": prof.get("current_title", "Unknown"),
                "yoe": prof.get("years_of_experience", 0),
                "reasoning": reasoning
            })
        df = pd.DataFrame(data)
        
        # Main Dashboard Tabs
        tab1, tab2, tab3, tab4 = st.tabs([
            "🏆 Top 100 Ranked Candidates", 
            "🔍 Candidate Deep Dive", 
            "🛡️ Honeypot Audit Log", 
            "📊 Scoring Analytics"
        ])
        
        # TAB 1: Top 100 Main List
        with tab1:
            st.markdown("### Ranked Candidate Pool")
            st.markdown("Below is the top 100 candidate recommendation list matching your criteria:")
            st.dataframe(df, use_container_width=True, hide_index=True)
            
            # Sidebar Download Button setup
            export_df = df[["candidate_id", "rank", "score", "reasoning"]]
            st.sidebar.markdown("---")
            st.sidebar.subheader("Export Results")
            st.sidebar.download_button(
                label="📥 Download submission.csv",
                data=export_df.to_csv(index=False).encode('utf-8'),
                file_name='submission.csv',
                mime='text/csv',
            )
            
        # TAB 2: Candidate Deep Dive Inspector
        with tab2:
            st.markdown("### Profile Verification & Resume Card")
            st.markdown("Select a candidate to inspect their match profile, career history, and behavioral availability:")
            
            # Setup choice list
            choices = [f"Rank {row['rank']} - {row['candidate_id']} ({row['title']})" for row in data]
            selected_choice = st.selectbox("Inspect Candidate Profile", choices)
            
            if selected_choice:
                selected_rank = int(selected_choice.split(" ")[1])
                candidate_data = top_candidates[selected_rank - 1]["cand"]
                candidate_score = top_candidates[selected_rank - 1]["score"]
                
                profile = candidate_data.get("profile", {})
                skills_list = candidate_data.get("skills", [])
                signals = candidate_data.get("redrob_signals", {})
                history = candidate_data.get("career_history", [])
                
                # Check skill normalization
                norm_skills = {normalize_skill(s.get("name")) for s in skills_list}
                matched_core = norm_skills.intersection(CORE_AI_SKILLS)
                other_skills = norm_skills.difference(CORE_AI_SKILLS)
                
                # Header info
                yoe_val = profile.get("years_of_experience", 0)
                location_val = f"{profile.get('location', '')}, {profile.get('country', '')}"
                headline_val = profile.get("headline", "")
                summary_val = profile.get("summary", "")
                
                # Factual reasoning
                reason_val = generate_factual_reasoning(candidate_data, rank=selected_rank, score=candidate_score)
                
                # Render profile HTML
                col_left, col_right = st.columns([2, 1])
                
                with col_left:
                    st.markdown(f"""
                    <div class="resume-card">
                        <div class="card-header">
                            <div>
                                <div class="candidate-title">{profile.get("anonymized_name", "Anonymized Candidate")}</div>
                                <div class="candidate-subtitle">{profile.get("current_title", "Engineer")} at {profile.get("current_company", "N/A")} ({profile.get("current_company_size", "1-10")} employees)</div>
                            </div>
                            <div style="text-align: right;">
                                <div style="font-size: 1.5rem; font-weight: 700; color: #10b981;">Score: {candidate_score:.2f}</div>
                                <div style="font-size: 0.8rem; color: #64748b; font-weight:600;">RANK #{selected_rank}</div>
                            </div>
                        </div>
                        
                        <div class="section-title">Headline & Summary</div>
                        <div style="font-size: 0.95rem; font-weight: 600; color: #334155; margin-bottom: 0.5rem;">"{headline_val}"</div>
                        <div style="font-size: 0.9rem; color: #475569; line-height: 1.5; margin-bottom: 1.5rem;">{summary_val}</div>
                        
                        <div class="section-title">JD Match Reasoning</div>
                        <div style="background-color: #f8fafc; border: 1px solid #e2e8f0; border-radius: 8px; padding: 1rem; font-size: 0.9rem; color: #1e293b; margin-bottom: 1.5rem; font-style: italic;">
                            "{reason_val}"
                        </div>
                    """, unsafe_allow_html=True)
                    
                    st.markdown("<div class='section-title'>Career History</div>", unsafe_allow_html=True)
                    for job in history:
                        st.markdown(f"""
                        <div class="job-item">
                            <div class="job-title">{job.get("title", "Engineer")} at {job.get("company", "Company")}</div>
                            <div class="job-meta">{job.get("start_date", "N/A")} to {job.get("end_date", "Present")} | {job.get("duration_months", 0)} months | {job.get("industry", "Technology")} ({job.get("company_size", "N/A")})</div>
                            <div class="job-desc">{job.get("description", "")}</div>
                        </div>
                        """, unsafe_allow_html=True)
                    
                    st.markdown("</div>", unsafe_allow_html=True)
                    
                with col_right:
                    # Skills scorecard
                    st.markdown("### Matched Skills")
                    
                    st.markdown("**Core JD Skills matched:**")
                    if matched_core:
                        for s in sorted(matched_core):
                            st.markdown(f"<span class='badge badge-core'>✓ {s}</span>", unsafe_allow_html=True)
                    else:
                        st.markdown("<span style='font-size: 0.85rem; color:#ef4444;'>No core JD skills found</span>", unsafe_allow_html=True)
                        
                    st.markdown("<div style='margin-top: 1rem;'>**Other Skills:**</div>", unsafe_allow_html=True)
                    if other_skills:
                        for s in sorted(other_skills)[:12]:
                            st.markdown(f"<span class='badge badge-other'>{s}</span>", unsafe_allow_html=True)
                    else:
                        st.markdown("<span style='font-size: 0.85rem; color:#64748b;'>None listed</span>", unsafe_allow_html=True)
                    
                    # Availability scorecard
                    st.markdown("---")
                    st.markdown("### Availability Scorecard")
                    
                    response_rate = signals.get("recruiter_response_rate", 0.0)
                    response_time = signals.get("avg_response_time_hours", 99)
                    notice_period = signals.get("notice_period_days", 90)
                    active_date = signals.get("last_active_date", "N/A")
                    github_score = signals.get("github_activity_score", -1)
                    work_mode = signals.get("preferred_work_mode", "N/A")
                    willing_relocate = "Yes" if signals.get("willing_to_relocate", False) else "No"
                    
                    st.markdown(f"""
                    <div class="signal-item">
                        <span class="signal-label">Profile Completeness</span>
                        <span class="signal-value">{signals.get("profile_completeness_score", 0)}%</span>
                    </div>
                    <div class="signal-item">
                        <span class="signal-label">Recruiter Response Rate</span>
                        <span class="signal-value">{int(response_rate*100)}%</span>
                    </div>
                    <div class="signal-item">
                        <span class="signal-label">Avg Response Time</span>
                        <span class="signal-value">{response_time:.1f} hrs</span>
                    </div>
                    <div class="signal-item">
                        <span class="signal-label">Notice Period</span>
                        <span class="signal-value">{notice_period} days</span>
                    </div>
                    <div class="signal-item">
                        <span class="signal-label">Last Active Date</span>
                        <span class="signal-value">{active_date}</span>
                    </div>
                    <div class="signal-item">
                        <span class="signal-label">GitHub Activity Score</span>
                        <span class="signal-value">{"N/A" if github_score == -1 else f"{github_score}/100"}</span>
                    </div>
                    <div class="signal-item">
                        <span class="signal-label">Preferred Work Mode</span>
                        <span class="signal-value" style="text-transform: capitalize;">{work_mode}</span>
                    </div>
                    <div class="signal-item">
                        <span class="signal-label">Willing to Relocate</span>
                        <span class="signal-value">{willing_relocate}</span>
                    </div>
                    """, unsafe_allow_html=True)
                    
                    # Highlight concerns
                    st.markdown("<div style='margin-top: 1rem;'>**Recruitment Status Alerts:**</div>", unsafe_allow_html=True)
                    has_concerns = False
                    
                    if notice_period > 60:
                        st.markdown(f"<span class='badge badge-alert'>⚠️ Long Notice Period ({notice_period} days)</span>", unsafe_allow_html=True)
                        has_concerns = True
                    else:
                        st.markdown(f"<span class='badge badge-success'>✓ Available Quickly ({notice_period} days)</span>", unsafe_allow_html=True)
                        
                    if response_rate < 0.3:
                        st.markdown(f"<span class='badge badge-alert'>⚠️ Low Recruiter Response ({int(response_rate*100)}%)</span>", unsafe_allow_html=True)
                        has_concerns = True
                    else:
                        st.markdown(f"<span class='badge badge-success'>✓ Responsive Candidate ({int(response_rate*100)}%)</span>", unsafe_allow_html=True)
                        
                    if not matched_core:
                        st.markdown("<span class='badge badge-warning'>⚠️ Lacks Core AI Skills</span>", unsafe_allow_html=True)
                        has_concerns = True
                    
        # TAB 3: Honeypot Audit Log
        with tab3:
            st.markdown("### Flagged Profiles Log")
            st.markdown("The system runs a multi-rule verification pass on profile timelines to filter out honeypots (impossible dates, skill duration exaggeration, impossible job overlaps) before scoring:")
            
            if honeypots:
                honeypot_df = pd.DataFrame([
                    {
                        "candidate_id": h["candidate_id"],
                        "current_title": h["title"],
                        "years_of_experience": h["yoe"],
                        "detected_anomaly": h["reason"]
                    } for h in honeypots
                ])
                st.dataframe(honeypot_df, use_container_width=True, hide_index=True)
            else:
                st.success("Clean dataset: 0 honeypot profiles detected.")
                
        # TAB 4: Visual Scoring Analytics
        with tab4:
            st.markdown("### Pool Analytics")
            
            col_chart1, col_chart2 = st.columns(2)
            
            with col_chart1:
                fig = px.histogram(
                    df, 
                    x="score", 
                    nbins=15, 
                    title="Score Distribution of Top 100", 
                    color_discrete_sequence=['#4f46e5']
                )
                fig.update_layout(
                    plot_bgcolor='rgba(0,0,0,0)', 
                    paper_bgcolor='rgba(0,0,0,0)',
                    xaxis_title="Final Score", 
                    yaxis_title="Count"
                )
                st.plotly_chart(fig, use_container_width=True)
                
            with col_chart2:
                skill_counts = pd.Series(all_skills).value_counts().head(10).reset_index()
                skill_counts.columns = ["Skill", "Count"]
                fig3 = px.bar(
                    skill_counts, 
                    x="Count", 
                    y="Skill", 
                    orientation='h', 
                    title="Most Common Skills in Top 100",
                    color_discrete_sequence=['#0ea5e9']
                )
                fig3.update_layout(
                    plot_bgcolor='rgba(0,0,0,0)', 
                    paper_bgcolor='rgba(0,0,0,0)',
                    yaxis={'categoryorder': 'total ascending'}
                )
                st.plotly_chart(fig3, use_container_width=True)
                
            st.markdown("---")
            fig2 = px.scatter(
                df, 
                x="yoe", 
                y="score", 
                hover_data=["title", "candidate_id"], 
                color="score", 
                size="yoe", 
                title="Years of Experience vs. Match Score",
                color_continuous_scale=px.colors.sequential.Plasma
            )
            fig2.update_layout(
                plot_bgcolor='rgba(0,0,0,0)', 
                paper_bgcolor='rgba(0,0,0,0)',
                xaxis_title="Years of Experience", 
                yaxis_title="Match Score"
            )
            st.plotly_chart(fig2, use_container_width=True)
