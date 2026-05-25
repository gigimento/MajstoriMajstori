# -*- coding: utf-8 -*-
import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, date, timedelta
from io import StringIO
from models import init_db, authenticate_user, register_user, get_db
from scheduler import (forward_schedule, backward_schedule, get_conflicts,
                       get_capacity_violations, move_job, what_if_rush_job,
                       get_jobs_past_due, snapshot_schedule, restore_snapshot)

st.set_page_config(page_title="SCHED//PRO", layout="wide", page_icon="\u26a1")

HC = st.sidebar.checkbox("HIGH CONTRAST", value=False, key="hc_toggle") if "user" in st.session_state else False

ACCENT = "#FF8800" if HC else "#FF8800"
ACCENT2 = "#0088FF"
SUCCESS = "#FF8800"
DANGER = "#FF4444"
WARN = "#FFCC00"
BG = "#000000"
BG2 = "#111111"
TEXT = "#FFFFFF"
TEXT2 = "#AAAAAA"
BORDER = "#444444"

DARK_CSS = f"""
<style>
    .stApp {{ background-color: {BG}; color: {TEXT}; font-size: 18px; }}
    .stApp h1, .stApp h2, .stApp h3 {{ color: {ACCENT}; font-family: monospace; text-transform: uppercase; letter-spacing: 2px; }}
    .stApp h1 {{ font-size: 28px; border-bottom: 2px solid {ACCENT}; padding-bottom: 8px; }}
    .stApp h2 {{ font-size: 24px; }}
    .stApp h3 {{ font-size: 20px; }}
    .stApp p, .stApp li, .stApp label {{ font-size: 18px; }}
    .stApp .stButton button {{ background-color: {ACCENT}; color: #000000; border: 2px solid #FFFFFF; border-radius: 0; font-family: monospace; font-weight: bold; font-size: 18px; padding: 8px 24px; }}
    .stApp .stButton button:hover {{ background-color: #FFAA44; }}
    .stApp .stTextInput input, .stApp .stNumberInput input, .stApp .stSelectbox select, .stApp .stDateInput input, .stApp .stTextArea textarea {{
        background-color: {BG2}; color: {TEXT}; border: 2px solid {BORDER}; border-radius: 0; font-size: 18px;
    }}
    .stApp .stDataFrame {{ border: 2px solid {BORDER}; font-size: 16px; }}
    .stApp .stDataFrame th {{ background-color: {BG2}; color: {ACCENT}; font-size: 16px; font-weight: bold; }}
    .stApp .stDataFrame td {{ background-color: {BG}; color: {TEXT}; font-size: 16px; }}
    .stApp .stTabs [data-baseweb="tab"] {{ color: {TEXT2}; font-family: monospace; font-size: 18px; }}
    .stApp .stTabs [aria-selected="true"] {{ color: {ACCENT}; border-bottom-color: {ACCENT}; border-bottom-width: 3px; }}
    .stApp .stSidebar {{ background-color: #0a0a0a; border-right: 2px solid {ACCENT}; }}
    .stApp .stSidebar .sidebar-content {{ font-size: 18px; }}
    .stApp .stAlert {{ background-color: #1a0000; color: {DANGER}; border: 2px solid {DANGER}; font-size: 18px; }}
    .stApp .stSuccess {{ background-color: #1a1a00; color: {SUCCESS}; border: 2px solid {SUCCESS}; font-size: 18px; }}
    .stApp .stWarning {{ background-color: #1a1a00; color: {WARN}; border: 2px solid {WARN}; font-size: 18px; }}
    .stApp .stException {{ background-color: #1a0000; }}
    .stApp .stCheckbox label {{ font-size: 18px; }}
    .metric-card {{ background: #0a0a0a; border: 2px solid {BORDER}; padding: 16px; margin: 8px 0; }}
    .metric-card .label {{ color: {TEXT2}; font-size: 14px; text-transform: uppercase; letter-spacing: 1px; }}
    .metric-card .value {{ color: {ACCENT}; font-size: 2.2em; font-weight: bold; font-family: monospace; }}
    .login-box {{ max-width: 440px; margin: 80px auto; padding: 40px; background: #0a0a0a; border: 2px solid {ACCENT}; }}
    hr {{ border-color: {BORDER}; border-width: 2px; }}
    .stApp .stSelectbox div[data-baseweb="select"] > div {{ font-size: 18px; }}
    .stApp .stRadio label {{ font-size: 18px; }}
    .stApp .stSlider label {{ font-size: 18px; }}
</style>
"""
st.markdown(DARK_CSS, unsafe_allow_html=True)

