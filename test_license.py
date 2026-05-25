import os, sys
sys.path.insert(0, '.')
from models import init_db, get_db
init_db()

from license import (init_license, check_license, get_license_info,
                     generate_license_key, activate_license, TRIAL_DAYS,
                     validate_license_key)

init_license(1)
info = get_license_info(1)
print(f"Test 1 - License record exists: {info is not None}")
print(f"  hw_id: {info['hw_id'][:16]}...")
print(f"  trial_start: {info['trial_start']}")
print(f"  license_key: {repr(info['license_key'])}")

lic = check_license(1)
print(f"\nTest 2 - License status: {lic['status']}")
print(f"  days_left: {lic['days_left']}")
print(f"  is_licensed: {lic['is_licensed']}")
assert lic['status'] == 'trial', f"Expected trial, got {lic['status']}"
assert lic['days_left'] == TRIAL_DAYS
assert not lic['is_licensed']
print("  PASS")

hw = get_license_info(1)['hw_id']
key = generate_license_key(hw)
print(f"\nTest 3 - Generated key: {key}")

ok, msg = activate_license(1, key)
print(f"  Activation: {ok} - {msg}")
assert ok

lic2 = check_license(1)
print(f"  After activation status: {lic2['status']}")
assert lic2['is_licensed']
print("  PASS")

assert not validate_license_key(hw, 'FAKE-KEY')
print("Test 4 - Wrong key rejected: PASS")

marker_path = os.path.join(os.environ.get('APPDATA', os.path.expanduser('~')), 'SCHEDPRO', '.license_marker')
print(f"\nMarker file: {marker_path}")
print(f"  Exists: {os.path.exists(marker_path)}")

print("\n=== ALL TESTS PASSED ===")
