from datetime import datetime, timedelta, date
from models import get_db

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


def _get_working_hours_between(start, end, holidays):
    total = 0.0
    current = start
    while current < end:
        if _is_working_day(current, holidays):
            day_start = current.replace(hour=WORK_START, minute=0, second=0, microsecond=0)
            day_end = current.replace(hour=WORK_END, minute=0, second=0, microsecond=0)
            block_start = max(current, day_start)
            block_end = min(end, day_end)
            if block_end > block_start:
                total += (block_end - block_start).total_seconds() / 3600
        current += timedelta(days=1)
        current = current.replace(hour=WORK_START, minute=0, second=0, microsecond=0)
    return total


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


def schedule_job(conn, job_id, tenant_id, start_dt=None, mode="forward", holidays=None):
    steps = conn.execute("""
        SELECT rs.*, wc.name AS wc_name, wc.type AS wc_type,
               wc.hours_per_day, wc.efficiency
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

    if mode == "backward":
        end_dt = datetime.fromisoformat(job["due_date"]).replace(hour=WORK_END, minute=0, second=0, microsecond=0)
        entries = []
        for step in reversed(steps):
            wc_id = step["work_center_id"]
            total_hrs = step["setup_hrs"] + (step["run_hrs_per_unit"] * job["quantity"])
            total_hrs /= step["efficiency"]
            start = _subtract_working_hours(end_dt, total_hrs, holidays)
            entries.append((start, end_dt, step["id"], wc_id))
            end_dt = start
        entries.reverse()
        for start, end, step_id, wc_id in entries:
            conn.execute("""
                INSERT OR REPLACE INTO schedule
                    (tenant_id, job_id, routing_step_id, work_center_id, start_datetime, end_datetime)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (tenant_id, job_id, step_id, wc_id, start.isoformat(), end.isoformat()))
    else:
        current = start_dt or datetime.now().replace(hour=WORK_START, minute=0, second=0, microsecond=0)
        current = _next_working_start(current, holidays)
        for step in steps:
            wc_id = step["work_center_id"]
            total_hrs = step["setup_hrs"] + (step["run_hrs_per_unit"] * job["quantity"])
            total_hrs /= step["efficiency"]
            end_time = _add_working_hours(current, total_hrs, holidays)
            conn.execute("""
                INSERT OR REPLACE INTO schedule
                    (tenant_id, job_id, routing_step_id, work_center_id, start_datetime, end_datetime)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (tenant_id, job_id, step["id"], wc_id, current.isoformat(), end_time.isoformat()))
            current = end_time

    conn.execute("""
        UPDATE jobs SET status = 'scheduled'
        WHERE id = ? AND tenant_id = ? AND status IN ('unscheduled','scheduled')
    """, (job_id, tenant_id))


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


def forward_schedule(tenant_id, start_date=None):
    conn = get_db()
    cur = conn.cursor()
    holidays = _get_holidays(conn, tenant_id)

    cur.execute("DELETE FROM schedule WHERE tenant_id = ?", (tenant_id,))

    daily_load = {}

    def _can_fit(wc_id, day, planned_hrs, max_hrs):
        key = (wc_id, day.isoformat())
        used = daily_load.get(key, 0)
        return used + planned_hrs <= max_hrs

    def _add_load(wc_id, day, hrs):
        key = (wc_id, day.isoformat())
        daily_load[key] = daily_load.get(key, 0) + hrs

    jobs = _get_sorted_jobs(cur, tenant_id)

    for job in jobs:
        start = start_date or datetime.now().replace(hour=WORK_START, minute=0, second=0, microsecond=0)
        start = _next_working_start(start, holidays)

        steps = cur.execute("""
            SELECT rs.*, wc.hours_per_day, wc.efficiency
            FROM routing_steps rs
            JOIN work_centers wc ON rs.work_center_id = wc.id
            WHERE rs.job_id = ? AND rs.tenant_id = ?
            ORDER BY rs.step_order
        """, (job["id"], tenant_id)).fetchall()

        current = start
        for step in steps:
            total_hrs = step["setup_hrs"] + (step["run_hrs_per_unit"] * job["quantity"])
            total_hrs /= step["efficiency"]

            while True:
                end_time = _add_working_hours(current, total_hrs, holidays)
                fits = True
                d = current.date()
                while d <= end_time.date():
                    hrs_on_day = _get_working_hours_between(
                        max(current, datetime.combine(d, datetime.min.time()).replace(hour=WORK_START)),
                        min(end_time, datetime.combine(d, datetime.min.time()).replace(hour=WORK_END)),
                        holidays
                    )
                    if hrs_on_day > 0 and not _can_fit(step["work_center_id"], d, hrs_on_day, step["hours_per_day"]):
                        fits = False
                        break
                    d += timedelta(days=1)
                if fits:
                    break
                current = _next_working_start(end_time, holidays)

            d = current.date()
            while d <= end_time.date():
                hrs_on_day = _get_working_hours_between(
                    max(current, datetime.combine(d, datetime.min.time()).replace(hour=WORK_START)),
                    min(end_time, datetime.combine(d, datetime.min.time()).replace(hour=WORK_END)),
                    holidays
                )
                if hrs_on_day > 0:
                    _add_load(step["work_center_id"], d, hrs_on_day)
                d += timedelta(days=1)

            cur.execute("""
                INSERT OR REPLACE INTO schedule
                    (tenant_id, job_id, routing_step_id, work_center_id, start_datetime, end_datetime)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (tenant_id, job["id"], step["id"], step["work_center_id"],
                  current.isoformat(), end_time.isoformat()))
            current = end_time

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

    for job in jobs:
        end_dt = datetime.fromisoformat(job["due_date"]).replace(hour=WORK_END, minute=0, second=0, microsecond=0)

        steps = cur.execute("""
            SELECT rs.*, wc.hours_per_day, wc.efficiency
            FROM routing_steps rs
            JOIN work_centers wc ON rs.work_center_id = wc.id
            WHERE rs.job_id = ? AND rs.tenant_id = ?
            ORDER BY rs.step_order
        """, (job["id"], tenant_id)).fetchall()

        entries = []
        for step in reversed(steps):
            total_hrs = step["setup_hrs"] + (step["run_hrs_per_unit"] * job["quantity"])
            total_hrs /= step["efficiency"]
            start = _subtract_working_hours(end_dt, total_hrs, holidays)
            entries.append((start, end_dt, step["id"], step["work_center_id"]))
            end_dt = start

        entries.reverse()
        for start, end, step_id, wc_id in entries:
            cur.execute("""
                INSERT OR REPLACE INTO schedule
                    (tenant_id, job_id, routing_step_id, work_center_id, start_datetime, end_datetime)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (tenant_id, job["id"], step_id, wc_id, start.isoformat(), end.isoformat()))

        cur.execute("""
            UPDATE jobs SET status = 'scheduled'
            WHERE id = ? AND tenant_id = ? AND status IN ('unscheduled','scheduled')
        """, (job["id"], tenant_id))

    conn.commit()
    conn.close()


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
