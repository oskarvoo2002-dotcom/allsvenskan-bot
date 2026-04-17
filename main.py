import telebot
import requests
from datetime import datetime
import re
import time
import os
from flask import Flask
from threading import Thread

# --- KEEP ALIVE SERVER (För Render) ---
app = Flask('')

@app.route('/')
def home():
    return "Boten pingar och är vaken!"

def run():
    port = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=port)

def keep_alive():
    t = Thread(target=run)
    t.daemon = True
    t.start()
# --------------------------------------

TELEGRAM_TOKEN = '8192692732:AAEDEbW9up1n_P_m6UC9VIDaDP09HTVckHk'
bot = telebot.TeleBot(TELEGRAM_TOKEN)

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
    'Accept': 'application/json, text/plain, */*',
    'Origin': 'https://www.sofascore.com',
    'Referer': 'https://www.sofascore.com/'
}
FLAT_UNIT = 1.5

def clean_val(v):
    try:
        v = re.sub(r'[^0-9.]', '', str(v).replace(',', '.'))
        return float(v) if v else 0
    except: return 0

# --- FUSKPAPPER: DIREKTA LAG-ID ---
def get_team_info(team_name):
    teams = {
        'malmö': (1888, 'Malmö FF'), 'mff': (1888, 'Malmö FF'),
        'aik': (1892, 'AIK'),
        'brommapojkarna': (1881, 'IF Brommapojkarna'), 'bp': (1881, 'IF Brommapojkarna'),
        'djurgården': (1883, 'Djurgårdens IF'), 'dif': (1883, 'Djurgårdens IF'),
        'hammarby': (1887, 'Hammarby IF'), 'bajen': (1887, 'Hammarby IF'),
        'elfsborg': (1885, 'IF Elfsborg'),
        'häcken': (1886, 'BK Häcken'), 'bkh': (1886, 'BK Häcken'),
        'halmstad': (1890, 'Halmstads BK'), 'hbk': (1890, 'Halmstads BK'),
        'värnamo': (6867, 'IFK Värnamo'),
        'göteborg': (1884, 'IFK Göteborg'), 'ifk göteborg': (1884, 'IFK Göteborg'), 'blåvitt': (1884, 'IFK Göteborg'),
        'sirius': (1916, 'IK Sirius'),
        'mjällby': (1902, 'Mjällby AIF'), 'maif': (1902, 'Mjällby AIF'),
        'västerås': (1896, 'Västerås SK'), 'vsk': (1896, 'Västerås SK'),
        'kalmar': (1891, 'Kalmar FF'), 'kff': (1891, 'Kalmar FF'),
        'gais': (1882, 'GAIS'),
        'norrköping': (1889, 'IFK Norrköping'), 'peking': (1889, 'IFK Norrköping')
    }
    return teams.get(team_name.lower().strip())

