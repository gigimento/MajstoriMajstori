import os
import uuid
import hashlib
import hmac
import json
from datetime import datetime, date
from models import get_db

TRIAL_DAYS = 30
LICENSE_SECRET = "SCHEDPRO-OFFLINE-V1-SECRET-KEY-2026"
MARKER_DIR = os.path.join(os.environ.get("APPDATA", os.path.expanduser("~")), "SCHEDPRO")
MARKER_FILE = os.path.join(MARKER_DIR, ".license_marker")
LICENSE_PREFIX = "SCHEDPRO-"


def get_hw_id():
    parts = [
        str(uuid.getnode()),
        os.environ.get("COMPUTERNAME", ""),
        os.environ.get("PROCESSOR_IDENTIFIER", ""),
    ]
    raw = "|".join(parts)
    return hashlib.sha256(raw.encode()).hexdigest()[:32]


def _marker_data():
    if not os.path.exists(MARKER_FILE):
        return None
    try:
        with open(MARKER_FILE, "r") as f:
            return json.loads(f.read())
    except Exception:
        return None


def _write_marker(data):
    os.makedirs(MARKER_DIR, exist_ok=True)
    try:
        with open(MARKER_FILE, "w") as f:
            json.dump(data, f)
    except Exception:
        pass


def init_license(tenant_id):
    conn = get_db()
    rec = conn.execute(
        "SELECT * FROM license WHERE tenant_id = ?", (tenant_id,)).fetchone()
    if not rec:
        conn.execute("INSERT INTO license (tenant_id) VALUES (?)", (tenant_id,))
        conn.commit()
        rec = conn.execute(
            "SELECT * FROM license WHERE tenant_id = ?", (tenant_id,)).fetchone()
    conn.close()

    if not rec["trial_start"]:
        now = datetime.now().isoformat()
        conn = get_db()
        conn.execute("UPDATE license SET trial_start = ?, hw_id = ? WHERE tenant_id = ?",
                     (now, get_hw_id(), tenant_id))
        conn.commit()
        conn.close()
        _write_marker({"hw_id": get_hw_id(), "installed_at": now, "tenant_id": tenant_id})

    if not rec["hw_id"]:
        conn = get_db()
        conn.execute("UPDATE license SET hw_id = ? WHERE tenant_id = ?",
                     (get_hw_id(), tenant_id))
        conn.commit()
        conn.close()


def check_license(tenant_id):
    conn = get_db()
    rec = conn.execute(
        "SELECT * FROM license WHERE tenant_id = ?", (tenant_id,)).fetchone()
    conn.close()

    if not rec:
        return {"status": "error", "message": "Licenca nije inicijalizovana"}

    current_hw = get_hw_id()
    stored_hw = rec["hw_id"]

    if stored_hw and stored_hw != current_hw:
        return {
            "status": "tampered",
            "message": "Hardver se promenio — licenca je nevažeća. Kontaktirajte developera.",
            "days_left": 0,
            "is_licensed": False,
        }

    marker = _marker_data()
    if marker and marker.get("hw_id") != current_hw:
        return {
            "status": "tampered",
            "message": "Instalacija je preslikana na drugi računar. Licenca je nevažeća.",
            "days_left": 0,
            "is_licensed": False,
        }

    if rec["license_key"] and rec["activated_at"]:
        return {
            "status": "licensed",
            "message": "Full verzija",
            "days_left": 999,
            "is_licensed": True,
        }

    if not rec["trial_start"]:
        return {
            "status": "trial_not_started",
            "message": "Probni period nije inicijalizovan",
            "days_left": TRIAL_DAYS,
            "is_licensed": False,
        }

    trial_start = datetime.fromisoformat(rec["trial_start"])
    now = datetime.now()
    elapsed = (now - trial_start).days

    marker_installed = marker.get("installed_at") if marker else None
    if marker_installed:
        marker_start = datetime.fromisoformat(marker_installed)
        marker_elapsed = (now - marker_start).days
        if abs(elapsed - marker_elapsed) > 1:
            return {
                "status": "tampered",
                "message": "Vremenska oznaka je nekonzistentna. Prijavljen pokušaj manipulacije.",
                "days_left": 0,
                "is_licensed": False,
            }

    last_run = rec["last_run"]
    if last_run:
        last_dt = datetime.fromisoformat(last_run)
        if now < last_dt:
            return {
                "status": "tampered",
                "message": "Sistemski sat je vraćen unazad. Licenca je suspendovana.",
                "days_left": 0,
                "is_licensed": False,
            }

    conn = get_db()
    conn.execute("UPDATE license SET last_run = ? WHERE tenant_id = ?",
                 (now.isoformat(), tenant_id))
    conn.commit()
    conn.close()

    days_left = TRIAL_DAYS - elapsed

    if days_left <= 0:
        return {
            "status": "expired",
            "message": "Probni period je istekao. Unesite licencni ključ za nastavak.",
            "days_left": 0,
            "is_licensed": False,
        }
    elif days_left <= 14:
        return {
            "status": "trial_warning",
            "message": f"Probni period ističe za {days_left} dan(a). Unesite licencni ključ.",
            "days_left": days_left,
            "is_licensed": False,
        }
    else:
        return {
            "status": "trial",
            "message": f"Probni period — preostalo {days_left} dana",
            "days_left": days_left,
            "is_licensed": False,
        }


def generate_license_key(hw_id):
    msg = hw_id + LICENSE_SECRET
    h = hashlib.sha256(msg.encode()).hexdigest().upper()[:20]
    return LICENSE_PREFIX + "-".join(h[i:i+5] for i in range(0, 20, 5))


def validate_license_key(hw_id, key):
    expected = generate_license_key(hw_id)
    return hmac.compare_digest(expected, key.strip().upper())


def activate_license(tenant_id, key):
    hw_id = get_hw_id()
    if not validate_license_key(hw_id, key):
        return False, "Nevažeći licencni ključ"

    conn = get_db()
    conn.execute("""
        UPDATE license SET license_key = ?, activated_at = ?, expires_at = ?
        WHERE tenant_id = ?
    """, (key.strip().upper(), datetime.now().isoformat(),
          datetime(2099, 12, 31).isoformat(), tenant_id))
    conn.commit()
    conn.close()
    return True, "Licenca aktivirana do 2099-12-31"


def get_license_info(tenant_id):
    conn = get_db()
    rec = conn.execute(
        "SELECT * FROM license WHERE tenant_id = ?", (tenant_id,)).fetchone()
    conn.close()
    return dict(rec) if rec else None