init_db()

if "user" not in st.session_state:
    st.markdown("<div class='login-box'>", unsafe_allow_html=True)
    st.markdown("## SCHED//PRO")
    st.markdown("---")
    tab_l, tab_r = st.tabs(["LOGIN", "REGISTER"])
    with tab_l:
        with st.form("login_form"):
            u = st.text_input("Username", key="login_user")
            p = st.text_input("Password", type="password", key="login_pass")
            if st.form_submit_button("LOGIN", type="primary", use_container_width=True):
                user, err = authenticate_user(u, p)
                if user:
                    st.session_state.user = user
                    st.rerun()
                else:
                    st.error(err)
    with tab_r:
        with st.form("register_form"):
            u2 = st.text_input("Username", key="reg_user")
            p2 = st.text_input("Password", type="password", key="reg_pass")
            t2 = st.text_input("Company / Tenant name", key="reg_tenant")
            if st.form_submit_button("REGISTER", use_container_width=True):
                user, err = register_user(u2, p2, t2 or None)
                if user:
                    st.success("Registered — now log in")
                else:
                    st.error(err)
    st.markdown("</div>", unsafe_allow_html=True)
    st.stop()

tid = st.session_state.user["tenant_id"]


def sidebar():
    with st.sidebar:
        st.markdown(f"## SCHED//PRO")
        st.markdown(f"**{st.session_state.user['tenant_name']}**")
        st.markdown(f"`@{st.session_state.user['username']}`")
        st.markdown("---")
        st.markdown("### v0.3 MVP")
        st.markdown("multi-tenant · priority · csv-import")
        st.markdown("---")

        mode = st.radio("Schedule mode", ["Forward (priority-weighted)", "Backward (from due date)"], key="sched_mode")
        st.markdown("---")

        if st.button(">> RUN SCHEDULER", use_container_width=True, type="primary"):
            with st.spinner("Scheduling..."):
                if "Backward" in mode:
                    backward_schedule(tid)
                else:
                    forward_schedule(tid)
            st.success("Schedule generated")
            st.rerun()

        st.markdown("---")
        if st.button("[SNAP] SNAPSHOT", use_container_width=True):
            snapshot_schedule(tid, f"snap_{datetime.now().strftime('%H%M%S')}")
            st.success("Snapshot saved")

        snapshots = get_db().execute(
            "SELECT id, name, created_at FROM schedule_snapshots WHERE tenant_id = ? ORDER BY id DESC",
            (tid,)).fetchall()
        if snapshots:
            snap_options = {f"#{s['id']} {s['name']} ({s['created_at'][:19]})": s["id"] for s in snapshots}
            selected = st.selectbox("Restore snapshot", list(snap_options.keys()), key="snap_select")
            if st.button("RESTORE", use_container_width=True):
                restore_snapshot(tid, snap_options[selected])
                st.success("Restored")
                st.rerun()

        st.markdown("---")
        if st.button("LOGOUT", use_container_width=True):
            del st.session_state.user
            st.rerun()


