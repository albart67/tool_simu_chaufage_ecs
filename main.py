import streamlit as st
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from datetime import time

# Configuration
st.set_page_config(page_title="Simulateur ECS Hybride", layout="wide")
st.title("Simulateur ECS : PAC + Chaudière (Bilan Complet & Temps de chauffe)")

# --- Constantes physiques ---
RHO_WATER = 1000 
CP_WATER = 4180  

def format_duration(seconds):
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    return f"{hours}h {minutes:02d}min"

# --- Barre latérale (Sidebar) ---
with st.sidebar:
    st.header("⚡ Paramètres PAC")
    P_pac_th = st.number_input("Puissance THERMIQUE PAC (kW)", 1.0, 50.0, 15.0)
    T_prim = st.number_input("T° Primaire PAC (°C)", 30.0, 80.0, 70.0)
    cop_moyen = st.slider("COP moyen de la PAC", 1.5, 5.0, 2.0, 0.1)
    t_delay_min = st.number_input("Temps montée en T° / démarrage (min)", 0, 15, 3)
    t_anti_cycle_min = st.number_input("Arrêt minimum anti-court-cycle (min)", 0, 30, 10)
    
    st.header("🔥 Chaudière d'appoint")
    P_chaud = st.number_input("Puissance Chaudière (kW)", 0.0, 100.0, 50.0)
    t_secours_min = st.slider("Délai avant secours chaudière (min)", 0, 90, 15, help="Ce délai inclut le temps de montée en température de la PAC")

    st.header("🌡️ Déperditions & Volume")
    V_ball = st.number_input("Volume ballon (L)", 100, 5000, 900)
    ua_ballon = st.number_input("Déperdition Cuve UA (W/K)", 0.1, 10.0, 1.0)
    P_bouclage_kW = st.number_input("Pertes bouclage (kW)", 0.0, 10.0, 0.5)
    T_amb = st.number_input("T° Ambiante local (°C)", 0.0, 40.0, 15.0)

    st.header("🚿 Consignes")
    T_cons = st.number_input("T° Consigne (°C)", 40.0, 65.0, 60.0)
    dT_restart = st.number_input("Delta T redémarrage (°C)", 1.0, 15.0, 7.0)
    T_init = st.number_input("T° initiale (°C)", 5.0, 65.0, 55.0)
    T_eau_froide = st.number_input("T° Eau froide (°C)", 5.0, 25.0, 10.0)

    dt = st.number_input("Pas de temps de calcul (s)", 1, 60, 10)

# --- Profil de Consommation ---
st.subheader("📅 Profil de consommation journalier (24h)")
c1, c2 = st.columns([1, 2])
with c1:
    v_total_jour = st.number_input("Besoin journalier total à 60°C (Litres)", 10, 10000, 1000)
    default_ratios = [0,0,0,0,0,0,10,15,10,5,2,2,3,2,2,2,3,5,10,15,10,4,0,0]
    df_profil = pd.DataFrame({"Heure": [f"{h}h" for h in range(24)], "Répartition (%)": default_ratios})
    
    edited_df = st.data_editor(df_profil, hide_index=True, width='stretch')
    
    ratios = edited_df["Répartition (%)"].values / 100
    hour_volumes = ratios * v_total_jour

# --- Simulation ---
t_max_min = 1440
t_steps = int((t_max_min * 60) / dt)
time_array = np.arange(0, t_steps * dt, dt)

T = np.zeros_like(time_array, dtype=float)
P_pac_active_th = np.zeros_like(time_array, dtype=float)
P_chaud_active = np.zeros_like(time_array, dtype=float)
P_tirage_array = np.zeros_like(time_array, dtype=float)
T[0] = T_init

pac_state = "OFF"
wait_timer = 0.0
chauffe_timer = 0.0
time_since_last_stop = 9999.0 

for i in range(1, len(time_array)):
    Ti = T[i-1]
    curr_hour = int((time_array[i] / 3600) % 24)
    vol_h = hour_volumes[curr_hour]
    # Calcul du tirage (énergie extraite du ballon)
    p_tirage = (vol_h / 3600) * CP_WATER * (60 - T_eau_froide)
    P_tirage_array[i] = p_tirage

    p_pac_inst = 0.0
    p_chaud_inst = 0.0

    if pac_state == "OFF":
        time_since_last_stop += dt
        if Ti <= (T_cons - dT_restart):
            if time_since_last_stop >= (t_anti_cycle_min * 60):
                pac_state = "STARTING" # Phase de montée en température
                wait_timer = 0.0
                chauffe_timer = 0.0

    elif pac_state == "STARTING":
        wait_timer += dt
        chauffe_timer += dt # Le chrono chaudière tourne déjà pendant la montée en T°
        
        # Enclenchement de la chaudière si le secours est court
        if chauffe_timer > (t_secours_min * 60):
            p_chaud_inst = P_chaud * 1000
            
        if wait_timer >= (t_delay_min * 60):
            pac_state = "HEATING"

    elif pac_state == "HEATING":
        if Ti >= T_cons or T_prim <= Ti:
            pac_state = "OFF"
            time_since_last_stop = 0.0
            chauffe_timer = 0.0
        else:
            p_pac_inst = P_pac_th * 1000
            chauffe_timer += dt
            if chauffe_timer > (t_secours_min * 60):
                p_chaud_inst = P_chaud * 1000

    P_pac_active_th[i] = p_pac_inst
    P_chaud_active[i] = p_chaud_inst

    # Bilan énergétique du pas de temps
    p_pertes = (ua_ballon * (Ti - T_amb)) + (P_bouclage_kW * 1000)
    m_ball = (V_ball/1000 * RHO_WATER)
    dT_step = (p_pac_inst + p_chaud_inst - p_pertes - p_tirage) * dt / (m_ball * CP_WATER)
    T[i] = max(T_eau_froide, Ti + dT_step)

