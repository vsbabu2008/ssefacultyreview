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
    # Base tables
    cur.execute("""
        CREATE TABLE IF NOT EXISTS faculty (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            department TEXT
        )
    """)

    # Create rating table if not exists (basic)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS rating (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            faculty_id INTEGER NOT NULL,
            leniency INTEGER NOT NULL,
            internal_marks INTEGER NOT NULL,
            correction INTEGER NOT NULL,
            comment TEXT,
            created_at TEXT NOT NULL,
            FOREIGN KEY (faculty_id) REFERENCES faculty (id)
        )
    """)

    # --- Schema migration: ensure user_email and reg_no columns exist ---
    cur.execute("PRAGMA table_info(rating)")
    cols = [row[1] for row in cur.fetchall()]  # column names

    if "user_email" not in cols:
        cur.execute("ALTER TABLE rating ADD COLUMN user_email TEXT")
    if "reg_no" not in cols:
        cur.execute("ALTER TABLE rating ADD COLUMN reg_no TEXT")

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
            AVG(r.leniency) AS avg_leniency,
            AVG(r.internal_marks) AS avg_internal,
            AVG(r.correction) AS avg_correction,
            COUNT(r.id) AS rating_count
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
            "avg_leniency": round(row[3], 1) if row[3] is not None else 0.0,
            "avg_internal": round(row[4], 1) if row[4] is not None else 0.0,
            "avg_correction": round(row[5], 1) if row[5] is not None else 0.0,
            "rating_count": row[6],
        })
    return result

def get_faculty_by_id(fid: int):
    cur.execute("SELECT id, name, department FROM faculty WHERE id = ?", (fid,))
    row = cur.fetchone()
    if row:
        return {"id": row[0], "name": row[1], "department": row[2]}
    return None

def add_rating(faculty_id, leniency, internal_marks, correction, comment, user_email, reg_no):
    created_at = datetime.datetime.now().isoformat(timespec="minutes")
    cur.execute("""
        INSERT INTO rating (faculty_id, leniency, internal_marks, correction,
                            comment, created_at, user_email, reg_no)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        faculty_id,
        leniency,
        internal_marks,
        correction,
        comment if comment else None,
        created_at,
        user_email,
        reg_no,
    ))
    conn.commit()

def get_ratings_for_faculty(faculty_id):
    cur.execute("""
        SELECT leniency, internal_marks, correction, comment, created_at,
               user_email, reg_no
        FROM rating
        WHERE faculty_id = ?
        ORDER BY datetime(created_at) DESC
    """, (faculty_id,))
    rows = cur.fetchall()
    ratings = []
    for row in rows:
        ratings.append({
            "leniency": row[0],
            "internal_marks": row[1],
            "correction": row[2],
            "comment": row[3],
            "created_at": row[4],
            "user_email": row[5],
            "reg_no": row[6],
        })
    return ratings

def get_avg_for_faculty(faculty_id):
    cur.execute("""
        SELECT
            AVG(leniency),
            AVG(internal_marks),
            AVG(correction),
            COUNT(id)
        FROM rating
        WHERE faculty_id = ?
    """, (faculty_id,))
    row = cur.fetchone()
    if not row or row[3] == 0:
        return {
            "avg_leniency": 0.0,
            "avg_internal": 0.0,
            "avg_correction": 0.0,
            "rating_count": 0,
        }
    return {
        "avg_leniency": round(row[0], 1),
        "avg_internal": round(row[1], 1),
        "avg_correction": round(row[2], 1),
        "rating_count": row[3],
    }

# ---------------------------
# Login helpers
# ---------------------------

def valid_college_email(email: str):
    """
    Valid emails: <regno>.simats@saveetha.com
    Example: 721221104001.simats@saveetha.com
    """
    pattern = r"^[A-Za-z0-9]+\.simats@saveetha\.com$"
    return re.match(pattern, email or "") is not None

def extract_reg_no(email: str):
    # Part before ".simats@saveetha.com"
    return email.split(".simats@saveetha.com")[0] if email and ".simats@saveetha.com" in email else None

def require_login():
    """Show message and stop if user not logged in."""
    if not st.session_state.get("logged_in"):
        st.warning("You must log in with your college email to use this page.")
        st.stop()

# ---------------------------
# Streamlit UI setup
# ---------------------------

st.set_page_config(
    page_title="College Faculty Review",
    page_icon="📊",
    layout="wide",
)

# Initialize session state
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False
    st.session_state.user_email = None
    st.session_state.reg_no = None

st.title("📊 College Faculty Review")
st.caption("Rate faculty based on **leniency**, **internal marks (0–100)**, and **correction**.")

# Sidebar
st.sidebar.subheader("User")
if st.session_state.logged_in:
    st.sidebar.success(f"Logged in as:\n{st.session_state.user_email}")
    if st.sidebar.button("Logout"):
        st.session_state.logged_in = False
        st.session_state.user_email = None
        st.session_state.reg_no = None
        st.rerun()          # <-- fixed here
else:
    st.sidebar.info("Not logged in")

page = st.sidebar.radio(
    "Navigate",
    ["Login / Profile", "View Faculty & Rate", "Add Faculty", "About"],
)

