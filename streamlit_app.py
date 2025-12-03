import streamlit as st
import sqlite3
import datetime
import re

# ---------------------------
# Database setup
# ---------------------------

conn = sqlite3.connect("faculty_ratings.db", check_same_thread=False)
cur = conn.cursor()

def init_db():
    cur.execute("""
        CREATE TABLE IF NOT EXISTS faculty (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            department TEXT
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS rating (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            faculty_id INTEGER NOT NULL,
            leniency INTEGER NOT NULL,
            correction INTEGER NOT NULL,
            teaching INTEGER NOT NULL,
            internal_from INTEGER NOT NULL,
            internal_to INTEGER NOT NULL,
            comment TEXT,
            created_at TEXT NOT NULL,
            user_email TEXT,
            reg_no TEXT,
            FOREIGN KEY (faculty_id) REFERENCES faculty (id)
        )
    """)

    # --------- Migration for existing DB ---------
    cur.execute("PRAGMA table_info(rating)")
    cols = [col[1] for col in cur.fetchall()]

    def add_column_if_missing(col_name, col_type):
        if col_name not in cols:
            try:
                cur.execute(f"ALTER TABLE rating ADD COLUMN {col_name} {col_type}")
            except:
                pass

    add_column_if_missing("teaching", "INTEGER")
    add_column_if_missing("internal_from", "INTEGER")
    add_column_if_missing("internal_to", "INTEGER")
    add_column_if_missing("user_email", "TEXT")
    add_column_if_missing("reg_no", "TEXT")

    conn.commit()

init_db()

# ---------------------------
# Helper functions
# ---------------------------

def add_faculty(name, department):
    cur.execute("INSERT INTO faculty (name, department) VALUES (?, ?)",
                (name, department if department else None))
    conn.commit()

def get_all_faculty_with_avg():
    cur.execute("""
        SELECT f.id, f.name, f.department,
        AVG(r.leniency), AVG((r.internal_from + r.internal_to)/2.0),
        AVG(r.correction), AVG(r.teaching), COUNT(r.id)
        FROM faculty f
        LEFT JOIN rating r ON f.id = r.faculty_id
        GROUP BY f.id
        ORDER BY f.name ASC
    """)
    rows = cur.fetchall()
    result = []
    for r in rows:
        result.append({
            "id": r[0],
            "name": r[1],
            "department": r[2],
            "avg_leniency": round(r[3] or 0, 1),
            "avg_internal": round(r[4] or 0, 1),
            "avg_correction": round(r[5] or 0, 1),
            "avg_teaching": round(r[6] or 0, 1),
            "rating_count": r[7],
        })
    return result

def get_faculty_by_id(fid):
    cur.execute("SELECT id, name, department FROM faculty WHERE id = ?", (fid,))
    row = cur.fetchone()
    return {"id": row[0], "name": row[1], "department": row[2]} if row else None

