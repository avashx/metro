import math
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.optimize import milp, LinearConstraint, Bounds
from scipy.sparse import coo_matrix, vstack


OUTPUT_FILE = "optimal_dispatch.csv"


def find_file(name_candidates):
    for name in name_candidates:
        p = Path(name)
        if p.exists():
            return p
    for root in [Path("."), Path("data")]:
        if root.exists():
            for name in name_candidates:
                p = root / name
                if p.exists():
                    return p
    raise FileNotFoundError(f"Could not find any of: {name_candidates}")


def norm_str(s):
    return str(s).strip().title()


def penalty(severity, skill):
    severity = norm_str(severity)
    skill = norm_str(skill)

    if severity == "Low":
        return 0.0

    if severity == "Medium":
        if skill == "Junior":
            return 1500.0
        return 0.0

    if severity == "Critical":
        if skill == "Junior":
            return 10000.0
        if skill == "Mid":
            return 5000.0
        return 0.0

    raise ValueError(f"Unknown severity: {severity}")


def main():
    incidents_path = find_file(["dispatch_incidents.csv", "data/dispatch_incidents.csv"])
    tech_path = find_file(["technicians.csv", "data/technicians.csv"])

    incidents = pd.read_csv(incidents_path)
    techs = pd.read_csv(tech_path)

    required_incident_cols = {"incident_id", "severity", "estimated_ttr_hours", "sla_tier"}
    required_tech_cols = {"technician_id", "skill_level", "max_incidents_per_shift", "hourly_rate_usd"}

    if not required_incident_cols.issubset(incidents.columns):
        raise ValueError(f"dispatch_incidents.csv must contain columns: {sorted(required_incident_cols)}")
    if not required_tech_cols.issubset(techs.columns):
        raise ValueError(f"technicians.csv must contain columns: {sorted(required_tech_cols)}")

    incidents = incidents.copy()
    techs = techs.copy()

    incidents["severity"] = incidents["severity"].map(norm_str)
    techs["skill_level"] = techs["skill_level"].map(norm_str)

    n_i = len(incidents)
    n_j = len(techs)
    n_vars = n_i * n_j

    # Objective coefficients and variable bounds
    c = np.zeros(n_vars, dtype=float)
    lb = np.zeros(n_vars, dtype=float)
    ub = np.ones(n_vars, dtype=float)

    allowed_critical_skills = {"Senior", "Expert"}

    for i in range(n_i):
        sev = incidents.loc[i, "severity"]
        ttr = float(incidents.loc[i, "estimated_ttr_hours"])
        for j in range(n_j):
            skill = techs.loc[j, "skill_level"]
            rate = float(techs.loc[j, "hourly_rate_usd"])

            idx = i * n_j + j
            c[idx] = rate * ttr + penalty(sev, skill)

            # C3: Critical incidents only to Senior or Expert
            if sev == "Critical" and skill not in allowed_critical_skills:
                lb[idx] = 0.0
                ub[idx] = 0.0

    # C1: each incident assigned exactly once
    rows, cols, data = [], [], []
    for i in range(n_i):
        for j in range(n_j):
            rows.append(i)
            cols.append(i * n_j + j)
            data.append(1.0)
    A_incident = coo_matrix((data, (rows, cols)), shape=(n_i, n_vars)).tocsr()
    con_incident = LinearConstraint(A_incident, np.ones(n_i), np.ones(n_i))

    # C2: technician capacity
    rows, cols, data = [], [], []
    for j in range(n_j):
        for i in range(n_i):
            rows.append(j)
            cols.append(i * n_j + j)
            data.append(1.0)
    A_capacity = coo_matrix((data, (rows, cols)), shape=(n_j, n_vars)).tocsr()
    con_capacity = LinearConstraint(
        A_capacity,
        -np.inf * np.ones(n_j),
        techs["max_incidents_per_shift"].astype(float).to_numpy(),
    )

    # C4: budget cap
    A_budget = coo_matrix(c.reshape(1, -1)).tocsr()
    con_budget = LinearConstraint(A_budget, -np.inf, np.array([600000.0]))

    constraints = [con_incident, con_capacity, con_budget]

    # C5: at least 95% of Critical incidents assigned to Senior or Expert
    critical_idx = [i for i in range(n_i) if incidents.loc[i, "severity"] == "Critical"]
    if critical_idx:
        rows, cols, data = [], [], []
        for i in critical_idx:
            for j in range(n_j):
                if techs.loc[j, "skill_level"] in allowed_critical_skills:
                    rows.append(0)
                    cols.append(i * n_j + j)
                    data.append(1.0)
        if data:
            A_crit = coo_matrix((data, (rows, cols)), shape=(1, n_vars)).tocsr()
            threshold = math.ceil(0.95 * len(critical_idx))
            con_crit = LinearConstraint(A_crit, np.array([threshold], dtype=float), np.array([np.inf]))
            constraints.append(con_crit)

    res = milp(
        c=c,
        integrality=np.ones(n_vars, dtype=int),
        bounds=Bounds(lb, ub),
        constraints=constraints,
        options={"disp": False},
    )

    if res.status != 0 or res.x is None:
        raise RuntimeError(f"Optimization failed. status={res.status}, message={res.message}")

    x = np.rint(res.x).astype(int).reshape(n_i, n_j)

    chosen_j = x.argmax(axis=1)
    assigned_tech_id = techs.loc[chosen_j, "technician_id"].to_numpy()
    assigned_skill = techs.loc[chosen_j, "skill_level"].to_numpy()

    assignment_cost = []
    for i, j in enumerate(chosen_j):
        sev = incidents.loc[i, "severity"]
        ttr = float(incidents.loc[i, "estimated_ttr_hours"])
        rate = float(techs.loc[j, "hourly_rate_usd"])
        skill = techs.loc[j, "skill_level"]
        assignment_cost.append(rate * ttr + penalty(sev, skill))

    dispatch = pd.DataFrame({
        "incident_id": incidents["incident_id"].values,
        "assigned_tech_id": assigned_tech_id,
        "assigned_skill": assigned_skill,
        "assignment_cost": assignment_cost,
    })

    dispatch.to_csv(OUTPUT_FILE, index=False)
    print(f"Saved {OUTPUT_FILE}")


if __name__ == "__main__":
    main()