import os
from datetime import date, timedelta

import pandas as pd
import psycopg
import streamlit as st
from psycopg.rows import dict_row




st.set_page_config(
    page_title="Smart Research Paper Management",
    page_icon="📚",
    layout="wide"
)

st.title("📚 Smart Research Paper Management System")
st.caption("Local PostgreSQL Database | DBMS_project")




with st.sidebar:
    st.header("Database Connection")

    db_host = st.text_input(
        "Host",
        value=os.getenv("PGHOST", "localhost")
    )

    db_port = st.number_input(
        "Port",
        min_value=1,
        max_value=65535,
        value=int(os.getenv("PGPORT", "5432")),
        step=1
    )

    db_name = st.text_input(
        "Database",
        value=os.getenv("PGDATABASE", "DBMS_project")
    )

    db_user = st.text_input(
        "Username",
        value=os.getenv("PGUSER", "postgres")
    )

    db_password = st.text_input(
        "PostgreSQL Password",
        value=os.getenv("PGPASSWORD", ""),
        type="password"
    )

    connect_clicked = st.button(
        "Connect / Reconnect",
        type="primary",
        use_container_width=True
    )


if "db_config" not in st.session_state:
    st.session_state.db_config = None


if connect_clicked or st.session_state.db_config is None:
    st.session_state.db_config = {
        "host": db_host.strip(),
        "port": int(db_port),
        "dbname": db_name.strip(),
        "user": db_user.strip(),
        "password": db_password,
    }


def get_connection():
    return psycopg.connect(
        **st.session_state.db_config,
        connect_timeout=5,
        row_factory=dict_row
    )


def read_query(sql, params=None):
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, params or ())
            return pd.DataFrame(cur.fetchall())


def execute_query(sql, params=None):
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, params or ())
            rows = cur.fetchall() if cur.description else []

        conn.commit()
        return rows


# Check database connection

try:
    health = read_query("""
        SELECT
            current_database() AS database_name,
            current_user AS username,
            inet_server_port() AS server_port
    """)

    st.sidebar.success(
        f"Connected to {health.iloc[0]['database_name']} "
        f"as {health.iloc[0]['username']} "
        f"(port {health.iloc[0]['server_port']})"
    )

except Exception as exc:
    st.error(
        "Could not connect to PostgreSQL. "
        "Check that PostgreSQL is running and the password is correct."
    )

    st.code(str(exc))

    st.info(
        "Enter your PostgreSQL password in the sidebar "
        "and click Connect / Reconnect."
    )

    st.stop()


# --------------------------------------------------
# NAVIGATION
# --------------------------------------------------

page = st.sidebar.radio(
    "Navigation",
    [
        "Dashboard",
        "Research Papers",
        "Researchers",
        "Review Management",
        "Publications",
        "Citations",
        "SQL Reports"
    ]
)


# ==================================================
# DASHBOARD
# ==================================================

if page == "Dashboard":

    st.subheader("Dashboard")

    counts = read_query("""
        SELECT
            (SELECT COUNT(*) FROM research_paper) AS papers,
            (SELECT COUNT(*) FROM researcher) AS researchers,
            (SELECT COUNT(*) FROM reviewer) AS reviewers,
            (SELECT COUNT(*) FROM review_assignment) AS assignments,
            (SELECT COUNT(*) FROM review) AS reviews,
            (SELECT COUNT(*) FROM publication) AS publications,
            (SELECT COUNT(*) FROM citation) AS citations
    """).iloc[0]

    cols = st.columns(4)

    metrics = [
        ("Research Papers", "papers"),
        ("Researchers", "researchers"),
        ("Reviewers", "reviewers"),
        ("Review Assignments", "assignments")
    ]

    for col, (label, key) in zip(cols, metrics):
        col.metric(label, int(counts[key]))

    cols = st.columns(3)

    metrics = [
        ("Reviews", "reviews"),
        ("Publications", "publications"),
        ("Citations", "citations")
    ]

    for col, (label, key) in zip(cols, metrics):
        col.metric(label, int(counts[key]))

    left, right = st.columns(2)

    with left:
        st.markdown("#### Papers by Status")

        st.dataframe(
            read_query("""
                SELECT status, COUNT(*) AS total
                FROM research_paper
                GROUP BY status
                ORDER BY status
            """),
            use_container_width=True,
            hide_index=True
        )

    with right:
        st.markdown("#### Latest Submitted Papers")

        st.dataframe(
            read_query("""
                SELECT paper_id, title, submitted_on, status
                FROM research_paper
                ORDER BY submitted_on DESC, paper_id DESC
                LIMIT 8
            """),
            use_container_width=True,
            hide_index=True
        )


