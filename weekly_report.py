#!/usr/bin/env python3
"""
ICA Weekly Marketing Report
Runs via GitHub Actions every Sunday at 7pm EST
"""

import ssl, certifi, json, urllib.request, urllib.parse, random, os
from datetime import datetime, timedelta

SLACK_TOKEN     = os.environ["SLACK_TOKEN"]
SLACK_CHANNEL   = "marketing-channel"
HYROS_KEY       = os.environ["HYROS_KEY"]
WJ_KEY          = os.environ["WJ_KEY"]
WJ_WEBINAR      = "22"
META_TOKEN      = os.environ["META_TOKEN"]
META_ACCOUNT    = os.environ["META_ACCOUNT"]
CLARITY_TOKEN   = os.environ["CLARITY_TOKEN"]
CLARITY_PROJECT = os.environ["CLARITY_PROJECT"]

GREETINGS = [
    "Hey everyone! Hope you all had an amazing week 🙌",
    "Hey team! Hope all is well — here's your weekly update 📊",
    "Good Sunday everyone! Another week, another report 💪",
    "Hey fam! Wishing you all a great week ahead — let's check the numbers!",
    "Happy Sunday team! Hope everyone is recharging well ⚡",
    "Hey everyone! Hope the week treated you well — here's where we stand:",
    "Good evening team! Wrapping up another week — let's see how we did 🔥",
    "Hey all! Hope you're enjoying your Sunday — quick update from the week:",
    "What's up team! Another week in the books — here's the breakdown 📈",
    "Hey everyone! Grateful for another great week — here are the numbers:",
    "Happy Sunday fam! Let's take a look at how this week went 👀",
    "Hey team! Hope you're all doing well — weekly numbers are in 🎯",
    "Good evening everyone! Time for our weekly check-in — let's go!",
    "Hey all! Another week of hard work — here's what the data says 💡",
    "Happy Sunday team! Hope you're all resting up — here's your weekly report 🚀",
]

ctx    = ssl.create_default_context(cafile=certifi.where())
opener = urllib.request.build_opener(urllib.request.HTTPSHandler(context=ctx))
today     = datetime.now()
yesterday = today - timedelta(days=1)
week_ago  = today - timedelta(days=7)
two_weeks = today - timedelta(days=14)

def fetch(url, headers={}):
    req = urllib.request.Request(url, headers=headers)
    return json.loads(opener.open(req, timeout=15).read().decode())

def post_form(url, params):
    data = urllib.parse.urlencode(params).encode()
    return json.loads(opener.open(urllib.request.Request(url, data=data), timeout=15).read().decode())

def change(curr, prev):
    if not prev or prev == 0: return "N/A", ""
    pct = round((curr - prev) / abs(prev) * 100, 1)
    if pct > 0:   return f"+{pct}%", "↑"
    elif pct < 0: return f"{pct}%", "↓"
    return "0%", "→"

def row(label, curr, prev, fmt="{}"):
    pct, arrow = change(curr, prev)
    return f"  • {label}: {fmt.format(curr)} (prev: {fmt.format(prev)} {arrow} {pct})"

def get_meta(start, end):
    try:
        url  = (f"https://graph.facebook.com/v19.0/act_{META_ACCOUNT}/insights"
                f"?fields=spend,impressions,clicks,cpm,ctr,actions,cost_per_action_type"
                f'&time_range={{"since":"{start}","until":"{end}"}}'
                f"&access_token={META_TOKEN}")
        data = fetch(url).get("data", [{}])[0]
        spend  = float(data.get("spend", 0))
        impr   = int(data.get("impressions", 0))
        cpm    = round(float(data.get("cpm", 0)), 2)
        ctr    = round(float(data.get("ctr", 0)), 2)
        acts   = {a["action_type"]: float(a["value"]) for a in data.get("actions", [])}
        leads  = int(acts.get("lead", acts.get("onsite_web_lead", 0)))
        lp     = int(acts.get("landing_page_view", 0))
        clicks = int(acts.get("link_click", int(data.get("clicks", 0))))
        cpa    = {a["action_type"]: float(a["value"]) for a in data.get("cost_per_action_type", [])}
        cpl    = round(cpa.get("lead", cpa.get("onsite_web_lead", spend / leads if leads else 0)), 2)
        return {"spend": spend, "impressions": impr, "clicks": clicks, "cpm": cpm, "ctr": ctr, "leads": leads, "cpl": cpl, "lp_views": lp}
    except Exception as e:
        return {"error": str(e)}

