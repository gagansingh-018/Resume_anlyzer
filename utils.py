"""
utils.py — Core Analysis Engine
Smart Resume Analyzer PRO v4.0
Industry-accurate skill matching, salary prediction, quality scoring.
"""

import re
from PyPDF2 import PdfReader
from io import BytesIO
from industry_data import (
    TECHNICAL_SKILLS, SOFT_SKILLS, CREATIVE_SKILLS, JOB_PROFILES,
    INDUSTRY_SALARY_DATA, SKILL_ALIASES, SKILL_MULTIPLIERS,
    LEARNING_PATHS, QUALITY_RUBRIC, CERTIFICATIONS_BY_INDUSTRY,
)


# ─────────────────────────────────────────────────────────────────────────────
# PDF EXTRACTION
# ─────────────────────────────────────────────────────────────────────────────

def extract_text_from_pdf(pdf_file) -> str:
    try:
        reader = PdfReader(BytesIO(pdf_file.read()) if hasattr(pdf_file, "read") else BytesIO(pdf_file))
        if len(reader.pages) == 0:
            return "Error: PDF has no pages"
        text = ""
        for page in reader.pages:
            try:
                text += (page.extract_text() or "") + "\n"
            except Exception:
                continue
        return text.strip() or "Error: Could not extract text"
    except Exception as e:
        return f"Error extracting PDF: {e}"


# ─────────────────────────────────────────────────────────────────────────────
# SKILL UTILITIES
# ─────────────────────────────────────────────────────────────────────────────

def normalize_skill(skill: str) -> str:
    return skill.lower().strip()


def is_technical_skill(skill: str) -> bool:
    sn = normalize_skill(skill)
    for k in TECHNICAL_SKILLS:
        if normalize_skill(k) == sn:
            return True
    soft_kw = {
        "communication", "leadership", "teamwork", "collaboration",
        "problem solving", "project management", "time management",
        "critical thinking", "negotiation", "presentation", "mentoring",
        "adaptability", "creativity", "emotional intelligence",
    }
    return sn not in soft_kw and sn not in {normalize_skill(k) for k in SOFT_SKILLS}


def filter_technical_skills(skills: list) -> list:
    return [s for s in skills if is_technical_skill(s)]


def expand_skill_with_aliases(skill: str) -> list:
    sn = normalize_skill(skill)
    if sn in SKILL_ALIASES:
        return [sn] + SKILL_ALIASES[sn]
    for main, aliases in SKILL_ALIASES.items():
        if sn in aliases:
            return [main] + aliases
    return [sn]


def extract_skills(text: str, skills=None) -> list:
    if not text or not isinstance(text, str):
        return []
    if skills is None:
        skills = list(TECHNICAL_SKILLS.keys()) + list(SOFT_SKILLS.keys())
    tl = text.lower()
    found = set()
    for skill in skills:
        sn = normalize_skill(skill)
        if sn in tl:
            found.add(skill)
            continue
        for alias in expand_skill_with_aliases(sn):
            if alias == sn:
                continue
            if (f" {alias} " in f" {tl} " or tl.startswith(alias)
                    or tl.endswith(f" {alias}")):
                found.add(skill)
                break
    return sorted(list(found))


def categorize_skills(skills: list) -> dict:
    tech_map   = {normalize_skill(k): k for k in TECHNICAL_SKILLS}
    soft_map   = {normalize_skill(k): k for k in SOFT_SKILLS}
    create_map = {normalize_skill(k): k for k in CREATIVE_SKILLS}
    technical, soft, creative, tools = [], [], [], []
    for sk in skills:
        sn = normalize_skill(sk)
        if sn in tech_map:      technical.append(tech_map[sn])
        elif sn in soft_map:    soft.append(soft_map[sn])
        elif sn in create_map:  creative.append(create_map[sn])
        else:                   tools.append(sk)
    return {
        "technical": sorted(set(technical)),
        "soft":      sorted(set(soft)),
        "creative":  sorted(set(creative)),
        "tools":     sorted(set(tools)),
        "total":     len(skills),
    }


# ─────────────────────────────────────────────────────────────────────────────
# RESUME PARSING
# ─────────────────────────────────────────────────────────────────────────────

def extract_experience(text: str) -> int:
    patterns = [
        r"(\d+)\s*\+?\s*(?:years?|yrs?)",
        r"(?:since|from)\s+(20\d{2}|19\d{2})",
    ]
    matches = []
    for pat in patterns:
        for item in re.findall(pat, text, re.IGNORECASE):
            try:
                v = int(item)
                if len(str(v)) == 4:
                    v = 2026 - v
                if 0 < v <= 50:
                    matches.append(v)
            except Exception:
                pass
    return min(max(matches), 50) if matches else 0


def extract_education(text: str) -> str:
    mapping = {
        "PhD":      [r"phd", r"doctorate", r"doctor of philosophy"],
        "Master":   [r"master'?s?", r"\bms\b", r"\bmba\b", r"mtech", r"m\.tech"],
        "Bachelor": [r"bachelor'?s?", r"\bbs\b", r"\bbsc\b", r"b\.tech", r"btech"],
        "Diploma":  [r"diploma", r"associate"],
        "High School": [r"high school", r"secondary"],
    }
    tl = text.lower()
    for degree, pats in mapping.items():
        for p in pats:
            if re.search(r"\b" + p + r"\b", tl):
                return degree
    return "Not Mentioned"