def tab_work_centers():
    st.markdown("## // WORK CENTERS")
    conn = get_db()

    if "edit_wc" in st.session_state:
        r = st.session_state.edit_wc
        with st.form("edit_wc_form"):
            name = st.text_input("Name", value=r["name"])
            wtype = st.selectbox("Type", ["production", "inspection"],
                                 index=0 if r["type"] == "production" else 1)
            hpd = st.number_input("Hrs/Day", min_value=1, max_value=24, value=int(r["hours_per_day"]))
            eff = st.number_input("Efficiency %", min_value=10, max_value=100, value=int(r["efficiency"] * 100))
            conc = st.number_input("Max concurrent jobs", min_value=1, value=int(r["max_concurrent_jobs"]))
            c1, c2 = st.columns(2)
            if c1.form_submit_button("SAVE"):
                conn.execute("""
                    UPDATE work_centers SET name=?, type=?, hours_per_day=?, efficiency=?, max_concurrent_jobs=?
                    WHERE id=? AND tenant_id=?
                """, (name, wtype, hpd, eff / 100, conc, r["id"], tid))
                conn.commit()
                del st.session_state.edit_wc
                conn.close()
                st.rerun()
            if c2.form_submit_button("CANCEL"):
                del st.session_state.edit_wc
                conn.close()
                st.rerun()
        conn.close()
        return

    wc = conn.execute("SELECT * FROM work_centers WHERE tenant_id = ?", (tid,)).fetchall()
    conn.close()

    data = [{"ID": r["id"], "Name": r["name"], "Type": r["type"],
             "Hrs/Day": r["hours_per_day"], "Efficiency": f"{int(r['efficiency']*100)}%",
             "Max Concurrent": r["max_concurrent_jobs"]} for r in wc]
    if data:
        for r in data:
            c1, c2, c3 = st.columns([16, 1, 1])
            c1.dataframe(pd.DataFrame([r]), use_container_width=True, hide_index=True)
            if c2.button("\u270f\ufe0f", key=f"wc_edit_{r['ID']}"):
                orig = [x for x in wc if x["id"] == r["ID"]][0]
                st.session_state.edit_wc = orig
                st.rerun()
            if c3.button("\U0001f5d1\ufe0f", key=f"wc_del_{r['ID']}"):
                conn2 = get_db()
                try:
                    conn2.execute("DELETE FROM work_centers WHERE id = ? AND tenant_id = ?", (r["ID"], tid))
                    conn2.commit()
                except Exception as e:
                    st.error(f"Cannot delete: {e}")
                conn2.close()
                st.rerun()
    else:
        st.info("No work centers defined")

    with st.expander("+ ADD WORK CENTER"):
        col1, col2, col3, col4, col5 = st.columns([3, 2, 2, 2, 2])
        name = col1.text_input("Name", key="wc_name")
        wtype = col2.selectbox("Type", ["production", "inspection"], key="wc_type")
        hpd = col3.number_input("Hrs/Day", min_value=1, max_value=24, value=8, key="wc_hrs")
        eff = col4.number_input("Efficiency %", min_value=10, max_value=100, value=85, key="wc_eff")
        conc = col5.number_input("Max concurrent", min_value=1, value=1, key="wc_conc")
        if st.button("ADD", key="add_wc"):
            conn2 = get_db()
            conn2.execute("""
                INSERT INTO work_centers (tenant_id, name, type, hours_per_day, efficiency, max_concurrent_jobs)
                VALUES (?,?,?,?,?,?)
            """, (tid, name, wtype, hpd, eff / 100, conc))
            conn2.commit()
            conn2.close()
            st.rerun()


