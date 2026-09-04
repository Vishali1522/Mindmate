import os
import re
import io
import json
import uuid
import base64
import hashlib
import secrets
from datetime import datetime, date, timedelta
from typing import Optional, Dict, List, Any

import streamlit as st
import pandas as pd
import numpy as np

# Optional cloud database
try:
    from supabase import create_client, Client
except Exception:
    create_client = None
    Client = Any

# Optional AI study helper
try:
    from google import genai
    from google.genai import types
except Exception:
    genai = None
    types = None


# ============================================================
# PAGE / APP CONFIG
# ============================================================
st.set_page_config(
    page_title="MindMate",
    page_icon="🧠",
    layout="wide",
    initial_sidebar_state="expanded",
)

APP_NAME = "MindMate"
APP_VERSION = "2.0"
PBKDF2_ITERATIONS = 310_000

PRESSURE_FIELDS = {
    "Study / exam pressure": "study_pressure",
    "Marks / result pressure": "marks_pressure",
    "Family / parent expectations": "family_pressure",
    "Peer / comparison pressure": "peer_pressure",
    "Workload / deadlines": "workload_pressure",
    "Free / personal time": "free_time",
    "Sleep routine": "sleep",
}

PRESSURE_KEYS = [
    "study_pressure",
    "marks_pressure",
    "family_pressure",
    "peer_pressure",
    "workload_pressure",
]

KEYWORDS = {
    "Study": [
        "study", "exam", "exams", "test", "tests", "revision", "syllabus",
        "homework", "assignment", "padhai", "exam pressure", "paper",
    ],
    "Marks": [
        "marks", "result", "grade", "grades", "score", "percentage",
        "rank", "fail", "top", "marks pressure",
    ],
    "Family": [
        "family", "parent", "parents", "mother", "father", "mom", "dad",
        "expectation", "ghar", "mummy", "papa",
    ],
    "Peer": [
        "friend", "friends", "peer", "comparison", "compare", "classmate",
        "competition", "jealous", "pressure from friends",
    ],
    "Workload": [
        "workload", "deadline", "deadlines", "busy", "too much work",
        "projects", "tasks", "schedule", "overload",
    ],
}


# ============================================================
# CSS / THEME
# ============================================================
def inject_css(theme: str = "System"):
    if theme == "Light":
        bg = "#f6f8fc"
        card = "#ffffff"
        text = "#172033"
        muted = "#667085"
        border = "#e5e7eb"
    elif theme == "Dark":
        bg = "#0b1220"
        card = "#111a2e"
        text = "#f3f6fb"
        muted = "#a9b4c7"
        border = "#26344d"
    else:
        bg = "#f6f8fc"
        card = "#ffffff"
        text = "#172033"
        muted = "#667085"
        border = "#e5e7eb"

    dark_override = ""
    if theme == "System":
        dark_override = """
        @media (prefers-color-scheme: dark) {
            :root {
                --mm-bg: #0b1220;
                --mm-card: #111a2e;
                --mm-text: #f3f6fb;
                --mm-muted: #a9b4c7;
                --mm-border: #26344d;
            }
        }
        """

    st.markdown(
        f"""
        <style>
        :root {{
            --mm-bg: {bg};
            --mm-card: {card};
            --mm-text: {text};
            --mm-muted: {muted};
            --mm-border: {border};
            --mm-accent: #6d5dfc;
            --mm-accent2: #3b82f6;
            --mm-success: #16a34a;
            --mm-warning: #d97706;
            --mm-danger: #dc2626;
        }}
        {dark_override}

        .stApp {{
            background: var(--mm-bg);
            color: var(--mm-text);
        }}

        [data-testid="stHeader"] {{
            background: transparent;
        }}

        [data-testid="stSidebar"] {{
            background: var(--mm-card);
            border-right: 1px solid var(--mm-border);
        }}

        .mm-hero {{
            padding: 28px 30px;
            border: 1px solid var(--mm-border);
            border-radius: 24px;
            background: var(--mm-card);
            margin-bottom: 20px;
        }}

        .mm-title {{
            font-size: clamp(2rem, 5vw, 3.2rem);
            font-weight: 800;
            line-height: 1.05;
            margin: 0;
            color: var(--mm-text);
        }}

        .mm-subtitle {{
            color: var(--mm-muted);
            font-size: 1.05rem;
            margin-top: 10px;
        }}

        .mm-card {{
            background: var(--mm-card);
            border: 1px solid var(--mm-border);
            border-radius: 18px;
            padding: 18px;
            margin: 8px 0;
        }}

        .mm-stat {{
            background: var(--mm-card);
            border: 1px solid var(--mm-border);
            border-radius: 18px;
            padding: 18px;
            min-height: 115px;
        }}

        .mm-stat-label {{
            color: var(--mm-muted);
            font-size: .86rem;
        }}

        .mm-stat-value {{
            color: var(--mm-text);
            font-size: 1.65rem;
            font-weight: 800;
            margin-top: 5px;
        }}

        .mm-muted {{
            color: var(--mm-muted);
        }}

        .mm-small {{
            font-size: .84rem;
            color: var(--mm-muted);
        }}

        .mm-badge {{
            display: inline-block;
            padding: 5px 10px;
            border-radius: 999px;
            font-size: .8rem;
            font-weight: 700;
            border: 1px solid var(--mm-border);
            margin-right: 5px;
        }}

        .mm-divider {{
            height: 1px;
            background: var(--mm-border);
            margin: 16px 0;
        }}

        .stButton > button {{
            border-radius: 12px;
            min-height: 42px;
            font-weight: 650;
        }}

        .stTextInput input, .stTextArea textarea {{
            border-radius: 12px;
        }}

        .stSelectbox div[data-baseweb="select"] > div {{
            border-radius: 12px;
        }}

        @media (max-width: 800px) {{
            .mm-hero {{
                padding: 20px;
                border-radius: 18px;
            }}
        }}
        </style>
        """,
        unsafe_allow_html=True,
    )


