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
    # Basic table (for fresh deployments)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS faculty (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            department TEXT
        )
    """)

    # Rating table with ALL columns (for new DBs)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS rating (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            faculty_id INTEGER NOT NULL,
            leniency INTEGER NOT NULL,
            internal_marks INTEGER NOT NULL,
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

    # --- Migration for existing DBs (old structure) ---
    cur.execute("PRAGMA table_info(rating)")
    cols = [col[1] for col in cur.fetchall()]

    def add_column_if_missing(name, col_type):
        if name not in cols:
            try:
                cur.execute(f"ALTER TABLE rating ADD COLUMN {name} {col_type}")
            except Exception:
                pass

    # Make sure all needed columns exist
    add_column_if_missing("internal_marks", "INTEGER")
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
    cur.execute(
        "INSERT INTO faculty (name, department) VALUES (?, ?)",
        (name, department if department else None),
    )
    conn.commit()

def get_all_faculty_with_avg():
    cur.execute("""
        SELECT
            f.id,
            f.name,
            f.department,
            AVG(r.leniency)                        AS avg_leniency,
            AVG((r.internal_from + r.internal_to)/2.0) AS avg_internal,
            AVG(r.correction)                      AS avg_correction,
            AVG(r.teaching)                        AS avg_teaching,
            COUNT(r.id)                            AS rating_count
        FROM faculty f
        LEFT JOIN rating r ON f.id = r.faculty_id
        GROUP BY f.id, f.name, f.department
        ORDER BY f.name ASC
    """)
    rows = cur.fetchall()
    result = []
    for row in rows:
        result.append({
            "id": row[0],
            "name": row[1],
            "department": row[2],
            "avg_leniency": round(row[3] or 0, 1),
            "avg_internal": round(row[4] or 0, 1),
            "avg_correction": round(row[5] or 0, 1),
            "avg_teaching": round(row[6] or 0, 1),
            "rating_count": row[7],
        })
    return result

def get_faculty_by_id(fid: int):
    cur.execute("SELECT id, name, department FROM faculty WHERE id = ?", (fid,))
    row = cur.fetchone()
    if row:
        return {"id": row[0], "name": row[1], "department": row[2]}
    return None

def add_rating(faculty_id, leniency, correction, teaching,
               internal_from, internal_to, comment, user_email, reg_no):
    # internal_marks (old column) = average of range
    internal_marks = int(round((internal_from + internal_to) / 2.0))
    created_at = datetime.datetime.now().isoformat(timespec="minutes")

    cur.execute("""
        INSERT INTO rating (
            faculty_id,
            leniency,
            internal_marks,
            correction,
            teaching,
            internal_from,
            internal_to,
            comment,
            created_at,
            user_email,
            reg_no
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        faculty_id,
        leniency,
        internal_marks,
        correction,
        teaching,
        internal_from,
        internal_to,
        comment if comment else None,
        created_at,
        user_email,
        reg_no,
    ))
    conn.commit()

def get_ratings_for_faculty(faculty_id):
    cur.execute("""
        SELECT
            leniency,
            correction,
            teaching,
            internal_from,
            internal_to,
            comment,
            created_at,
            reg_no
        FROM rating
        WHERE faculty_id = ?
        ORDER BY datetime(created_at) DESC
    """, (faculty_id,))
    rows = cur.fetchall()
    ratings = []
    for row in rows:
        ratings.append({
            "leniency": row[0],
            "correction": row[1],
            "teaching": row[2],
            "internal_range": f"{row[3]} – {row[4]}",
            "comment": row[5],
            "created_at": row[6],
            "reg_no": row[7],
        })
    return ratings

def get_avg_for_faculty(faculty_id):
    cur.execute("""
        SELECT
            AVG(leniency),
            AVG((internal_from + internal_to)/2.0),
            AVG(correction),
            AVG(teaching),
            COUNT(id)
        FROM rating
        WHERE faculty_id = ?
    """, (faculty_id,))
    row = cur.fetchone()
    if not row:
        return {
            "avg_leniency": 0.0,
            "avg_internal": 0.0,
            "avg_correction": 0.0,
            "avg_teaching": 0.0,
            "rating_count": 0,
        }
    return {
        "avg_leniency": round(row[0] or 0, 1),
        "avg_internal": round(row[1] or 0, 1),
        "avg_correction": round(row[2] or 0, 1),
        "avg_teaching": round(row[3] or 0, 1),
        "rating_count": row[4] or 0,
    }

