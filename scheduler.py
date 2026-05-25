from datetime import datetime, timedelta, date
from models import get_db
from collections import defaultdict

WORK_START = 6
WORK_END = 22


def _get_holidays(conn, tenant_id):
    return set(r["date"] for r in conn.execute(
        "SELECT date FROM holidays WHERE tenant_id = ?", (tenant_id,)).fetchall())


def _is_working_day(dt, holidays):
    if dt.weekday() >= 5:
        return False
    if dt.strftime("%Y-%m-%d") in holidays:
        return False
    return True


def _next_working_start(from_dt, holidays):
    d = from_dt
    if d.hour >= WORK_END:
        d = d.replace(hour=WORK_START, minute=0, second=0, microsecond=0) + timedelta(days=1)
    if d.hour < WORK_START:
        d = d.replace(hour=WORK_START, minute=0, second=0, microsecond=0)
    while not _is_working_day(d, holidays):
        d += timedelta(days=1)
        d = d.replace(hour=WORK_START, minute=0, second=0, microsecond=0)
    return d


def _prev_working_end(from_dt, holidays):
    d = from_dt
    if d.hour <= WORK_START:
        d = d.replace(hour=WORK_END, minute=0, second=0, microsecond=0) - timedelta(days=1)
    if d.hour > WORK_END:
        d = d.replace(hour=WORK_END, minute=0, second=0, microsecond=0)
    while not _is_working_day(d, holidays):
        d -= timedelta(days=1)
        d = d.replace(hour=WORK_END, minute=0, second=0, microsecond=0)
    return d


def _add_working_hours(start_dt, hours_needed, holidays):
    remaining = hours_needed * 60
    current = start_dt
    while remaining > 0:
        current = _next_working_start(current, holidays)
        day_end = current.replace(hour=WORK_END, minute=0, second=0, microsecond=0)
        available = (day_end - current).total_seconds() / 60
        if available <= 0:
            current = day_end + timedelta(days=1)
            continue
        take = min(remaining, available)
        current += timedelta(minutes=take)
        remaining -= take
    return current


def _subtract_working_hours(end_dt, hours_needed, holidays):
    remaining = hours_needed * 60
    current = end_dt
    while remaining > 0:
        current = _prev_working_end(current, holidays)
        day_start = current.replace(hour=WORK_START, minute=0, second=0, microsecond=0)
        available = (current - day_start).total_seconds() / 60
        if available <= 0:
            current = day_start - timedelta(days=1)
            continue
        take = min(remaining, available)
        current -= timedelta(minutes=take)
        remaining -= take
    return current


def _score_weight(due_date, priority, today=None):
    if today is None:
        today = date.today()
    due = date.fromisoformat(due_date[:10]) if isinstance(due_date, str) else due_date
    days_remaining = (due - today).days
    norm_days = max(0, min(1, days_remaining / 60))
    norm_priority = priority / 10
    score = norm_days * 0.4 - norm_priority * 0.6
    return score


def _get_sorted_jobs(conn, tenant_id):
    today = date.today()
    jobs = conn.execute("""
        SELECT * FROM jobs
        WHERE tenant_id = ? AND status IN ('unscheduled', 'scheduled')
        ORDER BY due_date ASC, priority DESC
    """, (tenant_id,)).fetchall()

    scored = []
    for j in jobs:
        s = _score_weight(j["due_date"], j["priority"], today)
        scored.append((s, j))
    scored.sort(key=lambda x: x[0])
    return [j for _, j in scored]


def _count_overlaps(intervals, start, end):
    """Count how many intervals overlap with [start, end)."""
    count = 0
    for b_start, b_end in intervals:
        if start < b_end and end > b_start:
            count += 1
    return count


def _find_forward_slot(wc_booked, wc_id, start_from, total_hrs, holidays, max_concurrent):
    """Find next available forward slot respecting existing bookings and concurrency limit."""
    booked = wc_booked[wc_id]
    current = start_from
    max_iter = 200
    for _ in range(max_iter):
        end = _add_working_hours(current, total_hrs, holidays)
        overlaps = _count_overlaps(booked, current, end)
        if overlaps < max_concurrent:
            booked.append((current, end))
            booked.sort(key=lambda x: x[0])
            return current, end
        earliest_end = min(b_end for b_start, b_end in booked
                           if current < b_end and end > b_start)
        if earliest_end <= current:
            earliest_end = current + timedelta(minutes=1)
        current = earliest_end
    raise RuntimeError(f"Could not find slot for {total_hrs}h on WC {wc_id}")