# ============================================================
# SECURITY HELPERS
# ============================================================
def hash_secret(value: str) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac(
        "sha256",
        value.encode("utf-8"),
        salt,
        PBKDF2_ITERATIONS,
    )
    return f"{base64.b64encode(salt).decode()}${base64.b64encode(digest).decode()}"


def verify_secret(value: str, stored: str) -> bool:
    try:
        salt_b64, digest_b64 = stored.split("$", 1)
        salt = base64.b64decode(salt_b64)
        expected = base64.b64decode(digest_b64)
        actual = hashlib.pbkdf2_hmac(
            "sha256",
            value.encode("utf-8"),
            salt,
            PBKDF2_ITERATIONS,
        )
        return secrets.compare_digest(actual, expected)
    except Exception:
        return False


def normalize_id(value: str) -> str:
    return re.sub(r"[^A-Z0-9]", "", value.upper())


def generate_mindmate_id() -> str:
    return "MM-" + secrets.token_hex(4).upper()


def valid_password(password: str) -> bool:
    return 8 <= len(password) <= 72


def valid_pin(pin: str) -> bool:
    return bool(re.fullmatch(r"\d{6}", pin))


# ============================================================
# DATABASE LAYER
# ============================================================
def get_supabase() -> Optional[Client]:
    if create_client is None:
        return None
    try:
        url = st.secrets.get("SUPABASE_URL", os.getenv("SUPABASE_URL", ""))
        key = st.secrets.get("SUPABASE_KEY", os.getenv("SUPABASE_KEY", ""))
        if url and key:
            return create_client(url, key)
    except Exception:
        return None
    return None


@st.cache_resource
def cached_supabase():
    return get_supabase()


def db_mode() -> str:
    return "cloud" if cached_supabase() is not None else "local-demo"