# ---------------------------
# Login helpers
# ---------------------------

def valid_college_email(email: str):
    """
    Valid: 9-digit regno + .simats@saveetha.com
    Example: 192524447.simats@saveetha.com
    """
    pattern = r"^[0-9]{9}\.simats@saveetha\.com$"
    return re.match(pattern, email or "") is not None

def extract_reg_no(email: str):
    return email.split(".simats@saveetha.com")[0] if email else None

def require_login():
    if not st.session_state.get("logged_in"):
        st.warning("You must log in first.")
        st.stop()

# ---------------------------
# Streamlit UI setup
# ---------------------------

st.set_page_config(
    page_title="SSE Faculty Rating Portal",
    page_icon="⭐",
    layout="wide",
)

# Session state init
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False
    st.session_state.user_email = None
    st.session_state.reg_no = None

st.title("⭐ SIMATS Faculty Review")
st.caption("Rate faculty based on **Leniency (1–10)**, **Internal Marks Range (50–100)**, **Correction (1–10)**, and **Overall Teaching Experience (1–10)**.")

# Sidebar
st.sidebar.subheader("Account")
if st.session_state.logged_in:
    st.sidebar.success(f"Logged in as: {st.session_state.user_email}")
    if st.sidebar.button("Logout"):
        st.session_state.logged_in = False
        st.session_state.user_email = None
        st.session_state.reg_no = None
        st.rerun()
else:
    st.sidebar.info("Not logged in")

page = st.sidebar.radio(
    "Navigate",
    ["Login / Profile", "Add Faculty", "Rate Faculty", "About"],
)

# ---------------------------
# Page: Login / Profile
# ---------------------------
if page == "Login / Profile":
    st.header("🔐 Login with College Email")

    if st.session_state.logged_in:
        st.success(f"You are logged in as **{st.session_state.user_email}**")
        st.write(f"Registration Number: `{st.session_state.reg_no}`")
        st.info("Use the sidebar to go to **Rate Faculty** or **Add Faculty**.")
    else:
        with st.form("login_form"):
            email = st.text_input(
                "College Email",
                placeholder="e.g., 192524447.simats@saveetha.com",
            )
            submitted = st.form_submit_button("Login")

        if submitted:
            email = email.strip()
            if not valid_college_email(email):
                st.error("Invalid email. Use format: `<9-digit-regno>.simats@saveetha.com`")
            else:
                st.session_state.logged_in = True
                st.session_state.user_email = email
                st.session_state.reg_no = extract_reg_no(email)
                st.success("Login successful!")
                st.rerun()

# ---------------------------
# Page: Add Faculty
# ---------------------------
elif page == "Add Faculty":
    require_login()
    st.header("➕ Add a Faculty Member")

    with st.form("add_faculty_form"):
        name = st.text_input("Faculty Name *")
        dept = st.text_input("Department", placeholder="e.g., CSE, ECE")
        submitted = st.form_submit_button("Save Faculty")

        if submitted:
            if not name.strip():
                st.error("Faculty name is required.")
            else:
                add_faculty(name.strip(), dept.strip())
                st.success(f"Faculty **{name}** added successfully!")

