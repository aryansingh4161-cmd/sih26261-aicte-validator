"""Random but plausible FAKE content. Every name below is invented."""
from __future__ import annotations

import random
from datetime import date, timedelta
from typing import Dict, List

PREFIX = ["Riverbend", "Hillcrest", "Lakeview", "Sunrise", "Maplewood", "Northfield", "Eastgate", "Cedar Grove",
          "Silverline", "Greenvale", "Orchid", "Ridgeway", "Harborview", "Pinecrest", "Meadowbrook", "Stonebridge",
          "Willowdale", "Brightwater", "Oakridge", "Falcon Ridge"]
KIND = ["Institute of Technology", "College of Engineering", "Institute of Engineering and Management",
        "Technical Campus", "School of Technology"]
CITIES = ["Exampleton", "Testville", "Sampleganj", "Demopur", "Mockabad", "Fictionagar", "Placeholderpur", "Stubnagar"]
STATES = ["Exampleland North", "Exampleland South", "Exampleland West", "Exampleland East"]
FIRST = ["Rohan", "Meera", "Arjun", "Kavya", "Vikram", "Anita", "Sanjay", "Neha", "Karan", "Pooja", "Imran", "Deepa"]
LAST = ["Verma", "Nair", "Kulkarni", "Singh", "Rao", "Mehta", "Iyer", "Gill", "Das", "Khan", "Joshi", "Menon"]
DESIG = ["Chairman", "Secretary"]
REGIONS = ["North-West", "South-East", "Central", "West"]
COURSES = [("UNDER GRADUATE", "ENGINEERING AND TECHNOLOGY", "COMPUTER SCIENCE AND ENGINEERING"),
           ("UNDER GRADUATE", "ENGINEERING AND TECHNOLOGY", "CIVIL ENGINEERING"),
           ("UNDER GRADUATE", "ENGINEERING AND TECHNOLOGY", "MECHANICAL ENGINEERING"),
           ("UNDER GRADUATE", "ENGINEERING AND TECHNOLOGY", "ELECTRICAL ENGINEERING"),
           ("UNDER GRADUATE", "ENGINEERING AND TECHNOLOGY", "ELECTRONICS AND COMMUNICATION ENGINEERING"),
           ("POST GRADUATE", "MANAGEMENT", "MBA"),
           ("POST GRADUATE", "ENGINEERING AND TECHNOLOGY", "COMPUTER SCIENCE AND ENGINEERING")]
FIRE_AUTH = ["Office of the Chief Fire Officer (Synthetic)", "District Fire Services Office (Synthetic)"]
STRUCT_AUTH = ["Office of the Executive Engineer, Public Works (Synthetic)", "Registered Structural Engineer (Synthetic)"]
UNIVERSITY = ["Example Technical University", "Demo State Technical University", "Sample Institute of Higher Studies"]
NUM_WORDS = {1: "One", 2: "Two", 3: "Three", 4: "Four", 5: "Five"}


def money_words():
    return "Rs. 100/-"


def fmt_dmy(d: date) -> str:                # 05-04-2025
    return d.strftime("%d-%m-%Y")


def fmt_dMy(d: date) -> str:                # 05-Apr-2025
    return d.strftime("%d-%b-%Y")


def fmt_long(d: date) -> str:               # 7 April 2025
    return f"{d.day} {d.strftime('%B %Y')}"


def make_institute(rng: random.Random, ay_start: int = 2026) -> Dict:
    pre = rng.choice(PREFIX)
    name = f"{pre} {rng.choice(KIND)}"
    city = rng.choice(CITIES)
    pid = f"1-{rng.randint(1000000, 9999999)}"
    aid = f"1-{rng.randint(10000000000, 99999999999)}"
    ay = f"{ay_start}-{str(ay_start + 1)[-2:]}"
    prev_ay = f"{ay_start - 1}-{str(ay_start)[-2:]}"
    n_prog = rng.randint(2, 4)
    progs = []
    for lvl, prog, course in rng.sample(COURSES, n_prog):
        prev = rng.choice([30, 60, 60, 90, 120])
        curr = prev                       # a clean letter keeps intake unless a defect is injected
        progs.append({"level": lvl, "program": prog, "course": course, "intake_prev": str(prev), "intake_curr": str(curr)})
    completion = date(rng.randint(1985, 2018), rng.randint(1, 12), rng.randint(1, 28))
    return {
        "institute_name": name, "trust_name": f"{pre} Education Society", "city": city, "state": rng.choice(STATES),
        "address": f"{rng.randint(1, 250)} {rng.choice(['Station Road', 'College Road', 'Ring Road', 'Market Lane'])}, {city}, {rng.choice(STATES)} - {rng.randint(100000, 999999)}",
        "permanent_id": pid, "application_id": aid, "academic_year": ay, "prev_academic_year": prev_ay,
        "region": rng.choice(REGIONS), "programs": progs, "university": rng.choice(UNIVERSITY),
        "signatory": f"{rng.choice(FIRST)} {rng.choice(LAST)}", "signatory_designation": rng.choice(DESIG),
        "notary": f"{rng.choice(FIRST)} {rng.choice(LAST)}",
        "building_completion_date": completion.isoformat(),
        "latitude": round(rng.uniform(12.0, 30.0), 5), "longitude": round(rng.uniform(72.0, 88.0), 5),
        "user_id": f"ae{rng.randint(100000, 999999)}",
    }


def rand_date(rng: random.Random, start: date, end: date) -> date:
    return start + timedelta(days=rng.randint(0, max((end - start).days, 1)))