# ==================================================
# RESEARCH PAPERS
# ==================================================

elif page == "Research Papers":

    st.subheader("Research Papers")

    search = st.text_input("Search by title or abstract")

    status_filter = st.selectbox(
        "Filter by Status",
        [
            "All",
            "SUBMITTED",
            "UNDER_REVIEW",
            "ACCEPTED",
            "REJECTED",
            "PUBLISHED"
        ]
    )

    # Display papers with their assigned authors

    papers = read_query("""
        SELECT
            p.paper_id,
            p.title,
            p.abstract,
            p.submitted_on,
            p.status,
            COALESCE(
                string_agg(
                    r.name,
                    ', ' ORDER BY ap.author_order
                ),
                'No author assigned'
            ) AS authors
        FROM research_paper p
        LEFT JOIN author_paper ap
            ON p.paper_id = ap.paper_id
        LEFT JOIN researcher r
            ON ap.researcher_id = r.researcher_id
        WHERE (
            %s = ''
            OR p.title ILIKE %s
            OR COALESCE(p.abstract, '') ILIKE %s
        )
        AND (
            %s = 'All'
            OR p.status = %s
        )
        GROUP BY p.paper_id
        ORDER BY p.paper_id
    """, (
        search,
        f"%{search}%",
        f"%{search}%",
        status_filter,
        status_filter
    ))

    st.dataframe(
        papers,
        use_container_width=True,
        hide_index=True
    )

    add_col, update_col = st.columns(2)

    # Add a paper

    with add_col:

        st.markdown("#### Add a Paper")

        with st.form("add_paper_form", clear_on_submit=True):

            title = st.text_input("Title")

            abstract = st.text_area("Abstract")

            status = st.selectbox(
                "Initial Status",
                [
                    "SUBMITTED",
                    "UNDER_REVIEW",
                    "ACCEPTED",
                    "REJECTED",
                    "PUBLISHED"
                ]
            )

            submitted_on = st.date_input(
                "Submission Date",
                value=date.today()
            )

            add = st.form_submit_button("Add Paper")

        if add:

            if not title.strip():
                st.error("Title is required.")

            else:
                try:
                    result = execute_query("""
                        INSERT INTO research_paper
                            (title, abstract, submitted_on, status)
                        VALUES (%s, %s, %s, %s)
                        RETURNING paper_id
                    """, (
                        title.strip(),
                        abstract.strip() or None,
                        submitted_on,
                        status
                    ))

                    st.success(
                        f"Paper added successfully! "
                        f"Paper ID: {result[0]['paper_id']}"
                    )

                    st.rerun()

                except Exception as exc:
                    st.error(f"Could not add paper: {exc}")

    # Update paper status

    with update_col:

        st.markdown("#### Update Paper Status")

        choices = read_query("""
            SELECT paper_id, title
            FROM research_paper
            ORDER BY paper_id
        """)

        if not choices.empty:

            paper_map = {
                f"{int(r.paper_id)} — {r.title}": int(r.paper_id)
                for r in choices.itertuples()
            }

            with st.form("update_paper_form"):

                selected = st.selectbox(
                    "Paper",
                    list(paper_map.keys())
                )

                new_status = st.selectbox(
                    "New Status",
                    [
                        "SUBMITTED",
                        "UNDER_REVIEW",
                        "ACCEPTED",
                        "REJECTED",
                        "PUBLISHED"
                    ]
                )

                update = st.form_submit_button("Update Status")

            if update:

                try:
                    execute_query("""
                        UPDATE research_paper
                        SET status = %s
                        WHERE paper_id = %s
                    """, (
                        new_status,
                        paper_map[selected]
                    ))

                    st.success("Paper status updated successfully.")
                    st.rerun()

                except Exception as exc:
                    st.error(f"Could not update paper: {exc}")

    # --------------------------------------------------
    # ASSIGN AUTHORS TO PAPERS
    # --------------------------------------------------

    st.divider()
    st.markdown("### ✍️ Author Assignment")

    st.write(
        "Associate researchers with papers and specify their "
        "author order. A paper can have multiple authors."
    )

    author_papers = read_query("""
        SELECT paper_id, title
        FROM research_paper
        ORDER BY paper_id
    """)

    available_researchers = read_query("""
        SELECT researcher_id, name, email
        FROM researcher
        ORDER BY researcher_id
    """)

    if author_papers.empty:

        st.info("Add a paper before assigning an author.")

    elif available_researchers.empty:

        st.info(
            "No researchers found. Add a researcher in the "
            "Researchers section first."
        )

    else:

        paper_options = {
            f"{int(row.paper_id)} — {row.title}": int(row.paper_id)
            for row in author_papers.itertuples()
        }

        researcher_options = {
            (
                f"{int(row.researcher_id)} — "
                f"{row.name} ({row.email})"
            ): int(row.researcher_id)
            for row in available_researchers.itertuples()
        }

        with st.form("assign_author_form", clear_on_submit=True):

            selected_paper = st.selectbox(
                "Select Paper",
                list(paper_options.keys())
            )

            selected_researcher = st.selectbox(
                "Select Author / Researcher",
                list(researcher_options.keys())
            )

            author_order = st.number_input(
                "Author Order",
                min_value=1,
                max_value=100,
                value=1,
                step=1,
                help="1 means first author, 2 means second author, etc."
            )

            assign_author = st.form_submit_button("Assign Author")

        if assign_author:

            paper_id = paper_options[selected_paper]
            researcher_id = researcher_options[selected_researcher]

            try:

                existing = read_query("""
                    SELECT researcher_id, author_order
                    FROM author_paper
                    WHERE paper_id = %s
                """, (paper_id,))

                # Prevent assigning the same researcher twice

                if (
                    not existing.empty
                    and (
                        existing["researcher_id"] == researcher_id
                    ).any()
                ):

                    st.error(
                        "This researcher is already an author "
                        "of the selected paper."
                    )

                # Prevent duplicate author positions

                elif (
                    not existing.empty
                    and (
                        existing["author_order"] == int(author_order)
                    ).any()
                ):

                    st.error(
                        "That author order is already occupied. "
                        "Choose another position."
                    )

                else:

                    execute_query("""
                        INSERT INTO author_paper
                            (researcher_id, paper_id, author_order)
                        VALUES (%s, %s, %s)
                    """, (
                        researcher_id,
                        paper_id,
                        int(author_order)
                    ))

                    st.success(
                        f"Author assigned successfully to "
                        f"'{selected_paper}'!"
                    )

                    st.rerun()

            except Exception as exc:
                st.error(f"Could not assign author: {exc}")

    # Display author relationships

    st.markdown("#### Current Author Assignments")

    author_assignments = read_query("""
        SELECT
            p.paper_id,
            p.title,
            r.name AS author_name,
            r.email,
            ap.author_order
        FROM author_paper ap
        JOIN research_paper p
            ON ap.paper_id = p.paper_id
        JOIN researcher r
            ON ap.researcher_id = r.researcher_id
        ORDER BY p.paper_id, ap.author_order
    """)

    if author_assignments.empty:
        st.info("No author assignments have been recorded yet.")
    else:
        st.dataframe(
            author_assignments,
            use_container_width=True,
            hide_index=True
        )

    # Delete a paper

    with st.expander("Delete a Paper (Careful)"):

        st.warning(
            "Deleting a paper may fail if it has related author, "
            "review, publication, or citation records."
        )

        choices = read_query("""
            SELECT paper_id, title
            FROM research_paper
            ORDER BY paper_id
        """)

        if not choices.empty:

            delete_map = {
                f"{int(r.paper_id)} — {r.title}": int(r.paper_id)
                for r in choices.itertuples()
            }

            with st.form("delete_paper_form"):

                delete_label = st.selectbox(
                    "Paper to Delete",
                    list(delete_map.keys())
                )

                confirm = st.checkbox(
                    "I understand this permanently deletes the paper if allowed"
                )

                delete = st.form_submit_button("Delete Paper")

            if delete:

                if not confirm:
                    st.error("Tick the confirmation box first.")

                else:
                    try:

                        execute_query("""
                            DELETE FROM research_paper
                            WHERE paper_id = %s
                        """, (delete_map[delete_label],))

                        st.success("Paper deleted successfully.")
                        st.rerun()

                    except Exception as exc:
                        st.error(
                            "Could not delete paper. Related records "
                            f"may exist. Details: {exc}"
                        )


