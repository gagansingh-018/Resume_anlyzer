"""
groq_utils.py — Groq-powered AI analysis functions
Smart Resume Analyzer PRO v4.0

Model : llama-3.3-70b-versatile (free tier, very fast)
Key   : https://console.groq.com  (free in < 60 seconds)

Every function falls back silently when no key is set.
"""

import os, re, json
import streamlit as st


def _get_client():
    key = os.environ.get("GROQ_API_KEY", "").strip()
    if not key:
        return None
    try:
        from groq import Groq
        return Groq(api_key=key)
    except Exception:
        return None


def is_groq_available() -> bool:
    return _get_client() is not None


def _chat(prompt: str, system: str = None, max_tokens: int = 512,
          temperature: float = 0.65) -> str:
    client = _get_client()
    if not client:
        return None
    if system is None:
        system = (
            "You are a senior technical recruiter and career coach with 15 years of "
            "experience analysing resumes and advising job seekers. Give direct, "
            "specific, actionable advice. No markdown headers. Stay concise."
        )
    try:
        r = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role":"system","content":system},
                      {"role":"user","content":prompt}],
            max_tokens=max_tokens, temperature=temperature,
        )
        return r.choices[0].message.content.strip()
    except Exception as e:
        st.toast(f"⚠️ Groq error: {e}")
        return None


def _chat_json(prompt: str, max_tokens: int = 650):
    sys_msg = "You are a resume analysis engine. Respond ONLY with valid JSON — no preamble, no markdown fences."
    raw = _chat(prompt, system=sys_msg, max_tokens=max_tokens, temperature=0.25)
    if not raw:
        return None
    raw = re.sub(r"^```(?:json)?", "", raw.strip(), flags=re.IGNORECASE)
    raw = re.sub(r"```$", "", raw.strip())
    try:
        return json.loads(raw.strip())
    except Exception:
        return None


# ── Public AI functions ───────────────────────────────────────────────────────

def ai_resume_summary(resume_text, job_description, match_score,
                      matched_skills, missing_skills, detected_role,
                      experience, education):
    matched_str = ", ".join(sorted(matched_skills)[:8]) or "none detected"
    missing_str = ", ".join(s.title() for s in sorted(missing_skills)[:6]) or "none"
    prompt = f"""Write a 4-sentence personalised resume-fit summary.
Role: {detected_role} | Match: {match_score:.0f}% | Exp: {experience} yrs | Edu: {education}
Matching skills: {matched_str}
Missing skills: {missing_str}
Job snippet: {job_description[:350]}
Resume snippet: {resume_text[:250]}

Structure — one sentence each:
1. Overall fit verdict (mention role + score)
2. Top 2-3 genuine strengths (use real skill names)
3. The single most critical gap and why it matters
4. One concrete action to take this week

Plain prose only. No bullet points."""
    return _chat(prompt, max_tokens=230)


def ai_improvement_suggestions(resume_text, job_description, missing_skills,
                                quality_issues, experience, detected_role, match_score):
    missing_str = ", ".join(s.title() for s in missing_skills[:8]) or "none"
    issues_str  = "; ".join(quality_issues[:4]) or "none"
    prompt = f"""Candidate applying for {detected_role} | Match: {match_score:.0f}% | Exp: {experience} yrs
Missing skills: {missing_str}
Resume quality issues: {issues_str}
Job snippet: {job_description[:280]}

Give exactly 5 improvement suggestions ordered by impact (highest first).
Each must be specific, actionable today, 1-2 sentences.
Return a JSON array of 5 strings."""
    result = _chat_json(prompt, max_tokens=520)
    if isinstance(result, list) and len(result) >= 3:
        return result[:5]
    fb = []
    if missing_skills:
        fb.append(f"Add these missing skills to your resume: {missing_str[:110]}.")
    fb.extend(quality_issues[:2])
    fb += ["Quantify every achievement with numbers (e.g. 'Reduced latency by 35%').",
           "Write a 2-3 line professional summary tailored to this specific role.",
           "Ensure clear sections: Experience · Skills · Education · Projects."]
    return fb[:5]


def ai_tailoring_phrases(job_description, missing_skills, resume_text, detected_role):
    missing_str = ", ".join(s.title() for s in missing_skills[:6]) or "none"
    prompt = f"""Candidate targeting a {detected_role} role.
Skills to incorporate: {missing_str}
Job description snippet: {job_description[:350]}
Resume snippet: {resume_text[:200]}

Write 6 resume bullet points they can add. Each must start with a strong past-tense
action verb, be 12-20 words, reference real skills from the JD, sound authentic.
Return a JSON array of 6 strings."""
    result = _chat_json(prompt, max_tokens=480)
    if isinstance(result, list) and len(result) >= 4:
        return result[:6]
    phrases = []
    for sk in missing_skills[:3]:
        s = sk.title()
        phrases.append(f"Designed and deployed {s} solutions in production, improving system reliability")
        phrases.append(f"Built automated {s} pipelines that reduced manual effort by over 40%")
    phrases.append(f"Led end-to-end {detected_role} delivery from requirements to production release")
    return phrases[:6]