def tab_jobs():
    st.markdown("## // JOBS")
    conn = get_db()

    if "edit_job" in st.session_state:
        r = st.session_state.edit_job
        with st.form("edit_job_form"):
            pn = st.text_input("Part Number", value=r["part_number"])
            qty = st.number_input("Quantity", min_value=1, value=r["quantity"])
            due = st.date_input("Due Date", value=datetime.fromisoformat(r["due_date"]).date())
            pri = st.number_input("Priority (1-10)", min_value=1, max_value=10, value=r["priority"] or 5)
            status = st.selectbox("Status",
                                  ["unscheduled", "scheduled", "released", "in_progress", "completed", "cancelled"],
                                  index=["unscheduled", "scheduled", "released", "in_progress", "completed", "cancelled"].index(r["status"]))
            notes = st.text_area("Notes", value=r["notes"] or "")
            c1, c2 = st.columns(2)
            if c1.form_submit_button("SAVE"):
                conn.execute("""
                    UPDATE jobs SET part_number=?, quantity=?, due_date=?, priority=?, status=?, notes=?
                    WHERE id=? AND tenant_id=?
                """, (pn, qty, due.isoformat(), pri, status, notes, r["id"], tid))
                conn.commit()
                del st.session_state.edit_job
                conn.close()
                st.rerun()
            if c2.form_submit_button("CANCEL"):
                del st.session_state.edit_job
                conn.close()
                st.rerun()
        conn.close()
        return

    jobs = conn.execute("SELECT * FROM jobs WHERE tenant_id = ? ORDER BY due_date", (tid,)).fetchall()
    conn.close()

    for r in jobs:
        late = False
        if r["status"] in ("scheduled", "released", "in_progress"):
            conn2 = get_db()
            final = conn2.execute("""
                SELECT end_datetime FROM schedule WHERE job_id = ? AND tenant_id = ? ORDER BY end_datetime DESC LIMIT 1
            """, (r["id"], tid)).fetchone()
            conn2.close()
            if final and final["end_datetime"] > f"{r['due_date']}T22:00:00":
                late = True

        c1, c2, c3 = st.columns([16, 1, 1])
        with c1:
            label = f"#{r['id']} {r['part_number']}  |  Qty:{r['quantity']}  Due:{r['due_date'][:10]}  Pri:{r['priority']}  [{r['status']}]"
            color = "#FF4444" if late else TEXT
            st.markdown(f"<div style='color:{color}'>{label}</div>", unsafe_allow_html=True)
        if c2.button("\u270f\ufe0f", key=f"job_edit_{r['id']}"):
            st.session_state.edit_job = r
            st.rerun()
        if c3.button("\U0001f5d1\ufe0f", key=f"job_del_{r['id']}"):
            conn2 = get_db()
            conn2.execute("DELETE FROM jobs WHERE id = ? AND tenant_id = ?", (r["id"], tid))
            conn2.commit()
            conn2.close()
            st.rerun()

    st.markdown("---")
    with st.expander("+ ADD JOB"):
        col1, col2, col3, col4 = st.columns([3, 2, 2, 2])
        pn = col1.text_input("Part Number", key="job_pn")
        qty = col2.number_input("Quantity", min_value=1, value=100, key="job_qty")
        due = col3.date_input("Due Date", value=date.today(), key="job_due")
        pri = col4.number_input("Priority (1-10)", min_value=1, max_value=10, value=5, key="job_pri")
        notes = st.text_area("Notes", key="job_notes")
        if st.button("ADD JOB"):
            conn2 = get_db()
            conn2.execute("""
                INSERT INTO jobs (tenant_id, part_number, quantity, due_date, priority, notes)
                VALUES (?,?,?,?,?,?)
            """, (tid, pn, qty, due.isoformat(), pri, notes))
            conn2.commit()
            conn2.close()
            st.success("Job created — now add routing steps below")
            st.rerun()

    st.markdown("---")
    st.markdown("### Routing Steps")
    conn = get_db()
    steps = conn.execute("""
        SELECT rs.*, j.part_number AS job_pn, wc.name AS wc_name
        FROM routing_steps rs
        JOIN jobs j ON rs.job_id = j.id
        JOIN work_centers wc ON rs.work_center_id = wc.id
        WHERE j.tenant_id = ?
        ORDER BY rs.job_id, rs.step_order
    """, (tid,)).fetchall()
    conn.close()

    if steps:
        sd = [{"Job": f"#{s['job_id']} {s['job_pn']}", "Step": s["step_order"],
               "WC": s["wc_name"], "Setup hrs": s["setup_hrs"],
               "Run hrs/unit": s["run_hrs_per_unit"], "Desc": s["description"]} for s in steps]
        st.dataframe(pd.DataFrame(sd), use_container_width=True, hide_index=True)
    else:
        st.info("No routing steps defined")

    with st.expander("+ ADD ROUTING STEP"):
        conn = get_db()
        jobs_list = conn.execute(
            "SELECT id, part_number FROM jobs WHERE tenant_id = ? ORDER BY id", (tid,)).fetchall()
        wc_list = conn.execute(
            "SELECT id, name FROM work_centers WHERE tenant_id = ? ORDER BY id", (tid,)).fetchall()
        conn.close()
        if not jobs_list or not wc_list:
            st.warning("Define jobs and work centers first")
        else:
            col1, col2, col3, col4, col5 = st.columns([2, 1, 2, 2, 2])
            sel_job = col1.selectbox("Job", {j["id"]: f"#{j['id']} {j['part_number']}" for j in jobs_list}, key="rs_job")
            order = col2.number_input("Step#", min_value=1, value=1, key="rs_order")
            sel_wc = col3.selectbox("Work Center", {w["id"]: w["name"] for w in wc_list}, key="rs_wc")
            setup = col4.number_input("Setup (hrs)", min_value=0.0, value=0.5, step=0.1, key="rs_setup")
            run = col5.number_input("Run hrs/unit", min_value=0.0, value=0.01, step=0.001, format="%.3f", key="rs_run")
            desc = st.text_input("Description", key="rs_desc")
            if st.button("ADD STEP"):
                conn2 = get_db()
                try:
                    conn2.execute("""
                        INSERT INTO routing_steps (tenant_id, job_id, step_order, work_center_id, setup_hrs, run_hrs_per_unit, description)
                        VALUES (?,?,?,?,?,?,?)
                    """, (tid, sel_job, order, sel_wc, setup, run, desc))
                    conn2.commit()
                except Exception as e:
                    st.error(str(e))
                conn2.close()
                st.rerun()


