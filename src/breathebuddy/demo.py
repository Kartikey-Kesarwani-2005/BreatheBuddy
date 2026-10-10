"""Command-line demo: exercises every acceptance criterion and prints results.

    python -m breathebuddy.demo
"""
from __future__ import annotations

from . import agent as agent_mod
from .service import aqi_query, bootstrap, route_query, run_cycle, school_today
from .store import STORE


def line(title: str) -> None:
    print("\n" + "=" * 68)
    print(title)
    print("=" * 68)


def main() -> None:
    bootstrap()
    line("1. INGEST + NOWCAST + ALERTS  (pipeline cycle)")
    cycle = run_cycle()
    print(f"ingested stations : {cycle['ingest']['ingested']}")
    print(f"grid cells        : {cycle['grid_cells']}")
    print(f"school alerts     : {len(cycle['school_alerts'])}")
    for a in cycle["school_alerts"]:
        print(f"   - [{a['kind']}] {a['message']}")
    print(f"subscriber alerts : {len(cycle['subscriber_alerts'])}")
    for a in cycle["subscriber_alerts"]:
        print(f"   - {a['target']}: {a['message']}")

    line("2. HYPERLOCAL AQI QUERY")
    nc = aqi_query(28.6129, 77.2295)
    print(f"AQI now={nc['aqi_now']} ({nc['category']})  clean_index={nc['clean_index']}")
    print(f"6h forecast: {nc['aqi_forecast']}")

    line("3. CLEANEST vs FASTEST ROUTE")
    res = route_query((28.6000, 77.1000), (28.6000, 77.3000))
    for mode in ("fastest", "cleanest"):
        r = res[mode]
        print(f"{mode:8s}: {r['distance_m']:.0f} m, avg AQI {r['avg_aqi']}, "
              f"clean-index {r['clean_index']}, {r['duration_min']} min")
    print(f"winner={res['winner']}  {res['note']}")

    line("4. CEDAR SCHOOL POLICY -> 'Today at your school'")
    for sid in STORE.schools:
        card = school_today(sid)
        print(f"\n{card['school']['name']}  (AQI {card['aqi_now']}, {card['status']})")
        print(f"  headline : {card['headline']}")
        print(f"  allowed  : {card['allowed']}")
        print(f"  blocked  : {card['blocked']}")
        dec = card["decisions"]["hold_outdoor_assembly"]
        print(f"  cedar outdoor_assembly -> allowed={dec['allowed']} ({dec['reason']})")

    line("5. STRANDS AGENT (deterministic fallback if SDK absent)")
    q = "Should Mater Dei School hold outdoor assembly at 8am tomorrow?"
    ans = agent_mod.ask(q, prefer_strands=False)
    print(f"Q: {q}")
    print(f"A: {ans['answer']}")
    for s in ans["steps"]:
        print(f"   - {s}")


if __name__ == "__main__":
    main()
