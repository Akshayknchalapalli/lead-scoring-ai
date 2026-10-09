# Entirely synthetic. Conversion probabilities are illustrative, NOT trained output.
LEADS = {
    ("demo-a", "hot-1"): {"category": "hot", "meeting": False, "signals": ["recent_reply", "site_visit"]},
    ("demo-a", "warm-1"): {"category": "warm", "meeting": False, "signals": ["recent_reply"]},
    ("demo-a", "cold-1"): {"category": "cold", "meeting": False, "signals": ["low_engagement"]},
    ("demo-a", "meeting-1"): {"category": "cold", "meeting": True, "signals": ["scheduled_meeting"]},
    ("demo-a", "empty-1"): {"category": "warm", "meeting": False, "signals": []},
    ("demo-b", "hot-1"): {"category": "cold", "meeting": False, "signals": ["low_engagement"]},
}
SIGNALS = {
    "recent_reply": "The lead replied recently.",
    "site_visit": "A site visit was completed.",
    "low_engagement": "Engagement is currently low.",
    "scheduled_meeting": "A meeting is already scheduled.",
}
ACTIONS = {
    "prioritize_outreach": "Prioritize a follow-up call.",
    "follow_up": "Follow up within 24–48 hours.",
    "nurture": "Keep this lead in the nurture queue.",
    "confirm_meeting": "Confirm the existing meeting and prepare for it.",
    "human_review": "Ask a sales representative to review this lead.",
    "unavailable": "No lead is available in this tenant scope.",
}
