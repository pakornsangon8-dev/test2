import math
import os
import sqlite3
from typing import Any, Dict, List, Optional
import pandas as pd

# กำหนด Path และชื่อตารางให้ชัดเจน
DB_PATH = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "officers_database.db"
)
TABLE_NAME = "officers_history"
ANNOUNCEMENTS_TABLE = "announcements"


def is_using_supabase() -> bool:
  """เราไม่ได้ใช้ Supabase แล้ว ให้คืนค่า False เสมอ"""
  return False


def get_connection():
  """เชื่อมต่อ SQLite ท้องถิ่น"""
  conn = sqlite3.connect(DB_PATH)
  conn.row_factory = sqlite3.Row
  return conn


def init_db():
  """สร้างโครงสร้างตารางฐานข้อมูล SQLite ท้องถิ่น (ถ้ายังไม่มี)"""
  conn = get_connection()
  cursor = conn.cursor()
  cursor.execute("""
        CREATE TABLE IF NOT EXISTS announcements (
            announcement_id INTEGER PRIMARY KEY,
            announcement_no INTEGER NOT NULL UNIQUE,
            start_date TEXT NOT NULL,
            minister_name TEXT,
            term_years REAL DEFAULT 4.0
        )
    """)
  try:
    # กรณีมีการอัปเดตตารางให้รองรับคอลัมน์ใหม่
    cursor.execute(
        "ALTER TABLE announcements ADD COLUMN term_years REAL DEFAULT 4.0"
    )
  except:
    pass

  conn.commit()
  conn.close()


def append_officers_history(df: pd.DataFrame) -> int:
  """บันทึกข้อมูลสะสม (Append) ลง SQLite"""
  if df.empty:
    return 0

  conn = get_connection()
  cursor = conn.cursor()

  # เช็คว่ามีตาราง officers_history สร้างไว้หรือยัง
  cursor.execute(
      "SELECT name FROM sqlite_master WHERE type='table' AND"
      " name='officers_history';"
  )
  table_exists = cursor.fetchone()

  # หากมีตารางแล้ว ให้เช็คว่ามีคอลัมน์ใหม่มาเพิ่มไหม ถ้ามีให้สร้างคอลัมน์เพิ่ม (Auto Migration)
  if table_exists:
    cursor.execute("PRAGMA table_info(officers_history);")
    existing_cols = {col[1] for col in cursor.fetchall()}
    for col_name in df.columns:
      if col_name not in existing_cols:
        try:
          cursor.execute(
              f'ALTER TABLE officers_history ADD COLUMN "{col_name}" TEXT;'
          )
        except Exception:
          pass
    conn.commit()

  # เขียนข้อมูลลง Database แบบเอาของใหม่ไปต่อท้าย (Append)
  df.to_sql(TABLE_NAME, conn, if_exists="append", index=False)
  conn.close()
  return len(df)


def load_officers_history() -> pd.DataFrame:
  """ดึงข้อมูลประวัติพนักงานทั้งหมดจาก SQLite"""
  if not os.path.exists(DB_PATH):
    return pd.DataFrame()

  conn = get_connection()
  check_query = (
      "SELECT name FROM sqlite_master WHERE type='table' AND"
      " name='officers_history';"
  )
  table_exists = pd.read_sql_query(check_query, conn)

  if table_exists.empty:
    conn.close()
    return pd.DataFrame()

  query = f"SELECT * FROM {TABLE_NAME}"
  df = pd.read_sql_query(query, conn)
  conn.close()
  return df


def delete_all_officers_history():
  """ล้างข้อมูลประวัติพนักงานทั้งหมด"""
  if os.path.exists(DB_PATH):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("DROP TABLE IF EXISTS officers_history")
    conn.commit()
    conn.close()
    # สร้างตารางเปล่าๆ เตรียมไว้ใหม่
    init_db()


def get_all_announcements():
  """ดึงข้อมูลประกาศราชกิจจาฯ ทั้งหมด"""
  if not os.path.exists(DB_PATH):
    return pd.DataFrame(
        columns=["announcement_no", "start_date", "minister_name", "term_years"]
    )

  conn = get_connection()
  query = (
      "SELECT announcement_no, start_date, minister_name, term_years FROM"
      " announcements ORDER BY announcement_no DESC"
  )
  try:
    df = pd.read_sql_query(query, conn)
  except Exception:
    df = pd.DataFrame(
        columns=["announcement_no", "start_date", "minister_name", "term_years"]
    )
  conn.close()
  return df


def get_announcement_dict():
  """ดึงประกาศราชกิจจาฯ ส่งกลับไปในรูปแบบ Dictionary เพื่อให้ Pipeline เรียกใช้"""
  if not os.path.exists(DB_PATH):
    return {}

  conn = get_connection()
  cursor = conn.cursor()
  try:
    cursor.execute(
        "SELECT announcement_no, start_date, minister_name, term_years FROM"
        " announcements"
    )
    rows = cursor.fetchall()
  except Exception:
    rows = []
  conn.close()

  result = {}
  for row in rows:
    result[row["announcement_no"]] = {
        "start_date": row["start_date"],
        "minister_name": row["minister_name"],
        "term_years": row["term_years"] if row["term_years"] else 4.0,
    }
  return result


def add_or_update_announcement(
    announcement_no, start_date, minister_name, term_years=4.0
):
  """เพิ่มหรืออัปเดตข้อมูลประกาศราชกิจจาฯ"""
  conn = get_connection()
  cursor = conn.cursor()
  cursor.execute(
      """
        INSERT INTO announcements (announcement_no, start_date, minister_name,"
      " term_years)
        VALUES (?, ?, ?, ?)
        ON CONFLICT(announcement_no) DO UPDATE SET
            start_date=excluded.start_date,
            minister_name=excluded.minister_name,
            term_years=excluded.term_years
    """,
      (announcement_no, start_date, minister_name, term_years),
  )
  conn.commit()
  conn.close()


def delete_announcement(announcement_no):
  """ลบประกาศราชกิจจาฯ ที่เลือก"""
  if os.path.exists(DB_PATH):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "DELETE FROM announcements WHERE announcement_no = ?", (announcement_no,)
    )
    conn.commit()
    conn.close()


def delete_history_by_file(source_filename: str):
  """ฟังก์ชันสำหรับลบประวัติการอัปโหลดเฉพาะไฟล์ที่กำหนด"""
  try:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        f"DELETE FROM {TABLE_NAME} WHERE source_file = ?", (source_filename,)
    )
    conn.commit()
    conn.close()
  except Exception as e:
    print(f"Error deleting history for file {source_filename}: {e}")
    raise e


# เรียกใช้ฟังก์ชัน init_db 1 ครั้ง เพื่อเตรียมพร้อมฐานข้อมูลตอนเปิดใช้งานระบบ
init_db()