def local_db_init():
    # Demo fallback only. Streamlit Cloud local files are not permanent.
    import sqlite3
    conn = sqlite3.connect("mindmate_demo.db", check_same_thread=False)
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS users (
            mindmate_id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            age INTEGER,
            class_name TEXT,
            subjects TEXT,
            password_hash TEXT NOT NULL,
            recovery_hash TEXT NOT NULL,
            theme TEXT DEFAULT 'System',
            created_at TEXT NOT NULL
        )
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS checkins (
            id TEXT PRIMARY KEY,
            mindmate_id TEXT NOT NULL,
            created_at TEXT NOT NULL,
            study_pressure INTEGER,
            marks_pressure INTEGER,
            family_pressure INTEGER,
            peer_pressure INTEGER,
            workload_pressure INTEGER,
            free_time INTEGER,
            sleep INTEGER,
            stress_score REAL,
            category TEXT,
            detected_factors TEXT,
            feeling_text TEXT
        )
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS todos (
            id TEXT PRIMARY KEY,
            mindmate_id TEXT NOT NULL,
            task TEXT NOT NULL,
            done INTEGER DEFAULT 0,
            created_at TEXT NOT NULL
        )
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS timetables (
            id TEXT PRIMARY KEY,
            mindmate_id TEXT NOT NULL,
            title TEXT NOT NULL,
            schedule_json TEXT NOT NULL,
            created_at TEXT NOT NULL
        )
    """)
    conn.commit()
    return conn


def local_query(sql: str, params=(), fetch=False):
    conn = local_db_init()
    cur = conn.cursor()
    cur.execute(sql, params)
    rows = cur.fetchall() if fetch else None
    conn.commit()
    conn.close()
    return rows


def db_insert(table: str, data: Dict[str, Any]):
    sb = cached_supabase()
    if sb:
        sb.table(table).insert(data).execute()
        return
    cols = ", ".join(data.keys())
    placeholders = ", ".join(["?"] * len(data))
    local_query(
        f"INSERT INTO {table} ({cols}) VALUES ({placeholders})",
        tuple(data.values()),
    )


def db_update(table: str, data: Dict[str, Any], match: Dict[str, Any]):
    sb = cached_supabase()
    if sb:
        q = sb.table(table).update(data)
        for k, v in match.items():
            q = q.eq(k, v)
        q.execute()
        return
    set_sql = ", ".join([f"{k}=?" for k in data])
    where_sql = " AND ".join([f"{k}=?" for k in match])
    local_query(
        f"UPDATE {table} SET {set_sql} WHERE {where_sql}",
        tuple(data.values()) + tuple(match.values()),
    )


def db_delete(table: str, match: Dict[str, Any]):
    sb = cached_supabase()
    if sb:
        q = sb.table(table).delete()
        for k, v in match.items():
            q = q.eq(k, v)
        q.execute()
        return
    where_sql = " AND ".join([f"{k}=?" for k in match])
    local_query(
        f"DELETE FROM {table} WHERE {where_sql}",
        tuple(match.values()),
    )


def db_select(table: str, match: Dict[str, Any], order_by: Optional[str] = None, ascending=False, limit: Optional[int] = None):
    sb = cached_supabase()
    if sb:
        q = sb.table(table).select("*")
        for k, v in match.items():
            q = q.eq(k, v)
        if order_by:
            q = q.order(order_by, desc=not ascending)
        if limit:
            q = q.limit(limit)
        result = q.execute()
        return result.data or []

    where_sql = " AND ".join([f"{k}=?" for k in match]) if match else "1=1"
    order_sql = f" ORDER BY {order_by} {'ASC' if ascending else 'DESC'}" if order_by else ""
    limit_sql = f" LIMIT {int(limit)}" if limit else ""
    rows = local_query(
        f"SELECT * FROM {table} WHERE {where_sql}{order_sql}{limit_sql}",
        tuple(match.values()),
        fetch=True,
    )
    # Convert SQLite tuples according to known table schemas.
    if table == "users":
        keys = ["mindmate_id","name","age","class_name","subjects","password_hash","recovery_hash","theme","created_at"]
    elif table == "checkins":
        keys = ["id","mindmate_id","created_at","study_pressure","marks_pressure","family_pressure","peer_pressure","workload_pressure","free_time","sleep","stress_score","category","detected_factors","feeling_text"]
    elif table == "todos":
        keys = ["id","mindmate_id","task","done","created_at"]
    elif table == "timetables":
        keys = ["id","mindmate_id","title","schedule_json","created_at"]
    else:
        return []
    return [dict(zip(keys, row)) for row in rows]


def db_user(mindmate_id: str):
    rows = db_select("users", {"mindmate_id": mindmate_id}, limit=1)
    return rows[0] if rows else None


def delete_user_everything(mindmate_id: str):
    # Delete child rows first.
    for table in ["checkins", "todos", "timetables"]:
        db_delete(table, {"mindmate_id": mindmate_id})
    db_delete("users", {"mindmate_id": mindmate_id})


# ============================================================
# ANALYTICS / NLP
# ============================================================
def detect_factors(text: str) -> List[str]:
    text = (text or "").lower()
    found = []
    for category, words in KEYWORDS.items():
        if any(word in text for word in words):
            found.append(category)
    return found


def calculate_stress(values: Dict[str, int]) -> float:
    pressure_mean = np.mean([values[k] for k in PRESSURE_KEYS])
    balance_penalty = (5 - values["free_time"]) * 2 + (5 - values["sleep"]) * 2
    return float(np.clip(pressure_mean * 20 + balance_penalty, 0, 100))


def stress_category(score: float) -> str:
    if score < 35:
        return "Low"
    if score < 60:
        return "Moderate"
    if score < 80:
        return "High"
    return "Very High"


def suggestions(values: Dict[str, int]) -> List[str]:
    tips = []
    if values["study_pressure"] >= 4:
        tips.append("Break large study goals into smaller 25–45 minute sessions.")
    if values["marks_pressure"] >= 4:
        tips.append("Focus on controllable actions: practice, revision and asking for help.")
    if values["family_pressure"] >= 4:
        tips.append("If comfortable, explain your workload and goals to a trusted adult.")
    if values["peer_pressure"] >= 4:
        tips.append("Avoid constant comparison; track your own progress instead.")
    if values["workload_pressure"] >= 4:
        tips.append("Prioritize tasks by urgency and importance rather than doing everything at once.")
    if values["free_time"] <= 2:
        tips.append("Protect a little daily personal time for rest or a hobby.")
    if values["sleep"] <= 2:
        tips.append("Try to keep a consistent sleep routine and wind down before bed.")
    if not tips:
        tips = [
            "Keep your current routine balanced.",
            "Review your priorities once a day.",
            "Use the timetable and to-do tools to reduce last-minute workload.",
        ]
    return tips[:5]


def balance_score(values: Dict[str, int]) -> int:
    score = (values["free_time"] + values["sleep"]) / 10 * 100
    return int(round(score))


# ============================================================
# SESSION / AUTH
# ============================================================
def init_state():
    defaults = {
        "authenticated": False,
        "mindmate_id": None,
        "page": "Home",
        "theme": "System",
        "login_attempts": 0,
        "last_checkin": None,
        "flash": None,
    }
    for key, value in defaults.items():
        st.session_state.setdefault(key, value)


def logout():
    for key in ["authenticated", "mindmate_id", "page", "last_checkin"]:
        st.session_state[key] = False if key == "authenticated" else None
    st.session_state["page"] = "Home"
    st.rerun()


# ============================================================
# AUTH SCREENS
# ============================================================
def create_account():
    st.markdown(
        """
        <div class="mm-hero">
            <div class="mm-title">🧠 MindMate</div>
            <div class="mm-subtitle">A personal space for planning, study support and everyday well-being.</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.subheader("Create your MindMate account")
    st.caption("Your password is stored as a one-way cryptographic hash, not as plain text.")

    with st.form("create_account_form"):
        name = st.text_input("Name", max_chars=60)
        age = st.number_input("Age", min_value=10, max_value=100, value=16, step=1)
        class_name = st.text_input("Class / level (optional)", max_chars=50)
        subjects = st.text_input("Subjects / interests (optional)", max_chars=200)
        password = st.text_input("Create password", type="password", max_chars=72)
        recovery = st.text_input("6-digit recovery PIN", type="password", max_chars=6)
        agree = st.checkbox("I understand that my check-ins and app data will be saved to my MindMate account.")
        submitted = st.form_submit_button("Create MindMate ID", type="primary", use_container_width=True)

    if submitted:
        if not name.strip():
            st.error("Please enter your name.")
            return
        if not valid_password(password):
            st.error("Password must be 8–72 characters.")
            return
        if not valid_pin(recovery):
            st.error("Recovery PIN must be exactly 6 digits.")
            return
        if not agree:
            st.error("Please confirm the data-storage notice to continue.")
            return

        mindmate_id = generate_mindmate_id()
        while db_user(mindmate_id):
            mindmate_id = generate_mindmate_id()

        db_insert(
            "users",
            {
                "mindmate_id": mindmate_id,
                "name": name.strip(),
                "age": int(age),
                "class_name": class_name.strip(),
                "subjects": subjects.strip(),
                "password_hash": hash_secret(password),
                "recovery_hash": hash_secret(recovery),
                "theme": "System",
                "created_at": datetime.utcnow().isoformat(),
            },
        )

        st.success("Account created successfully.")
        st.info(f"Your MindMate ID is: {mindmate_id}")
        st.code(mindmate_id)
        st.caption("Save this ID somewhere safe. It is required to sign in again.")
        if st.button("Continue to Login", type="primary"):
            st.session_state["show_create"] = False
            st.rerun()


