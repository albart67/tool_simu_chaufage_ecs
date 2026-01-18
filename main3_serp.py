import streamlit as st
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

# Configuration
st.set_page_config(page_title="Simulateur ECS Hybride Expert", layout="wide")
st.title("🚀 Simulateur ECS : PAC + Chaudière (Modèle Serpentin)")

# --- Constantes physiques ---
RHO_WATER = 1000 
CP_WATER = 4180  

def format_duration(seconds):
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    return f"{hours}h {minutes:02d}min"

# --- Barre latérale ---
with st.sidebar:
    st.header("🏗️ Échangeur (Serpentin)")
    S_serpentin = st.number_input("Surface du serpentin (m²)", 0.1, 15.0, 2.5)
    K_echange = st.number_input("Coeff. d'échange K (W/m²·K)", 100, 2000, 600)
    
    st.header("⚡ Pompe à Chaleur")
    P_pac_nom = st.number_input("P. Nominale PAC (kW)", 1.0, 50.0, 15.0)
    T_prim = st.number_input("T° Primaire PAC (°C)", 30.0, 85.0, 65.0)
    cop_moyen = st.slider("COP moyen PAC", 1.5, 5.0, 3.0, 0.1)
    t_delay_min = st.number_input("Délai démarrage PAC (min)", 0, 15, 3)
    t_anti_cycle_min = st.number_input("Arrêt mini (min)", 0, 30, 10)
    
    st.header("🔥 Appoint Chaudière")
    P_chaud_nom = st.number_input("P. Nominale Chaudière (kW)", 0.0, 100.0, 25.0)
    t_secours_min = st.slider("Temporisation secours (min)", 0, 120, 20)

    st.header("🌡️ Ballon & Pertes")
    V_ball = st.number_input("Volume (L)", 100, 5000, 1000)
    ua_ballon = st.number_input("Pertes Cuve (UA en W/K)", 0.1, 10.0, 1.5)
    P_bouclage_kW = st.number_input("Pertes Bouclage (kW)", 0.0, 5.0, 0.4)
    T_amb = st.number_input("T° Local (°C)", 0.0, 40.0, 15.0)

    st.header("🚿 Consignes")
    T_cons = st.number_input("Consigne ECS (°C)", 40.0, 70.0, 60.0)
    dT_restart = st.number_input("DeltaT Relance (°C)", 1.0, 15.0, 5.0)
    T_init = st.number_input("T° initiale (°C)", 5.0, 70.0, 50.0)
    T_eau_froide = st.number_input("T° Eau froide (°C)", 5.0, 25.0, 10.0)
    dt = st.number_input("Pas de temps (s)", 1, 60, 10)

# --- Profil de Consommation (Tableau de répartition) ---
st.subheader("📅 Profil de consommation journalier")
col_tirage, col_graph = st.columns([1, 2])

with col_tirage:
    v_total_jour = st.number_input("Volume journalier total (L à 60°C)", 100, 10000, 1500)
    default_ratios = [0,0,0,0,0,0,10,15,10,5,2,2,3,2,2,2,3,5,10,15,10,4,0,0]
    df_profil = pd.DataFrame({
        "Heure": [f"{h}h" for h in range(24)], 
        "Répartition (%)": default_ratios
    })
    # LE TABLEAU DE RÉPARTITION DES SOUTIRAGES
    edited_df = st.data_editor(df_profil, hide_index=True, use_container_width=True)
    hour_volumes = (edited_df["Répartition (%)"].values / 100) * v_total_jour

# --- Simulation ---
t_steps = int((1440 * 60) / dt)
time_array = np.arange(0, t_steps * dt, dt)
T = np.zeros(t_steps)
P_pac_act = np.zeros(t_steps)
P_chaud_act = np.zeros(t_steps)
P_tirage_act = np.zeros(t_steps)
T[0] = T_init

pac_state = "OFF"
wait_timer, chauffe_timer, time_since_stop = 0.0, 0.0, 9999.0