# --- FUNKTION 1: KORREKTA STATS ---
def get_basic_stats(team_name):
    try:
        info = get_team_info(team_name)
        if not info:
            return f"❌ Hittar inte '{team_name}'. Kolla stavningen eller använd vanliga smeknamn (t.ex. AIK, MFF, Bajen)."
        
        t_id, t_name = info
        events = requests.get(f"https://api.sofascore.com/api/v1/team/{t_id}/events/last/0", headers=HEADERS, timeout=10).json().get('events', [])
        
        match_log = []
        res = {
            'total': {'m':0,'f_s':0,'f_sot':0,'f_off':0,'a_s':0,'a_sot':0,'a_off':0},
            'home': {'m':0,'f_s':0,'f_sot':0,'f_off':0,'a_s':0,'a_sot':0,'a_off':0},
            'away': {'m':0,'f_s':0,'f_sot':0,'f_off':0,'a_s':0,'a_sot':0,'a_off':0}
        }
        
        # FIX: Ändrat till 2024 istället för 2026
        cutoff = datetime(2024, 1, 1).timestamp()

        for ev in events:
            if ev.get('tournament', {}).get('uniqueTournament', {}).get('id') != 40 or ev['startTimestamp'] < cutoff: continue
            
            m_res = requests.get(f"https://api.sofascore.com/api/v1/event/{ev['id']}/statistics", headers=HEADERS).json()
            stats_list = m_res.get('statistics', [])
            all_p = next((p for p in stats_list if p['period'] == 'ALL'), None)
            
            if all_p:
                is_h = ev['homeTeam']['id'] == t_id
                side, opp = ('home', 'away') if is_h else ('away', 'home')
                cat = 'home' if is_h else 'away'
                
                m_date = datetime.fromtimestamp(ev['startTimestamp']).strftime('%d/%m')
                match_log.append(f"• {m_date}: {ev['homeTeam']['name']} - {ev['awayTeam']['name']}")

                res['total']['m'] += 1
                res[cat]['m'] += 1
                
                seen = {'s': False, 'sot': False, 'off': False}

                for group in all_p['groups']:
                    for item in group['statisticsItems']:
                        n, v_my, v_opp = item['name'], clean_val(item.get(side,0)), clean_val(item.get(opp,0))
                        
                        if n == "Total shots" and not seen['s']:
                            for t in ['total', cat]: res[t]['f_s']+=v_my; res[t]['a_s']+=v_opp
                            seen['s'] = True
                        elif n == "Shots on target" and not seen['sot']:
                            for t in ['total', cat]: res[t]['f_sot']+=v_my; res[t]['a_sot']+=v_opp
                            seen['sot'] = True
                        elif n == "Offsides" and not seen['off']:
                            for t in ['total', cat]: res[t]['f_off']+=v_my; res[t]['a_off']+=v_opp
                            seen['off'] = True
        
        def fmt(d):
            m = d['m']
            if m == 0: return "_Ingen data funnen._\n"
            return (f"`🚀 Skott fram: {round(d['f_s']/m, 2)}` \n`🎯 På mål:    {round(d['f_sot']/m, 2)}` \n`🚩 Offsides:  {round(d['f_off']/m, 2)}` \n"
                    f"`-----------------------` \n`🛡️ Skott emot: {round(d['a_s']/m, 2)}` \n`🧤 På mål em: {round(d['a_sot']/m, 2)}` \n`🚩 Offs. em:  {round(d['a_off']/m, 2)}` \n")

        log_str = "\n".join(match_log[:5])
        return (f"🇸🇪 **{t_name.upper()} (ALLSVENSKAN 2024)**\n\n📅 **SENASTE MATCHER:**\n{log_str}\n\n📊 **TOTALT ({res['total']['m']} matcher)**\n{fmt(res['total'])}\n🏠 **HEMMA ({res['home']['m']})**\n{fmt(res['home'])}\n✈️ **BORTA ({res['away']['m']})**\n{fmt(res['away'])}")
    except Exception as e: return f"❌ Krasch! Felkod: {repr(e)}"

# --- FUNKTION 2: MATCH-STATS & UTRÄKNINGAR ---
def get_match_stats(team_name, is_home, mode):
    try:
        info = get_team_info(team_name)
        if not info: return None
        t_id, t_name = info

        events = requests.get(f"https://api.sofascore.com/api/v1/team/{t_id}/events/last/0", headers=HEADERS, timeout=10).json().get('events', [])

        stats = {'total_f': [], 'total_a': [], 'spec_f': [], 'spec_a': []}
        
        # FIX: Ändrat till 2024 istället för 2026
        cutoff = datetime(2024, 1, 1).timestamp()

        for ev in events:
            if ev.get('tournament', {}).get('uniqueTournament', {}).get('id') != 40 or ev['startTimestamp'] < cutoff: continue

            m_res = requests.get(f"https://api.sofascore.com/api/v1/event/{ev['id']}/statistics", headers=HEADERS, timeout=10).json()
            all_p = next((p for p in m_res.get('statistics', []) if p['period'] == 'ALL'), None)

            if all_p:
                current_is_home = ev['homeTeam']['id'] == t_id
                side, opp = ('home', 'away') if current_is_home else ('away', 'home')
                found = False
                for group in all_p['groups']:
                    for item in group['statisticsItems']:
                        n = item['name']
                        if (mode == "skott" and n == "Total shots") or (mode == "sot" and n == "Shots on target") or (mode == "offside" and n == "Offsides"):
                            val_f = clean_val(item.get(side, 0))
                            val_a = clean_val(item.get(opp, 0))
                            stats['total_f'].append(val_f)
                            stats['total_a'].append(val_a)
                            if current_is_home == is_home:
                                stats['spec_f'].append(val_f)
                                stats['spec_a'].append(val_a)
                            found = True
                            break
                    if found: break

        tot_f_avg = sum(stats['total_f'])/len(stats['total_f']) if stats['total_f'] else 0
        tot_a_avg = sum(stats['total_a'])/len(stats['total_a']) if stats['total_a'] else 0

        spec_f_avg = sum(stats['spec_f'])/len(stats['spec_f']) if stats['spec_f'] else tot_f_avg
        spec_a_avg = sum(stats['spec_a'])/len(stats['spec_a']) if stats['spec_a'] else tot_a_avg

        blended_f = (spec_f_avg + tot_f_avg) / 2
        blended_a = (spec_a_avg + tot_a_avg) / 2

        return {'name': t_name, 'offense': blended_f, 'defense': blended_a, 'using_fallback': not stats['spec_f']}
    except: return None