def get_hyros(start, end):
    try:
        leads = fetch(f"https://api.hyros.com/v1/api/v1.0/leads?startDate={start}&endDate={end}&limit=100", {"API-Key": HYROS_KEY}).get("result", [])
        sales = fetch(f"https://api.hyros.com/v1/api/v1.0/sales?startDate={start}&endDate={end}&limit=100", {"API-Key": HYROS_KEY}).get("result", [])
        sql   = sum(1 for l in leads if any("sql" in t for t in l.get("tags", [])))
        nql   = sum(1 for l in leads if any("nql" in t for t in l.get("tags", [])))
        return {"leads": len(leads), "sql": sql, "nql": nql, "sales": len(sales)}
    except Exception as e:
        return {"error": str(e)}

def get_webinar(since):
    try:
        d     = post_form("https://api.webinarjam.com/webinarjam/registrants", {"api_key": WJ_KEY, "webinar_id": WJ_WEBINAR, "page": 1})
        regs  = d["registrants"]["data"]
        total = d["registrants"]["total"]
        new_regs = []
        for r in regs:
            try:
                if datetime.strptime(r["signup_date"], "%a, %d %b %Y, %I:%M %p") >= since:
                    new_regs.append(r)
            except: pass
        attended  = sum(1 for r in new_regs if r["attended_live"] == "Yes")
        replay    = sum(1 for r in new_regs if r["attended_replay"] == "Yes")
        no_show   = sum(1 for r in new_regs if r["attended_live"] == "No" and r["attended_replay"] == "No")
        show_rate = round((attended + replay) / len(new_regs) * 100, 1) if new_regs else 0
        return {"total": total, "new": len(new_regs), "attended": attended, "replay": replay, "no_show": no_show, "show_rate": show_rate}
    except:
        return None

def get_clarity():
    try:
        data    = fetch(f"https://www.clarity.ms/export-data/api/v1/project-live-insights?projectId={CLARITY_PROJECT}",
                        {"Authorization": f"Bearer {CLARITY_TOKEN}"})
        metrics = {m["metricName"]: m["information"][0] for m in data if m.get("information")}
        return {
            "sessions":      int(metrics.get("Traffic", {}).get("totalSessionCount", 0)),
            "users":         int(metrics.get("Traffic", {}).get("distinctUserCount", 0)),
            "pages_session": round(float(metrics.get("Traffic", {}).get("pagesPerSessionPercentage", 0)), 2),
            "scroll_depth":  round(float(metrics.get("ScrollDepth", {}).get("averageScrollDepth", 0)), 1),
            "dead_clicks":   round(float(metrics.get("DeadClickCount", {}).get("sessionsWithMetricPercentage", 0)), 1),
            "rage_clicks":   round(float(metrics.get("RageClickCount", {}).get("sessionsWithMetricPercentage", 0)), 1),
            "quickback":     round(float(metrics.get("QuickbackClick", {}).get("sessionsWithMetricPercentage", 0)), 1),
        }
    except Exception as e:
        return {"error": str(e)}