def login_screen():
    st.markdown(
        """
        <div class="mm-hero">
            <div class="mm-title">🧠 MindMate</div>
            <div class="mm-subtitle">Your personal AI-powered space for study, planning and well-being.</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    tab1, tab2 = st.tabs(["Sign in", "Create account"])

    with tab1:
        with st.form("login_form"):
            mid = st.text_input("MindMate ID", placeholder="MM-XXXXXXXX")
            password = st.text_input("Password", type="password")
            submitted = st.form_submit_button("Sign in", type="primary", use_container_width=True)

        if submitted:
            mid = normalize_id(mid)
            user = db_user(mid)
            if user and verify_secret(password, user["password_hash"]):
                st.session_state["authenticated"] = True
                st.session_state["mindmate_id"] = mid
                st.session_state["theme"] = user.get("theme") or "System"
                st.session_state["page"] = "Home"
                st.rerun()
            else:
                st.session_state["login_attempts"] += 1
                st.error("MindMate ID or password is incorrect.")

        st.divider()
        with st.expander("Forgot password?"):
            recovery_id = st.text_input("MindMate ID", key="recovery_id")
            recovery_pin = st.text_input("6-digit recovery PIN", type="password", key="recovery_pin")
            new_password = st.text_input("New password", type="password", key="new_password")
            if st.button("Reset password"):
                user = db_user(normalize_id(recovery_id))
                if not user:
                    st.error("Account not found.")
                elif not valid_pin(recovery_pin) or not verify_secret(recovery_pin, user["recovery_hash"]):
                    st.error("Recovery details are incorrect.")
                elif not valid_password(new_password):
                    st.error("New password must be 8–72 characters.")
                else:
                    db_update(
                        "users",
                        {"password_hash": hash_secret(new_password)},
                        {"mindmate_id": normalize_id(recovery_id)},
                    )
                    st.success("Password updated. You can sign in now.")

    with tab2:
        create_account()


# ============================================================
# SIDEBAR / NAV
# ============================================================
def render_sidebar(user):
    with st.sidebar:
        st.markdown("## 🧠 MindMate")
        st.caption(f"Hi, {user['name']}")

        pages = [
            "Home",
            "Check-in",
            "Dashboard",
            "Timetable",
            "To-do",
            "Study Help",
            "Settings",
        ]
        current = st.session_state.get("page", "Home")
        page = st.radio("Navigate", pages, index=pages.index(current) if current in pages else 0)
        if page != current:
            st.session_state["page"] = page
            st.rerun()

        st.divider()
        st.caption(f"MindMate ID: {user['mindmate_id']}")
        st.caption(f"Mode: {'Cloud database' if db_mode() == 'cloud' else 'Local demo storage'}")

        if st.button("Log out", use_container_width=True):
            logout()


# ============================================================
# HOME
# ============================================================
def page_home(user):
    checkins = db_select(
        "checkins",
        {"mindmate_id": user["mindmate_id"]},
        order_by="created_at",
        limit=1,
    )

    st.markdown(
        f"""
        <div class="mm-hero">
            <div class="mm-title">Welcome back, {user['name']} 👋</div>
            <div class="mm-subtitle">
                Keep your day organized, understand your pressure patterns, and get study support when you need it.
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    if db_mode() != "cloud":
        st.warning(
            "Demo storage is active. For permanent private multi-user data on Streamlit Cloud, connect Supabase using the Secrets shown below."
        )

    if checkins:
        last = checkins[0]
        cols = st.columns(4)
        stats = [
            ("Latest indicator", f"{float(last['stress_score']):.0f}/100"),
            ("Category", last["category"]),
            ("Balance", f"{balance_score(last)}%"),
            ("Check-ins", str(len(db_select("checkins", {"mindmate_id": user["mindmate_id"]})))),
        ]
        for col, (label, value) in zip(cols, stats):
            with col:
                st.markdown(
                    f'<div class="mm-stat"><div class="mm-stat-label">{label}</div><div class="mm-stat-value">{value}</div></div>',
                    unsafe_allow_html=True,
                )
    else:
        st.info("You haven't completed a check-in yet. Start one to unlock your dashboard.")

    st.subheader("Quick actions")
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        if st.button("🧠 Check-in", use_container_width=True):
            st.session_state["page"] = "Check-in"
            st.rerun()
    with c2:
        if st.button("📊 Dashboard", use_container_width=True):
            st.session_state["page"] = "Dashboard"
            st.rerun()
    with c3:
        if st.button("📚 Study Help", use_container_width=True):
            st.session_state["page"] = "Study Help"
            st.rerun()
    with c4:
        if st.button("🗓️ Timetable", use_container_width=True):
            st.session_state["page"] = "Timetable"
            st.rerun()

    st.subheader("What MindMate can do")
    features = [
        ("🧠 Well-being check-in", "Estimate a simple project stress indicator from your self-reported inputs."),
        ("🔎 NLP factor detection", "Identify common themes in your written check-in."),
        ("📊 Personal analytics", "See your own trends and pressure breakdown over time."),
        ("🗓️ Planning", "Build and save a balanced timetable."),
        ("✅ To-do", "Keep tasks in one private list."),
        ("📷 Study Help", "Upload a question image and ask the AI to explain it."),
    ]
    for title, desc in features:
        st.markdown(
            f'<div class="mm-card"><b>{title}</b><br><span class="mm-muted">{desc}</span></div>',
            unsafe_allow_html=True,
        )

    st.caption("MindMate is an educational/support project. It does not diagnose mental-health conditions and is not a substitute for a trusted adult, counselor or healthcare professional.")


# ============================================================
# CHECK-IN
# ============================================================
def page_checkin(user):
    st.title("🧠 Daily Check-in")
    st.caption("Rate each area from 0 (not a problem) to 5 (very high). For free time and sleep, higher numbers mean better balance.")

    with st.form("checkin_form"):
        values = {}
        cols = st.columns(2)
        for i, (label, key) in enumerate(PRESSURE_FIELDS.items()):
            with cols[i % 2]:
                if key in ["free_time", "sleep"]:
                    help_text = "0 = very low, 5 = very good"
                else:
                    help_text = "0 = very low, 5 = very high"
                values[key] = st.slider(label, 0, 5, 2, help=help_text)

        feeling = st.text_area(
            "How are you feeling? (English / Hinglish)",
            placeholder="Example: Exams are close and I am worried about marks...",
            max_chars=1500,
        )
        submitted = st.form_submit_button("Analyze my check-in", type="primary", use_container_width=True)

    if submitted:
        score = calculate_stress(values)
        category = stress_category(score)
        factors = detect_factors(feeling)

        row = {
            "id": str(uuid.uuid4()),
            "mindmate_id": user["mindmate_id"],
            "created_at": datetime.utcnow().isoformat(),
            **values,
            "stress_score": score,
            "category": category,
            "detected_factors": json.dumps(factors),
            "feeling_text": feeling.strip(),
        }
        db_insert("checkins", row)
        st.session_state["last_checkin"] = row

        st.success("Check-in saved to your account.")
        st.subheader(f"Your project stress indicator: {score:.0f}/100")
        st.progress(min(score / 100, 1.0))
        st.write(f"**Category:** {category}")

        if category in ["High", "Very High"]:
            st.warning("Your answers suggest a higher current pressure level. Consider reducing overload and talking to a trusted adult or support person if you feel you need help.")

        top = sorted(
            [(k.replace("_pressure", "").replace("_", " ").title(), values[k]) for k in PRESSURE_KEYS],
            key=lambda x: x[1],
            reverse=True,
        )[:2]
        st.write("**Top pressure areas:** " + ", ".join(f"{name} ({value}/5)" for name, value in top))

        if factors:
            st.write("**NLP-detected themes:** " + ", ".join(factors))
        else:
            st.write("**NLP-detected themes:** None detected from the text.")

        st.subheader("Personalized suggestions")
        for tip in suggestions(values):
            st.markdown(f"- {tip}")

        if st.button("Open Dashboard"):
            st.session_state["page"] = "Dashboard"
            st.rerun()


# ============================================================
# DASHBOARD
# ============================================================
def page_dashboard(user):
    st.title("📊 Your Dashboard")
    rows = db_select(
        "checkins",
        {"mindmate_id": user["mindmate_id"]},
        order_by="created_at",
        ascending=True,
    )
    if not rows:
        st.info("Complete at least one check-in to see your dashboard.")
        return

    df = pd.DataFrame(rows)
    df["created_at"] = pd.to_datetime(df["created_at"], errors="coerce")
    df["stress_score"] = pd.to_numeric(df["stress_score"], errors="coerce")

    latest = df.iloc[-1]
    c1, c2, c3 = st.columns(3)
    with c1:
        st.metric("Latest indicator", f"{latest['stress_score']:.0f}/100")
    with c2:
        st.metric("Current category", str(latest["category"]))
    with c3:
        st.metric("Average indicator", f"{df['stress_score'].mean():.0f}/100")

    st.subheader("Trend")
    chart_df = df[["created_at", "stress_score"]].set_index("created_at")
    st.line_chart(chart_df)

    st.subheader("Pressure breakdown")
    breakdown = pd.DataFrame({
        "Area": [
            "Study", "Marks", "Family", "Peer", "Workload",
            "Free time", "Sleep"
        ],
        "Average": [
            df["study_pressure"].mean(),
            df["marks_pressure"].mean(),
            df["family_pressure"].mean(),
            df["peer_pressure"].mean(),
            df["workload_pressure"].mean(),
            df["free_time"].mean(),
            df["sleep"].mean(),
        ],
    }).set_index("Area")
    st.bar_chart(breakdown)

    st.subheader("Recent check-ins")
    show = df[[
        "created_at", "stress_score", "category",
        "study_pressure", "marks_pressure", "family_pressure",
        "peer_pressure", "workload_pressure", "free_time", "sleep"
    ]].copy()
    show["created_at"] = show["created_at"].dt.strftime("%d %b %Y, %I:%M %p")
    st.dataframe(show.iloc[::-1], use_container_width=True, hide_index=True)


# ============================================================
# TIMETABLE
# ============================================================
def parse_time(text: str):
    return datetime.strptime(text.strip(), "%H:%M")


def page_timetable(user):
    st.title("🗓️ Timetable")
    st.caption("Create a practical schedule with study blocks, breaks and personal time.")

    with st.form("timetable_form"):
        title = st.text_input("Timetable name", value="My Balanced Day")
        wake = st.time_input("Wake-up time", value=datetime.strptime("06:00", "%H:%M").time())
        sleep = st.time_input("Sleep time", value=datetime.strptime("22:30", "%H:%M").time())
        school_start = st.time_input("School / main work start", value=datetime.strptime("08:00", "%H:%M").time())
        school_end = st.time_input("School / main work end", value=datetime.strptime("14:00", "%H:%M").time())
        tuition = st.checkbox("Add tuition / coaching block")
        if tuition:
            tuition_start = st.time_input("Tuition start", value=datetime.strptime("16:00", "%H:%M").time())
            tuition_end = st.time_input("Tuition end", value=datetime.strptime("17:30", "%H:%M").time())
        else:
            tuition_start = tuition_end = None

        subjects = st.text_input("Subjects (comma-separated)", value="Accountancy, Mathematics, Business Studies, Economics")
        study_minutes = st.select_slider("Study session length", options=[25, 30, 40, 45, 50, 60], value=45)
        break_minutes = st.select_slider("Break length", options=[5, 10, 15, 20], value=10)

        generate = st.form_submit_button("Generate timetable", type="primary", use_container_width=True)

    if generate:
        subject_list = [s.strip() for s in subjects.split(",") if s.strip()]
        if not subject_list:
            st.error("Add at least one subject.")
            return

        # Build a simple daytime plan. Fixed blocks are kept intact.
        rows = []
        rows.append({"Time": wake.strftime("%H:%M"), "Activity": "Wake up + morning routine"})
        rows.append({"Time": school_start.strftime("%H:%M") + "–" + school_end.strftime("%H:%M"), "Activity": "School / main work"})
        if tuition and tuition_start and tuition_end:
            rows.append({"Time": tuition_start.strftime("%H:%M") + "–" + tuition_end.strftime("%H:%M"), "Activity": "Tuition / coaching"})

        # Four focused sessions after main commitments, placed as a recommended plan.
        session_start = datetime.combine(date.today(), datetime.strptime("18:00", "%H:%M").time())
        for i, subject in enumerate(subject_list[:4]):
            start = session_start + timedelta(minutes=i * (study_minutes + break_minutes))
            end = start + timedelta(minutes=study_minutes)
            rows.append({
                "Time": f"{start.strftime('%H:%M')}–{end.strftime('%H:%M')}",
                "Activity": f"Focused study: {subject}",
            })

        rows.extend([
            {"Time": "20:00", "Activity": "Dinner + screen break"},
            {"Time": "20:30", "Activity": "Light revision / homework"},
            {"Time": "21:30", "Activity": "Personal time + prepare for tomorrow"},
            {"Time": sleep.strftime("%H:%M"), "Activity": "Wind down + sleep"},
        ])

        # Sort only entries that begin with a time; preserve readability.
        schedule_json = json.dumps(rows)
        db_insert(
            "timetables",
            {
                "id": str(uuid.uuid4()),
                "mindmate_id": user["mindmate_id"],
                "title": title.strip() or "My Timetable",
                "schedule_json": schedule_json,
                "created_at": datetime.utcnow().isoformat(),
            },
        )

        st.success("Timetable saved.")
        st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)

    saved = db_select(
        "timetables",
        {"mindmate_id": user["mindmate_id"]},
        order_by="created_at",
        limit=10,
    )
    if saved:
        st.subheader("Saved timetables")
        for item in saved:
            with st.expander(f"{item['title']} • {str(item['created_at'])[:10]}"):
                try:
                    data = json.loads(item["schedule_json"])
                    st.dataframe(pd.DataFrame(data), use_container_width=True, hide_index=True)
                except Exception:
                    st.write(item["schedule_json"])