def tab_gantt():
    st.markdown("## // SCHEDULE GANTT")
    conn = get_db()
    schedule = conn.execute("""
        SELECT s.*, j.part_number, j.quantity, j.due_date, wc.name AS wc_name, wc.type AS wc_type,
               rs.step_order, rs.description AS step_desc
        FROM schedule s
        JOIN jobs j ON s.job_id = j.id
        JOIN work_centers wc ON s.work_center_id = wc.id
        JOIN routing_steps rs ON s.routing_step_id = rs.id
        WHERE s.tenant_id = ?
        ORDER BY s.start_datetime
    """, (tid,)).fetchall()
    conflicts = get_conflicts(tid)
    caps = get_capacity_violations(tid)
    conn.close()

    c1, c2, c3 = st.columns(3)
    c1.markdown(f"<div class='metric-card'><div class='label'>CONFLICTS</div><div class='value'>{len(conflicts)}</div></div>", unsafe_allow_html=True)
    c2.markdown(f"<div class='metric-card'><div class='label'>SCHEDULED OPS</div><div class='value'>{len(schedule)}</div></div>", unsafe_allow_html=True)
    c3.markdown(f"<div class='metric-card'><div class='label'>CAPACITY OVER</div><div class='value'>{len(caps)}</div></div>", unsafe_allow_html=True)

    if caps:
        st.warning("Capacity violations detected")
        cd = pd.DataFrame([{
            "Work Center": r["name"], "Date": r["date"],
            "Scheduled hrs": r["total_hrs"], "Max hrs": r["hours_per_day"]
        } for r in caps])
        st.dataframe(cd, use_container_width=True, hide_index=True)

    if len(conflicts) > 0:
        st.error(f"{len(conflicts)} overlapping operations detected")
    else:
        st.success("No conflicts")

    if not schedule:
        st.info("Run scheduler first")
        return

    df = pd.DataFrame([{
        "Job": f"#{r['job_id']} {r['part_number']}",
        "Work Center": r["wc_name"],
        "Type": r["wc_type"],
        "Step": f"Op{r['step_order']}",
        "Start": datetime.fromisoformat(r["start_datetime"]),
        "End": datetime.fromisoformat(r["end_datetime"]),
        "Due": r["due_date"],
    } for r in schedule])

    fig = go.Figure()
    job_colors = {}
    palette = ["#0088FF", "#FF8800", "#00CC88", "#CC44FF", "#FFCC00", "#44CCFF", "#FF4488", "#88FF44"]
    for i, jid in enumerate(sorted(df["Job"].unique())):
        job_colors[jid] = palette[i % len(palette)]

    for _, row in df.iterrows():
        color = job_colors.get(row["Job"], "#888888")
        is_inspection = row["Type"] == "inspection"
        fig.add_trace(go.Bar(
            base=[row["Start"]],
            x=[(row["End"] - row["Start"]).total_seconds() / 3600 / 24],
            y=[row["Work Center"]],
            orientation="h",
            name=row["Job"],
            text=f"{row['Job']} - {row['Step']}",
            hoverinfo="text",
            marker_color=color,
            marker_line_width=3,
            marker_line_color="#FFFFFF" if is_inspection else "#000000",
            marker_pattern_shape="/" if is_inspection else "",
            showlegend=False,
            width=0.7,
        ))

    fig.update_layout(
        barmode="stack",
        height=max(300, len(df["Work Center"].unique()) * 60),
        paper_bgcolor="#000000",
        plot_bgcolor="#000000",
        font_color="#cccccc",
        xaxis_title="Date",
        yaxis_title="Work Center",
        margin=dict(l=20, r=20, t=20, b=20),
    )
    fig.update_xaxes(gridcolor="#222222", zeroline=False)
    fig.update_yaxes(gridcolor="#222222")
    st.plotly_chart(fig, use_container_width=True)

    st.markdown("### Schedule Table")
    display = df[["Job", "Work Center", "Step", "Start", "End"]].copy()
    display["Start"] = display["Start"].dt.strftime("%Y-%m-%d %H:%M")
    display["End"] = display["End"].dt.strftime("%Y-%m-%d %H:%M")
    st.dataframe(display, use_container_width=True, hide_index=True)

    st.markdown("### Move Job (What-if)")
    conn2 = get_db()
    job_ops = conn2.execute("""
        SELECT DISTINCT s.job_id, j.part_number FROM schedule s
        JOIN jobs j ON s.job_id = j.id
        WHERE s.tenant_id = ? ORDER BY s.job_id
    """, (tid,)).fetchall()
    conn2.close()
    if job_ops:
        col1, col2, col3 = st.columns([3, 3, 1])
        job_map = {f"#{j['job_id']} {j['part_number']}": j["job_id"] for j in job_ops}
        sel = col1.selectbox("Select job to move", list(job_map.keys()), key="move_job_sel")
        new_start = col2.date_input("New start date", value=date.today(), key="move_date")
        if col3.button("MOVE"):
            move_job(job_map[sel], tid, new_start.isoformat())
            st.success("Job moved")
            st.rerun()


