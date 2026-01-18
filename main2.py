import streamlit as st
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

# Configuration
st.set_page_config(page_title="Simulateur ECS Physico-Technique", layout="wide")
st.title("🚀 Simulateur ECS : PAC + Chaudière (Modèle Physique Complet)")

# --- Constantes physiques ---
RHO_WATER = 1000 
CP_WATER = 4180  

def format_duration(seconds):
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    return f"{hours}h {minutes:02d}min"

# --- Barre latérale (Sidebar) ---
with st.sidebar:
    st.header("⚡ Pompe à Chaleur (PAC)")
    P_pac_nom = st.number_input("Puissance Nominale PAC (kW)", 1.0, 50.0, 15.0)
    T_prim = st.number_input("T° Primaire PAC (°C)", 30.0, 80.0, 70.0)
    cop_moyen = st.slider("COP moyen", 1.5, 5.0, 3.0, 0.1)
    t_delay_min = st.number_input("Temps montée en T° (min)", 0, 15, 3)
    t_anti_cycle_min = st.number_input("Arrêt mini anti-court-cycle (min)", 0, 30, 10)
    
    st.header("🌀 Échangeur (Serpentin)")
    S_serpentin = st.number_input("Surface d'échange (m²)", 0.1, 15.0, 3.5)
    U_coef = st.number_input("Coeff. d'échange U (W/m².K)", 100, 2000, 600)
    us_global = S_serpentin * U_coef

    st.header("🔥 Chaudière d'appoint")
    P_chaud = st.number_input("Puissance Chaudière (kW)", 0.0, 100.0, 50.0)
    t_secours_min = st.slider("Délai secours (min)", 0, 90, 20)

    st.header("🌡️ Ballon & Pertes")
    V_ball = st.number_input("Volume ballon (L)", 100, 5000, 1000)
    ua_ballon = st.number_input("Déperdition Cuve UA (W/K)", 0.1, 10.0, 1.5)
    P_bouclage_kW = st.number_input("Pertes bouclage (kW)", 0.0, 5.0, 0.5)
    T_amb = st.number_input("T° Ambiante local (°C)", 0.0, 40.0, 15.0)
    
    st.header("🚿 Consignes")
    T_cons = st.number_input("T° Consigne (°C)", 40.0, 65.0, 60.0)
    dT_restart = st.number_input("Delta T redémarrage (°C)", 1.0, 15.0, 5.0)
    T_init = st.number_input("T° initiale (°C)", 5.0, 65.0, 55.0)
    T_eau_froide = st.number_input("T° Eau froide (°C)", 5.0, 25.0, 10.0)

    dt = st.number_input("Pas de temps (s)", 1, 60, 10)

# --- Profil de Consommation ---
st.subheader("📅 Profil de consommation journalier")
c1, c2 = st.columns([1, 2])
with c1:
    v_total_jour = st.number_input("Volume total jour (L)", 10, 10000, 1500)
    default_ratios = [0,0,0,0,0,0,10,15,10,5,2,2,3,2,2,2,3,5,10,15,10,4,0,0]
    df_profil = pd.DataFrame({"Heure": [f"{h}h" for h in range(24)], "Répartition (%)": default_ratios})
    edited_df = st.data_editor(df_profil, hide_index=True, width='stretch')
    hour_volumes = (edited_df["Répartition (%)"].values / 100) * v_total_jour

# --- Simulation ---
t_steps = int((1440 * 60) / dt)
time_array = np.arange(0, t_steps * dt, dt)
T = np.zeros_like(time_array, dtype=float)
P_pac_eff, P_chaud_eff, P_tirage_array = [np.zeros_like(time_array) for _ in range(3)]
P_pertes_cuve = np.zeros_like(time_array)
T[0] = T_init

pac_state = "OFF"
wait_timer, chauffe_timer, time_since_stop = 0.0, 0.0, 9999.0

for i in range(1, len(time_array)):
    Ti = T[i-1]
    curr_hour = int((time_array[i] / 3600) % 24)
    p_tirage = (hour_volumes[curr_hour] / 3600) * CP_WATER * (60 - T_eau_froide)
    P_tirage_array[i] = p_tirage

    p_pac_inst, p_chaud_inst = 0.0, 0.0

    if pac_state == "OFF":
        time_since_stop += dt
        if Ti <= (T_cons - dT_restart) and time_since_stop >= (t_anti_cycle_min * 60):
            pac_state = "STARTING"
            wait_timer, chauffe_timer = 0.0, 0.0
    
    elif pac_state == "STARTING":
        wait_timer += dt
        chauffe_timer += dt
        if chauffe_timer > (t_secours_min * 60): p_chaud_inst = P_chaud * 1000
        if wait_timer >= (t_delay_min * 60): pac_state = "HEATING"
            
    elif pac_state == "HEATING":
        if Ti >= T_cons or T_prim <= (Ti + 0.1):
            pac_state = "OFF"
            time_since_stop, chauffe_timer = 0.0, 0.0
        else:
            p_echange_max = us_global * (T_prim - Ti)
            p_pac_inst = max(0, min(P_pac_nom * 1000, p_echange_max))
            chauffe_timer += dt
            if chauffe_timer > (t_secours_min * 60): p_chaud_inst = P_chaud * 1000

    P_pac_eff[i], P_chaud_eff[i] = p_pac_inst, p_chaud_inst
    P_pertes_cuve[i] = ua_ballon * (Ti - T_amb)
    p_pertes_tot = P_pertes_cuve[i] + (P_bouclage_kW * 1000)
    
    dT_step = (p_pac_inst + p_chaud_inst - p_pertes_tot - p_tirage) * dt / ((V_ball/1000 * RHO_WATER) * CP_WATER)
    T[i] = max(T_eau_froide, Ti + dT_step)