# ============================================================
# TO-DO
# ============================================================
def page_todo(user):
    st.title("✅ To-do")
    st.caption("Your tasks are private to your MindMate account.")

    with st.form("todo_form", clear_on_submit=True):
        task = st.text_input("Add a task", max_chars=200)
        add = st.form_submit_button("Add task", type="primary")
    if add and task.strip():
        db_insert(
            "todos",
            {
                "id": str(uuid.uuid4()),
                "mindmate_id": user["mindmate_id"],
                "task": task.strip(),
                "done": 0,
                "created_at": datetime.utcnow().isoformat(),
            },
        )
        st.rerun()

    todos = db_select(
        "todos",
        {"mindmate_id": user["mindmate_id"]},
        order_by="created_at",
        ascending=True,
    )
    if not todos:
        st.info("No tasks yet.")
        return

    for item in todos:
        done = bool(item["done"])
        c1, c2 = st.columns([8, 1])
        with c1:
            new_done = st.checkbox(item["task"], value=done, key=f"todo_{item['id']}")
        with c2:
            if st.button("🗑️", key=f"del_{item['id']}"):
                db_delete("todos", {"id": item["id"], "mindmate_id": user["mindmate_id"]})
                st.rerun()
        if new_done != done:
            db_update("todos", {"done": int(new_done)}, {"id": item["id"], "mindmate_id": user["mindmate_id"]})