def tab_dashboard():
    st.markdown("## // DASHBOARD")
    conn = get_db()

    jobs_all = conn.execute("SELECT COUNT(*) AS c FROM jobs WHERE tenant_id = ?", (tid,)).fetchone()
    jobs_sched = conn.execute("SELECT COUNT(*) AS c FROM jobs WHERE tenant_id = ? AND status = 'scheduled'", (tid,)).fetchone()
    jobs_comp = conn.execute("SELECT COUNT(*) AS c FROM jobs WHERE tenant_id = ? AND status = 'completed'", (tid,)).fetchone()
    jobs_prog = conn.execute("SELECT COUNT(*) AS c FROM jobs WHERE tenant_id = ? AND status = 'in_progress'", (tid,)).fetchone()
    wc_count = conn.execute("SELECT COUNT(*) AS c FROM work_centers WHERE tenant_id = ?", (tid,)).fetchone()
    late_count = len(get_jobs_past_due(tid))

    c1, c2, c3, c4, c5 = st.columns(5)
    c1.markdown(f"<div class='metric-card'><div class='label'>TOTAL JOBS</div><div class='value'>{jobs_all['c']}</div></div>", unsafe_allow_html=True)
    c2.markdown(f"<div class='metric-card'><div class='label'>SCHEDULED</div><div class='value'>{jobs_sched['c']}</div></div>", unsafe_allow_html=True)
    c3.markdown(f"<div class='metric-card'><div class='label'>IN PROGRESS</div><div class='value'>{jobs_prog['c']}</div></div>", unsafe_allow_html=True)
    c4.markdown(f"<div class='metric-card'><div class='label'>DONE</div><div class='value'>{jobs_comp['c']}</div></div>", unsafe_allow_html=True)
    c5.markdown(f"<div class='metric-card'><div class='label' style='color:#FF4444'>LATE</div><div class='value' style='color:#FF4444'>{late_count}</div></div>", unsafe_allow_html=True)

    load_data = conn.execute("""
        SELECT wc.name, wc.type, wc.hours_per_day,
               COALESCE(SUM(
                   (julianday(s.end_datetime) - julianday(s.start_datetime)) * 24
               ), 0) AS scheduled_hrs
        FROM work_centers wc
        LEFT JOIN schedule s ON s.work_center_id = wc.id
        WHERE wc.tenant_id = ?
        GROUP BY wc.id
    """, (tid,)).fetchall()
    conn.close()

    if load_data:
        st.markdown("### Work Center Load")
        ld = pd.DataFrame([{
            "Work Center": r["name"],
            "Type": r["type"],
            "Hours Scheduled": round(r["scheduled_hrs"], 1),
            "Capacity (hrs/week)": r["hours_per_day"] * 5,
        } for r in load_data])
        ld["Load %"] = (ld["Hours Scheduled"] / ld["Capacity (hrs/week)"] * 100).clip(upper=100).round(1)
        st.dataframe(ld, use_container_width=True, hide_index=True)

        fig = px.bar(ld, x="Work Center", y="Load %", color="Type",
                     color_discrete_map={"production": "#0088FF", "inspection": "#FF8800"},
                     title="CAPACITY LOAD %")
        fig.update_layout(paper_bgcolor="#000000", plot_bgcolor="#000000", font_color="#cccccc")
        fig.update_xaxes(gridcolor="#222222")
        fig.update_yaxes(gridcolor="#222222", range=[0, 110])
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("No schedule data")