if __name__ == "__main__":
    s_this = week_ago.strftime("%Y-%m-%d")
    e_this = yesterday.strftime("%Y-%m-%d")
    s_prev = two_weeks.strftime("%Y-%m-%d")
    e_prev = week_ago.strftime("%Y-%m-%d")

    m  = get_meta(s_this, e_this)
    h  = get_hyros(s_this, e_this)
    w  = get_webinar(week_ago)
    c  = get_clarity()
    mp = get_meta(s_prev, e_prev)
    hp = get_hyros(s_prev, e_prev)
    wp = get_webinar(two_weeks)

    this_week = f"{week_ago.strftime('%b %d')} – {yesterday.strftime('%b %d')}"
    prev_week = f"{two_weeks.strftime('%b %d')} – {week_ago.strftime('%b %d')}"

    lines = [
        f"📊 Weekly Marketing Report",
        f"_This week: {this_week}  |  Previous week: {prev_week}_",
        "",
        "*📣 Meta Ads Performance*", "",
    ]

    if "error" not in m:
        lines += [
            row("Ad Spend",           m['spend'],      mp.get('spend',0),      "${:,.2f}"),
            row("Impressions",        m['impressions'], mp.get('impressions',0), "{:,}"),
            row("Link Clicks",        m['clicks'],     mp.get('clicks',0),     "{:,}"),
            row("CTR",                m['ctr'],        mp.get('ctr',0),        "{:.2f}%"),
            row("CPM",                m['cpm'],        mp.get('cpm',0),        "${:.2f}"),
            row("Landing Page Views", m['lp_views'],   mp.get('lp_views',0),   "{:,}"),
            row("Leads (Meta)",       m['leads'],      mp.get('leads',0),      "{:,}"),
            row("Cost Per Lead",      m['cpl'],        mp.get('cpl',0),        "${:.2f}"),
        ]
    else:
        lines.append(f"  ⚠️  Could not load Meta data")

    lines += ["", "*👥 Leads & Sales (Hyros)*", ""]
    if "error" not in h:
        hyros_cpl = round(m['spend'] / h['leads'], 2) if h.get('leads') and "error" not in m else 0
        prev_cpl  = round(mp.get('spend', 0) / hp.get('leads', 1), 2) if hp.get('leads') else 0
        lines += [
            row("Leads Tracked",   h['leads'],  hp.get('leads',0),  "{:,}"),
            row("Qualified (SQL)", h['sql'],    hp.get('sql',0),    "{:,}"),
            row("Not Qualified",   h['nql'],    hp.get('nql',0),    "{:,}"),
            row("Cost Per Lead",   hyros_cpl,   prev_cpl,           "${:.2f}"),
            row("Sales Closed",    h['sales'],  hp.get('sales',0),  "{:,}"),
            f"  • Lead→Sale Rate: {round(h['sales']/h['leads']*100,1) if h['leads'] else 0}%",
        ]
    else:
        lines.append("  ⚠️  Could not load Hyros data")

    if w:
        lines += ["", "*🎤  Webinar — AI x Amazon*", ""]
        lines += [
            row("New Registrants", w['new'],       wp['new'] if wp else 0,       "{:,}"),
            row("Attended Live",   w['attended'],  wp['attended'] if wp else 0,  "{:,}"),
            row("Watched Replay",  w['replay'],    wp['replay'] if wp else 0,    "{:,}"),
            row("Show-up Rate",    w['show_rate'], wp['show_rate'] if wp else 0, "{:.1f}%"),
            row("No Show",         w['no_show'],   wp['no_show'] if wp else 0,   "{:,}"),
            f"  • Total All-Time Registrants: {w['total']:,}",
        ]

    lines += ["", "*🖥️  Landing Page Behavior (Clarity)*", ""]
    if "error" not in c:
        dead_flag  = "⚠️ " if c['dead_clicks'] > 5 else "✅"
        rage_flag  = "⚠️ " if c['rage_clicks'] > 3 else "✅"
        quick_flag = "⚠️ " if c['quickback'] > 5 else "✅"
        lines += [
            f"  • Sessions: {c['sessions']:,}  |  Unique Visitors: {c['users']:,}",
            f"  • Pages per Session: {c['pages_session']}",
            f"  • Avg Scroll Depth: {c['scroll_depth']}%",
            f"  • Dead Clicks: {dead_flag} {c['dead_clicks']}% of sessions",
            f"  • Rage Clicks: {rage_flag} {c['rage_clicks']}% of sessions",
            f"  • Quick Bounces: {quick_flag} {c['quickback']}% of sessions",
        ]
        insights = []
        if c['scroll_depth'] > 75:
            insights.append("✅ Visitors reading deep — content is engaging")
        elif c['scroll_depth'] < 50:
            insights.append("⚠️  Low scroll depth — visitors dropping off early")
        if c['dead_clicks'] > 5:
            insights.append("⚠️  High dead clicks — something looks clickable but isn't")
        if c['rage_clicks'] > 3:
            insights.append("⚠️  Rage clicks — possible broken element or frustration")
        if insights:
            lines += [""] + insights
    else:
        lines.append("  ⚠️  Could not load Clarity data")

    lines += ["", f"_Generated {today.strftime('%A, %B %d %Y at %I:%M %p EST')}_"]

    report = random.choice(GREETINGS) + "\n\n" + "\n".join(lines)
    print(report)

    payload = json.dumps({"channel": SLACK_CHANNEL, "text": report, "mrkdwn": True}).encode()
    req = urllib.request.Request("https://slack.com/api/chat.postMessage", data=payload,
          headers={"Authorization": f"Bearer {SLACK_TOKEN}", "Content-Type": "application/json"})
    r = json.loads(opener.open(req).read().decode())
    print("✅ Posted to Slack!" if r.get("ok") else f"❌ {r.get('error')}")
