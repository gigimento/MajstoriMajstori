"""
Admin alat za generisanje licencnog kljuca.
Koristi se sa razvojne masine da generise kljuc za korisnika.

Upotreba:
    python generate_key.py <HW_ID>

Korisnik dobija HW_ID iz aplikacije (prikazan u kill-switch ekranu).
Vi generisete kljuc i saljete ga korisniku.
"""
import sys
from license import generate_license_key, get_hw_id

if __name__ == "__main__":
    if len(sys.argv) > 1:
        hw_id = sys.argv[1]
    else:
        hw_id = get_hw_id()
        print(f"Hardver ID ove masine: {hw_id}")
        print()

    key = generate_license_key(hw_id)
    print("=" * 54)
    print("  SCHED//PRO - Licencni kljuc")
    print("=" * 54)
    print()
    print(f"  Hardver ID: {hw_id}")
    print(f"  Kljuc:      {key}")
    print()
    print("=" * 54)