# ---------------------------
# Page: Rate Faculty
# ---------------------------
elif page == "Rate Faculty":
    require_login()
    st.header("📊 Faculty List & Ratings")

    faculties = get_all_faculty_with_avg()

    if not faculties:
        st.info("No faculty added yet. Go to **Add Faculty** to create one.")
    else:
        st.subheader("All Faculty Overview")
        table_data = [{
            "Name": f["name"],
            "Department": f["department"] or "-",
            "Avg Leniency (1–10)": f["avg_leniency"],
            "Avg Internal Marks (/100)": f["avg_internal"],
            "Avg Correction (1–10)": f["avg_correction"],
            "Avg Teaching (1–10)": f["avg_teaching"],
            "Total Ratings": f["rating_count"],
        } for f in faculties]
        st.dataframe(table_data, use_container_width=True)

        st.markdown("---")
        st.subheader("Rate a Faculty")

        faculty_options = {
            f'{f["name"]} ({f["department"] or "No dept"})': f["id"]
            for f in faculties
        }
        selected_label = st.selectbox("Select Faculty", list(faculty_options.keys()))
        selected_id = faculty_options[selected_label]
        faculty = get_faculty_by_id(selected_id)
        avg = get_avg_for_faculty(selected_id)

        if faculty:
            col1, col2, col3, col4, col5 = st.columns(5)
            with col1:
                st.metric("Leniency avg", avg["avg_leniency"])
            with col2:
                st.metric("Internal avg (/100)", avg["avg_internal"])
            with col3:
                st.metric("Correction avg", avg["avg_correction"])
            with col4:
                st.metric("Teaching avg", avg["avg_teaching"])
            with col5:
                st.metric("Ratings", avg["rating_count"])

            st.markdown(f"### Rate: **{faculty['name']}**")
            st.caption(f"Department: {faculty['department'] or 'Not specified'}")

            with st.form("rating_form"):
                leniency = st.number_input(
                    "Leniency (1 = very strict, 10 = very lenient)",
                    min_value=1, max_value=10, step=1,
                )
                correction = st.number_input(
                    "Correction Strictness (1 = very strict, 10 = very forgiving)",
                    min_value=1, max_value=10, step=1,
                )
                teaching = st.number_input(
                    "Overall Teaching Experience (1 = bad, 10 = great)",
                    min_value=1, max_value=10, step=1,
                )
                internal_from = st.number_input(
                    "Internal Marks From (50–100)",
                    min_value=50, max_value=100, step=1,
                )
                internal_to = st.number_input(
                    "Internal Marks To (50–100)",
                    min_value=50, max_value=100, step=1,
                )
                comment = st.text_area(
                    "Comment (optional)",
                    placeholder="Share your experience (no abuse or personal info).",
                )

                submit_rating = st.form_submit_button("Submit Rating")

                if submit_rating:
                    if internal_from > internal_to:
                        st.error("Internal Marks 'From' cannot be greater than 'To'.")
                    else:
                        add_rating(
                            faculty_id=faculty["id"],
                            leniency=leniency,
                            correction=correction,
                            teaching=teaching,
                            internal_from=internal_from,
                            internal_to=internal_to,
                            comment=comment,
                            user_email=st.session_state.user_email,
                            reg_no=st.session_state.reg_no,
                        )
                        st.success("Rating submitted successfully!")

            st.markdown("---")
            st.subheader("Recent Ratings")

            ratings = get_ratings_for_faculty(faculty["id"])
            if not ratings:
                st.info("No ratings yet for this faculty. Be the first to rate!")
            else:
                for r in ratings:
                    st.write(
                        f"**Leniency:** {r['leniency']} | "
                        f"**Correction:** {r['correction']} | "
                        f"**Teaching:** {r['teaching']} | "
                        f"**Internal Marks:** {r['internal_range']}"
                    )
                    if r["comment"]:
                        st.write(r["comment"])
                    st.caption(f"Rated by: {r['reg_no']} • On: {r['created_at']}")
                    st.markdown("---")

# ---------------------------
# Page: About
# ---------------------------
elif page == "About":
    st.header("ℹ️ About this app")
    st.write(
        """
        This app lets students review faculty on four parameters:

        - **Leniency** – 1 (very strict) to 10 (very lenient)
        - **Internal Marks** – range between **50 and 100**
        - **Correction** – 1 (very strict) to 10 (very forgiving)
        - **Overall Teaching Experience** – 1 (bad) to 10 (great)

        Login is restricted to emails of the form:
        **`<9-digit-regno>.simats@saveetha.com`**
        """
    )
