import streamlit as st
import numpy as np
import pandas as pd

st.title("🔥 Chauffe ballon ECS – PAC limitée + bilan énergétique")

# -----------------------
# 📥 Entrées utilisateur
# -----------------------

st.sidebar.header("Paramètres échangeur")

U = st.sidebar.number_input("Coefficient U (W/m².K)", value=800.0)
S = st.sidebar.number_input("Surface serpentin (m²)", value=5.5)
T_depart = st.sidebar.number_input("Température départ PAC (°C)", value=62.0)
DeltaT_primaire = st.sidebar.number_input("Delta T primaire (°C)", value=7.0)

P_pac_max_kw = st.sidebar.number_input("Puissance PAC maximale (kW)", value=20.0)

st.sidebar.header("Paramètres ballon")

T_init = st.sidebar.number_input("Température initiale ballon (°C)", value=20.0)
T_consigne = st.sidebar.number_input("Température consigne ballon (°C)", value=55.0)
Volume = st.sidebar.number_input("Volume ballon (litres)", value=300.0)

dt = st.sidebar.number_input("Pas de temps (secondes)", value=10)

# -----------------------
# ⚙️ Constantes physiques
# -----------------------

rho = 1000        # kg/m3
cp = 4180         # J/kg/K
m_ballon = Volume / 1000 * rho
P_pac_max = P_pac_max_kw * 1000   # W

# -----------------------
# 🧮 Fonctions
# -----------------------

def calcul_echange(T_ballon):
    """
    Retourne :
    - Puissance réelle injectée (W)
    - Débit primaire (m3/h)
    - Température sortie serpentin (°C)
    - DeltaTlm (K)
    - Puissance théorique serpentin (W)
    """

    # Température sortie primaire imposée par deltaT PAC
    T_sortie = T_depart - DeltaT_primaire
    T_sortie = max(T_sortie, T_ballon)

    dT1 = T_depart - T_ballon
    dT2 = max(T_sortie - T_ballon, 0.01)

    if abs(dT1 - dT2) < 1e-6:
        DeltaT_lm = dT1
    else:
        DeltaT_lm = (dT1 - dT2) / np.log(dT1 / dT2)

    # Puissance échangeur théorique
    P_serpentin = U * S * DeltaT_lm   # W

    # Limitation par la PAC
    P_reelle = min(P_serpentin, P_pac_max)

    # Débit cohérent avec la puissance réelle
    m_dot = P_reelle / (cp * DeltaT_primaire)   # kg/s
    debit_m3_h = m_dot * 3600 / rho

    return P_reelle, debit_m3_h, T_sortie, DeltaT_lm, P_serpentin

# -----------------------
# ▶️ Simulation
# -----------------------

if st.button("▶️ Lancer la simulation"):

    T = T_init
    t = 0

    temps = []
    temperatures = []
    puissances = []
    puissances_serp = []
    debits = []

    while T < T_consigne and t < 6 * 3600:

        P, debit, T_sortie, DeltaT_lm, P_serp = calcul_echange(T)

        # Bilan énergétique ballon
        dT = (P * dt) / (m_ballon * cp)
        T = T + dT
        t = t + dt

        temps.append(t / 60)
        temperatures.append(T)
        puissances.append(P / 1000)
        puissances_serp.append(P_serp / 1000)
        debits.append(debit)

    df = pd.DataFrame({
        "Temps (min)": temps,
        "Température ballon (°C)": temperatures,
        "Puissance réelle (kW)": puissances,
        "Puissance serpentin théorique (kW)": puissances_serp,
        "Débit primaire (m3/h)": debits
    })

    st.success("Simulation terminée ✅")

    # -----------------------
    # 📈 Graphiques
    # -----------------------

    st.subheader("🌡️ Température ballon")
    st.line_chart(df.set_index("Temps (min)")["Température ballon (°C)"])

    st.subheader("⚡ Puissance : PAC vs serpentin")
    st.line_chart(
        df.set_index("Temps (min)")[
            ["Puissance réelle (kW)", "Puissance serpentin théorique (kW)"]
        ]
    )

    st.subheader("🚿 Débit primaire")
    st.line_chart(df.set_index("Temps (min)")["Débit primaire (m3/h)"])

    st.subheader("📊 Résultats détaillés")
    st.dataframe(df)
