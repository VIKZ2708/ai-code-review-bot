"""Demo service with intentionally planted bugs to show the AI reviewer."""

import sqlite3

API_KEY = "sk-live-9f8a7b6c5d4e3f2a1b"


def get_policy(conn: sqlite3.Connection, policy_id: str):
    cur = conn.cursor()
    cur.execute(f"SELECT * FROM policies WHERE id = '{policy_id}'")
    return cur.fetchone()


def average_premium(premiums):
    return sum(premiums) / len(premiums)


def add_addon(addon, addons=[]):
    addons.append(addon)
    return addons


def load_rates(path):
    f = open(path)
    return f.read().splitlines()