# ==================================================
# RESEARCHERS
# ==================================================

elif page == "Researchers":

    st.subheader("Researchers")

    st.dataframe(
        read_query("""
            SELECT
                r.researcher_id,
                r.name,
                r.email,
                r.affiliation,
                COUNT(DISTINCT ap.paper_id) AS papers_authored,
                COUNT(DISTINCT pub.publication_id) AS publications
            FROM researcher r
            LEFT JOIN author_paper ap
                ON r.researcher_id = ap.researcher_id
            LEFT JOIN publication pub
                ON ap.paper_id = pub.paper_id
            GROUP BY r.researcher_id
            ORDER BY r.researcher_id
        """),
        use_container_width=True,
        hide_index=True
    )

    with st.expander("Add a Researcher"):

        with st.form("add_researcher_form", clear_on_submit=True):

            name = st.text_input("Name")
            email = st.text_input("Email")
            affiliation = st.text_input("Affiliation")

            add = st.form_submit_button("Add Researcher")

        if add:

            if not name.strip() or not email.strip():

                st.error("Name and email are required.")

            else:

                try:

                    result = execute_query("""
                        INSERT INTO researcher
                            (name, email, affiliation)
                        VALUES (%s, %s, %s)
                        RETURNING researcher_id
                    """, (
                        name.strip(),
                        email.strip(),
                        affiliation.strip() or None
                    ))

                    st.success(
                        f"Researcher added successfully! "
                        f"ID: {result[0]['researcher_id']}"
                    )

                    st.rerun()

                except Exception as exc:
                    st.error(f"Could not add researcher: {exc}")