# --- Graphiques ---
df_res = pd.DataFrame({"h": time_array/3600, "T": T, "P_pac": P_pac_eff/1000, "P_chaud": P_chaud_eff/1000, "P_tirage": P_tirage_array/1000})
with c2:
    fig1, (ax1, ax2) = plt.subplots(2, 1, figsize=(10, 7), sharex=True, gridspec_kw={'height_ratios': [3, 1]})
    ax1.plot(df_res["h"], df_res["T"], color="#007bff", lw=2, label="T° Ballon")
    ax1.axhline(T_cons, color="red", ls="--", label="Consigne")
    ax1.set_ylabel("Température (°C)")
    ax1.legend()
    ax2.stackplot(df_res["h"], df_res["P_pac"], df_res["P_chaud"], labels=['PAC', 'Chaudière'], colors=['#4CAF50', '#FF5722'], alpha=0.7)
    ax2.set_ylabel("Puissance (kW)")
    ax2.legend(loc='upper right')
    st.pyplot(fig1)

# --- Bilan Énergétique Complet ---
st.divider()
st.subheader("📊 Bilan Énergétique Consolidé (24h)")

# Calculs énergétiques (kWh)
e_th_pac = np.sum(P_pac_eff * dt) / 3600000
e_elec_pac = e_th_pac / cop_moyen
e_th_chaud = np.sum(P_chaud_eff * dt) / 3600000
e_enr = e_th_pac - e_elec_pac
e_utile = np.sum(P_tirage_array * dt) / 3600000
e_pertes_cuve = np.sum(P_pertes_cuve * dt) / 3600000
e_pertes_bouclage = (P_bouclage_kW * 24)
e_pertes_totales = e_pertes_cuve + e_pertes_bouclage
e_total_genere = e_th_pac + e_th_chaud

# Tableau récapitulatif
data_bilan = {
    "Poste": ["Génération PAC (Thermique)", "Génération Chaudière", "Énergie Gratuite (ENR)", "Consommation Élec PAC", "Besoins Tirage (Utile)", "Pertes Cuve (Statiques)", "Pertes Bouclage"],
    "Énergie (kWh)": [f"{e_th_pac:.2f}", f"{e_th_chaud:.2f}", f"{e_enr:.2f}", f"{e_elec_pac:.2f}", f"{e_utile:.2f}", f"{e_pertes_cuve:.2f}", f"{e_pertes_bouclage:.2f}"],
    "Part (%)": [f"{(e_th_pac/e_total_genere*100):.1f}%" if e_total_genere>0 else "-", 
                 f"{(e_th_chaud/e_total_genere*100):.1f}%" if e_total_genere>0 else "-", 
                 "-", "-", 
                 f"{(e_utile/e_total_genere*100):.1f}%" if e_total_genere>0 else "-", 
                 f"{(e_pertes_cuve/e_total_genere*100):.1f}%" if e_total_genere>0 else "-", 
                 f"{(e_pertes_bouclage/e_total_genere*100):.1f}%" if e_total_genere>0 else "-"]
}
df_bilan = pd.DataFrame(data_bilan)

col_tab, col_pie = st.columns([2, 1])
with col_tab:
    st.table(df_bilan)

with col_pie:
    fig2, ax_pie = plt.subplots()
    ax_pie.pie([e_enr, e_elec_pac, e_th_chaud], labels=['Gratuit (Air)', 'Achat Élec', 'Chaudière'], 
                autopct='%1.1f%%', colors=['#4CAF50', '#FFC107', '#FF5722'], startangle=90)
    st.pyplot(fig2)

# --- Indicateurs de performance ---
st.write("**Indicateurs de fonctionnement :**")
i1, i2, i3, i4 = st.columns(4)
i1.metric("Rendement Global (COP sys)", f"{(e_total_genere/(e_elec_pac+e_th_chaud)):.2f}" if (e_elec_pac+e_th_chaud)>0 else "0")
i2.metric("Temps de marche PAC", format_duration(np.sum(P_pac_eff > 0) * dt))
i3.metric("Temps de marche Chaudière", format_duration(np.sum(P_chaud_eff > 0) * dt))
i4.metric("Démarrages PAC", len([i for i in range(1, len(P_pac_eff)) if P_pac_eff[i] > 0 and P_pac_eff[i-1] == 0]))