for i in range(1, t_steps):
    Ti = T[i-1]
    curr_h = int((time_array[i] / 3600) % 24)
    # Calcul du tirage
    p_tirage = (hour_volumes[curr_h] / 3600) * CP_WATER * (60 - T_eau_froide)
    P_tirage_act[i] = p_tirage
    
    p_pac, p_chaud = 0.0, 0.0

    # Logique d'état PAC / Chaudière
    if pac_state == "OFF":
        time_since_stop += dt
        if Ti <= (T_cons - dT_restart) and time_since_stop >= (t_anti_cycle_min * 60):
            pac_state = "STARTING"
            wait_timer, chauffe_timer = 0.0, 0.0
    elif pac_state == "STARTING":
        wait_timer += dt
        chauffe_timer += dt
        if wait_timer >= (t_delay_min * 60): pac_state = "HEATING"
        if chauffe_timer > (t_secours_min * 60):
            p_e_max = max(0, K_echange * S_serpentin * (T_prim - Ti))
            p_chaud = min(P_chaud_nom * 1000, p_e_max)
    elif pac_state == "HEATING":
        if Ti >= T_cons or Ti >= T_prim - 0.5:
            pac_state = "OFF"
            time_since_stop = 0.0
        else:
            p_e_max = max(0, K_echange * S_serpentin * (T_prim - Ti))
            p_pac = min(P_pac_nom * 1000, p_e_max)
            chauffe_timer += dt
            if chauffe_timer > (t_secours_min * 60):
                p_chaud = min(P_chaud_nom * 1000, max(0, p_e_max - p_pac))

    # Bilan énergétique du pas de temps
    p_pertes = (ua_ballon * (Ti - T_amb)) + (P_bouclage_kW * 1000)
    m_ball = (V_ball/1000 * RHO_WATER)
    dT_step = (p_pac + p_chaud - p_pertes - p_tirage) * dt / (m_ball * CP_WATER)
    T[i] = max(T_eau_froide, Ti + dT_step)
    P_pac_act[i], P_chaud_act[i] = p_pac, p_chaud

# --- Graphiques ---
with col_graph:
    fig1, (ax1, ax2) = plt.subplots(2, 1, figsize=(10, 8), sharex=True)
    ax1.plot(time_array/3600, T, color='#007bff', lw=2, label="Température Ballon")
    ax1.axhline(T_cons, color='red', ls='--', alpha=0.5, label="Consigne")
    ax1.set_ylabel("Température (°C)")
    ax1.legend()
    ax1.grid(True, alpha=0.2)

    ax2.stackplot(time_array/3600, P_pac_act/1000, P_chaud_act/1000, 
                  labels=["Puissance PAC", "Puissance Chaudière"], 
                  colors=['#ffa500', '#ff4500'], alpha=0.7)
    ax2.plot(time_array/3600, P_tirage_act/1000, color='black', lw=1, label="Tirage (Demande)")
    ax2.set_ylabel("Puissance (kW)")
    ax2.set_xlabel("Heures de la journée")
    ax2.set_xlim(0, 24)
    ax2.legend(loc='upper right')
    ax2.grid(True, alpha=0.2)
    st.pyplot(fig1)

# --- BILANS ---
st.divider()
st.subheader("📊 Bilan Énergétique Récapitulatif")

e_th_pac = np.sum(P_pac_act * dt) / 3600000
e_elec_pac = e_th_pac / cop_moyen
e_enr = e_th_pac - e_elec_pac
e_th_chaud = np.sum(P_chaud_act * dt) / 3600000
e_total_gen = e_th_pac + e_th_chaud

e_utile = np.sum(P_tirage_act * dt) / 3600000
e_pertes_statiques = np.sum((ua_ballon * (T - T_amb)) * dt) / 3600000
e_pertes_bouclage = (P_bouclage_kW * 24)

c1, c2, c3 = st.columns(3)
with c1:
    st.metric("Production Totale", f"{e_total_gen:.2f} kWh")
    st.write(f"PAC : {e_th_pac:.2f} kWh_th")
    st.write(f"Chaudière : {e_th_chaud:.2f} kWh_th")

with c2:
    st.metric("Besoins ECS + Pertes", f"{(e_utile + e_pertes_statiques + e_pertes_bouclage):.2f} kWh")
    st.write(f"Utile soutirage : {e_utile:.2f} kWh")
    st.write(f"Pertes (Bouclage+Cuve) : {(e_pertes_statiques + e_pertes_bouclage):.2f} kWh")

with c3:
    cop_sys = e_utile / (e_elec_pac + e_th_chaud) if (e_elec_pac + e_th_chaud) > 0 else 0
    st.metric("COP Système Global", f"{cop_sys:.2f}")
    st.write(f"Temps de marche PAC : {format_duration(np.sum(P_pac_act > 0) * dt)}")

# --- Camembert ---
if e_total_gen > 0:
    st.write("### Répartition de l'énergie finale consommée")
    fig2, ax_pie = plt.subplots(figsize=(5, 4))
    ax_pie.pie([e_enr, e_elec_pac, e_th_chaud], 
                labels=['EnR (Air)', 'Élec PAC', 'Chaudière'], 
                autopct='%1.1f%%', colors=['#4CAF50', '#FFC107', '#FF5722'], 
                startangle=90, pctdistance=0.85)
    centre_circle = plt.Circle((0,0),0.70,fc='white')
    fig2.gca().add_artist(centre_circle)
    st.pyplot(fig2)