# ============================================================
# AI STUDY HELP
# ============================================================
def get_gemini_client():
    if genai is None:
        return None
    try:
        key = st.secrets.get("GEMINI_API_KEY", os.getenv("GEMINI_API_KEY", ""))
        if key:
            return genai.Client(api_key=key)
    except Exception:
        return None
    return None


def extract_sources(response) -> List[Dict[str, str]]:
    sources = []
    try:
        candidates = getattr(response, "candidates", None) or []
        if not candidates:
            return sources
        metadata = getattr(candidates[0], "grounding_metadata", None)
        chunks = getattr(metadata, "grounding_chunks", None) or []
        for chunk in chunks:
            web_chunk = getattr(chunk, "web", None)
            if web_chunk:
                uri = getattr(web_chunk, "uri", None)
                title = getattr(web_chunk, "title", None)
                if uri:
                    sources.append({"title": title or uri, "uri": uri})
    except Exception:
        pass

    # Deduplicate
    unique = []
    seen = set()
    for s in sources:
        if s["uri"] not in seen:
            unique.append(s)
            seen.add(s["uri"])
    return unique[:8]


def ai_solve_image(image_bytes: bytes, mime_type: str, user_prompt: str):
    client = get_gemini_client()
    if client is None:
        return None, [], "Gemini API is not configured."

    try:
        image_part = types.Part.from_bytes(
            data=image_bytes,
            mime_type=mime_type,
        )
        prompt = f"""
You are MindMate's study assistant.

Read the uploaded question carefully. Solve the problem accurately and explain it step by step in clear, age-appropriate language.
If the image is unclear, say what part is unclear instead of inventing details.
Use Google Search grounding when current, factual, textbook/reference, or verification information is useful.
Prefer reliable educational or official sources when available.
Do not copy long copyrighted passages. Summarize or solve in your own words.
Return:
1. What the question is asking
2. Step-by-step solution
3. Final answer clearly marked
4. A short concept/tip
User's optional note: {user_prompt}
"""
        response = client.models.generate_content(
            model="gemini-3.7-flash",
            contents=[image_part, prompt],
            config=types.GenerateContentConfig(
                tools=[types.Tool(google_search=types.GoogleSearch())]
            ),
        )
        text = getattr(response, "text", None) or "No answer was returned."
        return text, extract_sources(response), None
    except Exception as exc:
        return None, [], f"AI request failed: {exc}"


