#!/usr/bin/env python3
import requests
import os
import time
import json
import csv
import argparse
import getpass
import sys
import xml.etree.ElementTree as ET

SESSION_FILE = "./.qrz_session"
SESSION_LIFETIME_MIN = 60
QRZ_URL = "https://xmldata.qrz.com/xml/current/"


# -----------------------------
# Load cached session
# -----------------------------
def load_session():
    if not os.path.exists(SESSION_FILE):
        return None

    age_minutes = (time.time() - os.path.getmtime(SESSION_FILE)) / 60
    if age_minutes > SESSION_LIFETIME_MIN:
        return None

    with open(SESSION_FILE, "r") as f:
        return f.read().strip()


# -----------------------------
# Save new session token
# -----------------------------
def save_session(token):
    with open(SESSION_FILE, "w") as f:
        f.write(token)


# -----------------------------
# Validate session by hitting QRZ
# -----------------------------
def session_valid(session_key):
    try:
        resp = requests.get(QRZ_URL, params={"s": session_key, "callsign": "TEST"})
        root = ET.fromstring(resp.text)

        # Check for invalid session
        for elem in root.iter("Error"):
            if "Invalid session key" in elem.text:
                return False

        return True
    except Exception:
        return False


# -----------------------------
# Get a new QRZ session
# -----------------------------
def new_session():
    print("QRZ Username: ", end="", flush=True)
    username = input().strip()
    password = getpass.getpass("QRZ Password: ")

    resp = requests.get(QRZ_URL, params={"username": username, "password": password})
    root = ET.fromstring(resp.text)

    key_elem = root.find(".//Key")
    if key_elem is None:
        print("❌ Failed to get session key.")
        print(resp.text)
        sys.exit(1)

    session_key = key_elem.text.strip()
    save_session(session_key)
    print("🔑 Got new session key:", session_key)
    return session_key


# -----------------------------
# Obtain a valid session
# -----------------------------
def get_session():
    session = load_session()
    if session and session_valid(session):
        print("✅ Using cached QRZ session.")
        return session

    print("⚠️ Session expired or missing — fetching new one.")
    return new_session()


# -----------------------------
# Perform callsign lookup
# -----------------------------
def lookup_call(session, callsign):
    resp = requests.get(QRZ_URL, params={"s": session, "callsign": callsign})
    xml = resp.text

    root = ET.fromstring(xml)

    # Detect login expiration
    err = root.find(".//Error")
    if err is not None:
        print("❌ QRZ session expired mid-query. Restart script.")
        sys.exit(1)

    # extract fields
    def get(tag): 
        elem = root.find(f".//{tag}")
        return elem.text.strip() if elem is not None else ""

    return {
        "call": get("call"),
        "fname": get("fname"),
        "name": get("name"),
        "addr": get("addr2"),
        "state": get("state"),
        "country": get("country"),
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S")
    }


# -----------------------------
# Export CSV
# -----------------------------
def export_csv(record, filename="qrz_callsigns.csv"):
    file_exists = os.path.exists(filename)

    with open(filename, "a", newline="") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=["call", "fname", "name", "addr", "state", "country", "timestamp"]
        )
        if not file_exists:
            writer.writeheader()
        writer.writerow(record)

    print("💾 CSV updated:", filename)


# -----------------------------
# Export JSON
# -----------------------------
def export_json(record, filename="qrz_callsigns.json"):
    if os.path.exists(filename):
        with open(filename, "r") as f:
            try:
                data = json.load(f)
            except json.JSONDecodeError:
                data = []
    else:
        data = []

    data.append(record)

    with open(filename, "w") as f:
        json.dump(data, f, indent=2)

    print("💾 JSON updated:", filename)


# -----------------------------
# MAIN
# -----------------------------
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="QRZ Callsign Lookup")
    parser.add_argument("callsign", help="Callsign to search")
    parser.add_argument("--csv", action="store_true", help="Export CSV")
    parser.add_argument("--json", action="store_true", help="Export JSON")
    parser.add_argument("--both", action="store_true", help="Export both CSV and JSON")
    args = parser.parse_args()

    callsign = args.callsign.upper()

    session = get_session()
    result = lookup_call(session, callsign)

    # print result
    print("\n📡 Callsign Lookup Result:")
    print(" Call:     ", result["call"])
    print(" Name:     ", result["fname"], result["name"])
    print(" Location: ", result["addr"], ",", result["state"])
    print(" Country:  ", result["country"])
    print()

    # exports
    if args.csv or args.both:
        export_csv(result)

    if args.json or args.both:
        export_json(result)
