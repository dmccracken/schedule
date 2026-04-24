import pandas as pd
from datetime import datetime
import calendar


def get_monthly_headcount(
    excel_path: str,
    start_month: str,
    end_month: str,
) -> dict[str, int]:
    """
    Calculate month-end headcount from Excel staffing data.

    Args:
        excel_path: Path to Excel file with AMAT DOJ and AMAT DOD columns
        start_month: Start month in "YYYY-MM" format
        end_month: End month in "YYYY-MM" format

    Returns:
        Dict mapping month labels ("Mon YYYY") to headcount at month-end
    """
    df = pd.read_excel(excel_path)

    df = df.dropna(subset=["AMAT DOJ", "AMAT DOD"])

    df["AMAT DOJ"] = pd.to_datetime(df["AMAT DOJ"])
    df["AMAT DOD"] = pd.to_datetime(df["AMAT DOD"])

    start_date = datetime.strptime(start_month, "%Y-%m")
    end_date = datetime.strptime(end_month, "%Y-%m")

    result = {}
    current = start_date

    while current <= end_date:
        last_day = calendar.monthrange(current.year, current.month)[1]
        month_end = datetime(current.year, current.month, last_day)

        count = ((df["AMAT DOJ"] <= month_end) & (df["AMAT DOD"] >= month_end)).sum()

        month_label = current.strftime("%b %Y")
        result[month_label] = int(count)

        if current.month == 12:
            current = datetime(current.year + 1, 1, 1)
        else:
            current = datetime(current.year, current.month + 1, 1)

    return result