# --- Graphiques ---
df_res = pd.DataFrame({"h": time_array/3600, "T": T, "P_pac_th": P_pac_active_th/1000, "P_chaud": P_chaud_active/1000, "P_tirage": P_tirage_array/1000})
with c2:
    fig1, (ax1, ax2) = plt.subplots(2, 1, figsize=(10, 8), sharex=True, gridspec_kw={'height_ratios': [3, 1]})
    ax1.plot(df_res["h"], df_res["T"], color="#007bff", lw=2, label="T° Ballon")
    ax1.axhline(T_cons, color="red", ls="-", alpha=0.6, label="Consigne")
    ax1.axhline(T_cons - dT_restart, color="orange", ls="--", alpha=0.8, label="Seuil Relance")
    ax1.set_ylabel("Température (°C)")
    ax1.grid(True, alpha=0.2)
    ax1.legend()

    ax2.stackplot(df_res["h"], df_res["P_pac_th"], df_res["P_chaud"], labels=['PAC (Th)', 'Chaudière'], colors=['#ffa500', '#ff4500'], alpha=0.6)
    ax2.plot(df_res["h"], df_res["P_tirage"], color="blue", lw=1, label="Tirage")
    ax2.set_xlim(0, 24)
    ax2.set_xticks(range(0, 25, 2))
    ax2.set_ylabel("Puissance (kW)")
    ax2.legend(loc='upper right', fontsize='small')
    st.pyplot(fig1)

# --- Bilan d'Exploitation ---
st.divider()
st.subheader("📊 Bilan Énergétique & Technique Complet")

e_th_pac = np.sum(P_pac_active_th * dt) / 3600000
e_elec_pac = e_th_pac / cop_moyen
e_th_chaud = np.sum(P_chaud_active * dt) / 3600000
e_total_produite = e_th_pac + e_th_chaud
e_enr = e_th_pac - e_elec_pac

e_utile_tirage = np.sum(P_tirage_array * dt) / 3600000
e_bouclage_kwh = P_bouclage_kW * 24
e_pertes_statiques = np.sum((ua_ballon * (T - T_amb)) * dt) / 3600000
e_besoin_total = e_utile_tirage + e_bouclage_kwh + e_pertes_statiques

demarrages = len([i for i in range(1, len(P_pac_active_th)) if P_pac_active_th[i] > 0 and P_pac_active_th[i-1] == 0])

m1, m2, m3, m4 = st.columns(4)
m1.metric("Production Totale", f"{e_total_produite:.2f} kWh")
m2.metric("Besoin Global", f"{e_besoin_total:.2f} kWh")
m3.metric("Nombre Démarrages PAC", f"{demarrages}")

col_a, col_b, col_c = st.columns([1, 1, 1])
with col_a:
    st.write("**📡 Bilan Pompe à Chaleur**")
    st.metric("P. Thermique Fournie", f"{e_th_pac:.2f} kWh_th")
    st.metric("P. Élec Consommée", f"{e_elec_pac:.2f} kWh_elec")
    st.write(f"Temps de marche PAC : **{format_duration(np.sum(P_pac_active_th > 0) * dt)}**")

with col_b:
    st.write("**🔥 Bilan Chaudière**")
    st.metric("Apport Chaudière", f"{e_th_chaud:.2f} kWh")
    st.write(f"Temps de marche Chaud. : **{format_duration(np.sum(P_chaud_active > 0) * dt)}**")
    part_chaud = (e_th_chaud/e_total_produite*100 if e_total_produite>0 else 0)
    st.write(f"Part Chaudière : {part_chaud:.1f} %")

with col_c:
    st.write("**📉 Détail des Besoins**")
    st.write(f"- Tirage ECS utile : {e_utile_tirage:.2f} kWh")
    st.write(f"- Pertes Bouclage : {e_bouclage_kwh:.2f} kWh")
    st.write(f"- Pertes Cuve : {e_pertes_statiques:.2f} kWh")
    st.metric("Énergie Gratuite (EnR)", f"{e_enr:.2f} kWh")

# --- Camembert ---
if e_total_produite > 0:
    st.write("---")
    st.write("**Répartition du bilan énergétique**")
    fig2, ax_pie = plt.subplots(figsize=(4, 3))
    ax_pie.pie([e_enr, e_elec_pac, e_th_chaud], 
                labels=['ENR Gratuit', 'Consommation Elec PAC', 'Consommation Chaudière'], 
                autopct='%1.1f%%', colors=['#4CAF50', '#FFC107', '#FF5722'], startangle=90)
    st.pyplot(fig2)

if demarrages / 24 > 3:
    st.error(f"⚠️ Risque de court-cycle ({demarrages/24:.1f} cycles/h).")