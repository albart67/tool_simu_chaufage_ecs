import streamlit as st
import numpy as np
import matplotlib.pyplot as plt

# =========================================================
# CONSTANTES
# =========================================================
cp = 4180        # J/kg/K
rho = 1000       # kg/m3

# =========================================================
# ΔT LOGARITHMIQUE MOYEN STABLE
# =========================================================
def delta_T_lm_stable(ΔT1, ΔT2):
    eps = 1e-6
    ΔT1 = max(ΔT1, eps)
    ΔT2 = max(ΔT2, eps)

    if abs(ΔT1 - ΔT2) < 1e-3:
        return ΔT1  # limite mathématique
    return (ΔT1 - ΔT2) / np.log(ΔT1 / ΔT2)

# =========================================================
# INTERFACE
# =========================================================
st.title("🔥 Simulation chauffe ballon ECS – PAC + serpentin")

st.sidebar.header("🔧 PAC")
P_pac_max_kw = st.sidebar.number_input("Puissance PAC max (kW)", 2.0, 20.0, 6.0, 0.5)
delta_depart = st.sidebar.number_input("ΔT départ PAC au-dessus ballon (°C)", 3.0, 20.0, 10.0, 0.5)
delta_hyd = st.sidebar.number_input("ΔT hydraulique cible (°C)", 5.0, 10.0, 7.0, 0.5)

st.sidebar.header("🌀 Serpentin")
A_serp = st.sidebar.number_input("Surface serpentin (m²)", 1.0, 10.0, 5.5, 0.1)
U = st.sidebar.number_input("Coefficient U (W/m²·K)", 300.0, 1200.0, 600.0, 50.0)

st.sidebar.header("🛢️ Ballon")
volume = st.sidebar.number_input("Volume ballon (L)", 200, 3000, 1000, 50)
T_init = st.sidebar.number_input("Température initiale ballon (°C)", 5.0, 30.0, 10.0, 1.0)
T_consigne = st.sidebar.number_input("Consigne ballon (°C)", 40.0, 65.0, 60.0, 1.0)

dt = 10  # s

# =========================================================
# CONVERSIONS
# =========================================================
P_pac_max = P_pac_max_kw * 1000
UA = U * A_serp
masse_ballon = volume / 1000 * rho

# Température départ PAC MAX (PAC ne suit pas indéfiniment le ballon)
T_depart_max = T_consigne + delta_depart

# =========================================================
# INITIALISATION
# =========================================================
T_ballon = T_init
temps = 0

temps_list = []
T_list = []
P_list = []
P_serp_list = []

# =========================================================
# SIMULATION
# =========================================================
while T_ballon < T_consigne:
    # Température départ PAC plafonnée
    T_depart = min(T_ballon + delta_depart, T_depart_max)
    T_retour = T_depart - delta_hyd

    # Puissance PAC disponible (inverter simplifié)
    facteur_modulation = max(0.3, (T_consigne - T_ballon) / (T_consigne - T_init))
    P_pac = P_pac_max * facteur_modulation

    # Débit régulé par la PAC
    m_dot = P_pac / (cp * delta_hyd)

    # ΔTlm
    ΔT1 = T_depart - T_ballon
    ΔT2 = T_retour - T_ballon
    ΔT_lm = delta_T_lm_stable(ΔT1, ΔT2)

    # Limitation serpentin
    P_serp_max = UA * ΔT_lm

    # Puissance réellement échangée
    P_echange = min(P_pac, P_serp_max)

    # Évolution ballon
    dT = P_echange * dt / (masse_ballon * cp)
    T_ballon += dT

    # Stockage
    temps_list.append(temps / 60)
    T_list.append(T_ballon)
    P_list.append(P_echange)
    P_serp_list.append(P_serp_max)

    temps += dt
    if temps > 8 * 3600:
        break

# =========================================================
# GRAPHIQUE
# =========================================================
fig, ax = plt.subplots()
ax.plot(temps_list, T_list, label="Température ballon")
ax.set_xlabel("Temps (min)")
ax.set_ylabel("Température (°C)")
ax.set_title("Montée en température du ballon ECS")
ax.grid(True)
ax.legend()
st.pyplot(fig)

# =========================================================
# BILAN ÉNERGÉTIQUE
# =========================================================
temps_h = temps / 3600
energie_kWh = np.trapz(P_list, dx=dt) / 3.6e6

st.subheader("📊 Bilan énergétique")

st.write(f"⏱️ Temps de chauffe : **{temps_h:.2f} h**")
st.write(f"⚡ Énergie consommée : **{energie_kWh:.2f} kWh**")

st.write(f"🔌 Puissance PAC max : **{P_pac_max:.0f} W**")
st.write(f"🌀 UA serpentin : **{UA:.0f} W/K**")
st.write(f"📐 Surface serpentin : **{A_serp:.2f} m²**")
st.write(f"🌡️ Coefficient U : **{U:.0f} W/m²·K**")

if min(P_serp_list) < P_pac_max:
    st.warning("⚠️ En fin de chauffe, la PAC est limitée par le serpentin")
else:
    st.success("✅ Le serpentin n'est jamais limitant")

st.write(f"💧 Débit primaire moyen : **{np.mean(P_list)/(cp*delta_hyd)*3600/rho:.2f} m³/h**")