def tab_conflicts():
    st.markdown("## // CONFLICTS & CAPACITY")
    t1, t2 = st.tabs(["Overlapping Operations", "Capacity Violations"])

    with t1:
        conflicts = get_conflicts(tid)
        if not conflicts:
            st.success("No overlapping operations")
        else:
            conn = get_db()
            data = []
            for r in conflicts:
                j = conn.execute("SELECT part_number FROM jobs WHERE id = ? AND tenant_id = ?", (r["job_id"], tid)).fetchone()
                w = conn.execute("SELECT name FROM work_centers WHERE id = ? AND tenant_id = ?", (r["work_center_id"], tid)).fetchone()
                data.append({
                    "Job": f"#{r['job_id']} {j['part_number'] if j else ''}",
                    "Work Center": w["name"] if w else "",
                    "Start": r["start_datetime"][:16],
                    "End": r["end_datetime"][:16],
                })
            conn.close()
            st.dataframe(pd.DataFrame(data), use_container_width=True, hide_index=True)

    with t2:
        caps = get_capacity_violations(tid)
        if not caps:
            st.success("No capacity violations")
        else:
            cd = pd.DataFrame([{
                "Work Center": r["name"],
                "Date": r["date"],
                "Operations": r["ops"],
                "Scheduled hrs": r["total_hrs"],
                "Max hrs": r["hours_per_day"],
                "Over by": round(r["total_hrs"] - r["hours_per_day"], 1),
            } for r in caps])
            st.dataframe(cd, use_container_width=True, hide_index=True)


def tab_holidays():
    st.markdown("## // CALENDAR")
    conn = get_db()
    holidays = conn.execute(
        "SELECT * FROM holidays WHERE tenant_id = ? ORDER BY date", (tid,)).fetchall()
    conn.close()

    if holidays:
        hd = pd.DataFrame([{"Date": r["date"], "Description": r["description"]} for r in holidays])
        st.dataframe(hd, use_container_width=True, hide_index=True)
    else:
        st.info("No holidays defined")

    with st.expander("+ ADD HOLIDAY"):
        col1, col2 = st.columns([2, 4])
        hdate = col1.date_input("Date", key="hol_date")
        hdesc = col2.text_input("Description (e.g. New Year)", key="hol_desc")
        if st.button("ADD", key="add_holiday"):
            conn2 = get_db()
            try:
                conn2.execute("INSERT INTO holidays (tenant_id, date, description) VALUES (?, ?, ?)",
                              (tid, hdate.isoformat(), hdesc))
                conn2.commit()
                st.rerun()
            except Exception as e:
                st.error(str(e))
            conn2.close()


def tab_whatif():
    st.markdown("## // WHAT-IF: RUSH JOB")
    conn = get_db()
    wc_list = conn.execute(
        "SELECT id, name FROM work_centers WHERE tenant_id = ? ORDER BY id", (tid,)).fetchall()
    conn.close()

    if not wc_list:
        st.warning("Define work centers first")
        return

    st.markdown("Simulate inserting an urgent job into the current schedule")

    with st.form("whatif_form"):
        pn = st.text_input("Part Number", value="RUSH-001")
        qty = st.number_input("Quantity", min_value=1, value=50)
        due = st.date_input("Due Date", value=date.today() + timedelta(days=7))

        st.markdown("**Routing steps**")
        steps = []
        n_steps = st.number_input("Number of operations", min_value=1, max_value=10, value=2, key="wi_nsteps")
        for i in range(int(n_steps)):
            col1, col2, col3, col4, col5 = st.columns([2, 2, 2, 2, 3])
            wc_opts = {w["id"]: w["name"] for w in wc_list}
            wc_id = col1.selectbox(f"Op{i+1} WC", list(wc_opts.keys()),
                                   format_func=lambda x: wc_opts[x],
                                   key=f"wi_wc_{i}")
            setup = col2.number_input(f"Setup hrs", min_value=0.0, value=0.5, step=0.1, key=f"wi_setup_{i}")
            run = col3.number_input(f"Run hrs/unit", min_value=0.0, value=0.02, step=0.001, format="%.3f", key=f"wi_run_{i}")
            order = col4.number_input(f"Step order", min_value=1, value=i + 1, key=f"wi_order_{i}")
            desc = col5.text_input(f"Description", value="", key=f"wi_desc_{i}")
            steps.append({"work_center_id": wc_id, "setup_hrs": setup,
                          "run_hrs_per_unit": run, "order": order, "desc": desc})

        if st.form_submit_button("SIMULATE RUSH JOB", type="primary"):
            result = what_if_rush_job(tid, pn, qty, due.isoformat(), steps, priority=10)
            if result["rush_on_time"]:
                st.success(f"Rush job #{result['rush_job_id']} fits on time! ({result['total_late_jobs']} total late jobs)")
            else:
                st.warning(f"Rush job #{result['rush_job_id']} will be late. {result['total_late_jobs']} total late jobs in schedule.")
            st.json(result)
            st.rerun()