def _find_backward_slot(wc_booked, wc_id, end_at, total_hrs, holidays, max_concurrent):
    """Find previous available backward slot respecting existing bookings."""
    booked = wc_booked[wc_id]
    current = end_at
    max_iter = 200
    for _ in range(max_iter):
        start = _subtract_working_hours(current, total_hrs, holidays)
        overlaps = _count_overlaps(booked, start, current)
        if overlaps < max_concurrent:
            booked.append((start, current))
            booked.sort(key=lambda x: x[0])
            return start, current
        latest_start = max(b_start for b_start, b_end in booked
                           if start < b_end and current > b_start)
        if latest_start >= current:
            latest_start = current - timedelta(minutes=1)
        current = latest_start


def _calc_job_hrs(job, step):
    """Calculate total hours for a step given job and step data."""
    return (step["setup_hrs"] + (step["run_hrs_per_unit"] * job["quantity"])) / step["efficiency"]


def forward_schedule(tenant_id, start_date=None):
    conn = get_db()
    cur = conn.cursor()
    holidays = _get_holidays(conn, tenant_id)

    cur.execute("DELETE FROM schedule WHERE tenant_id = ?", (tenant_id,))

    jobs = _get_sorted_jobs(cur, tenant_id)
    if not jobs:
        conn.commit()
        conn.close()
        return

    wc_max = {}
    wc_booked = defaultdict(list)

    for job in jobs:
        start = start_date or datetime.now().replace(hour=WORK_START, minute=0, second=0, microsecond=0)
        start = _next_working_start(start, holidays)

        steps = cur.execute("""
            SELECT rs.*, wc.hours_per_day, wc.efficiency, wc.max_concurrent_jobs
            FROM routing_steps rs
            JOIN work_centers wc ON rs.work_center_id = wc.id
            WHERE rs.job_id = ? AND rs.tenant_id = ?
            ORDER BY rs.step_order
        """, (job["id"], tenant_id)).fetchall()

        current = start
        for step in steps:
            wc_id = step["work_center_id"]
            if wc_id not in wc_max:
                wc_max[wc_id] = step["max_concurrent_jobs"]
            total_hrs = _calc_job_hrs(job, step)
            slot_start, slot_end = _find_forward_slot(
                wc_booked, wc_id, current, total_hrs, holidays, wc_max[wc_id])
            cur.execute("""
                INSERT OR REPLACE INTO schedule
                    (tenant_id, job_id, routing_step_id, work_center_id, start_datetime, end_datetime)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (tenant_id, job["id"], step["id"], wc_id,
                  slot_start.isoformat(), slot_end.isoformat()))
            current = slot_end

        cur.execute("""
            UPDATE jobs SET status = 'scheduled'
            WHERE id = ? AND tenant_id = ? AND status IN ('unscheduled','scheduled')
        """, (job["id"], tenant_id))

    conn.commit()
    conn.close()


def backward_schedule(tenant_id):
    conn = get_db()
    cur = conn.cursor()
    holidays = _get_holidays(conn, tenant_id)

    cur.execute("DELETE FROM schedule WHERE tenant_id = ?", (tenant_id,))

    jobs = _get_sorted_jobs(cur, tenant_id)
    if not jobs:
        conn.commit()
        conn.close()
        return

    wc_max = {}
    wc_booked = defaultdict(list)

    for job in jobs:
        end_dt = datetime.fromisoformat(job["due_date"]).replace(hour=WORK_END, minute=0, second=0, microsecond=0)

        steps = cur.execute("""
            SELECT rs.*, wc.hours_per_day, wc.efficiency, wc.max_concurrent_jobs
            FROM routing_steps rs
            JOIN work_centers wc ON rs.work_center_id = wc.id
            WHERE rs.job_id = ? AND rs.tenant_id = ?
            ORDER BY rs.step_order
        """, (job["id"], tenant_id)).fetchall()

        current = end_dt
        entries = []
        for step in reversed(steps):
            wc_id = step["work_center_id"]
            if wc_id not in wc_max:
                wc_max[wc_id] = step["max_concurrent_jobs"]
            total_hrs = _calc_job_hrs(job, step)
            slot_start, slot_end = _find_backward_slot(
                wc_booked, wc_id, current, total_hrs, holidays, wc_max[wc_id])
            entries.append((slot_start, slot_end, step["id"], wc_id))
            current = slot_start

        entries.reverse()
        for slot_start, slot_end, step_id, wc_id in entries:
            cur.execute("""
                INSERT OR REPLACE INTO schedule
                    (tenant_id, job_id, routing_step_id, work_center_id, start_datetime, end_datetime)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (tenant_id, job["id"], step_id, wc_id,
                  slot_start.isoformat(), slot_end.isoformat()))

        cur.execute("""
            UPDATE jobs SET status = 'scheduled'
            WHERE id = ? AND tenant_id = ? AND status IN ('unscheduled','scheduled')
        """, (job["id"], tenant_id))

    conn.commit()
    conn.close()


