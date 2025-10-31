# core.py
from pydantic import BaseModel, Field
import numpy as np

class Inputs(BaseModel):
    # Demand
    E_bill_month_kwh: float | None = Field(None, description="Monthly billed energy (kWh)")
    N_day: int = Field(0, ge=0, description="Daytime residents")
    N_night: int = Field(0, ge=0, description="Overnight residents")
    growth_pct: float = 0.0  # %

    # Water / pump
    W_month_liters: float = 0.0
    head_m: float | None = None          # if None -> use proxy specific energy
    pump_eff: float = 0.55               # 0..1
    P_pump_kw: float = 0.75              # nameplate kW (runtime hint)
    S_water: int = 7                     # 1..10 priority scale
    beta_water: float = 0.3

    # Outages / autonomy
    outage_duration: str = "30-60m"      # "<30m","30-60m","1-2h",">2h"
    outage_time: str = "Afternoon"       # Morning/Afternoon/Evening
    T_water_extra_h_max: float = 1.0

    # Critical load
    essentials_listed: bool = False

    # PV performance / resource
    PSH: float = 4.5                     # kWh/m^2/day equivalent (sun hours)
    PR_base: float = 0.78
    shading_pct: float = 0.0

    # Margins
    dust_level: str = "Low"              # Low/Medium/Heavy
    severe_event: str = "None"           # None/Storm/DustStorm/HeavyRain/...
    severe_freq: str = "Seasonal"        # Rare/Seasonal/Often
    S_elec: int = 7

    # Site area & density
    A_roof_m2: float = 120.0
    A_ground_m2: float = 0.0
    PD_kwp_per_m2: float = 0.19          # module power density

    # Inverter / storage
    DC_AC: float = 1.2
    DoD: float = 0.8
    eta_sys: float = 0.9

    # Carbon & market
    grid_yes: bool = True
    EF_grid: float = 0.6                 # kgCO2/kWh
    EF_diesel: float = 0.8
    p_CO2: float = 6.0                   # $/tCO2e

    # Safety bounds
    growth_cap: float = 2.0              # max growth multiplier

def daily_site_energy_kwh(i: Inputs) -> float:
    if i.E_bill_month_kwh and i.E_bill_month_kwh > 0:
        return i.E_bill_month_kwh / 30.0
    # fallback per-capita: day vs night presence
    return 2.8 * i.N_day + 1.4 * i.N_night

def pump_energy_kwh_day(i: Inputs) -> float:
    # hydraulic if head known, else proxy specific energy (kWh/m3)
    if i.head_m is not None:
        rho, g = 1000.0, 9.81
        m3_per_day = (i.W_month_liters / 30.0) / 1000.0
        J_per_day = rho * g * i.head_m * m3_per_day
        kWh_per_day = J_per_day / (i.pump_eff * 3.6e6)
        return max(kWh_per_day, 0.0)
    e_spec = 0.45  # kWh/m3 proxy
    return (i.W_month_liters / 30_000.0) * e_spec

def water_priority_factor(i: Inputs) -> float:
    return 1.0 + i.beta_water * max(0.0, (i.S_water - 7) / 3.0)

def growth_multiplier(i: Inputs) -> float:
    G = 1.0 + i.growth_pct / 100.0
    return min(G, i.growth_cap)

def critical_fraction(i: Inputs) -> float:
    base = 0.30 + (0.05 if i.essentials_listed else 0.0)
    return float(np.clip(base, 0.20, 0.40))

def autonomy_hours(i: Inputs) -> float:
    base_map = {"<30m": 0.5, "30-60m": 1.0, "1-2h": 2.0, ">2h": 3.0}
    t_mult = {"Morning": 1.0, "Afternoon": 1.2, "Evening": 1.5}
    T_base = base_map.get(i.outage_duration, 1.0)
    kappa = t_mult.get(i.outage_time, 1.0)
    T = max(2.0, T_base * kappa)
    # optional water-priority bump
    bump = i.T_water_extra_h_max * max(0.0, (i.S_water - 7) / 2.0)
    return T + bump

def performance_ratio_eff(i: Inputs) -> float:
    return i.PR_base * (1.0 - i.shading_pct / 100.0)

def dust_margin(i: Inputs) -> float:
    return {"Low": 0.00, "Medium": 0.05, "Heavy": 0.10}.get(i.dust_level, 0.0)

def severe_margin(i: Inputs) -> float:
    if i.severe_event == "None":
        return 0.0
    base = 0.03
    freq = {"Rare": 0.5, "Seasonal": 1.0, "Often": 1.5}.get(i.severe_freq, 1.0)
    return base * freq

def priority_margins(i: Inputs) -> float:
    m = 0.0
    if i.S_elec >= 8: m += 0.02
    if i.S_water >= 8: m += 0.02
    return m

def total_margin(i: Inputs) -> float:
    M = dust_margin(i) + severe_margin(i) + priority_margins(i)
    return min(M, 0.20)

def plan(i: Inputs) -> dict:
    # Demand
    E_site = daily_site_energy_kwh(i)
    E_pump = pump_energy_kwh_day(i) * water_priority_factor(i)
    G = growth_multiplier(i)
    E_daily = (E_site + E_pump) * G

    # Critical and autonomy
    fcrit = critical_fraction(i)
    E_crit = fcrit * E_daily
    T_aut = autonomy_hours(i)
    E_aut = E_daily * (T_aut / 24.0)
    E_need = max(E_crit, E_aut)
    E_bat = E_need / (i.DoD * i.eta_sys)

    # PV size
    PR_eff = performance_ratio_eff(i)
    kWp_raw = E_daily / (i.PSH * PR_eff) * (1.0 + total_margin(i))
    kWp_cap = (i.A_roof_m2 + i.A_ground_m2) * i.PD_kwp_per_m2
    kWp = min(kWp_raw, kWp_cap)
    P_inv = kWp / i.DC_AC

    # Annuals & carbon
    E_pv_yr = kWp * i.PSH * PR_eff * 365.0
    E_load_yr = E_daily * 365.0
    E_matched = min(E_pv_yr, E_load_yr)
    EF = i.EF_grid if i.grid_yes else i.EF_diesel
    tCO2_yr = E_matched * EF / 1000.0
    credits_yr = tCO2_yr                 # no buffer
    value_carbon_yr = credits_yr * i.p_CO2

    # Convenience hints
    h_pump = max(0.5, E_pump / max(i.P_pump_kw, 0.1))

    return {
        "E_site": E_site,
        "E_pump": E_pump,
        "G": G,
        "E_daily": E_daily,
        "fcrit": fcrit,
        "T_aut": T_aut,
        "E_crit": E_crit,
        "E_aut": E_aut,
        "E_need": E_need,
        "E_bat": E_bat,
        "PR_eff": PR_eff,
        "kWp_raw": kWp_raw,
        "kWp_cap": kWp_cap,
        "kWp": kWp,
        "P_inv": P_inv,
        "E_pv_yr": E_pv_yr,
        "E_load_yr": E_load_yr,
        "E_matched": E_matched,
        "tCO2_yr": tCO2_yr,
        "credits_yr": credits_yr,
        "value_carbon_yr": value_carbon_yr,
        "h_pump": h_pump,
    }
