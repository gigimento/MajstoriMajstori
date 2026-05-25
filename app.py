# -*- coding: utf-8 -*-
import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from datetime import datetime, date, timedelta
from models import init_db, authenticate_user, register_user, get_db
from scheduler import (forward_schedule, backward_schedule, get_conflicts,
                       get_capacity_violations, move_job, what_if_rush_job,
                       snapshot_schedule, restore_snapshot)
from license import init_license, check_license, activate_license, get_license_info

st.set_page_config(page_title="SCHED//PRO", layout="wide", page_icon="\u26a1")

HC = st.sidebar.checkbox("VISOKI KONTRAST", value=False, key="hc_toggle") if "user" in st.session_state else False

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
    tab_l, tab_r = st.tabs(["PRIJAVA", "REGISTRACIJA"])
    with tab_l:
        with st.form("login_form"):
            u = st.text_input("Korisničko ime", key="login_user")
            p = st.text_input("Lozinka", type="password", key="login_pass")
            if st.form_submit_button("PRIJAVA", type="primary", use_container_width=True):
                user, err = authenticate_user(u, p)
                if user:
                    st.session_state.user = user
                    st.rerun()
                else:
                    st.error(err)
    with tab_r:
        with st.form("register_form"):
            u2 = st.text_input("Korisničko ime", key="reg_user")
            p2 = st.text_input("Lozinka", type="password", key="reg_pass")
            t2 = st.text_input("Naziv firme / tenanta", key="reg_tenant")
            if st.form_submit_button("REGISTRACIJA", use_container_width=True):
                user, err = register_user(u2, p2, t2 or None)
                if user:
                    st.success("Registracija uspešna — sada se prijavite")
                else:
                    st.error(err)
    st.markdown("</div>", unsafe_allow_html=True)
    st.stop()

tid = st.session_state.user["tenant_id"]

init_license(tid)
lic = check_license(tid)

if lic["status"] in ("expired", "tampered"):
    st.markdown("## // LICENCA")
    st.error(lic["message"])
    with st.form("license_form"):
        key_input = st.text_input("Unesite licencni ključ", placeholder="SCHEDPRO-XXXXX-XXXXX-XXXXX-XXXXX")
        if st.form_submit_button("AKTIVIRAJ", type="primary", use_container_width=True):
            ok, msg = activate_license(tid, key_input)
            if ok:
                st.success(msg)
                st.rerun()
            else:
                st.error(msg)
    st.markdown("---")
    st.markdown("**Hardver ID:** `" + get_license_info(tid)["hw_id"][:16] + "..." + "`")
    st.markdown("Pošaljite ovaj Hardver ID developeru da dobijete licencni ključ.")
    st.stop()


def sidebar():
    with st.sidebar:
        st.markdown(f"## SCHED//PRO")
        st.markdown(f"**{st.session_state.user['tenant_name']}**")
        st.markdown(f"`@{st.session_state.user['username']}`")

        lic_status = check_license(tid)
        if lic_status["is_licensed"]:
            st.markdown("✅ **Full verzija**")
        elif lic_status["days_left"] > 0:
            days = lic_status["days_left"]
            color = "#FFCC00" if days <= 14 else "#AAAAAA"
            st.markdown(f"<span style='color:{color}'>⏳ Trial: {days} dan(a)</span>", unsafe_allow_html=True)
        else:
            st.markdown("❌ **Licenca istekla**")

        st.markdown("---")
        st.markdown("### v1.0")
        st.markdown("nalozi · sabloni · stampa · zalihe")
        st.markdown("---")

        mode = st.radio("Režim raspoređivanja", ["Napred (prioritet)", "Nazad (od roka)"], key="sched_mode")
        st.markdown("---")

        if st.button(">> POKRENI RASPOREĐIVAČ", use_container_width=True, type="primary"):
            with st.spinner("Raspoređivanje..."):
                if "Nazad" in mode:
                    backward_schedule(tid)
                else:
                    forward_schedule(tid)
            st.success("Raspored generisan")
            st.rerun()

        st.markdown("---")
        if st.button("[SNAP] SNAPSHOT", use_container_width=True):
            snapshot_schedule(tid, f"snap_{datetime.now().strftime('%H%M%S')}")
            st.success("Snimljeno")

        snapshots = get_db().execute(
            "SELECT id, name, created_at FROM schedule_snapshots WHERE tenant_id = ? ORDER BY id DESC",
            (tid,)).fetchall()
        if snapshots:
            snap_options = {f"#{s['id']} {s['name']} ({s['created_at'][:19]})": s["id"] for s in snapshots}
            selected = st.selectbox("Vrati snapshot", list(snap_options.keys()), key="snap_select")
            if st.button("VRAĆANJE", use_container_width=True):
                restore_snapshot(tid, snap_options[selected])
                st.success("Vraćeno")
                st.rerun()

        st.markdown("---")
        if st.button("ODJAVA", use_container_width=True):
            del st.session_state.user
            st.rerun()


