"""
Load demo data for tenant_id=1 (default admin tenant).
Run this after models.init_db().
"""
from models import init_db, get_db

init_db()
conn = get_db()

TENANT = 1

conn.execute("DELETE FROM schedule WHERE tenant_id = ?", (TENANT,))
conn.execute("DELETE FROM routing_steps WHERE tenant_id = ?", (TENANT,))
conn.execute("DELETE FROM jobs WHERE tenant_id = ?", (TENANT,))
conn.execute("DELETE FROM work_centers WHERE tenant_id = ?", (TENANT,))
conn.execute("DELETE FROM holidays WHERE tenant_id = ?", (TENANT,))
conn.execute("DELETE FROM sqlite_sequence")  # reset auto-increment

for i in range(1, 11):
    conn.execute("INSERT INTO work_centers (tenant_id, name, type, hours_per_day, efficiency, max_concurrent_jobs) VALUES (?,?,?,?,?,?)",
                 (TENANT, f"Radno mesto {i}", "production" if i % 3 != 0 else "inspection", 8, 0.85 if i % 3 != 0 else 0.90, 2 if i == 3 else 1))
conn.commit()

conn.execute("INSERT INTO jobs (tenant_id, part_number, quantity, due_date, priority) VALUES (?,?,?,?,?)",
             (TENANT, "BRACKET-001", 200, "2026-06-01", 5))
conn.execute("INSERT INTO jobs (tenant_id, part_number, quantity, due_date, priority) VALUES (?,?,?,?,?)",
             (TENANT, "SHAFT-042", 50, "2026-05-28", 8))
conn.execute("INSERT INTO jobs (tenant_id, part_number, quantity, due_date, priority) VALUES (?,?,?,?,?)",
             (TENANT, "HOUSING-101", 100, "2026-06-05", 3))
conn.commit()

conn.execute("INSERT INTO routing_steps (tenant_id, job_id, step_order, work_center_id, setup_hrs, run_hrs_per_unit, description) VALUES (?,?,?,?,?,?,?)",
             (TENANT, 1, 1, 1, 1.0, 0.05, "Obrada na RM1"))
conn.execute("INSERT INTO routing_steps (tenant_id, job_id, step_order, work_center_id, setup_hrs, run_hrs_per_unit, description) VALUES (?,?,?,?,?,?,?)",
             (TENANT, 1, 2, 2, 0.5, 0.02, "Kontrola na RM2"))
conn.execute("INSERT INTO routing_steps (tenant_id, job_id, step_order, work_center_id, setup_hrs, run_hrs_per_unit, description) VALUES (?,?,?,?,?,?,?)",
             (TENANT, 2, 1, 1, 0.5, 0.08, "Obrada na RM1"))
conn.execute("INSERT INTO routing_steps (tenant_id, job_id, step_order, work_center_id, setup_hrs, run_hrs_per_unit, description) VALUES (?,?,?,?,?,?,?)",
             (TENANT, 2, 2, 2, 0.5, 0.01, "Kontrola na RM2"))
conn.execute("INSERT INTO routing_steps (tenant_id, job_id, step_order, work_center_id, setup_hrs, run_hrs_per_unit, description) VALUES (?,?,?,?,?,?,?)",
             (TENANT, 3, 1, 3, 0.5, 0.03, "Montaža na RM3"))
conn.execute("INSERT INTO routing_steps (tenant_id, job_id, step_order, work_center_id, setup_hrs, run_hrs_per_unit, description) VALUES (?,?,?,?,?,?,?)",
             (TENANT, 3, 2, 2, 0.5, 0.015, "Kontrola na RM2"))
conn.commit()
conn.close()

print("=== FORWARD SCHEDULE ===")
from scheduler import forward_schedule, get_conflicts, get_capacity_violations
forward_schedule(TENANT)
print(f"Conflicts: {len(get_conflicts(TENANT))}, Capacity violations: {len(get_capacity_violations(TENANT))}")

conn = get_db()
for row in conn.execute("""
    SELECT s.start_datetime, s.end_datetime, j.part_number, wc.name AS wc_name, rs.step_order
    FROM schedule s
    JOIN jobs j ON s.job_id = j.id
    JOIN work_centers wc ON s.work_center_id = wc.id
    JOIN routing_steps rs ON s.routing_step_id = rs.id
    WHERE s.tenant_id = ?
    ORDER BY s.start_datetime
""", (TENANT,)).fetchall():
    print(f"  {row['start_datetime'][:16]} - {row['end_datetime'][:16]} | {row['part_number']:15} | {row['wc_name']:12} | Op{row['step_order']}")
conn.close()

print("\n=== BACKWARD SCHEDULE ===")
from scheduler import backward_schedule
backward_schedule(TENANT)
conn = get_db()
for row in conn.execute("""
    SELECT s.start_datetime, s.end_datetime, j.part_number, wc.name AS wc_name, rs.step_order
    FROM schedule s
    JOIN jobs j ON s.job_id = j.id
    JOIN work_centers wc ON s.work_center_id = wc.id
    JOIN routing_steps rs ON s.routing_step_id = rs.id
    WHERE s.tenant_id = ?
    ORDER BY s.start_datetime
""", (TENANT,)).fetchall():
    print(f"  {row['start_datetime'][:16]} - {row['end_datetime'][:16]} | {row['part_number']:15} | {row['wc_name']:12} | Op{row['step_order']}")
conn.close()

print("\n=== TEST WHAT-IF RUSH ===")
from scheduler import what_if_rush_job
result = what_if_rush_job(TENANT, "RUSH-SHAFT", 30, "2026-05-30", [
    {"order": 1, "work_center_id": 1, "setup_hrs": 0.5, "run_hrs_per_unit": 0.06, "desc": "Hitna obrada RM1"},
    {"order": 2, "work_center_id": 2, "setup_hrs": 0.25, "run_hrs_per_unit": 0.01, "desc": "Hitna kontrola RM2"},
])
print(f"Rush job #{result['rush_job_id']}: on_time={result['rush_on_time']}, late={result['total_late_jobs']}")

print("\nALL OK")