def page_study_help(user):
    st.title("📷 Study Help")
    st.caption("Upload a photo of a question → scan it → get an explained answer. No separate AI-site login is required.")

    if get_gemini_client() is None:
        st.info("AI Study Help is currently unavailable because GEMINI_API_KEY is not configured in Streamlit Secrets.")

    uploaded = st.file_uploader(
        "Upload a question image",
        type=["png", "jpg", "jpeg", "webp"],
        help="Use a clear, well-lit photo with the full question visible.",
    )
    note = st.text_input("Optional instruction", placeholder="Example: Explain it in simple Class 11 language.")

    if uploaded:
        st.image(uploaded, caption="Question image", use_container_width=True)
        if st.button("🔍 Scan & Solve", type="primary", use_container_width=True):
            data = uploaded.getvalue()
            mime = uploaded.type or "image/jpeg"
            with st.spinner("Reading the question and preparing the solution..."):
                answer, sources, error = ai_solve_image(data, mime, note)

            if error:
                st.error(error)
            else:
                st.subheader("Solution")
                st.markdown(answer)
                if sources:
                    st.subheader("Web sources used")
                    for source in sources:
                        st.markdown(f"- [{source['title']}]({source['uri']})")

    st.divider()
    st.caption("AI can make mistakes. For important schoolwork, compare the solution with your textbook/teacher's guidance.")