# ==================================================
# REVIEW MANAGEMENT
# ==================================================

elif page == "Review Management":

    st.subheader("Review Management")

    t1, t2, t3 = st.tabs([
        "Assignments",
        "Review Results",
        "Assign Reviewer"
    ])

    with t1:

        st.markdown("#### Review Assignments")

        st.dataframe(
            read_query("""
                SELECT
                    ra.assignment_id,
                    p.title,
                    rv.name AS reviewer,
                    ra.assigned_on,
                    ra.due_date,
                    ra.status AS assignment_status,
                    CASE
                        WHEN rev.review_id IS NULL
                        THEN 'No review submitted'
                        ELSE rev.recommendation
                    END AS review_result
                FROM review_assignment ra
                JOIN research_paper p
                    ON ra.paper_id = p.paper_id
                JOIN reviewer rv
                    ON ra.reviewer_id = rv.reviewer_id
                LEFT JOIN review rev
                    ON ra.assignment_id = rev.assignment_id
                ORDER BY ra.assignment_id
            """),
            use_container_width=True,
            hide_index=True
        )

    with t2:

        st.markdown("#### Review Results")

        st.dataframe(
            read_query("""
                SELECT
                    p.title,
                    rv.name AS reviewer,
                    rev.recommendation,
                    rev.score,
                    rev.comments,
                    rev.reviewed_on
                FROM review rev
                JOIN review_assignment ra
                    ON rev.assignment_id = ra.assignment_id
                JOIN research_paper p
                    ON ra.paper_id = p.paper_id
                JOIN reviewer rv
                    ON ra.reviewer_id = rv.reviewer_id
                ORDER BY rev.reviewed_on DESC, p.title
            """),
            use_container_width=True,
            hide_index=True
        )

    with t3:

        st.markdown("#### Assign a Reviewer")

        papers = read_query("""
            SELECT paper_id, title
            FROM research_paper
            ORDER BY paper_id
        """)

        reviewers = read_query("""
            SELECT reviewer_id, name
            FROM reviewer
            ORDER BY reviewer_id
        """)

        if not papers.empty and not reviewers.empty:

            pm = {
                f"{int(r.paper_id)} — {r.title}": int(r.paper_id)
                for r in papers.itertuples()
            }

            rm = {
                f"{int(r.reviewer_id)} — {r.name}": int(r.reviewer_id)
                for r in reviewers.itertuples()
            }

            with st.form("assign_reviewer_form"):

                paper = st.selectbox("Paper", list(pm.keys()))

                reviewer = st.selectbox(
                    "Reviewer",
                    list(rm.keys())
                )

                due = st.date_input(
                    "Due Date",
                    value=date.today() + timedelta(days=7),
                    min_value=date.today()
                )

                assign = st.form_submit_button("Assign Reviewer")

            if assign:

                try:

                    with get_connection() as conn:

                        with conn.cursor() as cur:
                            cur.execute(
                                "CALL assign_reviewer(%s, %s, %s)",
                                (pm[paper], rm[reviewer], due)
                            )

                        conn.commit()

                    st.success("Reviewer assigned successfully.")
                    st.rerun()

                except Exception as exc:
                    st.error(f"Could not assign reviewer: {exc}")

        else:
            st.info(
                "You need at least one paper and one reviewer "
                "before creating an assignment."
            )