def extract_contact_info(text: str) -> dict:
    info = {"email": None, "phone": None, "linkedin": None}
    m = re.search(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b", text)
    if m: info["email"] = m.group(0)
    m = re.search(r"\b\d{3}[-.\s]?\d{3}[-.\s]?\d{4}\b", text)
    if m: info["phone"] = m.group(0)
    m = re.search(r"linkedin\.com/in/[A-Za-z0-9\-]+", text, re.IGNORECASE)
    if m: info["linkedin"] = m.group(0)
    return info


def extract_keywords(text: str) -> list:
    kws = {"experience","responsibility","skill","requirement","qualification",
           "lead","manage","develop","design","implement","bachelor","master"}
    tl = text.lower()
    return sorted({kw.title() for kw in kws if kw in tl})


def detect_job_role(job_description: str) -> str:
    if not job_description:
        return "Software Engineer"
    jl = re.sub(r"\s+", " ", job_description.lower().strip())

    # Non-tech / creative roles checked FIRST
    non_tech = {
        "Digital Marketing":       ["digital marketing","performance marketing","growth marketing","seo specialist","ppc specialist"],
        "Video Editor":            ["video editor","video editing"],
        "Graphic Designer":        ["graphic designer","graphic design","visual designer"],
        "Content Writer":          ["content writer","content writing","copywriter"],
        "Social Media Manager":    ["social media manager","social media specialist","smm ","community manager"],
        "UX Designer":             ["ux designer","ux design","user experience designer"],
        "UI Designer":             ["ui designer","ui design","user interface designer"],
        "Motion Graphics Designer":["motion graphics","motion designer"],
        "Video Producer":          ["video producer","video production"],
    }
    for role, phrases in non_tech.items():
        for ph in phrases:
            if ph in jl:
                return role

    # Tech roles
    tech = {
        "Product Manager":       ["product manager","product management"],
        "Project Manager":       ["project manager","project management"],
        "Business Analyst":      ["business analyst","business analysis"],
        "Scrum Master":          ["scrum master","agile coach"],
        "DevOps Engineer":       ["devops engineer","dev ops engineer"],
        "Cloud Architect":       ["cloud architect","solutions architect"],
        "Data Scientist":        ["data scientist"],
        "Data Engineer":         ["data engineer"],
        "Data Analyst":          ["data analyst","bi analyst"],
        "Backend Developer":     ["backend developer","back-end developer","backend engineer"],
        "Frontend Developer":    ["frontend developer","front-end developer","frontend engineer"],
        "Full Stack Developer":  ["full stack developer","fullstack developer","full stack engineer"],
        "iOS Developer":         ["ios developer","swift developer"],
        "Android Developer":     ["android developer","kotlin developer"],
        ".NET Developer":        [".net developer","c# developer","asp.net developer"],
        "QA Engineer":           ["qa engineer","quality assurance engineer","test engineer"],
        "Security Engineer":     ["security engineer","cybersecurity engineer"],
        "Machine Learning Engineer": ["machine learning engineer","ml engineer","ai engineer"],
        "Technical Writer":      ["technical writer","documentation writer"],
        "Software Engineer":     ["software engineer","software developer"],
    }
    for role, phrases in tech.items():
        for ph in phrases:
            if ph in jl:
                return role

    # Keyword scoring fallback
    kw_roles = {
        "DevOps Engineer":    ["devops","kubernetes","docker","terraform","ci/cd"],
        "Backend Developer":  ["backend","api development","django","flask","fastapi"],
        "Frontend Developer": ["frontend","react developer","vue developer","angular"],
        "Full Stack Developer":["full stack","fullstack","full-stack"],
        "Machine Learning Engineer":["machine learning","deep learning","tensorflow","pytorch"],
        "Data Scientist":     ["data scientist","predictive model","statistical analysis"],
        "Data Engineer":      ["data engineer","etl","data pipeline","spark","hadoop"],
        "Data Analyst":       ["data analyst","tableau","power bi","sql analyst"],
    }
    scores = {}
    for role, kws in kw_roles.items():
        c = sum(1 for k in kws if k in jl)
        if c: scores[role] = c
    if scores:
        return max(scores, key=scores.get)
    return "Software Engineer"


def extract_job_requirements(job_description: str) -> list:
    if not job_description or len(job_description.strip()) < 10:
        return []
    all_skills = (list(TECHNICAL_SKILLS.keys())
                  + list(SOFT_SKILLS.keys())
                  + list(CREATIVE_SKILLS.keys()))
    jl = job_description.lower()
    detected = set()

    # Try requirement sections first
    req_markers = ["required skills:","must have:","should have:","qualifications:",
                   "requirements:","technical skills:","key skills:","tools:"]
    for marker in req_markers:
        if marker in jl:
            idx   = jl.find(marker)
            chunk = job_description[idx + len(marker): idx + len(marker) + 500]
            detected.update(extract_skills(chunk, all_skills))

    if not detected:
        detected.update(extract_skills(job_description, all_skills))

    if len(detected) < 5:
        for phrase in ["experience with","proficiency in","skilled in","expertise in","familiar with"]:
            for part in jl.split(phrase)[1:]:
                detected.update(extract_skills(part[:150], all_skills))

    role = detect_job_role(job_description)
    role_defaults = {
        "Backend Developer":         ["Python","Django","REST API","PostgreSQL","AWS","SQL","Git"],
        "Frontend Developer":        ["React","JavaScript","HTML","CSS","TypeScript","REST API","Git"],
        "Full Stack Developer":      ["React","Node.js","Python","SQL","AWS","Git","REST API","HTML","CSS"],
        "DevOps Engineer":           ["Docker","Kubernetes","AWS","Jenkins","Terraform","Linux","Git"],
        "Cloud Architect":           ["AWS","Azure","Google Cloud","Terraform","System Design","Security","Docker"],
        "Data Scientist":            ["Python","Machine Learning","SQL","TensorFlow","Pandas","NumPy"],
        "Data Engineer":             ["Python","SQL","Spark","AWS","Airflow","Kafka"],
        "Data Analyst":              ["SQL","Excel","Tableau","Python","Power BI","Data Analysis"],
        "QA Engineer":               ["Selenium","Testing","Java","Git","CI/CD"],
        "Security Engineer":         ["Linux","AWS","Encryption","Penetration Testing","Security"],
        "Machine Learning Engineer": ["Python","Machine Learning","Deep Learning","TensorFlow","PyTorch","SQL"],
        "Software Engineer":         ["Python","JavaScript","SQL","Git","REST API","Problem Solving"],
        "Video Editor":              ["Premiere Pro","After Effects","Video Editing","Motion Graphics","DaVinci Resolve"],
        "Graphic Designer":          ["Photoshop","Illustrator","Graphic Design","Figma","Canva"],
        "Content Writer":            ["Content Writing","Copywriting","SEO","Communication"],
        "Digital Marketing":         ["Digital Marketing","SEO","Social Media Marketing","Google Analytics","Email Marketing"],
        "Product Manager":           ["Project Management","Communication","Problem Solving","SQL","Data Analysis","Agile"],
        "Project Manager":           ["Project Management","Communication","Leadership","Agile"],
        "Business Analyst":          ["SQL","Excel","Data Analysis","Communication","Problem Solving"],
    }
    if role in role_defaults and len(detected) < 6:
        detected.update(role_defaults[role])

    return sorted(list(detected))


# ─────────────────────────────────────────────────────────────────────────────
# MATCHING & SCORING
# ─────────────────────────────────────────────────────────────────────────────

def calculate_match(resume_skills: list, job_requirements) -> tuple:
    if isinstance(job_requirements, str):
        job_requirements = extract_skills(job_requirements)
    required = list(job_requirements)
    if not required:
        return 0.0, [], []
    r_set = {normalize_skill(s) for s in resume_skills}
    j_set = {normalize_skill(s) for s in required}
    matched_norm = r_set & j_set
    missing_norm = j_set - r_set
    pct = round(len(matched_norm) / len(j_set) * 100, 2)
    matched = [s for s in resume_skills if normalize_skill(s) in matched_norm]
    return pct, matched, list(missing_norm)


def calculate_weighted_match_score(resume_skills: list, job_requirements) -> float:
    if isinstance(job_requirements, str):
        job_requirements = extract_skills(job_requirements)
    required = list(job_requirements)
    if not required:
        return 0.0
    r_norm = {normalize_skill(s) for s in resume_skills}
    total = matched = 0.0
    for sk in required:
        sn  = normalize_skill(sk)
        wt  = (1.0 + SKILL_MULTIPLIERS.get(sn, 0.0)) * 10
        total += wt
        if sn in r_norm:
            matched += wt
    return round(matched / total * 100, 2) if total else 0.0


# ─────────────────────────────────────────────────────────────────────────────
# RESUME QUALITY
# ─────────────────────────────────────────────────────────────────────────────

def analyze_resume_quality(resume_text: str, resume_skills: list,
                           experience, education) -> tuple:
    if not resume_text:
        return 0.0, ["Resume text is empty"], {}
    score, issues, analysis = 0, [], {}
    chars = len(resume_text)

    # 1. Length (15 pts)
    r = QUALITY_RUBRIC["length"]
    if chars >= r["excellent"]:   score += 15;  analysis["Length"] = f"Excellent ({chars} chars)"
    elif chars >= r["good"]:      score += 12;  analysis["Length"] = f"Good ({chars} chars)"
    elif chars >= r["acceptable"]:score += 8;   analysis["Length"] = f"Acceptable ({chars} chars)"; issues.append(f"Resume is short ({chars} chars; 800+ recommended)")
    else:                         analysis["Length"] = f"Too short ({chars} chars)"; issues.append(f"Resume too brief ({chars} chars; minimum 400)")

    # 2. Skills (15 pts)
    n = len(resume_skills)
    r = QUALITY_RUBRIC["skills_count"]
    if n >= r["excellent"]:   score += 15; analysis["Skills"] = f"Excellent ({n} skills)"
    elif n >= r["good"]:      score += 12; analysis["Skills"] = f"Good ({n} skills)"
    elif n >= r["acceptable"]:score += 8;  analysis["Skills"] = f"Acceptable ({n} skills)"
    else:                     analysis["Skills"] = f"Limited ({n} skills)"; issues.append(f"Too few skills ({n}; 8+ recommended)")

    # 3. Experience (20 pts)
    try:    exp = int(re.search(r"\d+", str(experience)).group(0)) if experience else 0
    except: exp = 0
    r = QUALITY_RUBRIC["experience"]
    if exp >= r["excellent"]:   score += 20; analysis["Experience"] = f"Excellent ({exp}+ yrs)"
    elif exp >= r["good"]:      score += 15; analysis["Experience"] = f"Good ({exp} yrs)"
    elif exp >= r["acceptable"]:score += 10; analysis["Experience"] = f"Entry ({exp} yr)"
    else:                       analysis["Experience"] = "No experience found"; issues.append("Add professional experience with years")

    # 4. Education (15 pts)
    r = QUALITY_RUBRIC["education"]
    if education in r["excellent"]:  score += 15; analysis["Education"] = f"Excellent ({education})"
    elif education in r["good"]:     score += 12; analysis["Education"] = f"Good ({education})"
    elif education in r["acceptable"]:score += 8; analysis["Education"] = f"Basic ({education})"
    else:                            analysis["Education"] = "Not mentioned"; issues.append("Mention your educational background")

    # 5. Contact (10 pts)
    ci = extract_contact_info(resume_text)
    n_contact = sum(1 for v in ci.values() if v)
    if n_contact >= 3:   score += 10; analysis["Contact"] = "Perfect (all info)"
    elif n_contact >= 2: score += 8;  analysis["Contact"] = "Good (2 items)"
    elif n_contact >= 1: score += 5;  analysis["Contact"] = "Partial (1 item)"; issues.append("Add email, phone, and LinkedIn URL")
    else:                analysis["Contact"] = "Missing"; issues.append("Add contact info: email, phone, LinkedIn")

    # 6. Sections (10 pts)
    req_secs = ["experience", "education", "skills"]
    found_secs = [s for s in req_secs if s in resume_text.lower()]
    if len(found_secs) >= 3:   score += 10; analysis["Sections"] = f"All found"
    elif len(found_secs) >= 2: score += 7;  analysis["Sections"] = f"Missing 1 section"; issues.append("Add all three sections: Experience, Education, Skills")
    else:                      score += 3;  analysis["Sections"] = "Incomplete"; issues.append("Add Experience, Education, and Skills sections")

    # 7. Action verbs (10 pts)
    verbs = QUALITY_RUBRIC["action_verbs"]["verbs"]
    vc = sum(resume_text.lower().count(v.lower()) for v in verbs)
    if vc >= 8:   score += 10; analysis["Action Verbs"] = f"Excellent ({vc})"
    elif vc >= 5: score += 7;  analysis["Action Verbs"] = f"Good ({vc})"
    elif vc >= 2: score += 4;  analysis["Action Verbs"] = f"Some ({vc})"; issues.append("Use more action verbs (Led, Developed, Built …)")
    else:         analysis["Action Verbs"] = "Needs work"; issues.append("Start bullets with strong action verbs")

    # 8. Quantification (5 pts)
    qkws = QUALITY_RUBRIC["quantification"]["metric_verbs"]
    qc = sum(resume_text.count(k) for k in qkws)
    if qc >= 5:   score += 5; analysis["Metrics"] = f"Excellent ({qc})"
    elif qc >= 2: score += 3; analysis["Metrics"] = f"Good ({qc})"
    else:         analysis["Metrics"] = "Needs more"; issues.append("Quantify achievements (e.g. '20% improvement')")

    return round(min(100, score), 1), issues, analysis


# ─────────────────────────────────────────────────────────────────────────────
# SALARY PREDICTION
# ─────────────────────────────────────────────────────────────────────────────

def predict_salary(experience_years, resume_skills: list,
                   education: str, industry: str = "Tech") -> dict:
    try:
        exp = int(re.search(r"\d+", str(experience_years)).group(0))
    except Exception:
        exp = 0
    exp = min(exp, 30)

    data = INDUSTRY_SALARY_DATA.get(industry, INDUSTRY_SALARY_DATA["Tech"])
    level = ("Entry Level" if exp < 2 else "Junior" if exp < 5 else
             "Mid-Level" if exp < 10 else "Senior" if exp < 15 else "Staff+")
    base = data.get(level, data["Mid-Level"])

    skill_mult = 1.0
    r_norm = {normalize_skill(s) for s in resume_skills}
    for sk, prem in SKILL_MULTIPLIERS.items():
        if sk in r_norm:
            skill_mult += prem
    skill_mult = min(2.0, skill_mult)

    edu_mult = (1.15 if education == "PhD" else 1.10 if education == "Master"
                else 1.05 if education == "Bachelor" else 1.0)
    exp_mult = 1.0 + min(exp, 20) * 0.02
    total = skill_mult * edu_mult * exp_mult

    return {
        "min":    round(max(35, base["min"] * total)),
        "avg":    round(max(50, base["avg"] * total)),
        "max":    round(max(70, base["max"] * total)),
        "level":  level,
        "currency": "USD",
        "period": "annual (2024–2026)",
    }


# ─────────────────────────────────────────────────────────────────────────────
# CAREER INSIGHTS
# ─────────────────────────────────────────────────────────────────────────────

def get_skill_gaps(resume_skills: list, job_requirements) -> list:
    if isinstance(job_requirements, str):
        job_requirements = extract_skills(job_requirements)
    r_norm = {normalize_skill(s) for s in resume_skills}
    j_norm = {normalize_skill(s) for s in job_requirements}
    missing = j_norm - r_norm
    t_norm  = {normalize_skill(k) for k in TECHNICAL_SKILLS}
    default_res = ["Udemy", "Coursera", "Official docs", "Hands-on projects"]
    gaps = []
    for sk in sorted(missing):
        disp = sk.title()
        path = LEARNING_PATHS.get(disp, {})
        sdata = TECHNICAL_SKILLS.get(disp, {})
        gaps.append({
            "skill":    disp,
            "priority": "Critical" if sk in SKILL_MULTIPLIERS else "High",
            "timeline": path.get("timeline", "6–12 weeks"),
            "resources":path.get("entry", []) or default_res,
            "demand":   sdata.get("demand", "Medium"),
            "growth":   sdata.get("growth", 0),
        })
    return gaps[:8]


def get_interview_readiness_score(resume_skills: list, job_requirements,
                                  experience, education) -> dict:
    match_pct, _, _ = calculate_match(resume_skills, job_requirements)
    score, strengths, concerns = 0, [], []
    try:    exp = int(re.search(r"\d+", str(experience)).group(0))
    except: exp = 0

    if exp >= 5:   score += 30; strengths.append(f"Strong experience ({exp}+ years)")
    elif exp >= 2: score += 20; strengths.append(f"Relevant experience ({exp} years)")
    elif exp >= 1: score += 10; concerns.append("Limited experience — prepare specific examples")
    else:          concerns.append("Entry-level — emphasise learning agility")

    if match_pct >= 90:   score += 40; strengths.append(f"Expert skill match ({match_pct:.0f}%)")
    elif match_pct >= 70: score += 30; strengths.append(f"Good skill match ({match_pct:.0f}%)")
    elif match_pct >= 50: score += 20; concerns.append("Moderate skill gaps — prepare a learning plan")
    else:                 score += 10; concerns.append("Highlight transferable skills to offset gaps")

    if education in ["Master", "PhD"]:
        score += 15; strengths.append(f"Advanced degree ({education})")
    elif education == "Bachelor":
        score += 10

    tech = [s for s in resume_skills if s in TECHNICAL_SKILLS]
    if len(tech) >= 10:   score += 15; strengths.append("Strong technical depth")
    elif len(tech) >= 5:  score += 10

    return {
        "score": min(100, score),
        "strengths": strengths[:3],
        "concerns":  concerns[:3],
        "readiness_level": ("Excellent" if score >= 85 else "Very Good" if score >= 75
                            else "Good" if score >= 60 else "Fair"),
    }


def get_career_progression_path(experience_years, resume_skills: list) -> list:
    try:    exp = int(re.search(r"\d+", str(experience_years)).group(0))
    except: exp = 0
    r_norm = {normalize_skill(s) for s in resume_skills}
    paths  = []

    if any(s in r_norm for s in ["python", "java", "javascript", "node.js"]):
        if exp < 2:
            paths.append({"title":"Mid-Level Developer","timeline":"1–2 years","salary_increase":"15–25%","skills":["System Design","SQL Optimisation","API Design","Architecture"]})
        elif exp < 5:
            paths.append({"title":"Senior Developer","timeline":"2–3 years","salary_increase":"25–40%","skills":["System Architecture","Performance","Security","Tech Lead"]})
        else:
            paths.append({"title":"Tech Lead / Eng Manager","timeline":"3–5 years","salary_increase":"35–60%","skills":["Leadership","Strategy","Mentoring","Planning"]})

    if any(s in r_norm for s in ["aws","azure","docker","kubernetes"]):
        if exp < 2:
            paths.append({"title":"Cloud Engineer","timeline":"1–2 years","salary_increase":"20–30%","skills":["IaC","Kubernetes","CI/CD","Cloud Security"]})
        elif exp < 5:
            paths.append({"title":"Senior DevOps/Cloud","timeline":"2–3 years","salary_increase":"30–45%","skills":["Multi-cloud","Terraform","Cost Optimisation","K8s"]})
        else:
            paths.append({"title":"Cloud Architect","timeline":"2–4 years","salary_increase":"40–70%","skills":["Enterprise Arch","Compliance","Disaster Recovery","Cost Strategy"]})

    if any(s in r_norm for s in ["machine learning","deep learning","python"]):
        if exp < 3:
            paths.append({"title":"ML Engineer","timeline":"2–3 years","salary_increase":"25–35%","skills":["Deep Learning","Feature Eng","MLOps","Model Deploy"]})
        else:
            paths.append({"title":"Senior ML / ML Architect","timeline":"3–4 years","salary_increase":"40–60%","skills":["Advanced ML","Distributed ML","Research","Prod Systems"]})

    if not paths:
        paths.append({"title":"Senior Specialist","timeline":"2–3 years","salary_increase":"20–30%","skills":["Advanced Expertise","Leadership","Specialisation","Innovation"]})

    return paths[:3]


# ─────────────────────────────────────────────────────────────────────────────
# RECOMMENDATIONS
# ─────────────────────────────────────────────────────────────────────────────

def get_improvement_suggestions(resume_skills: list, job_requirements,
                                experience, quality_issues: list) -> list:
    recs = list(quality_issues[:3]) if quality_issues else []
    _, _, missing = calculate_match(resume_skills, job_requirements)
    if missing:
        disp = [s.title() for s in list(missing)[:3]]
        recs.append(f"Learn in-demand skills: {', '.join(disp)}")
    if not recs:
        recs.append("✓ Resume looks great! Focus on interview preparation.")
    return recs[:5]


# ─────────────────────────────────────────────────────────────────────────────
# CERTIFICATIONS
# ─────────────────────────────────────────────────────────────────────────────

def match_certifications(job_description: str, resume_text: str,
                         resume_skills: list = None) -> list:
    role = detect_job_role(job_description)
    job_req = extract_job_requirements(job_description)

    cert_map = {
        "kubernetes":         {"cert":"CKA — Kubernetes Administrator","relevance":"Critical","duration":"3–4 months"},
        "docker":             {"cert":"Docker Certified Associate","relevance":"Critical","duration":"1–2 months"},
        "terraform":          {"cert":"HashiCorp Terraform Associate","relevance":"Critical","duration":"2 months"},
        "aws":                {"cert":"AWS Solutions Architect Associate","relevance":"Critical","duration":"2–3 months"},
        "azure":              {"cert":"Azure Administrator","relevance":"Critical","duration":"2–3 months"},
        "google cloud":       {"cert":"GCP Associate Cloud Engineer","relevance":"Critical","duration":"2–3 months"},
        "machine learning":   {"cert":"AWS ML Specialty","relevance":"Critical","duration":"3–4 months"},
        "python":             {"cert":"Google ML Engineer Certificate","relevance":"High","duration":"3–6 months"},
        "data science":       {"cert":"Google Data Analytics Certificate","relevance":"Critical","duration":"3–6 months"},
        "sql":                {"cert":"Google Cloud Data Engineer","relevance":"High","duration":"3–4 months"},
        "tableau":            {"cert":"Tableau Public Certified Associate","relevance":"Critical","duration":"2–3 months"},
        "power bi":           {"cert":"Microsoft: Data Analyst Associate","relevance":"Critical","duration":"3–4 months"},
        "java":               {"cert":"Oracle Certified Java Programmer","relevance":"High","duration":"2–3 months"},
        "react":              {"cert":"Google Mobile Web Specialist","relevance":"High","duration":"1–2 months"},
        "testing":            {"cert":"ISTQB Certified Tester","relevance":"Critical","duration":"2–4 weeks"},
        "security":           {"cert":"AWS Security Specialty","relevance":"Critical","duration":"2–3 months"},
        "devops":             {"cert":"AWS DevOps Engineer Professional","relevance":"Critical","duration":"3–4 months"},
        "premiere pro":       {"cert":"Adobe Certified Professional — Video Design","relevance":"Critical","duration":"1–2 months"},
        "after effects":      {"cert":"Adobe Certified Professional — Visual Design","relevance":"Critical","duration":"1–2 months"},
        "photoshop":          {"cert":"Adobe Certified Professional — Graphic Design","relevance":"Critical","duration":"1–2 months"},
        "figma":              {"cert":"Figma Certified Professional","relevance":"High","duration":"2–4 weeks"},
        "ux design":          {"cert":"Google UX Certificate","relevance":"Critical","duration":"3–6 months"},
        "seo":                {"cert":"Google Analytics / SEO Certification","relevance":"Critical","duration":"1–2 months"},
        "digital marketing":  {"cert":"Google Digital Marketing Certificate","relevance":"Critical","duration":"3–6 months"},
        "social media marketing":{"cert":"Meta Blueprint Certified","relevance":"High","duration":"1–2 months"},
    }
    role_defaults = {
        "DevOps Engineer":    [{"cert":"CKA — Kubernetes Administrator","relevance":"Critical","duration":"3–4 months"},{"cert":"AWS DevOps Engineer Professional","relevance":"Critical","duration":"3–4 months"},{"cert":"Docker Certified Associate","relevance":"Critical","duration":"1–2 months"}],
        "Cloud Architect":    [{"cert":"AWS Solutions Architect Professional","relevance":"Critical","duration":"3–4 months"},{"cert":"GCP Professional Cloud Architect","relevance":"Critical","duration":"3–4 months"},{"cert":"Azure Solutions Architect","relevance":"Critical","duration":"3 months"}],
        "Data Scientist":     [{"cert":"Google ML Engineer Certificate","relevance":"Critical","duration":"3–6 months"},{"cert":"AWS ML Specialty","relevance":"Critical","duration":"3–4 months"},{"cert":"Azure Data Scientist","relevance":"High","duration":"3 months"}],
        "Data Analyst":       [{"cert":"Google Data Analytics Certificate","relevance":"Critical","duration":"3–6 months"},{"cert":"Microsoft: Data Analyst Associate","relevance":"Critical","duration":"3–4 months"},{"cert":"Tableau Public Certified Associate","relevance":"High","duration":"2–3 months"}],
        "Backend Developer":  [{"cert":"AWS Solutions Architect Associate","relevance":"Critical","duration":"2–3 months"},{"cert":"Oracle Certified Java Programmer","relevance":"High","duration":"2–3 months"}],
        "Frontend Developer": [{"cert":"Google Mobile Web Specialist","relevance":"Critical","duration":"1–2 months"},{"cert":"AWS Solutions Architect Associate","relevance":"High","duration":"2–3 months"}],
        "Full Stack Developer":[{"cert":"AWS Solutions Architect Associate","relevance":"Critical","duration":"2–3 months"},{"cert":"GCP Associate Cloud Engineer","relevance":"High","duration":"2–3 months"}],
        "Video Editor":       [{"cert":"Adobe Certified Professional — Video Design","relevance":"Critical","duration":"2–3 months"},{"cert":"Blackmagic DaVinci Resolve Certified","relevance":"High","duration":"1–2 months"}],
        "Graphic Designer":   [{"cert":"Adobe Certified Professional — Graphic Design","relevance":"Critical","duration":"2–3 months"},{"cert":"Figma Certified Professional","relevance":"High","duration":"2–4 weeks"}],
        "Digital Marketing":  [{"cert":"Google Digital Marketing Certificate","relevance":"Critical","duration":"3–6 months"},{"cert":"Google Analytics Certification","relevance":"Critical","duration":"1–2 months"},{"cert":"Meta Blueprint Certified","relevance":"High","duration":"1–2 months"}],
        "Product Manager":    [{"cert":"Google Project Management Certificate","relevance":"High","duration":"3–6 months"},{"cert":"Certified Scrum Product Owner (CSPO)","relevance":"High","duration":"2–4 weeks"}],
        "Project Manager":    [{"cert":"PMP — Project Management Professional","relevance":"Critical","duration":"3–4 months"},{"cert":"Certified Scrum Master (CSM)","relevance":"High","duration":"2–4 weeks"}],
        "Machine Learning Engineer":[{"cert":"Google ML Engineer Certificate","relevance":"Critical","duration":"3–6 months"},{"cert":"AWS ML Specialty","relevance":"Critical","duration":"3–4 months"}],
        "Software Engineer":  [{"cert":"AWS Solutions Architect Associate","relevance":"Critical","duration":"2–3 months"},{"cert":"GCP Associate Cloud Engineer","relevance":"High","duration":"2–3 months"}],
    }

    recs, seen = [], set()
    for sk in job_req:
        sn = normalize_skill(sk)
        for kw, info in cert_map.items():
            if kw in sn and info["cert"] not in seen:
                recs.append({"area": role, **info})
                seen.add(info["cert"])
                break

    if not recs:
        for c in role_defaults.get(role, []):
            if c["cert"] not in seen:
                recs.append({"area": role, **c})
                seen.add(c["cert"])

    # top up to 4
    for c in role_defaults.get(role, []):
        if len(recs) >= 4: break
        if c["cert"] not in seen:
            recs.append({"area": role, **c})
            seen.add(c["cert"])

    return recs[:6]


def match_job_profile(resume_skills: list, job_description: str) -> tuple:
    best, best_score = None, 0
    for role, profile in JOB_PROFILES.items():
        req = profile["required_skills"]["critical"] + profile["required_skills"]["required"]
        sc, _, _ = calculate_match(resume_skills, req)
        if sc > best_score:
            best_score, best = sc, role
    return best or "Unclassified", best_score


# ─────────────────────────────────────────────────────────────────────────────
# ATS & POWER TOOLS
# ─────────────────────────────────────────────────────────────────────────────

def get_keyword_density(resume_text: str, job_skills: list) -> dict:
    if not resume_text or not job_skills:
        return {"found": [], "missing": list(job_skills), "score_pct": 0}
    tl = text_lower = resume_text.lower()
    found, missing = [], []
    for sk in job_skills:
        sn = normalize_skill(sk)
        cnt = tl.count(sn)
        for alias in expand_skill_with_aliases(sk):
            if alias != sn:
                cnt += tl.count(alias)
        if cnt > 0: found.append((sk, cnt))
        else:       missing.append(sk)
    score = round(len(found) / len(job_skills) * 100, 1) if job_skills else 0
    return {"found": found, "missing": missing, "score_pct": score}


def get_ats_checklist(resume_text: str, resume_skills: list,
                      experience, education) -> list:
    ci     = extract_contact_info(resume_text)
    cc     = sum(1 for v in ci.values() if v)
    tl     = resume_text.lower()
    verbs  = QUALITY_RUBRIC["action_verbs"]["verbs"]
    vc     = sum(tl.count(v.lower()) for v in verbs)
    wc     = len(resume_text.split())
    try:    exp = int(re.search(r"\d+", str(experience)).group(0))
    except: exp = 0
    return [
        {"item":"Contact info (email, phone, LinkedIn)",
         "status":"pass" if cc>=2 else "warn" if cc>=1 else "fail",
         "tip":"Add email, phone, and LinkedIn URL."},
        {"item":"Experience section present",
         "status":"pass" if "experience" in tl else "fail",
         "tip":"Add a clear Work Experience section."},
        {"item":"Education section present",
         "status":"pass" if "education" in tl else "fail",
         "tip":"Add Education with degree and institution."},
        {"item":"Skills section present",
         "status":"pass" if "skills" in tl else "fail",
         "tip":"List your skills explicitly."},
        {"item":"Resume length (400–1 500 words)",
         "status":"pass" if 400<=wc<=1500 else "warn" if 200<=wc<400 or wc>2000 else "fail",
         "tip":"Aim for 1–2 pages (400–800 words)."},
        {"item":"Action verbs (5+)",
         "status":"pass" if vc>=5 else "warn" if vc>=2 else "fail",
         "tip":"Start bullets with Led, Built, Designed, etc."},
        {"item":"Skills count (8+)",
         "status":"pass" if len(resume_skills)>=8 else "warn" if len(resume_skills)>=5 else "fail",
         "tip":"List 8–15 relevant skills."},
        {"item":"Experience years mentioned",
         "status":"pass" if exp>0 else "fail",
         "tip":"State years of experience explicitly."},
    ]


def get_readability_stats(resume_text: str) -> dict:
    if not resume_text:
        return {"word_count":0,"char_count":0,"reading_time_mins":1,"length_ok":False,
                "suggestion":"Add resume content."}
    wc  = len(resume_text.split())
    cc  = len(resume_text)
    rtm = max(1, round(wc / 200.0))
    ok  = 400 <= wc <= 1200
    if wc < 400:    sug = "Too short — add achievements and role details (target 400–800 words)."
    elif wc > 1200: sug = "Too long — trim to 1–2 pages (under 800 words) for ATS."
    else:           sug = "Length is ideal for ATS and recruiters."
    return {"word_count":wc,"char_count":cc,"reading_time_mins":rtm,"length_ok":ok,"suggestion":sug}


def get_action_verb_suggestions(resume_text: str) -> dict:
    strong = ["Led","Developed","Managed","Created","Implemented","Designed","Built",
              "Improved","Achieved","Optimized","Launched","Reduced","Increased","Automated"]
    weak   = ["did","made","worked","helped","used","responsible for","handled"]
    tl     = resume_text.lower()
    used       = [v for v in strong if v.lower() in tl]
    weak_found = [w for w in weak if w in tl]
    suggested  = [v for v in ["Led","Developed","Implemented","Designed","Achieved"] if v not in used][:5]
    return {"count":len(used),"used":used[:10],"weak_found":weak_found,"suggested_add":suggested}


def get_tailoring_phrases(job_skills: list, missing_skills: list, job_role: str) -> list:
    phrases = []
    for sk in missing_skills[:5]:
        s = sk.title() if isinstance(sk, str) else sk
        phrases.append(f"Implemented {s} solutions in production environments")
        phrases.append(f"Proficient in {s} for building scalable systems")
    phrases.append(f"Strong fit for {job_role} role with end-to-end delivery experience")
    return phrases[:8]


def get_interview_questions(job_role: str, missing_skills: list, experience) -> list:
    qs = []
    rl = job_role.lower()
    if "data" in rl or "ml" in rl or "scientist" in rl:
        qs += ["Walk me through a data or ML project end-to-end.",
               "How do you handle class imbalance or missing data?"]
    if "engineer" in rl or "developer" in rl:
        qs += ["Describe a complex technical challenge you solved.",
               "How do you balance code quality with delivery speed?"]
    if "devops" in rl or "cloud" in rl:
        qs += ["Describe your CI/CD and production deployment experience.",
               "How do you approach incident response?"]
    for sk in (missing_skills or [])[:3]:
        qs.append(f"What is your hands-on experience with {sk.title()}?")
    qs.append("Why do you want to join our team, and what will you contribute in the first 90 days?")
    return qs[:8]


def get_cover_letter_bullets(resume_skills: list, job_skills: list,
                              experience, job_role: str) -> list:
    pct, matched, _ = calculate_match(resume_skills, job_skills)
    top = sorted(matched)[:5]
    return [
        f"Over {experience} years of professional experience delivering {job_role} solutions.",
        f"Proficient in {', '.join(top[:3])} and related technologies." if top else "Strong technical foundation aligned with the role.",
        f"Committed to the {job_role} responsibilities with a focus on quality and impact.",
        f"Strong alignment with role requirements — {pct:.0f}% skill match.",
    ][:5]


def get_ideal_candidate_snapshot(job_role: str) -> list:
    profile = JOB_PROFILES.get(job_role)
    if not profile:
        return ["Strong technical skills matching the job description",
                "Clear experience section with quantified achievements",
                "Relevant education and certifications"]
    crit = profile["required_skills"]["critical"][:5]
    req  = profile["required_skills"]["required"][:3]
    return [
        f"Key skills: {', '.join(crit)}",
        f"Also valuable: {', '.join(req)}",
        f"Experience: {profile['min_experience']}+ years",
        f"Education: {profile.get('education','Bachelor')} or equivalent",
    ]


def generate_report_text(detected_role, match_score, weighted_score, quality_score,
                         ats_score, experience, education, resume_skills, job_skills,
                         matched_technical, missing_technical, quality_issues,
                         skill_gaps, salary_prediction, interview_readiness,
                         keyword_density) -> str:
    lines = [
        "RESUME ANALYSIS REPORT",
        "=" * 40,
        f"Job Role   : {detected_role}",
        f"Match      : {match_score:.1f}%  |  Weighted: {weighted_score:.0f}%",
        f"Quality    : {quality_score:.1f}%  |  ATS: {ats_score:.1f}%",
        f"Experience : {experience} years  |  Education: {education}",
        "",
        f"YOUR SKILLS ({len(resume_skills)})",
        ", ".join(sorted(resume_skills)[:20]) + ("…" if len(resume_skills)>20 else ""),
        "",
        "MATCHED : " + (", ".join(sorted(matched_technical)[:15]) or "None"),
        "MISSING : " + (", ".join(s.title() for s in sorted(missing_technical)[:15]) or "None"),
        "",
        "QUALITY ISSUES: " + ("; ".join(quality_issues) if quality_issues else "None"),
        "",
        f"SALARY RANGE : ${salary_prediction['min']:.0f}K – ${salary_prediction['max']:.0f}K  (avg ${salary_prediction['avg']:.0f}K)",
        f"INTERVIEW    : {interview_readiness['score']}% — {interview_readiness['readiness_level']}",
        f"KEYWORD MATCH: {keyword_density['score_pct']}%  ({len(keyword_density['found'])}/{len(keyword_density['found'])+len(keyword_density['missing'])} keywords present)",
    ]
    if skill_gaps:
        lines += ["", "SKILL GAPS TO LEARN:"]
        for g in skill_gaps[:5]:
            lines.append(f"  • {g['skill']}  ({g['timeline']}, {g['priority']} priority)")
    return "\n".join(lines)