def schedule_job(conn, job_id, tenant_id, start_dt=None, mode="forward", holidays=None):
    steps = conn.execute("""
        SELECT rs.*, wc.name AS wc_name, wc.type AS wc_type,
               wc.hours_per_day, wc.efficiency, wc.max_concurrent_jobs
        FROM routing_steps rs
        JOIN work_centers wc ON rs.work_center_id = wc.id
        WHERE rs.job_id = ? AND rs.tenant_id = ?
        ORDER BY rs.step_order
    """, (job_id, tenant_id)).fetchall()

    if not steps:
        return

    job = conn.execute(
        "SELECT * FROM jobs WHERE id = ? AND tenant_id = ?",
        (job_id, tenant_id)).fetchone()
    if not job:
        return

    conn.execute("DELETE FROM schedule WHERE job_id = ? AND tenant_id = ?", (job_id, tenant_id))

    if holidays is None:
        holidays = _get_holidays(conn, tenant_id)

    wc_booked = defaultdict(list)
    existing = conn.execute("""
        SELECT work_center_id, start_datetime, end_datetime
        FROM schedule WHERE tenant_id = ?
    """, (tenant_id,)).fetchall()
    for r in existing:
        wc_booked[r["work_center_id"]].append((
            datetime.fromisoformat(r["start_datetime"]),
            datetime.fromisoformat(r["end_datetime"]),
        ))
    for lst in wc_booked.values():
        lst.sort(key=lambda x: x[0])

    if mode == "backward":
        end_dt = datetime.fromisoformat(job["due_date"]).replace(hour=WORK_END, minute=0, second=0, microsecond=0)
        entries = []
        for step in reversed(steps):
            wc_id = step["work_center_id"]
            total_hrs = _calc_job_hrs(job, step)
            slot_start, slot_end = _find_backward_slot(
                wc_booked, wc_id, end_dt, total_hrs, holidays, step["max_concurrent_jobs"])
            entries.append((slot_start, slot_end, step["id"], wc_id))
            end_dt = slot_start
        entries.reverse()
        for slot_start, slot_end, step_id, wc_id in entries:
            conn.execute("""
                INSERT OR REPLACE INTO schedule
                    (tenant_id, job_id, routing_step_id, work_center_id, start_datetime, end_datetime)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (tenant_id, job_id, step_id, wc_id, slot_start.isoformat(), slot_end.isoformat()))
    else:
        current = start_dt or datetime.now().replace(hour=WORK_START, minute=0, second=0, microsecond=0)
        current = _next_working_start(current, holidays)
        for step in steps:
            wc_id = step["work_center_id"]
            total_hrs = _calc_job_hrs(job, step)
            slot_start, slot_end = _find_forward_slot(
                wc_booked, wc_id, current, total_hrs, holidays, step["max_concurrent_jobs"])
            conn.execute("""
                INSERT OR REPLACE INTO schedule
                    (tenant_id, job_id, routing_step_id, work_center_id, start_datetime, end_datetime)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (tenant_id, job_id, step["id"], wc_id,
                  slot_start.isoformat(), slot_end.isoformat()))
            current = slot_end

    conn.execute("""
        UPDATE jobs SET status = 'scheduled'
        WHERE id = ? AND tenant_id = ? AND status IN ('unscheduled','scheduled')
    """, (job_id, tenant_id))


def get_conflicts(tenant_id):
    conn = get_db()
    rows = conn.execute("""
        SELECT s1.id, s1.job_id, s1.work_center_id, s1.start_datetime, s1.end_datetime
        FROM schedule s1
        JOIN schedule s2 ON s1.work_center_id = s2.work_center_id
            AND s1.id != s2.id
            AND s1.start_datetime < s2.end_datetime
            AND s1.end_datetime > s2.start_datetime
        WHERE s1.tenant_id = ?
        ORDER BY s1.start_datetime
    """, (tenant_id,)).fetchall()
    conn.close()
    return rows