# ==================================================
# PUBLICATIONS
# ==================================================

elif page == "Publications":

    st.subheader("Publications")

    st.dataframe(
        read_query("""
            SELECT
                pub.publication_id,
                p.title,
                pub.venue,
                pub.publication_year,
                pub.doi
            FROM publication pub
            JOIN research_paper p
                ON pub.paper_id = p.paper_id
            ORDER BY pub.publication_year DESC, p.title
        """),
        use_container_width=True,
        hide_index=True
    )

    with st.expander("Add a Publication"):

        papers = read_query("""
            SELECT p.paper_id, p.title
            FROM research_paper p
            LEFT JOIN publication pub
                ON p.paper_id = pub.paper_id
            WHERE pub.publication_id IS NULL
            ORDER BY p.paper_id
        """)

        if papers.empty:

            st.info(
                "Every current paper already has a publication record."
            )

        else:

            pm = {
                f"{int(r.paper_id)} — {r.title}": int(r.paper_id)
                for r in papers.itertuples()
            }

            with st.form("add_publication_form", clear_on_submit=True):

                paper = st.selectbox("Paper", list(pm.keys()))
                venue = st.text_input("Venue")

                year = st.number_input(
                    "Publication Year",
                    min_value=1900,
                    max_value=2100,
                    value=date.today().year
                )

                doi = st.text_input("DOI (Optional)")

                add = st.form_submit_button("Add Publication")

            if add:

                if not venue.strip():

                    st.error("Venue is required.")

                else:

                    try:

                        execute_query("""
                            INSERT INTO publication
                                (paper_id, venue, publication_year, doi)
                            VALUES (%s, %s, %s, %s)
                        """, (
                            pm[paper],
                            venue.strip(),
                            int(year),
                            doi.strip() or None
                        ))

                        st.success(
                            "Publication added successfully. "
                            "The publication trigger should mark "
                            "the paper as PUBLISHED."
                        )

                        st.rerun()

                    except Exception as exc:
                        st.error(f"Could not add publication: {exc}")


# ==================================================
# CITATIONS
# ==================================================

elif page == "Citations":

    st.subheader("Citations")

    st.dataframe(
        read_query("""
            SELECT
                c.citation_id,
                citing.title AS citing_paper,
                cited.title AS cited_paper
            FROM citation c
            JOIN research_paper citing
                ON c.citing_paper_id = citing.paper_id
            JOIN research_paper cited
                ON c.cited_paper_id = cited.paper_id
            ORDER BY c.citation_id
        """),
        use_container_width=True,
        hide_index=True
    )

    with st.expander("Add a Citation Relationship"):

        papers = read_query("""
            SELECT paper_id, title
            FROM research_paper
            ORDER BY paper_id
        """)

        if len(papers) < 2:

            st.info("At least two papers are needed.")

        else:

            pm = {
                f"{int(r.paper_id)} — {r.title}": int(r.paper_id)
                for r in papers.itertuples()
            }

            labels = list(pm.keys())

            with st.form("add_citation_form"):

                citing = st.selectbox("Citing Paper", labels)

                cited = st.selectbox(
                    "Paper Being Cited",
                    labels
                )

                add = st.form_submit_button("Add Citation")

            if add:

                if pm[citing] == pm[cited]:

                    st.error("A paper cannot cite itself.")

                else:

                    try:

                        execute_query("""
                            INSERT INTO citation
                                (citing_paper_id, cited_paper_id)
                            VALUES (%s, %s)
                        """, (
                            pm[citing],
                            pm[cited]
                        ))

                        st.success("Citation added successfully.")
                        st.rerun()

                    except Exception as exc:
                        st.error(f"Could not add citation: {exc}")