# ============================================================
# SETTINGS
# ============================================================
def page_settings(user):
    st.title("⚙️ Settings")

    st.subheader("Appearance")
    current_theme = user.get("theme") or "System"
    theme = st.selectbox("Theme", ["System", "Light", "Dark"], index=["System", "Light", "Dark"].index(current_theme))
    if theme != current_theme:
        db_update("users", {"theme": theme}, {"mindmate_id": user["mindmate_id"]})
        st.session_state["theme"] = theme
        st.rerun()

    st.subheader("Profile")
    with st.form("profile_form"):
        name = st.text_input("Name", value=user.get("name", ""), max_chars=60)
        age = st.number_input("Age", min_value=10, max_value=100, value=int(user.get("age") or 16))
        class_name = st.text_input("Class / level", value=user.get("class_name", ""), max_chars=50)
        subjects = st.text_input("Subjects / interests", value=user.get("subjects", ""), max_chars=200)
        save_profile = st.form_submit_button("Save profile")
    if save_profile:
        db_update(
            "users",
            {
                "name": name.strip(),
                "age": int(age),
                "class_name": class_name.strip(),
                "subjects": subjects.strip(),
            },
            {"mindmate_id": user["mindmate_id"]},
        )
        st.success("Profile updated.")

    st.subheader("Security")
    with st.form("password_change_form"):
        old_password = st.text_input("Current password", type="password")
        new_password = st.text_input("New password", type="password")
        change_password = st.form_submit_button("Change password")
    if change_password:
        if not verify_secret(old_password, user["password_hash"]):
            st.error("Current password is incorrect.")
        elif not valid_password(new_password):
            st.error("New password must be 8–72 characters.")
        else:
            db_update(
                "users",
                {"password_hash": hash_secret(new_password)},
                {"mindmate_id": user["mindmate_id"]},
            )
            st.success("Password changed successfully.")

    st.subheader("Your data")
    checkins = db_select("checkins", {"mindmate_id": user["mindmate_id"]})
    todos = db_select("todos", {"mindmate_id": user["mindmate_id"]})
    timetables = db_select("timetables", {"mindmate_id": user["mindmate_id"]})
    st.write(
        f"Check-ins: **{len(checkins)}** · To-dos: **{len(todos)}** · Timetables: **{len(timetables)}**"
    )

    with st.expander("Delete my account and all my MindMate data"):
        st.warning("This permanently removes your account, check-ins, tasks and saved timetables.")
        confirm = st.checkbox("I understand that this cannot be undone.")
        if st.button("Delete my account", type="secondary"):
            if not confirm:
                st.error("Please confirm first.")
            else:
                delete_user_everything(user["mindmate_id"])
                st.session_state.clear()
                st.success("Your MindMate data has been deleted.")
                st.rerun()

    st.subheader("About")
    st.caption(f"MindMate v{APP_VERSION}")
    st.caption("Educational project. Not a diagnostic or emergency service.")


# ============================================================
# MAIN
# ============================================================
init_state()

# Load theme before page rendering.
if st.session_state.get("authenticated") and st.session_state.get("mindmate_id"):
    current_user = db_user(st.session_state["mindmate_id"])
    if current_user:
        st.session_state["theme"] = current_user.get("theme") or "System"
        inject_css(st.session_state["theme"])
        render_sidebar(current_user)

        page = st.session_state.get("page", "Home")
        if page == "Home":
            page_home(current_user)
        elif page == "Check-in":
            page_checkin(current_user)
        elif page == "Dashboard":
            page_dashboard(current_user)
        elif page == "Timetable":
            page_timetable(current_user)
        elif page == "To-do":
            page_todo(current_user)
        elif page == "Study Help":
            page_study_help(current_user)
        elif page == "Settings":
            page_settings(current_user)
        else:
            page_home(current_user)
    else:
        st.session_state.clear()
        st.rerun()
else:
    inject_css("System")
    login_screen()

st.markdown(
    """
    <div style="text-align:center; padding:24px 0 10px 0;">
        <span class="mm-small">MindMate • Built with Python + Streamlit</span>
    </div>
    """,
    unsafe_allow_html=True,
)
