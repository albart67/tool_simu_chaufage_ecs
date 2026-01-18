import streamlit as st
import numpy as np

st.set_page_config(page_title="Dimensionnement Serpentin PAC", layout="centered")

st.title("🔥 Calcul échange serpentin PAC")

st.markdown("Saisie des paramètres :")

# --- Entrées utilisateur ---
col1, col2 = st.columns(2)

with col1:
    delta_T = st.number_input("ΔT primaire souhaité (K)", 1.0, 20.0, 7.0, step=0.5)
    T_depart = st.number_input("Température départ PAC (°C)", 30.0, 90.0, 70.0)
    T_ballon = st.number_input("Température ballon (°C)", 10.0, 80.0, 55.0)

with col2:
    surface = st.number_input("Surface serpentin (m²)", 0.5, 20.0, 4.0, step=0.1)
    U = st.number_input("Coefficient U (W/m²/K)", 100.0, 3000.0, 800.0, step=50.0)

Cp = 4180  # J/kg/K
rho = 1000 # kg/m3

# --- Calculs ---
T_sortie = T_depart - delta_T

DT1 = T_depart - T_ballon
DT2 = T_sortie - T_ballon

if DT1 <= 0 or DT2 <= 0:
    st.error("⚠️ Les températures ne permettent pas d'échange thermique (ΔT <= 0).")
else:
    # Delta T logarithmique
    DTlm = (DT1 - DT2) / np.log(DT1 / DT2)

    # Puissance échangée
    P = U * surface * DTlm   # Watts

    # Débit nécessaire
    m_dot = P / (Cp * delta_T)  # kg/s
    Q_m3_h = m_dot * 3600 / rho

    # --- Affichage résultats ---
    st.divider()
    st.subheader("📊 Résultats")

    col3, col4 = st.columns(2)

    with col3:
        st.metric("Puissance échangée", f"{P/1000:.1f} kW")
        st.metric("ΔT logarithmique", f"{DTlm:.2f} K")

    with col4:
        st.metric("Débit primaire nécessaire", f"{Q_m3_h:.2f} m³/h")
        st.metric("Température retour PAC", f"{T_sortie:.1f} °C")

    st.info("💡 La puissance réelle sera limitée par la PAC si P dépasse sa puissance nominale.")
