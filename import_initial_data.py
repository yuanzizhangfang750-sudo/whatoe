r"""
Import initial data from 今天吃啥.xlsx into Supabase.

PowerShell:
  $env:SUPABASE_SERVICE_ROLE_KEY="你的 service_role key"
  python scripts\import_initial_data.py --dry-run
  python scripts\import_initial_data.py --reset

SUPABASE_URL defaults to the project already used by index.html.
Never put the service_role key into index.html or GitHub.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path

import openpyxl


DEFAULT_SUPABASE_URL = "https://jaokuilqswvphsyuxxyp.supabase.co"
WORKBOOK = Path(__file__).resolve().parents[1] / "今天吃啥.xlsx"
SHEETS = {
    "外卖红榜": ("red", "online"),
    "外卖黑榜": ("black", "online"),
    "线下店红榜": ("red", "offline"),
    "线下店黑榜": ("black", "offline"),
}


def clean_cell(value) -> str:
    if value is None:
        return ""
    return str(value).replace("\u3000", " ").strip()


def read_rows(path: Path) -> list[dict]:
    wb = openpyxl.load_workbook(path, data_only=True)
    rows: list[dict] = []
    for sheet_name, (kind, loc) in SHEETS.items():
        ws = wb[sheet_name]
        for excel_row in ws.iter_rows(min_row=2, values_only=True):
            name = clean_cell(excel_row[0] if len(excel_row) > 0 else "")
            product = clean_cell(excel_row[1] if len(excel_row) > 1 else "") or "店铺整体"
            reasons = [clean_cell(v) for v in excel_row[2:]]
            reasons = [v for v in reasons if v]
            if not name:
                continue
            if not reasons:
                reasons = ["被同学推荐" if kind == "red" else "被同学避雷"]
            rows.append({
                "name": name,
                "type": kind,
                "loc": loc,
                "product": product,
                "reasons": reasons,
            })
    return rows


class SupabaseRest:
    def __init__(self, url: str, key: str):
        self.base = url.rstrip("/") + "/rest/v1"
        self.key = key

    def request(self, method: str, path: str, payload=None, *, returning=False):
        url = f"{self.base}/{path}"
        headers = {
            "apikey": self.key,
            "Authorization": f"Bearer {self.key}",
            "Content-Type": "application/json",
            "Prefer": "return=representation" if returning else "return=minimal",
        }
        data = None if payload is None else json.dumps(payload, ensure_ascii=False).encode("utf-8")
        req = urllib.request.Request(url, data=data, headers=headers, method=method)
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                body = resp.read().decode("utf-8")
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"{method} {url} failed: {exc.code} {detail}") from exc
        if not body:
            return None
        return json.loads(body)

    def reset(self):
        self.request("DELETE", "comments?id=not.is.null")
        self.request("DELETE", "reasons?id=not.is.null")
        self.request("DELETE", "shops?id=not.is.null")

    def insert_shop(self, row: dict) -> int:
        payload = {
            "name": row["name"],
            "type": row["type"],
            "loc": row["loc"],
            "product": row["product"],
            "status": "approved",
        }
        data = self.request("POST", "shops?select=id", payload, returning=True)
        return int(data[0]["id"])

    def insert_reasons(self, shop_id: int, reasons: list[str]):
        payload = [{"shop_id": shop_id, "text": text, "likes": 0, "dislikes": 0} for text in reasons]
        self.request("POST", "reasons", payload)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--file", type=Path, default=WORKBOOK, help="Excel file path")
    parser.add_argument("--dry-run", action="store_true", help="Only parse and print counts")
    parser.add_argument("--reset", action="store_true", help="Delete existing rows before import")
    args = parser.parse_args()

    rows = read_rows(args.file)
    reason_count = sum(len(row["reasons"]) for row in rows)
    print(f"Parsed {len(rows)} shops and {reason_count} reasons from {args.file}")
    print("Sample:")
    for row in rows[:5]:
        print(f"  - {row['type']} {row['loc']} {row['name']} / {row['product']} ({len(row['reasons'])})")

    if args.dry_run:
        return 0

    key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
    if not key:
        print("Missing SUPABASE_SERVICE_ROLE_KEY. Use the service_role key only for this local import.", file=sys.stderr)
        return 2

    url = os.environ.get("SUPABASE_URL", DEFAULT_SUPABASE_URL)
    client = SupabaseRest(url, key)
    if args.reset:
        print("Resetting existing shops/reasons/comments...")
        client.reset()

    for index, row in enumerate(rows, 1):
        shop_id = client.insert_shop(row)
        client.insert_reasons(shop_id, row["reasons"])
        if index % 20 == 0 or index == len(rows):
            print(f"Imported {index}/{len(rows)} shops")

    print("Done.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
