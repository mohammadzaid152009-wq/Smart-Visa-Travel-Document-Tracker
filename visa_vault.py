"""Visa Vault - simple visa/document tracker.

Run:
    pip install streamlit pandas
    streamlit run visa_vault.py
"""
import sqlite3
from datetime import date, timedelta
from pathlib import Path

import pandas as pd
import streamlit as st

DB = "visa_vault.db"
UPLOADS = Path("uploads")
UPLOADS.mkdir(exist_ok=True)


def conn():
    c = sqlite3.connect(DB)
    c.execute(
        """CREATE TABLE IF NOT EXISTS visas (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            holder TEXT, country TEXT, visa_type TEXT, visa_number TEXT,
            issue_date TEXT, expiry_date TEXT, notes TEXT, file_path TEXT)"""
    )
    return c


def add_visa(row):
    with conn() as c:
        c.execute(
            """INSERT INTO visas (holder, country, visa_type, visa_number,
               issue_date, expiry_date, notes, file_path)
               VALUES (?,?,?,?,?,?,?,?)""",
            row,
        )


def load():
    with conn() as c:
        df = pd.read_sql("SELECT * FROM visas ORDER BY expiry_date", c)
    df["expiry_date"] = pd.to_datetime(df["expiry_date"]).dt.date
    return df


def delete(visa_id):
    with conn() as c:
        c.execute("DELETE FROM visas WHERE id = ?", (visa_id,))


def status(expiry, warn_days=60):
    today = date.today()
    if expiry < today:
        return "Expired"
    if expiry <= today + timedelta(days=warn_days):
        return "Expiring soon"
    return "Valid"


st.set_page_config(page_title="Visa Vault", page_icon="🛂", layout="wide")
st.title("🛂 Visa Vault")

with st.sidebar:
    st.header("Add visa")
    with st.form("add", clear_on_submit=True):
        holder = st.text_input("Holder name")
        country = st.text_input("Country")
        visa_type = st.text_input("Visa type (e.g. Tourist, Work)")
        visa_number = st.text_input("Visa number")
        issue = st.date_input("Issue date", value=date.today())
        expiry = st.date_input("Expiry date", value=date.today() + timedelta(days=365))
        notes = st.text_area("Notes")
        doc = st.file_uploader("Document (PDF/image)", type=["pdf", "png", "jpg", "jpeg"])
        if st.form_submit_button("Save") and holder and country:
            path = ""
            if doc:
                path = str(UPLOADS / f"{date.today().isoformat()}_{doc.name}")
                Path(path).write_bytes(doc.getbuffer())
            add_visa((holder, country, visa_type, visa_number,
                      issue.isoformat(), expiry.isoformat(), notes, path))
            st.success("Saved")
            st.rerun()

df = load()
if df.empty:
    st.info("No visas yet. Add one from the sidebar.")
else:
    df["status"] = df["expiry_date"].apply(status)
    c1, c2, c3 = st.columns(3)
    c1.metric("Total", len(df))
    c2.metric("Expiring soon", int((df["status"] == "Expiring soon").sum()))
    c3.metric("Expired", int((df["status"] == "Expired").sum()))

    flt = st.multiselect("Filter by status", ["Valid", "Expiring soon", "Expired"],
                         default=["Valid", "Expiring soon", "Expired"])
    view = df[df["status"].isin(flt)]
    st.dataframe(view.drop(columns=["file_path"]), use_container_width=True, hide_index=True)

    st.subheader("Manage")
    for _, r in view.iterrows():
        with st.expander(f"{r['holder']} - {r['country']} ({r['visa_type']}) - {r['status']}"):
            st.write(f"Number: {r['visa_number']} | Expires: {r['expiry_date']}")
            if r["notes"]:
                st.write(r["notes"])
            if r["file_path"] and Path(r["file_path"]).exists():
                st.download_button("Download document",
                                   Path(r["file_path"]).read_bytes(),
                                   file_name=Path(r["file_path"]).name,
                                   key=f"dl{r['id']}")
            if st.button("Delete", key=f"del{r['id']}"):
                delete(r["id"])
                st.rerun()