def tab_work_centers():
    st.markdown("## // RADNA MESTA")
    conn = get_db()

    if "edit_wc" in st.session_state:
        r = st.session_state.edit_wc
        with st.form("edit_wc_form"):
            name = st.text_input("Naziv", value=r["name"])
            wtype = st.selectbox("Tip", ["proizvodno", "kontrola"],
                                 index=0 if r["type"] == "production" else 1)
            hpd = st.number_input("H/dan", min_value=1, max_value=24, value=int(r["hours_per_day"]))
            eff = st.number_input("Efikasnost %", min_value=10, max_value=100, value=int(r["efficiency"] * 100))
            conc = st.number_input("Maks. paralelnih poslova", min_value=1, value=int(r["max_concurrent_jobs"]))
            c1, c2 = st.columns(2)
            if c1.form_submit_button("SAČUVAJ"):
                conn.execute("""
                    UPDATE work_centers SET name=?, type=?, hours_per_day=?, efficiency=?, max_concurrent_jobs=?
                    WHERE id=? AND tenant_id=?
                """, (name, "production" if wtype == "proizvodno" else "inspection", hpd, eff / 100, conc, r["id"], tid))
                conn.commit()
                del st.session_state.edit_wc
                conn.close()
                st.rerun()
            if c2.form_submit_button("ODUSTANI"):
                del st.session_state.edit_wc
                conn.close()
                st.rerun()
        conn.close()
        return

    wc = conn.execute("SELECT * FROM work_centers WHERE tenant_id = ?", (tid,)).fetchall()
    conn.close()

    data = [{"ID": r["id"], "Naziv": r["name"], "Tip": "proizvodno" if r["type"] == "production" else "kontrola",
             "H/dan": r["hours_per_day"], "Efikasnost": f"{int(r['efficiency']*100)}%",
             "Maks. paralelno": r["max_concurrent_jobs"]} for r in wc]
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
                    st.error(f"Ne može da se obriše: {e}")
                conn2.close()
                st.rerun()
    else:
        st.info("Nema definisanih radnih mesta")

    with st.expander("+ DODAJ RADNO MESTO"):
        col1, col2, col3, col4, col5 = st.columns([3, 2, 2, 2, 2])
        name = col1.text_input("Naziv", key="wc_name")
        wtype = col2.selectbox("Tip", ["proizvodno", "kontrola"], key="wc_type")
        hpd = col3.number_input("H/dan", min_value=1, max_value=24, value=8, key="wc_hrs")
        eff = col4.number_input("Efikasnost %", min_value=10, max_value=100, value=85, key="wc_eff")
        conc = col5.number_input("Maks. paralelno", min_value=1, value=1, key="wc_conc")
        if st.button("DODAJ", key="add_wc"):
            conn2 = get_db()
            conn2.execute("""
                INSERT INTO work_centers (tenant_id, name, type, hours_per_day, efficiency, max_concurrent_jobs)
                VALUES (?,?,?,?,?,?)
            """, (tid, name, "production" if wtype == "proizvodno" else "inspection", hpd, eff / 100, conc))
            conn2.commit()
            conn2.close()
            st.rerun()


def _print_job_html(job, steps):
    rows = "".join(f"""
        <tr>
            <td>{s['step_order']}</td>
            <td>{s['wc_name']}</td>
            <td>{s['description'] or ''}</td>
            <td>{s['setup_hrs']}h</td>
            <td>{s['run_hrs_per_unit']}h</td>
        </tr>""" for s in steps)
    return f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"><title>Radni nalog #{job['id']}</title>