def get_capacity_violations(tenant_id):
    conn = get_db()
    rows = conn.execute("""
        SELECT wc.id, wc.name, wc.hours_per_day, wc.max_concurrent_jobs,
               s.date, s.ops, s.total_hrs
        FROM work_centers wc
        JOIN (
            SELECT work_center_id,
                   date(start_datetime) AS date,
                   COUNT(*) AS ops,
                   ROUND(SUM((julianday(end_datetime) - julianday(start_datetime)) * 24), 1) AS total_hrs
            FROM schedule
            WHERE tenant_id = ?
            GROUP BY work_center_id, date(start_datetime)
        ) s ON wc.id = s.work_center_id
        WHERE wc.tenant_id = ? AND s.total_hrs > wc.hours_per_day
        ORDER BY s.date
    """, (tenant_id, tenant_id)).fetchall()
    conn.close()
    return rows


def move_job(job_id, tenant_id, new_start_iso):
    conn = get_db()
    holidays = _get_holidays(conn, tenant_id)
    start = datetime.fromisoformat(new_start_iso)
    start = _next_working_start(start, holidays)
    schedule_job(conn, job_id, tenant_id, start_dt=start, mode="forward", holidays=holidays)
    conn.commit()
    conn.close()


def what_if_rush_job(tenant_id, part_number, quantity, due_date, steps_data, priority=10):
    conn = get_db()
    cur = conn.cursor()
    holidays = _get_holidays(conn, tenant_id)

    cur.execute("""
        INSERT INTO jobs (tenant_id, part_number, quantity, due_date, priority, status)
        VALUES (?, ?, ?, ?, ?, 'unscheduled')
    """, (tenant_id, part_number, quantity, due_date, priority))
    rush_id = cur.lastrowid

    for s in steps_data:
        cur.execute("""
            INSERT INTO routing_steps (tenant_id, job_id, step_order, work_center_id, setup_hrs, run_hrs_per_unit, description)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (tenant_id, rush_id, s["order"], s["work_center_id"],
              s["setup_hrs"], s["run_hrs_per_unit"], s.get("desc", "")))

    start = datetime.now().replace(hour=WORK_START, minute=0, second=0, microsecond=0)
    start = _next_working_start(start, holidays)
    schedule_job(cur, rush_id, tenant_id, start_dt=start, mode="forward", holidays=holidays)

    conn.commit()
    conn.close()

    late = get_jobs_past_due(tenant_id)
    rush_late = any(j["id"] == rush_id for j in late)

    return {
        "rush_job_id": rush_id,
        "rush_on_time": not rush_late,
        "total_late_jobs": len(late),
    }


def get_jobs_past_due(tenant_id):
    conn = get_db()
    rows = conn.execute("""
        SELECT DISTINCT j.id, j.part_number, j.due_date, j.quantity, j.priority,
               MIN(s.end_datetime) AS final_op_end
        FROM jobs j
        JOIN schedule s ON s.job_id = j.id
        WHERE j.tenant_id = ?
        GROUP BY j.id
        HAVING datetime(s.end_datetime) > datetime(j.due_date || 'T' || '22:00:00')
        ORDER BY j.due_date
    """, (tenant_id,)).fetchall()
    conn.close()
    return rows


def snapshot_schedule(tenant_id, name):
    conn = get_db()
    rows = conn.execute(
        "SELECT * FROM schedule WHERE tenant_id = ? ORDER BY job_id, start_datetime",
        (tenant_id,)).fetchall()
    data = "\n".join(f"{r['job_id']}|{r['routing_step_id']}|{r['work_center_id']}|{r['start_datetime']}|{r['end_datetime']}"
                     for r in rows)
    conn.execute("INSERT INTO schedule_snapshots (tenant_id, name, data) VALUES (?, ?, ?)",
                 (tenant_id, name, data))
    conn.commit()
    conn.close()


def restore_snapshot(tenant_id, snapshot_id):
    conn = get_db()
    snap = conn.execute(
        "SELECT * FROM schedule_snapshots WHERE id = ? AND tenant_id = ?",
        (snapshot_id, tenant_id)).fetchone()
    if not snap:
        conn.close()
        return
    conn.execute("DELETE FROM schedule WHERE tenant_id = ?", (tenant_id,))
    for line in snap["data"].strip().split("\n"):
        if not line.strip():
            continue
        parts = line.split("|")
        conn.execute("""
            INSERT INTO schedule (tenant_id, job_id, routing_step_id, work_center_id, start_datetime, end_datetime)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (tenant_id, int(parts[0]), int(parts[1]), int(parts[2]), parts[3], parts[4]))
    conn.commit()
    conn.close()