def tab_import():
    st.markdown("## // CSV IMPORT")
    st.markdown("Upload a CSV to bulk-import jobs (and optionally routing steps).")

    st.markdown("""
    ### Format
    **Required columns:** `part_number`, `quantity`, `due_date`  
    **Optional columns:** `priority`, `notes`, `wc_1`, `setup_1`, `run_1`, `wc_2`, `setup_2`, `run_2`, ...

    Example:
    ```
    part_number,quantity,due_date,priority,wc_1,setup_1,run_1,wc_2,setup_2,run_2
    BRKT-100,200,2026-06-15,5,1,1.0,0.05,2,0.5,0.02
    SHFT-050,50,2026-06-01,8,1,0.5,0.08,2,0.25,0.01
    ```
    Use work center IDs from the WORK CENTERS tab.
    """)

    uploaded = st.file_uploader("Choose CSV file", type="csv", key="csv_uploader")
    if uploaded is not None:
        df = pd.read_csv(uploaded)
        st.markdown(f"**{len(df)} rows loaded**")
        st.dataframe(df.head(10), use_container_width=True, hide_index=True)

        if st.button("IMPORT JOBS", type="primary", key="import_btn"):
            conn = get_db()
            imported = 0
            errors = []
            for _, row in df.iterrows():
                row = row.dropna().to_dict()
                pn = row.get("part_number")
                qty = row.get("quantity")
                due = row.get("due_date")
                if not pn or not qty or not due:
                    errors.append(f"Missing required field: {row}")
                    continue
                pri = int(row.get("priority", 5))
                notes = str(row.get("notes", ""))
                cur = conn.execute("""
                    INSERT INTO jobs (tenant_id, part_number, quantity, due_date, priority, notes)
                    VALUES (?,?,?,?,?,?)
                """, (tid, str(pn), int(qty), str(due)[:10], pri, notes))
                job_id = cur.lastrowid
                for i in range(1, 20):
                    wc_key = f"wc_{i}"
                    setup_key = f"setup_{i}"
                    run_key = f"run_{i}"
                    wc = row.get(wc_key)
                    setup = row.get(setup_key)
                    run_hrs = row.get(run_key)
                    if wc is not None and run_hrs is not None:
                        desc = row.get(f"desc_{i}", "")
                        wc_id = int(wc)
                        setup_hrs = float(setup) if setup else 0
                        run_val = float(run_hrs)
                        try:
                            conn.execute("""
                                INSERT INTO routing_steps (tenant_id, job_id, step_order, work_center_id, setup_hrs, run_hrs_per_unit, description)
                                VALUES (?,?,?,?,?,?,?)
                            """, (tid, job_id, i, wc_id, setup_hrs, run_val, desc))
                        except Exception as e:
                            errors.append(f"Step {i} for job {pn}: {e}")
                    else:
                        break
                imported += 1
            conn.commit()
            conn.close()
            st.success(f"Imported {imported} jobs")
            if errors:
                for e in errors[:5]:
                    st.warning(e)
                if len(errors) > 5:
                    st.warning(f"... and {len(errors)-5} more errors")
            st.rerun()


tabs = st.tabs(["WORK CENTERS", "JOBS", "GANTT", "DASHBOARD", "CONFLICTS", "CALENDAR", "WHAT-IF", "CSV IMPORT"])

with tabs[0]: tab_work_centers()
with tabs[1]: tab_jobs()
with tabs[2]: tab_gantt()
with tabs[3]: tab_dashboard()
with tabs[4]: tab_conflicts()
with tabs[5]: tab_holidays()
with tabs[6]: tab_whatif()
with tabs[7]: tab_import()

sidebar()