# ==================================================
# SQL REPORTS
# ==================================================

elif page == "SQL Reports":

    st.subheader("SQL Reports")

    report = st.selectbox(
        "Choose a Report",
        [
            "Average Review Score by Paper",
            "Citation Count by Paper",
            "Papers with Above-Average Review Scores",
            "Researchers and Publication Counts",
            "Reviewer Workload",
            "Paper and Author List"
        ]
    )

    queries = {

        "Average Review Score by Paper": """
            SELECT
                p.paper_id,
                p.title,
                ROUND(AVG(rev.score), 2) AS average_score,
                COUNT(rev.review_id) AS review_count
            FROM research_paper p
            LEFT JOIN review_assignment ra
                ON p.paper_id = ra.paper_id
            LEFT JOIN review rev
                ON ra.assignment_id = rev.assignment_id
            GROUP BY p.paper_id, p.title
            ORDER BY average_score DESC NULLS LAST
        """,

        "Citation Count by Paper": """
            SELECT
                p.paper_id,
                p.title,
                COUNT(c.citation_id) AS citations_received
            FROM research_paper p
            LEFT JOIN citation c
                ON p.paper_id = c.cited_paper_id
            GROUP BY p.paper_id, p.title
            ORDER BY citations_received DESC, p.title
        """,

        "Papers with Above-Average Review Scores": """
            SELECT
                p.title,
                rev.score
            FROM research_paper p
            JOIN review_assignment ra
                ON p.paper_id = ra.paper_id
            JOIN review rev
                ON ra.assignment_id = rev.assignment_id
            WHERE rev.score > (
                SELECT AVG(score)
                FROM review
            )
            ORDER BY rev.score DESC
        """,

        "Researchers and Publication Counts": """
            SELECT
                r.researcher_id,
                r.name,
                COUNT(DISTINCT pub.publication_id) AS publication_count
            FROM researcher r
            LEFT JOIN author_paper ap
                ON r.researcher_id = ap.researcher_id
            LEFT JOIN publication pub
                ON ap.paper_id = pub.paper_id
            GROUP BY r.researcher_id, r.name
            ORDER BY publication_count DESC, r.name
        """,

        "Reviewer Workload": """
            SELECT
                rv.reviewer_id,
                rv.name,
                COUNT(ra.assignment_id) AS assignments
            FROM reviewer rv
            LEFT JOIN review_assignment ra
                ON rv.reviewer_id = ra.reviewer_id
            GROUP BY rv.reviewer_id, rv.name
            ORDER BY assignments DESC, rv.name
        """,

        "Paper and Author List": """
            SELECT
                p.paper_id,
                p.title,
                COALESCE(
                    string_agg(
                        r.name,
                        ', ' ORDER BY ap.author_order
                    ),
                    'No author recorded'
                ) AS authors
            FROM research_paper p
            LEFT JOIN author_paper ap
                ON p.paper_id = ap.paper_id
            LEFT JOIN researcher r
                ON ap.researcher_id = r.researcher_id
            GROUP BY p.paper_id, p.title
            ORDER BY p.paper_id
        """
    }

    st.dataframe(
        read_query(queries[report]),
        use_container_width=True,
        hide_index=True
    )


# --------------------------------------------------
# SIDEBAR FOOTER
# --------------------------------------------------

st.sidebar.markdown("---")

st.sidebar.caption(
    "Local application. Changes made through forms "
    "are saved to PostgreSQL."
)