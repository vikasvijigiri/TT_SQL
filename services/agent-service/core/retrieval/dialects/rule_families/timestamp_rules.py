from typing import List


def get_timestamp_rules() -> List[str]:
    return [
        "Never use CURRENT_DATE, CURRENT_TIMESTAMP, NOW, SYSDATE, or GETDATE. All date-relative logic MUST use {REFERENCE_DATE}. Date: DATEADD(day, -N, TO_DATE({REFERENCE_DATE})).",
        "DATEADD(unit, amount, col) and DATEDIFF(unit, start, end). Always specify unit: year, quarter, month, week, day, hour, minute, second.",
        "Never compare DATE or TIMESTAMP to a bare string literal. DATE: TO_DATE('val', 'YYYY-MM-DD'). TIMESTAMP_NTZ: TO_TIMESTAMP_NTZ('val').",
        "DATE_TRUNC('part', \"col\") for grouping or filtering. Returns TIMESTAMP -- add ::DATE if DATE type needed.",
        'DATE_PART(\'part\', "col") or EXTRACT(part FROM "col"). Both return FLOAT -- add ::INTEGER if needed.',
        "Detect storage unit from magnitude before converting: 10-digit -> seconds -> TO_TIMESTAMP(col). 13-digit -> milliseconds -> TO_TIMESTAMP(col / 1000). 16-digit -> microseconds -> TO_TIMESTAMP(col / 1000000).",
    ]