def ai_cover_letter_bullets(resume_skills, job_skills, experience,
                             job_role, resume_text, match_score):
    matched = sorted(set(s.lower() for s in resume_skills) & set(s.lower() for s in job_skills))
    matched_str = ", ".join(s.title() for s in matched[:6]) or "relevant technical skills"
    prompt = f"""Write 4 cover letter bullet points for a {job_role} application.
Candidate: {experience} yrs exp | {match_score:.0f}% skill match | Matching: {matched_str}
Resume snippet: {resume_text[:200]}
Each bullet: 1-2 natural professional sentences, highlights specific value,
references actual background, avoids clichés like "team player".
Return a JSON array of 4 strings."""
    result = _chat_json(prompt, max_tokens=420)
    if isinstance(result, list) and len(result) >= 3:
        return result[:5]
    return [
        f"With {experience} years of experience, I bring proven delivery capability to the {job_role} role.",
        f"My proficiency in {matched_str[:80]} directly meets your core technical requirements.",
        "I consistently deliver clean, production-ready solutions that drive measurable outcomes.",
        f"I am ready to contribute immediately and grow with your team long-term.",
    ]


def ai_interview_questions(job_role, missing_skills, experience, resume_text, job_description):
    missing_str = ", ".join(s.title() for s in missing_skills[:5]) or "none"
    prompt = f"""Generate 7 interview questions for a {job_role} position.
Candidate: {experience} yrs exp | Gaps to probe: {missing_str}
Job snippet: {job_description[:280]} | Resume snippet: {resume_text[:180]}

Mix: 2-3 technical, 2 STAR behavioural, 1-2 gap-probing, 1 motivation.
Return a JSON array of 7 question strings (no answers, no numbering inside strings)."""
    result = _chat_json(prompt, max_tokens=540)
    if isinstance(result, list) and len(result) >= 5:
        return result[:8]
    qs = [
        f"Walk me through your most impactful {job_role} project end-to-end.",
        "Describe a time you had to learn a new technology quickly under a deadline.",
        f"How do you approach technical architecture decisions in a {job_role} context?",
        "Tell me about a technical disagreement — how did you resolve it?",
    ]
    for sk in missing_skills[:2]:
        qs.append(f"We rely heavily on {sk.title()} here — what is your hands-on experience level?")
    qs.append("Why are you interested in this specific role and company right now?")
    return qs[:7]


def ai_skill_gap_commentary(skill_gaps, experience, job_role):
    if not skill_gaps:
        return None
    gap_str = ", ".join(g["skill"] for g in skill_gaps[:6])
    prompt = f"""A {job_role} candidate with {experience} yrs exp is missing: {gap_str}.
In 2-3 sentences: (1) name the 1-2 most critical gaps and why they matter for this role,
(2) give an encouraging realistic note on the learning timeline. Plain prose, no bullets."""
    return _chat(prompt, max_tokens=145)


def ai_career_advice(experience, resume_skills, job_role, salary_avg, education):
    skills_str = ", ".join(sorted(resume_skills)[:8]) or "general tech skills"
    prompt = f"""Career advice for a {job_role} professional.
Profile: {experience} yrs | {education} | Skills: {skills_str} | Benchmark: ~${salary_avg:.0f}K/yr
In 3-4 sentences: (1) best next role title, (2) 1-2 specific certs/skill tracks to pursue,
(3) realistic timeline for salary increase or promotion. Name real roles and certs. No bullets."""
    return _chat(prompt, max_tokens=185)


def ai_ats_feedback(ats_score, quality_issues, resume_text,
                    matched_keywords, missing_keywords):
    issues_str  = "; ".join(quality_issues[:3]) or "none"
    matched_str = ", ".join(k[0] if isinstance(k, tuple) else k
                            for k in matched_keywords[:5]) or "none"
    missing_str = ", ".join(k[0] if isinstance(k, tuple) else k
                            for k in missing_keywords[:6]) if missing_keywords else "none"
    prompt = f"""Resume ATS score: {ats_score:.0f}/100
Issues: {issues_str} | Keywords present: {matched_str} | Keywords missing: {missing_str}
In 2-3 sentences: (1) what this score means for real recruiter screening,
(2) the single highest-impact fix to make right now. Plain prose, no bullets."""
    return _chat(prompt, max_tokens=155)


def ai_ideal_candidate(job_role, job_description):
    prompt = f"""Ideal candidate for a {job_role} position in 4 bullet points.
Job description snippet: {job_description[:350]}
Cover: (1) must-have technical skills, (2) experience/background,
(3) working style/soft skills, (4) education or certification expectations.
Return a JSON array of 4 strings. Each 10-20 words, specific and practical."""
    result = _chat_json(prompt, max_tokens=330)
    if isinstance(result, list) and len(result) >= 3:
        return result[:4]
    return [
        f"Strong hands-on experience with the core technical stack for {job_role}",
        "3+ years professional experience with a portfolio of shipped projects",
        "Clear communicator who collaborates well cross-functionally under pressure",
        "Relevant degree or equivalent self-taught background with industry certifications",
    ]


def ai_batch_one_liner(filename, match_score, ats_score, quality_score,
                       matched_skills, missing_skills, experience):
    matched_str = ", ".join(sorted(matched_skills)[:4]) or "few skills"
    missing_str = ", ".join(s.title() for s in sorted(missing_skills)[:3]) or "minor gaps"
    prompt = f"""ONE sentence (max 25 words) hiring recommendation.
{filename} | Match: {match_score:.0f}% | ATS: {ats_score:.0f}% | Quality: {quality_score:.0f}%
Strengths: {matched_str} | Gaps: {missing_str} | Exp: {experience} yrs
Be direct: Recommend / Consider / Pass — and give the key reason."""
    result = _chat(prompt, max_tokens=55)
    return result or f"{match_score:.0f}% match — {matched_str[:55]}"