def add_rating(fid, leniency, correction, teaching, internal_from, internal_to, comment, email, reg_no):
    cur.execute("""
        INSERT INTO rating (faculty_id, leniency, correction, teaching,
                            internal_from, internal_to, comment,
                            created_at, user_email, reg_no)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        fid, leniency, correction, teaching, internal_from, internal_to,
        comment if comment else None,
        datetime.datetime.now().isoformat(timespec="minutes"),
        email, reg_no
    ))
    conn.commit()

def get_ratings_for_faculty(fid):
    cur.execute("""
        SELECT leniency, correction, teaching,
               internal_from, internal_to,
               comment, created_at, reg_no
        FROM rating WHERE faculty_id = ?
        ORDER BY datetime(created_at) DESC
    """, (fid,))
    rows = cur.fetchall()
    result = []
    for r in rows:
        result.append({
            "leniency": r[0],
            "correction": r[1],
            "teaching": r[2],
            "internal_range": f"{r[3]} – {r[4]}",
            "comment": r[5],
            "created_at": r[6],
            "reg_no": r[7],
        })
    return result

def get_avg_for_faculty(fid):
    cur.execute("""
        SELECT AVG(leniency),
               AVG((internal_from + internal_to)/2.0),
               AVG(correction),
               AVG(teaching),
               COUNT(id)
        FROM rating WHERE faculty_id = ?
    """, (fid,))
    row = cur.fetchone()
    return {
        "avg_leniency": round(row[0] or 0, 1),
        "avg_internal": round(row[1] or 0, 1),
        "avg_correction": round(row[2] or 0, 1),
        "avg_teaching": round(row[3] or 0, 1),
        "rating_count": row[4]
    }

# ---------------------------
# Login Handling
# ---------------------------

def valid_email(email):
    return re.match(r"^[0-9]{9}\.simats@saveetha\.com$", email or "") is not None

def extract_reg_no(email):
    return email.split(".")[0]

def require_login():
    if not st.session_state.get("logged_in"):
        st.warning("Login required!")
        st.stop()

# ---------------------------
# Streamlit UI
# ---------------------------

st.set_page_config(page_title="Faculty Rating Portal", page_icon="⭐", layout="wide")

if "logged_in" not in st.session_state:
    st.session_state.logged_in = False

st.title("⭐ College Faculty Review System")
st.caption("Rate faculty based on multiple teaching parameters.")

# Sidebar
st.sidebar.subheader("Account")
if st.session_state.logged_in:
    st.sidebar.success(f"Logged in as {st.session_state.email}")
    if st.sidebar.button("Logout"):
        st.session_state.logged_in = False
        st.rerun()
else:
    st.sidebar.info("Not logged in")

page = st.sidebar.radio("Navigate", ["Login", "Add Faculty", "Rate Faculty", "About"])

# LOGIN PAGE
if page == "Login":
    st.header("🔐 Login")

    if not st.session_state.logged_in:
        with st.form("login_form"):
            email = st.text_input("College Email",
                                  placeholder="e.g., 123456789.simats@saveetha.com")
            ok = st.form_submit_button("Login")

            if ok:
                if not valid_email(email):
                    st.error("Invalid Email Format!")
                else:
                    st.session_state.logged_in = True
                    st.session_state.email = email
                    st.session_state.reg_no = extract_reg_no(email)
                    st.success("Login Successful!")
                    st.rerun()

    else:
        st.success(f"Already logged in as {st.session_state.email}")

# ADD FACULTY PAGE
elif page == "Add Faculty":
    require_login()
    st.header("➕ Add Faculty")

    with st.form("add_faculty"):
        name = st.text_input("Faculty Name*")
        dept = st.text_input("Department")
        submit = st.form_submit_button("Add Faculty")

        if submit:
            if name.strip():
                add_faculty(name, dept)
                st.success("Faculty Added!")
            else:
                st.error("Name is required!")

# RATE FACULTY PAGE
elif page == "Rate Faculty":
    require_login()
    st.header("📊 Faculty Ratings")

    data = get_all_faculty_with_avg()

    if not data:
        st.info("No faculty available.")
        st.stop()

    st.subheader("📋 Faculty Overview")
    st.dataframe(data, use_container_width=True)

    st.markdown("---")
    st.subheader("Rate Selected Faculty")

    names = {f"{d['name']} ({d['department']})": d["id"] for d in data}
    selected = st.selectbox("Select Faculty", names.keys())
    fid = names[selected]
    faculty = get_faculty_by_id(fid)
    avg = get_avg_for_faculty(fid)

    st.metric("Leniency Avg (1–10)", avg["avg_leniency"])
    st.metric("Internal Marks Avg (/100)", avg["avg_internal"])
    st.metric("Correction Avg (1–10)", avg["avg_correction"])
    st.metric("Teaching Avg (1–10)", avg["avg_teaching"])
    st.metric("Ratings Count", avg["rating_count"])

    st.markdown("### Submit a Rating")

    with st.form("rate"):
        leniency = st.number_input("Leniency (1–10)", 1, 10)
        correction = st.number_input("Correction (1–10)", 1, 10)
        teaching = st.number_input("Overall Teaching Experience (1–10)", 1, 10)
        int_from = st.number_input("Internal Marks From", 50, 100)
        int_to = st.number_input("Internal Marks To", 50, 100)
        comment = st.text_area("Comment (optional)")
        ok = st.form_submit_button("Submit Rating")

        if ok:
            if int_from > int_to:
                st.error("From cannot be greater than To!")
            else:
                add_rating(fid, leniency, correction, teaching,
                           int_from, int_to, comment,
                           st.session_state.email, st.session_state.reg_no)
                st.success("Rating Submitted!")

    st.markdown("---")
    st.subheader("Recent Ratings")

    ratings = get_ratings_for_faculty(fid)
    for r in ratings:
        st.write(
            f"**Leniency:** {r['leniency']} | **Correction:** {r['correction']} | "
            f"**Teaching:** {r['teaching']} | **Internal Marks:** {r['internal_range']}"
        )
        if r["comment"]:
            st.write(r["comment"])
        st.caption(f"Rated by: {r['reg_no']} • {r['created_at']}")
        st.markdown("---")

# ABOUT PAGE
elif page == "About":
    st.header("ℹ️ About this System")
    st.write("""
    This system allows students to review faculty based on:
    - **Leniency** (1–10)
    - **Internal Marks** (Range 50–100)
    - **Correction Strictness** (1–10)
    - **Overall Teaching Experience** (1–10)

    Login is restricted to **valid Saveetha University students**.
    """)

