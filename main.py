# main.py
import os
import json
from datetime import date
from jinja2 import Template
from nicegui import ui
from core import Inputs, plan

# Load HTML template once
with open('report_template.html', 'r', encoding='utf-8') as f:
    REPORT_TPL = Template(f.read())

def render_report(inputs: Inputs, results: dict) -> str:
    return REPORT_TPL.render(
        today=date.today().isoformat(),
        site_name="Demo Site",
        inputs=inputs,
        results=results,
    )

def number(label, value=0.0, step=1.0, minv=None, maxv=None):
    return ui.number(label, value=value, step=step, min=minv, max=maxv).props('outlined dense').classes('w-full')

# -------- UI -----------
ui.label('Solarization Planner').classes('text-2xl font-bold my-2')
ui.label('Browser-first sizing tool (NiceGUI)').classes('mb-4 text-gray-600')

with ui.tabs() as tabs:
    t1 = ui.tab('Demand & Water')
    t2 = ui.tab('Outages & Critical')
    t3 = ui.tab('PV, Site & Margins')
    t4 = ui.tab('Carbon')
    t5 = ui.tab('Run & Report')

with ui.tab_panels(tabs, value=t1).classes('w-full'):
    with ui.tab_panel(t1):
        with ui.row().classes('items-stretch w-full'):
            with ui.card().classes('w-1/2'):
                ui.label('Demand').classes('text-lg font-semibold')
                bill = number('Monthly bill (kWh)', 0, step=10)
                nday = number('Residents (day)', 0, step=1, minv=0)
                nnig = number('Residents (night)', 0, step=1, minv=0)
                grow = number('Growth % (cap 100%)', 0, step=1, minv=0, maxv=100)
            with ui.card().classes('w-1/2'):
                ui.label('Water & Pump').classes('text-lg font-semibold')
                wmo  = number('Water volume (L/month)', 0, step=1000, minv=0)
                head = number('Head (m) (0 for proxy)', 0, step=1, minv=0)
                peff = number('Pump efficiency (0–1)', 0.55, step=0.05, minv=0.1, maxv=0.9)
                pkw  = number('Pump rated power (kW)', 0.75, step=0.1, minv=0.1)
                swat = number('Water priority score (1–10)', 7, step=1, minv=1, maxv=10)
                bwat = number('Water priority beta (0–0.5)', 0.3, step=0.05, minv=0, maxv=0.5)

    with ui.tab_panel(t2):
        with ui.row().classes('items-stretch w-full'):
            with ui.card().classes('w-1/2'):
                ui.label('Outages').classes('text-lg font-semibold')
                outdur = ui.select(['<30m','30-60m','1-2h','>2h'], value='30-60m', label='Outage duration').props('outlined dense').classes('w-full')
                outtod = ui.select(['Morning','Afternoon','Evening'], value='Afternoon', label='Outage time').props('outlined dense').classes('w-full')
                twmax  = number('Water autonomy bump max (h)', 1.0, step=0.5, minv=0, maxv=2)
            with ui.card().classes('w-1/2'):
                ui.label('Critical Load').classes('text-lg font-semibold')
                ess = ui.toggle(['No essentials listed','Essentials listed'], value='No essentials listed')

    with ui.tab_panel(t3):
        with ui.row().classes('items-stretch w-full'):
            with ui.card().classes('w-1/2'):
                ui.label('PV Performance & Margins').classes('text-lg font-semibold')
                psh   = number('PSH (sun hours)', 4.5, step=0.1, minv=2, maxv=7)
                prb   = number('Base PR', 0.78, step=0.01, minv=0.6, maxv=0.9)
                shade = number('Shading (%)', 0, step=1, minv=0, maxv=100)
                dust  = ui.select(['Low','Medium','Heavy'], value='Low', label='Dust level').props('outlined dense').classes('w-full')
                sev   = ui.select(['None','Storm','DustStorm','HeavyRain'], value='None', label='Severe event').props('outlined dense').classes('w-full')
                sf    = ui.select(['Rare','Seasonal','Often'], value='Seasonal', label='Event frequency').props('outlined dense').classes('w-full')
                selec = number('Electricity priority score (1–10)', 7, step=1, minv=1, maxv=10)
            with ui.card().classes('w-1/2'):
                ui.label('Site & Hardware').classes('text-lg font-semibold')
                aroof = number('Roof area (m²)', 120, step=10, minv=0)
                agnd  = number('Ground area (m²)', 0, step=10, minv=0)
                pdens = number('Power density (kWp/m²)', 0.19, step=0.01, minv=0.1, maxv=0.25)
                dcr   = number('DC/AC ratio', 1.2, step=0.05, minv=1.0, maxv=1.6)
                dod   = number('Battery DoD', 0.8, step=0.05, minv=0.5, maxv=0.95)
                eta   = number('System efficiency', 0.9, step=0.02, minv=0.7, maxv=1.0)

    with ui.tab_panel(t4):
        with ui.row().classes('items-stretch w-full'):
            with ui.card().classes('w-1/2'):
                ui.label('Carbon').classes('text-lg font-semibold')
                grid = ui.select(['Grid','Diesel'], value='Grid', label='Primary baseline').props('outlined dense').classes('w-full')
                efgr = number('EF grid (kgCO₂/kWh)', 0.6, step=0.05, minv=0.0)
                efd  = number('EF diesel (kgCO₂/kWh)', 0.8, step=0.05, minv=0.0)
                pco2 = number('Carbon price ($/tCO₂e)', 6.0, step=1, minv=0)

    with ui.tab_panel(t5):
        result_card = ui.card().classes('w-full')
        ui.separator()
        with ui.row():
            def run():
                data = Inputs(
                    E_bill_month_kwh=(bill.value or 0) or None,
                    N_day=int(nday.value or 0),
                    N_night=int(nnig.value or 0),
                    growth_pct=float(grow.value or 0),

                    W_month_liters=float(wmo.value or 0),
                    head_m=(float(head.value or 0) if float(head.value or 0) > 0 else None),
                    pump_eff=float(peff.value or 0.55),
                    P_pump_kw=float(pkw.value or 0.75),
                    S_water=int(swat.value or 7),
                    beta_water=float(bwat.value or 0.3),

                    outage_duration=outdur.value,
                    outage_time=outtod.value,
                    T_water_extra_h_max=float(twmax.value or 1.0),

                    essentials_listed=(ess.value == 'Essentials listed'),

                    PSH=float(psh.value or 4.5),
                    PR_base=float(prb.value or 0.78),
                    shading_pct=float(shade.value or 0.0),

                    dust_level=dust.value,
                    severe_event=sev.value,
                    severe_freq=sf.value,
                    S_elec=int(selec.value or 7),

                    A_roof_m2=float(aroof.value or 0),
                    A_ground_m2=float(agnd.value or 0),
                    PD_kwp_per_m2=float(pdens.value or 0.19),

                    DC_AC=float(dcr.value or 1.2),
                    DoD=float(dod.value or 0.8),
                    eta_sys=float(eta.value or 0.9),

                    grid_yes=(grid.value == 'Grid'),
                    EF_grid=float(efgr.value or 0.6),
                    EF_diesel=float(efd.value or 0.8),
                    p_CO2=float(pco2.value or 6.0),
                )
                results = plan(data)

                result_card.clear()
                with result_card:
                    ui.label('Results').classes('text-lg font-semibold')
                    ui.json_editor({'inputs': data.model_dump(), 'results': results}).classes('w-full h-96')

                    def dl_json():
                        ui.download(
                            data=json.dumps({'inputs': data.model_dump(), 'results': results}, indent=2).encode('utf-8'),
                            filename='solar_plan.json'
                        )

                    def dl_html():
                        html = render_report(data, results).encode('utf-8')
                        ui.download(data=html, filename='solar_plan.html')

                    with ui.row().classes('mt-2'):
                        ui.button('Download JSON', on_click=dl_json).props('outline')
                        ui.button('Download HTML report', on_click=dl_html).props('outline')

            ui.button('Run sizing', on_click=run).classes('bg-blue-600 text-white')

# ---- server start (Render provides PORT env var) ----
port = int(os.environ.get('PORT', '8080'))
ui.run(host='0.0.0.0', port=port, reload=False)  # reload False for production
