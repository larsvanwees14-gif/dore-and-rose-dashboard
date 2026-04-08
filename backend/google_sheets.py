import json
import os
import re
from datetime import datetime

from google.oauth2 import service_account
from googleapiclient.discovery import build

from backend.cache import save_cache, load_cache, is_cache_stale

SCOPES = ["https://www.googleapis.com/auth/spreadsheets.readonly"]

MONTH_NAMES = {
    "january": 1, "february": 2, "march": 3, "april": 4,
    "may": 5, "june": 6, "july": 7, "august": 8,
    "september": 9, "october": 10, "november": 11, "december": 12,
}


def safe_float(value) -> float:
    if value is None or value == "":
        return 0.0
    s = str(value).replace("\u20ac", "").replace("$", "").replace(".", "").replace(",", ".").replace("- ", "-").strip()
    if s.endswith("%"):
        s = s[:-1].strip()
    try:
        return float(s)
    except ValueError:
        return 0.0


def col_to_index(letter):
    letter = letter.upper().strip()
    result = 0
    for c in letter:
        result = result * 26 + (ord(c) - ord('A') + 1)
    return result - 1


class DoreAndRoseSheets:
    def __init__(self, config):
        self.config = config["google_sheets"]
        self.cache_ttl = config.get("cache", {}).get("ttl_minutes", 5)

        # Credentials: must be provided via GOOGLE_CREDENTIALS_JSON env var
        creds_json = os.environ.get("GOOGLE_CREDENTIALS_JSON")
        if not creds_json:
            raise RuntimeError(
                "Missing required environment variable GOOGLE_CREDENTIALS_JSON. "
                "Set it to the full JSON content of your Google service account key file. "
                "In Railway: go to your service → Variables and add GOOGLE_CREDENTIALS_JSON "
                "with the contents of your service account JSON."
            )
        info = json.loads(creds_json)
        creds = service_account.Credentials.from_service_account_info(info, scopes=SCOPES)

        self._service = build("sheets", "v4", credentials=creds)
        self._sheet_id = self.config["spreadsheet_id"]

    def _read_range(self, range_str):
        result = self._service.spreadsheets().values().get(
            spreadsheetId=self._sheet_id, range=range_str
        ).execute()
        return result.get("values", [])

    def get_dashboard_data(self, force_refresh=False):
        cache_key = "dashboard"
        if not force_refresh and not is_cache_stale(cache_key, self.cache_ttl):
            cached = load_cache(cache_key)
            if cached:
                return cached["data"]

        data = self._fetch_overview()
        save_cache(cache_key, data)
        return data

    def get_month_detail(self, tab_name, force_refresh=False):
        cache_key = f"month_{tab_name.replace(' ', '_')}"
        if not force_refresh and not is_cache_stale(cache_key, self.cache_ttl):
            cached = load_cache(cache_key)
            if cached:
                return cached["data"]

        data = self._fetch_month_tab(tab_name)
        save_cache(cache_key, data)
        return data

    def get_category_actuals(self, target_config, force_refresh=False):
        """Aggregate revenue per category per month from gross_products data."""
        cache_key = "category_actuals"
        if not force_refresh and not is_cache_stale(cache_key, self.cache_ttl):
            cached = load_cache(cache_key)
            if cached:
                return cached["data"]

        btw_rate = target_config.get("btw_rate", 0.21)
        categories = target_config.get("categories", {})
        target_year = target_config.get("year", 2026)

        # Build match rules: category_name -> list of name prefixes
        match_rules = {}
        for cat_name, cat_conf in categories.items():
            match_rules[cat_name] = [n.lower() for n in cat_conf.get("match_names", [])]

        # For each month tab, get gross products and categorize
        result = {}  # { "Sleep Masks": { "2026-01": revenue_inc_btw, ... }, ... }
        for cat_name in categories:
            result[cat_name] = {}

        tabs = self.config.get("month_tabs", [])
        for tab in tabs:
            # Determine year/month for this tab
            parts = tab.split()
            month_name = parts[0].lower()
            month_num = MONTH_NAMES.get(month_name, 0)
            if not month_num:
                continue
            if len(parts) == 2 and parts[1].isdigit():
                year = 2000 + int(parts[1]) if int(parts[1]) < 100 else int(parts[1])
            else:
                today = datetime.now()
                year = today.year if month_num <= today.month + 1 else today.year - 1

            # Only process target year
            if year != target_year:
                continue

            month_key = f"{year}-{month_num:02d}"

            # Get gross products for this tab
            detail = self.get_month_detail(tab)
            gross_products = detail.get("gross_products", [])

            # Categorize
            cat_totals = {cat: 0.0 for cat in categories}
            for product in gross_products:
                name_lower = product["name"].lower()
                matched = False
                for cat_name, prefixes in match_rules.items():
                    for prefix in prefixes:
                        if prefix in name_lower:
                            cat_totals[cat_name] += product["nett_rev"]
                            matched = True
                            break
                    if matched:
                        break

            for cat_name in categories:
                result[cat_name][month_key] = round(cat_totals[cat_name] * (1 + btw_rate), 2)

        save_cache(cache_key, result)
        return result

    def _fetch_overview(self):
        rows = self._read_range(f"'Overview'!A1:J200")
        months = []
        current_month = None
        block = {}
        block_right = {}

        for row in rows:
            if len(row) < 2:
                continue

            label_b = str(row[1]).strip() if len(row) > 1 else ""
            val_c = row[2] if len(row) > 2 else ""
            val_d = row[3] if len(row) > 3 else ""

            label_f = str(row[5]).strip() if len(row) > 5 else ""
            val_g = row[6] if len(row) > 6 else ""

            if label_b == "Month":
                if current_month and block:
                    months.append(self._build_month(current_month, block, block_right))
                current_month = str(val_c).strip() if val_c else str(row[3]).strip() if len(row) > 3 else ""
                block = {}
                block_right = {}
                continue

            if label_b in ("Revenue", "Nett Revenue"):
                block["revenue"] = safe_float(val_c)
            elif "Gross Margin" in label_b:
                block["gross_margin"] = safe_float(val_c)
                block["gross_margin_pct"] = safe_float(val_d)
            elif "Nett Margin Product" in label_b:
                block["nett_margin_product"] = safe_float(val_c)
                block["nett_margin_product_pct"] = safe_float(val_d)
            elif label_b == "Nett Margin Business":
                block["nett_margin_business"] = safe_float(val_c)
                block["nett_margin_business_pct"] = safe_float(val_d)
            elif "Nett Margin Business - Fee" in label_b:
                block["nett_margin_after_fee"] = safe_float(val_c)
            elif "Invoice amount" in label_b:
                block["invoice_amount"] = safe_float(val_c)

            if label_f == "Invoiced Revenue":
                block_right["invoiced_revenue"] = safe_float(val_g)
            elif label_f == "VAT":
                block_right["vat"] = safe_float(val_g)
            elif "Costs made by" in label_f:
                block_right["costs_lars"] = safe_float(val_g)
            elif label_f == "Fee Lars":
                block_right["fee_lars"] = safe_float(val_g)
            elif label_f == "Profit Lars":
                block_right["profit_lars"] = safe_float(val_g)

        if current_month and block:
            months.append(self._build_month(current_month, block, block_right))

        months.sort(key=lambda m: (m["year"], m["month_num"]))

        available_tabs = [t for t in self.config.get("month_tabs", [])]

        return {"months": months, "available_tabs": available_tabs}

    def _build_month(self, month_name, block, block_right):
        month_num = MONTH_NAMES.get(month_name.lower(), 0)
        today = datetime.now()

        # Handle tab names like "January 26" -> year 2026
        parts = month_name.split()
        if len(parts) == 2 and parts[1].isdigit():
            short_year = int(parts[1])
            year = 2000 + short_year if short_year < 100 else short_year
            month_num = MONTH_NAMES.get(parts[0].lower(), 0)
        elif month_num > today.month + 1:
            year = today.year - 1
        else:
            year = today.year

        return {
            "month": month_name,
            "month_num": month_num,
            "year": year,
            "revenue": block.get("revenue", 0),
            "gross_margin": block.get("gross_margin", 0),
            "gross_margin_pct": block.get("gross_margin_pct", 0),
            "nett_margin_product": block.get("nett_margin_product", 0),
            "nett_margin_product_pct": block.get("nett_margin_product_pct", 0),
            "nett_margin_business": block.get("nett_margin_business", 0),
            "nett_margin_business_pct": block.get("nett_margin_business_pct", 0),
            "nett_margin_after_fee": block.get("nett_margin_after_fee", 0),
            "invoice_amount": block.get("invoice_amount", 0),
            "invoiced_revenue": block_right.get("invoiced_revenue", 0),
            "vat": block_right.get("vat", 0),
            "costs_lars": block_right.get("costs_lars", 0),
            "fee_lars": block_right.get("fee_lars", 0),
            "profit_lars": block_right.get("profit_lars", 0),
        }

    def _fetch_month_tab(self, tab_name):
        rows = self._read_range(f"'{tab_name}'!A1:Q200")

        overview = {}
        if len(rows) > 1:
            overview["nett_revenue"] = safe_float(rows[1][2]) if len(rows[1]) > 2 else 0
        if len(rows) > 2:
            overview["gross_margin"] = safe_float(rows[2][2]) if len(rows[2]) > 2 else 0
            overview["gross_margin_pct"] = safe_float(rows[2][3]) if len(rows[2]) > 3 else 0
        if len(rows) > 3:
            overview["nett_margin_product"] = safe_float(rows[3][2]) if len(rows[3]) > 2 else 0
            overview["nett_margin_product_pct"] = safe_float(rows[3][3]) if len(rows[3]) > 3 else 0
        if len(rows) > 4:
            overview["nett_margin_business"] = safe_float(rows[4][2]) if len(rows[4]) > 2 else 0
            overview["nett_margin_business_pct"] = safe_float(rows[4][3]) if len(rows[4]) > 3 else 0
        if len(rows) > 6:
            overview["acc_taxes"] = safe_float(rows[6][2]) if len(rows[6]) > 2 else 0

        # Gross margins per product (starting ~row 11, header at row 10)
        gross_products = []
        header_row = None
        for i, row in enumerate(rows):
            if len(row) > 0 and str(row[0]).strip() == "EAN":
                header_row = i
                break

        def is_ean(val):
            """Check if value looks like an EAN (starts with digits)."""
            return bool(val) and len(val) >= 8 and val[:4].isdigit()

        def is_section_end(row, i, rows):
            """Detect end of product section (totals row or new section header)."""
            if len(row) == 0:
                return False
            first = str(row[0]).strip()
            # Totals row: empty EAN but has numeric values in col C
            if not first and len(row) > 2 and safe_float(row[2]) != 0:
                # Check if next meaningful row is a new section
                return True
            # New section header like "Nett margins Per Product" or "Overhead cost"
            if "margin" in first.lower() or "overhead" in first.lower():
                return True
            return False

        if header_row is not None:
            for i in range(header_row + 1, len(rows)):
                row = rows[i]
                if len(row) < 2:
                    continue

                first = str(row[0]).strip() if len(row) > 0 else ""

                # Skip category headers (empty EAN, short row or just a label)
                if not first and len(row) <= 3:
                    continue

                # Check for section end (totals row)
                if is_section_end(row, i, rows):
                    break

                # Skip non-EAN rows
                if not is_ean(first):
                    continue

                product = {
                    "ean": first,
                    "name": str(row[1]).strip() if len(row) > 1 else "",
                    "nett_rev": safe_float(row[2]) if len(row) > 2 else 0,
                    "sales": safe_float(row[3]) if len(row) > 3 else 0,
                    "direct_cost": safe_float(row[6]) if len(row) > 6 else 0,
                    "gross_profit": safe_float(row[7]) if len(row) > 7 else 0,
                    "gross_margin": safe_float(row[8]) if len(row) > 8 else 0,
                    "conversion": safe_float(row[9]) if len(row) > 9 else 0,
                    "returns": safe_float(row[10]) if len(row) > 10 else 0,
                    "returns_pct": safe_float(row[11]) if len(row) > 11 else 0,
                    "ad_spend": safe_float(row[12]) if len(row) > 12 else 0,
                    "acos": safe_float(row[15]) if len(row) > 15 else 0,
                    "tacos": safe_float(row[16]) if len(row) > 16 else 0,
                }
                gross_products.append(product)

        # Nett margins per product - find second "Nett margins" section header
        nett_products = []
        nett_section_start = None
        for i, row in enumerate(rows):
            if len(row) > 0 and "Nett margin" in str(row[0]):
                nett_section_start = i
                break

        nett_header = None
        if nett_section_start is not None:
            for i in range(nett_section_start, min(nett_section_start + 3, len(rows))):
                if len(rows[i]) > 0 and str(rows[i][0]).strip() == "EAN":
                    nett_header = i
                    break

        if nett_header is not None:
            for i in range(nett_header + 1, len(rows)):
                row = rows[i]
                if len(row) < 2:
                    continue

                first = str(row[0]).strip() if len(row) > 0 else ""

                # Skip category headers
                if not first and len(row) <= 3:
                    continue

                # Check for section end
                if is_section_end(row, i, rows):
                    break

                if not is_ean(first):
                    continue

                product = {
                    "ean": first,
                    "name": str(row[1]).strip() if len(row) > 1 else "",
                    "gross_profit": safe_float(row[2]) if len(row) > 2 else 0,
                    "ad_cost": safe_float(row[4]) if len(row) > 4 else 0,
                    "return_costs": safe_float(row[5]) if len(row) > 5 else 0,
                    "storage_cost": safe_float(row[7]) if len(row) > 7 else 0,
                    "netto_profit": safe_float(row[9]) if len(row) > 9 else 0,
                    "netto_margin": safe_float(row[10]) if len(row) > 10 else 0,
                }
                nett_products.append(product)

        # Overhead costs - find "Overhead cost" section
        overhead = []
        overhead_start = None
        for i, row in enumerate(rows):
            if len(row) > 0 and "Overhead" in str(row[0]):
                overhead_start = i
                break

        if overhead_start is not None:
            # Skip header row(s) and empty rows, find data rows
            for j in range(overhead_start + 2, min(overhead_start + 30, len(rows))):
                orow = rows[j] if j < len(rows) else []
                if len(orow) == 0:
                    continue
                first = str(orow[0]).strip() if len(orow) > 0 else ""
                second = str(orow[1]).strip() if len(orow) > 1 else ""
                # Stop at totals or new sections
                if any(kw in first or kw in second for kw in ("Totaal", "Nett Margin", "Non-sale")):
                    break
                overhead_type = second or first
                cost = safe_float(orow[2]) if len(orow) > 2 else 0
                if overhead_type and cost != 0:
                    overhead.append({
                        "made_by": first,
                        "type": overhead_type,
                        "cost": cost,
                    })

        return {
            "tab": tab_name,
            "overview": overview,
            "gross_products": gross_products,
            "nett_products": nett_products,
            "overhead": overhead,
        }