def handle_all(user_input):
    low_input = user_input.lower()

    if "-" in user_input and any(x in low_input for x in ["över", "under", "linan"]):
        try:
            match_part = re.split(r'över|under|linan', low_input)[0]
            teams = match_part.split('-')
            mode, label = ("offside", "Offside") if "offside" in low_input else (("sot", "Skott på mål") if any(x in low_input for x in ["mål", "target", "sot"]) else ("skott", "Skott"))

            parts = low_input.split()
            line = next((clean_val(parts[i+1]) for i, x in enumerate(parts) if x in ["över", "under", "linan"]), 0)
            odds = next((clean_val(parts[i+1]) for i, x in enumerate(parts) if x == "odds"), 0)
            is_over = "under" not in low_input

            home = get_match_stats(teams[0].strip(), True, mode)
            away = get_match_stats(teams[1].strip(), False, mode)

            if not home or not away:
                return "❌ Kunde inte hämta stats för något av lagen. Kolla stavningen!"

            exp_h = (home['offense'] + away['defense']) / 2
            exp_a = (away['offense'] + home['defense']) / 2

            target_scope = "TOTALT"
            after_line_text = low_input.split(str(line).replace('.0',''))[-1]

            if home['name'].lower() in after_line_text or teams[0].strip().lower() in after_line_text:
                target_scope = home['name'].upper()
                final_pred = exp_h
            elif away['name'].lower() in after_line_text or teams[1].strip().lower() in after_line_text:
                target_scope = away['name'].upper()
                final_pred = exp_a
            else:
                final_pred = exp_h + exp_a

            edge = (final_pred / line) - 1 if is_over else (line / final_pred) - 1

            res = (f"⚔️ **{home['name']} - {away['name']}**\n📊 {label.upper()} ({target_scope})\n\n"
                   f"🧮 **MATEMATIK (Hemma/Borta inbakat med Totalsnitt):**\n"
                   f"🔹 {home['name']}: {round(home['offense'],1)} (Off) + {round(away['defense'],1)} (Motst. Def) / 2 = {round(exp_h,1)}\n"
                   f"🔹 {away['name']}: {round(away['offense'],1)} (Off) + {round(home['defense'],1)} (Motst. Def) / 2 = {round(exp_a,1)}\n"
                   f"{'⚠️ *Använder endast totalsnitt (saknas H/B-data)*' if home['using_fallback'] or away['using_fallback'] else ''}\n\n"
                   f"📈 **RELEVANT SNITT: {round(final_pred, 2)}**\n---------------------------\n")

            if line > 0 and odds > 0:
                if edge < 0: res += f"❌ INGET VÄRDE på {line}."
                else:
                    u = 5.0 if edge > 1.0 else (FLAT_UNIT * 2.5 if edge > 0.4 else (FLAT_UNIT * 1.5 if edge > 0.2 else FLAT_UNIT))
                    res += f"💎 **VALUE!**\n📈 Edge: `+{round(edge*100, 1)}%` | Odds: `{odds}`\n💰 Insats: **{round(min(5.0, u), 1)} / 5 Units**"
            return res
        except: return "Skriv: `Hemma - Borta över 24.5 skott odds 1.85`"
    else:
        return get_basic_stats(user_input.strip())

@bot.message_handler(func=lambda m: True)
def h(m):
    bot.reply_to(m, handle_all(m.text), parse_mode='Markdown')

if __name__ == "__main__":
    keep_alive()
    bot.infinity_polling()