<style>
    @page {{ margin: 8mm; }}
    body {{ font-family: 'Courier New', monospace; font-size: 11pt; color: #000; background: #fff; }}
    h1 {{ font-size: 18pt; border-bottom: 3px solid #000; padding-bottom: 4px; text-transform: uppercase; }}
    h2 {{ font-size: 14pt; margin-top: 20px; }}
    table {{ width: 100%; border-collapse: collapse; margin-top: 10px; }}
    th, td {{ border: 2px solid #000; padding: 6px 10px; text-align: left; }}
    th {{ background: #eee; font-weight: bold; text-transform: uppercase; font-size: 10pt; }}
    td {{ font-size: 11pt; }}
    .info {{ margin: 4px 0; }}
    .label {{ font-weight: bold; }}
    .footer {{ margin-top: 30px; border-top: 1px solid #000; padding-top: 8px; font-size: 9pt; }}
</style>
</head><body>
<h1>RADNI NALOG</h1>
<p class="info"><span class="label">Broj naloga:</span> #{job['id']}</p>
<p class="info"><span class="label">Oznaka dela:</span> {job['part_number']}</p>
<p class="info"><span class="label">Količina:</span> {job['quantity']} kom</p>
<p class="info"><span class="label">Rok isporuke:</span> {job['due_date'][:10]}</p>
<p class="info"><span class="label">Prioritet:</span> {job['priority']}</p>
<hr>
<h2>TEHNOLOŠKI POSTUPAK</h2>
<table>
<tr><th>Korak</th><th>Radno mesto</th><th>Opis</th><th>Priprema</th><th>Obrada/kom</th></tr>
{rows}
</table>
<div class="footer">
    <p>Štampano: {datetime.now().strftime('%d.%m.%Y %H:%M')}</p>
    <p style="margin-top:40px">Izvršilac: ___________________  Datum: ________  Potpis: ________</p>
</div>
</body></html>"""


def tab_jobs():
    st.markdown("## // RADNI NALOZI (PROIZVODNJA)")
    conn = get_db()

    if "edit_job" in st.session_state:
        r = st.session_state.edit_job
        with st.form("edit_job_form"):
            pn = st.text_input("Oznaka dela", value=r["part_number"])
            qty = st.number_input("Količina", min_value=1, value=r["quantity"])
            due = st.date_input("Rok isporuke", value=datetime.fromisoformat(r["due_date"]).date())
            pri = st.number_input("Prioritet (1-10)", min_value=1, max_value=10, value=r["priority"] or 5)
            status = st.selectbox("Status",
                                  ["neraspoređeno", "raspoređeno", "pušteno", "u_radu", "završeno", "otkazano"],
                                  index=["unscheduled", "scheduled", "released", "in_progress", "completed", "cancelled"].index(r["status"]))
            notes = st.text_area("Napomena", value=r["notes"] or "")
            c1, c2 = st.columns(2)
            if c1.form_submit_button("SAČUVAJ"):
                status_map = {"neraspoređeno": "unscheduled", "raspoređeno": "scheduled",
                              "pušteno": "released", "u_radu": "in_progress",
                              "završeno": "completed", "otkazano": "cancelled"}
                conn.execute("""
                    UPDATE jobs SET part_number=?, quantity=?, due_date=?, priority=?, status=?, notes=?
                    WHERE id=? AND tenant_id=?
                """, (pn, qty, due.isoformat(), pri, status_map[status], notes, r["id"], tid))
                conn.commit()
                del st.session_state.edit_job
                conn.close()
                st.rerun()
            if c2.form_submit_button("ODUSTANI"):
                del st.session_state.edit_job
                conn.close()
                st.rerun()
        conn.close()
        return

    delivery_orders = {r["id"]: r for r in conn.execute(
        "SELECT id, customer_name, part_number FROM delivery_orders WHERE tenant_id = ?", (tid,)).fetchall()}

    jobs = conn.execute("""
        SELECT j.*, do.customer_name
        FROM jobs j
        LEFT JOIN delivery_orders do ON j.delivery_order_id = do.id
        WHERE j.tenant_id = ?
        ORDER BY j.due_date
    """, (tid,)).fetchall()
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

        c1, c2, c3, c4 = st.columns([12, 2, 1, 1])
        with c1:
            status_sr = {"unscheduled": "neraspoređeno", "scheduled": "raspoređeno",
                         "released": "pušteno", "in_progress": "u_radu",
                         "completed": "završeno", "cancelled": "otkazano"}
            cust = f" [{r['customer_name']}]" if r["customer_name"] else ""
            label = f"#{r['id']} {r['part_number']}{cust}  |  Kol:{r['quantity']}  Rok:{r['due_date'][:10]}  Pri:{r['priority']}  [{status_sr[r['status']]}]"
            color = "#FF4444" if late else TEXT
            st.markdown(f"<div style='color:{color}'>{label}</div>", unsafe_allow_html=True)

        if c2.button("🖨️", key=f"job_print_{r['id']}"):
            st.session_state.print_job_id = r["id"]
            st.rerun()
        if c3.button("✏️", key=f"job_edit_{r['id']}"):
            st.session_state.edit_job = r
            st.rerun()
        if c4.button("🗑️", key=f"job_del_{r['id']}"):
            conn2 = get_db()
            conn2.execute("DELETE FROM jobs WHERE id = ? AND tenant_id = ?", (r["id"], tid))
            conn2.commit()
            conn2.close()
            st.rerun()

    if "print_job_id" in st.session_state:
        st.markdown("---")
        conn = get_db()
        pj = conn.execute("SELECT * FROM jobs WHERE id = ? AND tenant_id = ?",
                          (st.session_state.print_job_id, tid)).fetchone()
        psteps = conn.execute("""
            SELECT rs.*, wc.name AS wc_name FROM routing_steps rs
            JOIN work_centers wc ON rs.work_center_id = wc.id
            WHERE rs.job_id = ? AND rs.tenant_id = ?
            ORDER BY rs.step_order
        """, (st.session_state.print_job_id, tid)).fetchall()
        conn.close()
        if pj:
            html = _print_job_html(dict(pj), [dict(s) for s in psteps])
            st.download_button("📥 PREUZMI HTML ZA ŠTAMPU", data=html.encode("utf-8"),
                               file_name=f"radni_nalog_{pj['id']}.html", mime="text/html",
                               type="primary", use_container_width=True)
            st.markdown("---")
            st.markdown("### Pregled za štampu")
            st.components.v1.html(html, height=800, scrolling=True)
        if st.button("ZATVORI"):
            del st.session_state.print_job_id
            st.rerun()


def tab_gantt():
    st.markdown("## // GANT RASPORED")
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
    c1.markdown(f"<div class='metric-card'><div class='label'>KONFLIKTI</div><div class='value'>{len(conflicts)}</div></div>", unsafe_allow_html=True)
    c2.markdown(f"<div class='metric-card'><div class='label'>RASPOREĐENE OPERACIJE</div><div class='value'>{len(schedule)}</div></div>", unsafe_allow_html=True)
    c3.markdown(f"<div class='metric-card'><div class='label'>PREKORAČENJE KAPACITETA</div><div class='value'>{len(caps)}</div></div>", unsafe_allow_html=True)

    if caps:
        st.warning("Detektovano prekoračenje kapaciteta")
        cd = pd.DataFrame([{
            "Radno mesto": r["name"], "Datum": r["date"],
            "Planirano h": r["total_hrs"], "Max h": r["hours_per_day"]
        } for r in caps])
        st.dataframe(cd, use_container_width=True, hide_index=True)

    if len(conflicts) > 0:
        st.error(f"{len(conflicts)} operacija se preklapa")
    else:
        st.success("Nema konflikata")

    if not schedule:
        st.info("Prvo pokreni raspoređivač")
        return

    df = pd.DataFrame([{
        "Posao": f"#{r['job_id']} {r['part_number']}",
        "Radno mesto": r["wc_name"],
        "Tip": r["wc_type"],
        "Korak": f"Op{r['step_order']}",
        "Početak": datetime.fromisoformat(r["start_datetime"]),
        "Kraj": datetime.fromisoformat(r["end_datetime"]),
        "Rok": r["due_date"],
    } for r in schedule])

    fig = go.Figure()
    job_colors = {}
    palette = ["#0088FF", "#FF8800", "#00CC88", "#CC44FF", "#FFCC00", "#44CCFF", "#FF4488", "#88FF44"]
    for i, jid in enumerate(sorted(df["Posao"].unique())):
        job_colors[jid] = palette[i % len(palette)]

    for _, row in df.iterrows():
        color = job_colors.get(row["Posao"], "#888888")
        is_inspection = row["Tip"] == "inspection"
        fig.add_trace(go.Bar(
            base=[row["Početak"]],
            x=[(row["Kraj"] - row["Početak"]).total_seconds() / 3600 / 24],
            y=[row["Radno mesto"]],
            orientation="h",
            name=row["Posao"],
            text=f"{row['Posao']} - {row['Korak']}",
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
        height=max(300, len(df["Radno mesto"].unique()) * 60),
        paper_bgcolor="#000000",
        plot_bgcolor="#000000",
        font_color="#cccccc",
        xaxis_title="Datum",
        yaxis_title="Radno mesto",
        margin=dict(l=20, r=20, t=20, b=20),
    )
    fig.update_xaxes(gridcolor="#222222", zeroline=False)
    fig.update_yaxes(gridcolor="#222222")
    st.plotly_chart(fig, use_container_width=True)

    st.markdown("### Tabela rasporeda")
    display = df[["Posao", "Radno mesto", "Korak", "Početak", "Kraj"]].copy()
    display["Početak"] = display["Početak"].dt.strftime("%Y-%m-%d %H:%M")
    display["Kraj"] = display["Kraj"].dt.strftime("%Y-%m-%d %H:%M")
    st.dataframe(display, use_container_width=True, hide_index=True)

    st.markdown("### Pomeri posao (Šta-ako)")
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
        sel = col1.selectbox("Izaberi posao za pomeranje", list(job_map.keys()), key="move_job_sel")
        new_start = col2.date_input("Novi datum početka", value=date.today(), key="move_date")
        if col3.button("POMERI"):
            move_job(job_map[sel], tid, new_start.isoformat())
            st.success("Posao pomeren")
            st.rerun()


def tab_conflicts():
    st.markdown("## // KONFLIKTI I KAPACITET")
    t1, t2 = st.tabs(["Preklapanje operacija", "Prekoračenje kapaciteta"])

    with t1:
        conflicts = get_conflicts(tid)
        if not conflicts:
            st.success("Nema preklapanja operacija")
        else:
            conn = get_db()
            data = []
            for r in conflicts:
                j = conn.execute("SELECT part_number FROM jobs WHERE id = ? AND tenant_id = ?", (r["job_id"], tid)).fetchone()
                w = conn.execute("SELECT name FROM work_centers WHERE id = ? AND tenant_id = ?", (r["work_center_id"], tid)).fetchone()
                data.append({
                    "Posao": f"#{r['job_id']} {j['part_number'] if j else ''}",
                    "Radno mesto": w["name"] if w else "",
                    "Početak": r["start_datetime"][:16],
                    "Kraj": r["end_datetime"][:16],
                })
            conn.close()
            st.dataframe(pd.DataFrame(data), use_container_width=True, hide_index=True)

    with t2:
        caps = get_capacity_violations(tid)
        if not caps:
            st.success("Nema prekoračenja kapaciteta")
        else:
            cd = pd.DataFrame([{
                "Radno mesto": r["name"],
                "Datum": r["date"],
                "Operacije": r["ops"],
                "Planirano h": r["total_hrs"],
                "Max h": r["hours_per_day"],
                "Prekoračenje": round(r["total_hrs"] - r["hours_per_day"], 1),
            } for r in caps])
            st.dataframe(cd, use_container_width=True, hide_index=True)


def tab_holidays():
    st.markdown("## // KALENDAR")
    conn = get_db()
    holidays = conn.execute(
        "SELECT * FROM holidays WHERE tenant_id = ? ORDER BY date", (tid,)).fetchall()
    conn.close()

    if holidays:
        hd = pd.DataFrame([{"Datum": r["date"], "Opis": r["description"]} for r in holidays])
        st.dataframe(hd, use_container_width=True, hide_index=True)
    else:
        st.info("Nema definisanih praznika")

    with st.expander("+ DODAJ PRAZNIK"):
        col1, col2 = st.columns([2, 4])
        hdate = col1.date_input("Datum", key="hol_date")
        hdesc = col2.text_input("Opis (npr. Nova godina)", key="hol_desc")
        if st.button("DODAJ", key="add_holiday"):
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
    st.markdown("## // ŠTA-AKO: HITAN POSAO")
    conn = get_db()
    wc_list = conn.execute(
        "SELECT id, name FROM work_centers WHERE tenant_id = ? ORDER BY id", (tid,)).fetchall()
    conn.close()

    if not wc_list:
        st.warning("Prvo definiši radna mesta")
        return

    st.markdown("Simuliraj ubacivanje hitnog posla u postojeći raspored")

    with st.form("whatif_form"):
        pn = st.text_input("Oznaka dela", value="HITNO-001")
        qty = st.number_input("Količina", min_value=1, value=50)
        due = st.date_input("Rok isporuke", value=date.today() + timedelta(days=7))

        st.markdown("**Operacije (rutiranje)**")
        steps = []
        n_steps = st.number_input("Broj operacija", min_value=1, max_value=10, value=2, key="wi_nsteps")
        for i in range(int(n_steps)):
            col1, col2, col3, col4, col5 = st.columns([2, 2, 2, 2, 3])
            wc_opts = {w["id"]: w["name"] for w in wc_list}
            wc_id = col1.selectbox(f"Op{i+1} RM", list(wc_opts.keys()),
                                   format_func=lambda x: wc_opts[x],
                                   key=f"wi_wc_{i}")
            setup = col2.number_input(f"Priprema h", min_value=0.0, value=0.5, step=0.1, key=f"wi_setup_{i}")
            run = col3.number_input(f"Obrada h/kom", min_value=0.0, value=0.02, step=0.001, format="%.3f", key=f"wi_run_{i}")
            order = col4.number_input(f"Red. broj", min_value=1, value=i + 1, key=f"wi_order_{i}")
            desc = col5.text_input(f"Opis", value="", key=f"wi_desc_{i}")
            steps.append({"work_center_id": wc_id, "setup_hrs": setup,
                          "run_hrs_per_unit": run, "order": order, "desc": desc})

        if st.form_submit_button("SIMULIRAJ HITAN POSAO", type="primary"):
            result = what_if_rush_job(tid, pn, qty, due.isoformat(), steps, priority=10)
            if result["rush_on_time"]:
                st.success(f"Hitni posao #{result['rush_job_id']} stiže na vreme! ({result['total_late_jobs']} ukupno kasnih poslova)")
            else:
                st.warning(f"Hitni posao #{result['rush_job_id']} će kasniti. {result['total_late_jobs']} ukupno kasnih poslova.")
            st.json(result)
            st.rerun()

    st.markdown("---")
    if st.button("OČISTI SIMULIRANE POSLOVE", use_container_width=True):
        conn2 = get_db()
        conn2.execute("""
            DELETE FROM schedule WHERE job_id IN (
                SELECT id FROM jobs WHERE tenant_id = ? AND part_number LIKE 'HITNO%'
            ) AND tenant_id = ?
        """, (tid, tid))
        conn2.execute("""
            DELETE FROM routing_steps WHERE job_id IN (
                SELECT id FROM jobs WHERE tenant_id = ? AND part_number LIKE 'HITNO%'
            ) AND tenant_id = ?
        """, (tid, tid))
        conn2.execute("DELETE FROM jobs WHERE tenant_id = ? AND part_number LIKE 'HITNO%'", (tid,))
        conn2.commit()
        conn2.close()
        st.success("Simulirani poslovi obrisani")
        st.rerun()


def tab_import():
    st.markdown("## // CSV UVOZ")
    st.markdown("Otpremite CSV za grupni uvoz naloga za isporuku (automatski kreira radne naloge iz šablona).")

    csv_template = pd.DataFrame([
        {"customer": "Primer Kupac", "part_number": "PRIMER-001", "quantity": 100, "due_date": "2026-06-15",
         "priority": 5, "notes": "uzorak"},
    ])
    csv_data = csv_template.to_csv(index=False).encode("utf-8")
    st.download_button(
        label="PREUZMI CSV ŠABLON",
        data=csv_data,
        file_name="schedpro_import_template.csv",
        mime="text/csv",
        type="primary",
        use_container_width=True,
    )

    st.markdown("""
    ### Format
    **Obavezne kolone:** `part_number`, `quantity`, `due_date`  
    **Opcione kolone:** `customer`, `priority`, `notes`
    """)

    uploaded = st.file_uploader("Izaberi CSV fajl", type="csv", key="csv_uploader")
    if uploaded is not None:
        df = pd.read_csv(uploaded)
        st.markdown(f"**{len(df)} redova učitano**")
        st.dataframe(df.head(10), use_container_width=True, hide_index=True)

        if st.button("UVOZI NALOGE", type="primary", key="import_btn"):
            conn = get_db()
            imported = 0
            errors = []
            for _, row in df.iterrows():
                row = row.dropna(how="all").to_dict()
                pn = row.get("part_number")
                qty = row.get("quantity")
                due = row.get("due_date")
                if not pn or not qty or not due:
                    errors.append(f"Nedostaje obavezno polje: {row}")
                    continue
                cust = str(row.get("customer", ""))
                pri = int(row.get("priority", 5))
                notes = str(row.get("notes", ""))
                try:
                    cur = conn.execute("""
                        INSERT INTO delivery_orders (tenant_id, customer_name, part_number, quantity, due_date, priority, notes)
                        VALUES (?,?,?,?,?,?,?)
                    """, (tid, cust, str(pn), int(qty), str(due)[:10], pri, notes))
                    do_id = cur.lastrowid

                    template = conn.execute("""
                        SELECT * FROM tech_templates WHERE tenant_id = ? AND part_number = ?
                        ORDER BY step_order
                    """, (tid, str(pn))).fetchall()

                    if template:
                        cur2 = conn.execute("""
                            INSERT INTO jobs (tenant_id, part_number, quantity, due_date, priority, notes, delivery_order_id)
                            VALUES (?,?,?,?,?,?,?)
                        """, (tid, str(pn), int(qty), str(due)[:10], pri, notes, do_id))
                        job_id = cur2.lastrowid
                        for step in template:
                            conn.execute("""
                                INSERT INTO routing_steps (tenant_id, job_id, step_order, work_center_id, setup_hrs, run_hrs_per_unit, description)
                                VALUES (?,?,?,?,?,?,?)
                            """, (tid, job_id, step["step_order"], step["work_center_id"],
                                   step["setup_hrs"], step["run_hrs_per_unit"], step["description"]))
                    imported += 1
                except Exception as e:
                    errors.append(f"{pn}: {e}")
            conn.commit()
            conn.close()
            st.success(f"Uvezeno {imported} naloga")
            if errors:
                for e in errors[:5]:
                    st.warning(e)
                if len(errors) > 5:
                    st.warning(f"... i još {len(errors)-5} grešaka")
            st.rerun()


if lic["status"] == "trial_warning":
    st.warning(f"⚠️ {lic['message']}")

def tab_delivery_orders():
    st.markdown("## // NALOZI ZA ISPORUKU")
    conn = get_db()

    if "edit_do" in st.session_state:
        r = st.session_state.edit_do
        with st.form("edit_do_form"):
            cust = st.text_input("Kupac", value=r["customer_name"])
            pn = st.text_input("Oznaka dela", value=r["part_number"])
            qty = st.number_input("Količina", min_value=1, value=r["quantity"])
            due = st.date_input("Rok isporuke", value=datetime.fromisoformat(r["due_date"]).date())
            pri = st.number_input("Prioritet (1-10)", min_value=1, max_value=10, value=r["priority"] or 5)
            do_status = st.selectbox("Status", ["pending", "in_production", "completed", "cancelled"],
                                     index=["pending", "in_production", "completed", "cancelled"].index(r["status"]))
            notes = st.text_area("Napomena", value=r["notes"] or "")
            c1, c2 = st.columns(2)
            if c1.form_submit_button("SAČUVAJ"):
                conn.execute("""
                    UPDATE delivery_orders SET customer_name=?, part_number=?, quantity=?, due_date=?, priority=?, status=?, notes=?
                    WHERE id=? AND tenant_id=?
                """, (cust, pn, qty, due.isoformat(), pri, do_status, notes, r["id"], tid))
                conn.commit()
                del st.session_state.edit_do
                conn.close()
                st.rerun()
            if c2.form_submit_button("ODUSTANI"):
                del st.session_state.edit_do
                conn.close()
                st.rerun()
        conn.close()
        return

    orders = conn.execute("SELECT * FROM delivery_orders WHERE tenant_id = ? ORDER BY due_date", (tid,)).fetchall()

    for r in orders:
        jobs = conn.execute("""
            SELECT id, part_number, quantity, status FROM jobs
            WHERE delivery_order_id = ? AND tenant_id = ?
        """, (r["id"], tid)).fetchall()
        status_sr = {"pending": "na čekanju", "in_production": "u proizvodnji", "completed": "završeno", "cancelled": "otkazano"}
        c1, c2, c3, c4 = st.columns([10, 3, 1, 1])
        with c1:
            st.markdown(f"**#{r['id']} {r['part_number']}** — {r['customer_name']}  |  Kol:{r['quantity']}  Rok:{r['due_date'][:10]}  [{status_sr[r['status']]}]")
            if jobs:
                for j in jobs:
                    st.markdown(f"&nbsp;&nbsp;→ Radni nalog #{j['id']} ({j['status']})", unsafe_allow_html=True)
        c2.markdown(f"<div style='text-align:center; color:{ACCENT}'>{len(jobs)} RN</div>", unsafe_allow_html=True)
        if c3.button("✏️", key=f"do_edit_{r['id']}"):
            st.session_state.edit_do = r
            st.rerun()
        if c4.button("🗑️", key=f"do_del_{r['id']}"):
            conn2 = get_db()
            conn2.execute("DELETE FROM delivery_orders WHERE id = ? AND tenant_id = ?", (r["id"], tid))
            conn2.commit()
            conn2.close()
            st.rerun()

    st.markdown("---")
    st.markdown("### + NOVI NALOG ZA ISPORUKU")
    col1, col2, col3, col4, col5 = st.columns([2, 2, 1, 1, 1])
    cust = col1.text_input("Kupac", key="do_cust")
    pn = col2.text_input("Oznaka dela", key="do_pn")
    qty = col3.number_input("Količina", min_value=1, value=100, key="do_qty")
    due = col4.date_input("Rok isporuke", value=date.today(), key="do_due")
    pri = col5.number_input("Prioritet", min_value=1, max_value=10, value=5, key="do_pri")
    notes = st.text_area("Napomena", key="do_notes")
    if st.button("KREIRAJ NALOG I GENERIŠI RADNI NALOG", type="primary", use_container_width=True):
        if not pn:
            st.error("Unesite oznaku dela")
        else:
            conn2 = get_db()
            cur = conn2.execute("""
                INSERT INTO delivery_orders (tenant_id, customer_name, part_number, quantity, due_date, priority, notes)
                VALUES (?,?,?,?,?,?,?)
            """, (tid, cust, pn, qty, due.isoformat(), pri, notes))
            do_id = cur.lastrowid

            template = conn2.execute("""
                SELECT * FROM tech_templates WHERE tenant_id = ? AND part_number = ?
                ORDER BY step_order
            """, (tid, pn)).fetchall()

            if template:
                cur2 = conn2.execute("""
                    INSERT INTO jobs (tenant_id, part_number, quantity, due_date, priority, notes, delivery_order_id)
                    VALUES (?,?,?,?,?,?,?)
                """, (tid, pn, qty, due.isoformat(), pri, notes, do_id))
                job_id = cur2.lastrowid
                for step in template:
                    conn2.execute("""
                        INSERT INTO routing_steps (tenant_id, job_id, step_order, work_center_id, setup_hrs, run_hrs_per_unit, description)
                        VALUES (?,?,?,?,?,?,?)
                    """, (tid, job_id, step["step_order"], step["work_center_id"],
                           step["setup_hrs"], step["run_hrs_per_unit"], step["description"]))
                conn2.commit()
                st.success(f"Nalog #{do_id} kreiran → Radni nalog #{job_id} sa {len(template)} operacija")
            else:
                conn2.commit()
                st.warning(f"Nalog #{do_id} kreiran, ali nema šablona za '{pn}'. Definiši ga u kartici ŠABLONI pa ručno kreiraj radni nalog.")
            conn2.close()
            st.rerun()

    conn.close()


def tab_templates():
    st.markdown("## // TEHNOLOŠKI ŠABLONI")
    st.markdown("Definiši rutiranje za svaku oznaku dela — operacije se automatski kopiraju kad se kreira nalog za isporuku.")
    conn = get_db()

    if "edit_tmpl" in st.session_state:
        r = st.session_state.edit_tmpl
        with st.form("edit_tmpl_form"):
            pn = st.text_input("Oznaka dela", value=r["part_number"])
            order = st.number_input("Redni broj", min_value=1, value=r["step_order"])
            wc_list = conn.execute("SELECT id, name FROM work_centers WHERE tenant_id = ? ORDER BY id", (tid,)).fetchall()
            wc_opts = {w["id"]: w["name"] for w in wc_list}
            wc_id = st.selectbox("Radno mesto", list(wc_opts.keys()), format_func=lambda x: wc_opts[x],
                                 index=[w["id"] for w in wc_list].index(r["work_center_id"]))
            setup = st.number_input("Priprema (h)", min_value=0.0, value=r["setup_hrs"], step=0.1)
            run = st.number_input("Obrada h/kom", min_value=0.0, value=r["run_hrs_per_unit"], step=0.001, format="%.3f")
            desc = st.text_input("Opis", value=r["description"] or "")
            c1, c2 = st.columns(2)
            if c1.form_submit_button("SAČUVAJ"):
                conn.execute("""
                    UPDATE tech_templates SET part_number=?, step_order=?, work_center_id=?, setup_hrs=?, run_hrs_per_unit=?, description=?
                    WHERE id=? AND tenant_id=?
                """, (pn, order, wc_id, setup, run, desc, r["id"], tid))
                conn.commit()
                del st.session_state.edit_tmpl
                conn.close()
                st.rerun()
            if c2.form_submit_button("ODUSTANI"):
                del st.session_state.edit_tmpl
                conn.close()
                st.rerun()
        conn.close()
        return

    templates = conn.execute("""
        SELECT tt.*, wc.name AS wc_name FROM tech_templates tt
        JOIN work_centers wc ON tt.work_center_id = wc.id
        WHERE tt.tenant_id = ?
        ORDER BY tt.part_number, tt.step_order
    """, (tid,)).fetchall()
    conn.close()

    if templates:
        grouped = {}
        for t in templates:
            grouped.setdefault(t["part_number"], []).append(t)
        for pn, steps in grouped.items():
            st.markdown(f"**`{pn}`** — {len(steps)} operacija")
            for s in steps:
                c1, c2, c3, c4 = st.columns([1, 3, 2, 1])
                c1.markdown(f"**Op{s['step_order']}**")
                c2.markdown(s["wc_name"])
                c3.markdown(f"Priprema {s['setup_hrs']}h · Obrada {s['run_hrs_per_unit']}h/kom")
                c4.markdown(f"_{s['description'] or ''}_")
                col1, col2 = st.columns([1, 1])
                if col1.button("✏️", key=f"tmpl_edit_{s['id']}"):
                    st.session_state.edit_tmpl = s
                    st.rerun()
                if col2.button("🗑️", key=f"tmpl_del_{s['id']}"):
                    conn2 = get_db()
                    conn2.execute("DELETE FROM tech_templates WHERE id = ? AND tenant_id = ?", (s["id"], tid))
                    conn2.commit()
                    conn2.close()
                    st.rerun()
            st.markdown("---")
    else:
        st.info("Nema definisanih šablona")

    st.markdown("### + DODAJ OPERACIJU U ŠABLON")
    conn = get_db()
    wc_list = conn.execute("SELECT id, name FROM work_centers WHERE tenant_id = ? ORDER BY id", (tid,)).fetchall()
    conn.close()
    if not wc_list:
        st.warning("Prvo definiši radna mesta")
    else:
        col1, col2, col3, col4, col5, col6 = st.columns([2, 1, 2, 1, 1, 2])
        pn = col1.text_input("Oznaka dela", key="tmpl_pn")
        order = col2.number_input("Korak#", min_value=1, value=1, key="tmpl_order")
        wc_opts = {w["id"]: w["name"] for w in wc_list}
        wc_id = col3.selectbox("Radno mesto", list(wc_opts.keys()), format_func=lambda x: wc_opts[x], key="tmpl_wc")
        setup = col4.number_input("Priprema (h)", min_value=0.0, value=0.5, step=0.1, key="tmpl_setup")
        run = col5.number_input("Obrada h/kom", min_value=0.0, value=0.01, step=0.001, format="%.3f", key="tmpl_run")
        desc = col6.text_input("Opis", key="tmpl_desc")
        if st.button("DODAJ U ŠABLON"):
            conn2 = get_db()
            try:
                conn2.execute("""
                    INSERT INTO tech_templates (tenant_id, part_number, step_order, work_center_id, setup_hrs, run_hrs_per_unit, description)
                    VALUES (?,?,?,?,?,?,?)
                """, (tid, pn, order, wc_id, setup, run, desc))
                conn2.commit()
                st.success(f"Operacija dodata u šablon za '{pn}'")
            except Exception as e:
                st.error(str(e))
            conn2.close()
            st.rerun()


def tab_inventory():
    st.markdown("## // ZALIHE")
    conn = get_db()

    if "edit_inv" in st.session_state:
        r = st.session_state.edit_inv
        with st.form("edit_inv_form"):
            pn = st.text_input("Oznaka dela", value=r["part_number"])
            name = st.text_input("Naziv", value=r["name"])
            qty = st.number_input("Količina", min_value=0.0, value=float(r["quantity"]), step=1.0)
            alert = st.number_input("Min. zaliha (alert)", min_value=0.0, value=float(r["min_alert"]), step=1.0)
            unit = st.text_input("Jedinica mere", value=r["unit"])
            c1, c2 = st.columns(2)
            if c1.form_submit_button("SAČUVAJ"):
                conn.execute("""
                    UPDATE inventory_items SET part_number=?, name=?, quantity=?, min_alert=?, unit=?
                    WHERE id=? AND tenant_id=?
                """, (pn, name, qty, alert, unit, r["id"], tid))
                conn.commit()
                del st.session_state.edit_inv
                conn.close()
                st.rerun()
            if c2.form_submit_button("ODUSTANI"):
                del st.session_state.edit_inv
                conn.close()
                st.rerun()
        conn.close()
        return

    items = conn.execute("""
        SELECT * FROM inventory_items WHERE tenant_id = ? ORDER BY name
    """, (tid,)).fetchall()
    conn.close()

    low_stock = [r for r in items if r["min_alert"] > 0 and r["quantity"] <= r["min_alert"]]
    if low_stock:
        for r in low_stock:
            st.warning(f"⚠️ Niska zaliha: **{r['name']}** ({r['part_number']}) — {r['quantity']} {r['unit']} (min: {r['min_alert']})")

    for r in items:
        c1, c2, c3, c4 = st.columns([12, 2, 1, 1])
        color = DANGER if r["min_alert"] > 0 and r["quantity"] <= r["min_alert"] else TEXT
        with c1:
            st.markdown(f"<div style='color:{color}'><b>{r['name']}</b> — `{r['part_number']}` — **{r['quantity']}** {r['unit']}</div>", unsafe_allow_html=True)
        if c2.button("PROMET", key=f"inv_tx_{r['id']}"):
            st.session_state.show_tx = r["id"]
            st.rerun()
        if c3.button("✏️", key=f"inv_edit_{r['id']}"):
            st.session_state.edit_inv = r
            st.rerun()
        if c4.button("🗑️", key=f"inv_del_{r['id']}"):
            conn2 = get_db()
            try:
                conn2.execute("DELETE FROM inventory_items WHERE id = ? AND tenant_id = ?", (r["id"], tid))
                conn2.commit()
            except Exception as e:
                st.error(f"Ne može da se obriše: {e}")
            conn2.close()
            st.rerun()

    if "show_tx" in st.session_state:
        st.markdown("---")
        st.markdown("### Promet")
        conn = get_db()
        txns = conn.execute("""
            SELECT * FROM inventory_transactions
            WHERE tenant_id = ? AND item_id = ?
            ORDER BY created_at DESC LIMIT 50
        """, (tid, st.session_state.show_tx)).fetchall()
        conn.close()
        if txns:
            td = pd.DataFrame([{
                "Tip": "ULAZ" if r["type"] == "in" else "IZLAZ",
                "Količina": r["quantity"],
                "Referenca": r["reference"] or "",
                "Vreme": r["created_at"][:19],
            } for r in txns])
            st.dataframe(td, use_container_width=True, hide_index=True)
        else:
            st.info("Nema prometa")
        if st.button("ZATVORI PROMET"):
            del st.session_state.show_tx
            st.rerun()

    st.markdown("---")
    c1, c2, c3 = st.columns(3)
    pn = c1.text_input("Oznaka dela", key="inv_pn")
    name = c2.text_input("Naziv", key="inv_name")
    unit = c3.text_input("Jedinica", value="kom", key="inv_unit")
    c1, c2 = st.columns(2)
    init_qty = c1.number_input("Početna količina", min_value=0.0, value=0.0, step=1.0, key="inv_qty")
    alert = c2.number_input("Min. zaliha (alert)", min_value=0.0, value=0.0, step=1.0, key="inv_alert")
    if st.button("DODAJ NA ZALIHU"):
        conn2 = get_db()
        try:
            cur = conn2.execute("""
                INSERT INTO inventory_items (tenant_id, part_number, name, quantity, min_alert, unit)
                VALUES (?,?,?,?,?,?)
            """, (tid, pn, name, init_qty, alert, unit))
            item_id = cur.lastrowid
            if init_qty > 0:
                conn2.execute("""
                    INSERT INTO inventory_transactions (tenant_id, item_id, type, quantity, reference)
                    VALUES (?,?,?,?,?)
                """, (tid, item_id, "in", init_qty, "Početno stanje"))
            conn2.commit()
            st.success("Stavka dodata")
        except Exception as e:
            st.error(str(e))
        conn2.close()
        st.rerun()


tabs = st.tabs(["RADNA MESTA", "NALOZI", "POSLOVI", "ŠABLONI", "GANT", "KONFLIKTI", "KALENDAR", "ŠTA-AKO", "CSV UVOZ", "ZALIHE"])

with tabs[0]: tab_work_centers()
with tabs[1]: tab_delivery_orders()
with tabs[2]: tab_jobs()
with tabs[3]: tab_templates()
with tabs[4]: tab_gantt()
with tabs[5]: tab_conflicts()
with tabs[6]: tab_holidays()
with tabs[7]: tab_whatif()
with tabs[8]: tab_import()
with tabs[9]: tab_inventory()

sidebar()
