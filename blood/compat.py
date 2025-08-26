# blood/compat.py

# סדר עדיפויות לתרומת כדוריות אדומות (RBC) לפי סוג דם של מקבל
# המפתח: סוג הדם המבוקש (מקבל), הערך: רשימת סוגי הדם שניתן לספק לו לפי עדיפות
DONORS_BY_RECIPIENT = {
    "O-":  ["O-"],
    "O+":  ["O+", "O-"],
    "A-":  ["A-", "O-"],
    "A+":  ["A+", "A-", "O+", "O-"],
    "B-":  ["B-", "O-"],
    "B+":  ["B+", "B-", "O+", "O-"],
    "AB-": ["AB-", "A-", "B-", "O-"],
    "AB+": ["AB+", "AB-", "A+", "A-", "B+", "B-", "O+", "O-"],
}

def plan_dispense(requested_type: str, qty: int, inventory_counts: dict[str, int]) -> tuple[dict, int]:
    """
    יוצר תכנית ניפוק: כמה מנות לקחת מכל סוג תואם כדי לספק כמות מבוקשת.
    :param requested_type: סוג הדם המבוקש (לדוגמה "A+")
    :param qty: כמות מבוקשת (int > 0)
    :param inventory_counts: מילון {סוג: כמות זמינה}
    :return: (plan_dict, shortfall)
             plan_dict: לדוגמה {"A+":2, "O-":1}
             shortfall: אם לא הצליח להגיע למלוא הכמות – כמה חסר (0 אם מלא)
    """
    plan = {}
    remaining = qty
    for donor_type in DONORS_BY_RECIPIENT.get(requested_type, []):
        available = inventory_counts.get(donor_type, 0)
        if available <= 0:
            continue
        take = min(available, remaining)
        if take > 0:
            plan[donor_type] = take
            remaining -= take
            if remaining == 0:
                break
    return plan, remaining  # remaining הוא החוסר