# ---------------------------
# Page: Login / Profile
# ---------------------------
if page == "Login / Profile":
    st.header("🔐 Login with College Email")

    if st.session_state.logged_in:
        st.success(f"You are logged in as **{st.session_state.user_email}**")
        st.write(f"Registration Number: `{st.session_state.reg_no}`")
        st.info("Use the sidebar to go to **View Faculty & Rate** or **Add Faculty**.")
    else:
        with st.form("login_form"):
            email = st.text_input(
                "College Email",
                placeholder="e.g., 721221104001.simats@saveetha.com",
            )
            submitted = st.form_submit_button("Login")

        if submitted:
            if not valid_college_email(email.strip()):
                st.error("Invalid email. Use format: `<regno>.simats@saveetha.com`")
            else:
                reg_no = extract_reg_no(email.strip())
                st.session_state.logged_in = True
                st.session_state.user_email = email.strip()
                st.session_state.reg_no = reg_no
                st.success("Login successful!")
                st.rerun()   # <-- fixed here

# ---------------------------
# Page: Add Faculty
# ---------------------------
elif page == "Add Faculty":
    require_login()

    st.header("➕ Add a Faculty Member")

    with st.form("add_faculty_form"):
        name = st.text_input("Faculty Name *")
        dept = st.text_input("Department (optional)", placeholder="e.g., CSE, ECE")
        submitted = st.form_submit_button("Save Faculty")

        if submitted:
            if not name.strip():
                st.error("Faculty name is required.")
            else:
                add_faculty(name.strip(), dept.strip())
                st.success(f"Faculty **{name}** added successfully!")

# ---------------------------
# Page: View Faculty & Rate
# ---------------------------
elif page == "View Faculty & Rate":
    require_login()

    st.header("👩‍🏫 Faculty List & Ratings")

    faculties = get_all_faculty_with_avg()

    if not faculties:
        st.info("No faculty added yet. Go to **'Add Faculty'** to create one.")
    else:
        st.subheader("All Faculty Overview")
        table_data = [{
            "Name": f["name"],
            "Department": f["department"] or "-",
            "Avg Leniency (1–5)": f["avg_leniency"],
            "Avg Internal Marks (/100)": f["avg_internal"],
            "Avg Correction (1–5)": f["avg_correction"],
            "Total Ratings": f["rating_count"],
        } for f in faculties]
        st.dataframe(table_data, use_container_width=True)

        st.markdown("---")
        st.subheader("Rate a Faculty")

        faculty_options = {f'{f["name"]} ({f["department"] or "No dept"})': f["id"] for f in faculties}
        selected_label = st.selectbox("Select Faculty", list(faculty_options.keys()))
        selected_id = faculty_options[selected_label]
        faculty = get_faculty_by_id(selected_id)

        if faculty:
            avg = get_avg_for_faculty(faculty["id"])

            col1, col2, col3, col4 = st.columns(4)
            with col1:
                st.metric("Leniency (avg, 1–5)", avg["avg_leniency"])
            with col2:
                st.metric("Internal Marks Avg (/100)", avg["avg_internal"])
            with col3:
                st.metric("Correction (avg, 1–5)", avg["avg_correction"])
            with col4:
                st.metric("Total Ratings", avg["rating_count"])

            st.markdown(f"### Rate: **{faculty['name']}**")
            st.caption(f"Department: {faculty['department'] or 'Not specified'}")

            with st.form("rating_form"):
                leniency = st.number_input(
                    "Leniency (1 = strict, 5 = very lenient)",
                    min_value=1,
                    max_value=5,
                    step=1,
                )
                internal_marks = st.number_input(
                    "Internal Marks (0 to 100)",
                    min_value=0,
                    max_value=100,
                    step=1,
                )
                correction = st.number_input(
                    "Correction (1 = very strict, 5 = very forgiving)",
                    min_value=1,
                    max_value=5,
                    step=1,
                )
                comment = st.text_area(
                    "Comment (optional)",
                    placeholder="Share your experience (no abuse or personal info).",
                )

                submit_rating = st.form_submit_button("Submit Rating")

                if submit_rating:
                    add_rating(
                        faculty["id"],
                        leniency,
                        internal_marks,
                        correction,
                        comment,
                        st.session_state.user_email,
                        st.session_state.reg_no,
                    )
                    st.success("Rating submitted successfully!")

            st.markdown("---")
            st.subheader("Recent Ratings")

            ratings = get_ratings_for_faculty(faculty["id"])
            if not ratings:
                st.info("No ratings yet for this faculty. Be the first to rate!")
            else:
                for r in ratings:
                    with st.container():
                        st.write(
                            f"**Leniency:** {r['leniency']} | "
                            f"**Internal Marks (out of 100):** {r['internal_marks']} | "
                            f"**Correction:** {r['correction']}"
                        )
                        if r["comment"]:
                            st.write(r["comment"])
                        label = r["reg_no"] or r["user_email"] or "Anonymous"
                        st.caption(f"Rated by: {label}  •  On: {r['created_at']}")
                        st.markdown("---")

# ---------------------------
# Page: About
# ---------------------------
elif page == "About":
    st.header("ℹ️ About this app")
    st.write(
        """
        This app lets students review faculty on three parameters:

        - **Leniency** – how strict/lenient the faculty is in class (1–5).
        - **Internal Marks** – how generously they give internal marks (**0–100**).
        - **Correction** – how strict or easy-going they are while correcting papers (1–5).

        🔐 **Login restriction**

        - Only emails in the format `<regno>.simats@saveetha.com` can log in.
        - Example: `721221104001.simats@saveetha.com`.

        Built with **Streamlit** and **SQLite**, deployable on **streamlit.app**.
        """
    )
