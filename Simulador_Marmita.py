import streamlit as st
import streamlit.components.v1 as components
import pandas as pd
import time
import requests
from datetime import datetime

# ==========================================
# 1. CONFIGURACIÓN DEL SISTEMA Y API
# ==========================================
POWER_BI_URL = "https://api.powerbi.com/beta/cbc2c381-2f2e-4d93-91d1-506c9316ace7/datasets/ccbd2ba0-336f-4cdc-b478-9e2398efc114/rows?experience=power-bi&clientSideAuth=0&key=A%2FgUPAJw6SQrGOeFO3lPI3sIDWoMzTa%2F%2FpPD5zUwpByzUAWihgH%2FX6%2FZ4NvUiyF3s0RirNAQ0Ku7BRiQLpKjug%3D%3D"

st.set_page_config(page_title="SCADA Marmita", page_icon="🏭", layout="wide")

st.markdown("""
<style>
    .stApp { background-color: #1E1E1E; color: #ECF0F1; font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;}
    .hmi-panel { background-color: #2C3E50; padding: 20px; border-radius: 8px; border-top: 5px solid #E67E22; box-shadow: 0 4px 8px rgba(0,0,0,0.3); margin-bottom: 20px;}
    .lcd-screen { background-color: #000000; color: #2ECC71; font-family: 'Courier New', monospace; font-size: 20px; font-weight: bold; padding: 10px; border-radius: 5px; text-align: center; border: 2px solid #7F8C8D;}
    .alert-text { color: #E74C3C; font-weight: bold; }
    h1, h2, h3, h4 { color: #F39C12; }
    .stNumberInput > div > div > input { background-color: #34495E; color: white; }
</style>
""", unsafe_allow_html=True)

# ==========================================
# 2. VARIABLES DEL RETO (FUNDAMENTOS)
# ==========================================
# Teoría Eléctrica: V = 24V, I = 20mA (0.02A) -> R = 1200 Ohms
VOLTAJE_PLC = 24.0 
CORRIENTE_OBJETIVO = 0.02 
R_IDEAL = VOLTAJE_PLC / CORRIENTE_OBJETIVO 

# Teoría Mecánica: Torque = F x d -> 150N x 0.4m = 60 Nm
FUERZA_MOTOR = 150.0 
RADIO_AGITADOR = 0.4 
TORQUE_IDEAL = FUERZA_MOTOR * RADIO_AGITADOR

# ==========================================
# 3. MEMORIA RAM (st.session_state)
# ==========================================
if 'grupo' not in st.session_state: st.session_state.grupo = ""
if 'resistencia' not in st.session_state: st.session_state.resistencia = 0.0
if 'torque' not in st.session_state: st.session_state.torque = 0.0
if 'calibrado' not in st.session_state: st.session_state.calibrado = False

# Variables de Operación
if 'tiempo_min' not in st.session_state: st.session_state.tiempo_min = 0
if 'temp_real' not in st.session_state: st.session_state.temp_real = 25.0
if 'valvula_vapor' not in st.session_state: st.session_state.valvula_vapor = 0
if 'historial_t' not in st.session_state: st.session_state.historial_t = [25.0]
if 'lote_terminado' not in st.session_state: st.session_state.lote_terminado = False
if 'falla_critica' not in st.session_state: st.session_state.falla_critica = "Ninguna"

def reset_lote():
    st.session_state.tiempo_min = 0
    st.session_state.temp_real = 25.0
    st.session_state.valvula_vapor = 0
    st.session_state.historial_t = [25.0]
    st.session_state.lote_terminado = False
    st.session_state.falla_critica = "Ninguna"

# ==========================================
# 4. MOTOR GRÁFICO SVG (SCADA HMI)
# ==========================================
def render_marmita_hmi(temp_hmi, vapor_pct, rpm_motor, falla):
    # Animaciones y colores
    color_salsa = "#E67E22" if temp_hmi < 95 else "#A04000" # Se oscurece si se quema
    color_camisa = "#E74C3C" if vapor_pct > 50 else ("#F39C12" if vapor_pct > 0 else "#BDC3C7")
    giro = "spin 1s linear infinite" if rpm_motor > 0 else "none"
    burbujas = '<g style="animation: rise 1s infinite;"><circle cx="150" cy="180" r="10" fill="#FAD7A1" opacity="0.6"/><circle cx="130" cy="200" r="15" fill="#FAD7A1" opacity="0.6"/></g>' if temp_hmi > 85 else ""

    alerta_ui = f'<rect x="20" y="340" width="360" height="40" fill="#E74C3C" rx="5"/><text x="200" y="365" text-anchor="middle" font-family="Arial" font-weight="bold" fill="white">⚠️ {falla.upper()}</text>' if falla != "Ninguna" else ""

    html = f"""<!DOCTYPE html><html><head><style>
        body {{ margin: 0; display: flex; justify-content: center; background: #1E1E1E; font-family: 'Courier New', monospace; }}
        @keyframes spin {{ 100% {{ transform: rotate(360deg); }} }}
        @keyframes rise {{ 0% {{ transform: translateY(0) scale(1); opacity:0.8;}} 100% {{ transform: translateY(-30px) scale(1.5); opacity:0;}} }}
    </style></head><body>
    <svg viewBox="0 0 400 400" width="100%" height="400">
        <path d="M 30,100 L 90,100 L 90,150" fill="none" stroke="#95A5A6" stroke-width="8"/>
        <circle cx="60" cy="100" r="15" fill="#C0392B"/>
        <text x="60" y="80" text-anchor="middle" font-size="12" fill="white" font-family="Arial">VAPOR {vapor_pct}%</text>
        
        <path d="M 90,120 L 90,280 A 60 60 0 0 0 210,280 L 210,120 Z" fill="{color_camisa}" stroke="#34495E" stroke-width="4"/>
        
        <path d="M 100,120 L 100,275 A 50 50 0 0 0 200,275 L 200,120 Z" fill="#FDFEFE" stroke="#2C3E50" stroke-width="2"/>
        <path d="M 102,170 L 102,275 A 48 48 0 0 0 198,275 L 198,170 Z" fill="{color_salsa}"/>
        {burbujas}
        
        <rect x="130" y="50" width="40" height="50" fill="#2980B9" stroke="#1ABC9C" stroke-width="2" rx="5"/>
        <rect x="145" y="100" width="10" height="150" fill="#7F8C8D"/>
        <g style="transform-box: fill-box; transform-origin: center; animation: {giro};">
            <path d="M 115,240 L 185,240 L 185,260 L 115,260 Z" fill="#34495E"/>
        </g>
        
        <rect x="250" y="120" width="130" height="80" fill="#000" rx="5" stroke="#7F8C8D" stroke-width="2"/>
        <text x="260" y="145" font-size="14" fill="#2ECC71">TT-101 (Temp)</text>
        <text x="260" y="170" font-size="22" font-weight="bold" fill="#2ECC71">{temp_hmi:.1f} °C</text>
        
        <rect x="250" y="210" width="130" height="60" fill="#000" rx="5" stroke="#7F8C8D" stroke-width="2"/>
        <text x="260" y="235" font-size="14" fill="#3498DB">MT-101 (RPM)</text>
        <text x="260" y="255" font-size="20" font-weight="bold" fill="#3498DB">{rpm_motor} RPM</text>
        
        {alerta_ui}
    </svg>
    </body></html>"""
    return html

# ==========================================
# 5. SIDEBAR: IDENTIFICACIÓN
# ==========================================
st.sidebar.image("https://upload.wikimedia.org/wikipedia/commons/thumb/8/83/Sena_Colombia_logo.svg/200px-Sena_Colombia_logo.svg.png", width=100)
st.sidebar.markdown("### 📋 Ingreso de Cuadrilla")

if not st.session_state.grupo:
    nom = st.sidebar.text_input("Nombres de los Operadores:")
    if st.sidebar.button("Autenticar Operador", type="primary"):
        st.session_state.grupo = nom
        st.rerun()
    st.stop()

st.sidebar.success(f"**🟢 Operador Activo:**\n{st.session_state.grupo}")
if st.sidebar.button("🔄 Reiniciar Planta Completa"):
    st.session_state.clear()
    st.rerun()

st.title("🏭 SCADA Avanzado: Planta de Salsas")

# ==========================================
# 6. ESTRUCTURA DE PESTAÑAS
# ==========================================
tab1, tab2, tab3 = st.tabs(["⚙️ 1. Mantenimiento y Calibración", "🎛️ 2. Operación del HMI", "📊 3. Reporte Power BI"])

# ---------------------------------------------------------
# PESTAÑA 1: FUNDAMENTOS Y MECÁNICA (CALIBRACIÓN)
# ---------------------------------------------------------
with tab1:
    st.markdown("### Área de Ingeniería y Mantenimiento")
    st.info("💡 **Instrucción:** Antes de operar la Marmita, debe calibrar los instrumentos usando las leyes físicas vistas en clase.")
    
    col_e, col_m = st.columns(2)
    
    with col_e:
        st.markdown("""<div class="hmi-panel">
        <h4>⚡ Calibración Eléctrica (PT100)</h4>
        <p>El transmisor de temperatura envía una señal de corriente al PLC. El PLC opera con una fuente de <b>24 Voltios</b>. Para que la pantalla HMI muestre la temperatura real sin errores, la corriente circulante en el lazo debe ser exactamente de <b>20 mA (0.02 A)</b>.</p>
        <hr>
        <p><i>Aplique la Ley de Ohm (V = I * R) para calcular qué resistencia (shunt) debe instalar en la bornera:</i></p>
        </div>""", unsafe_allow_html=True)
        
        r_input = st.number_input("Resistencia a Instalar (Ohmios - Ω):", min_value=0.0, step=10.0, value=st.session_state.resistencia)
        
    with col_m:
        st.markdown("""<div class="hmi-panel">
        <h4>⚙️ Calibración Mecánica (Agitador)</h4>
        <p>La salsa es un fluido no newtoniano de alta densidad. Los cálculos de fluidos indican que las aspas ejercen una fuerza de resistencia de <b>150 Newtons</b>. El radio del eje del agitador es de <b>0.4 metros</b>.</p>
        <hr>
        <p><i>Calcule el Torque o Par Mecánico (τ = F * d) necesario para programar el límite en el variador de frecuencia del motor:</i></p>
        </div>""", unsafe_allow_html=True)
        
        t_input = st.number_input("Torque en Variador (Newton-Metro - Nm):", min_value=0.0, step=1.0, value=st.session_state.torque)
        
    if st.button("💾 Guardar Calibración en el PLC", use_container_width=True, type="primary"):
        st.session_state.resistencia = r_input
        st.session_state.torque = t_input
        st.session_state.calibrado = True
        st.success("✅ Parámetros guardados en el PLC. Proceda a la pestaña de Operación.")

# ---------------------------------------------------------
# PESTAÑA 2: OPERACIÓN EN VIVO (SCADA)
# ---------------------------------------------------------
with tab2:
    if not st.session_state.calibrado:
        st.warning("⚠️ El PLC está bloqueado. Debe realizar la calibración en la Pestaña 1 primero.")
    else:
        st.markdown("### Lazo de Control de Cocción")
        
        # --- LÓGICA DE TRAMPAS DE CALIBRACIÓN ---
        # 1. Trampa Eléctrica (El HMI miente si la resistencia está mal)
        if st.session_state.resistencia <= 0:
            temp_hmi = 0.0
        else:
            # Si R es 1200 -> Multiplicador = 1.0 (HMI muestra Temp Real)
            # Si R es menor (ej 600) -> Muestra el doble (El operador la bajará y dejará la salsa cruda)
            factor_error = R_IDEAL / st.session_state.resistencia 
            temp_hmi = st.session_state.temp_real * factor_error

        # 2. Trampa Mecánica (El motor falla si el torque está mal)
        rpm_motor = 60 # Default RPM
        falla_activa = st.session_state.falla_critica
        
        if st.session_state.torque < (TORQUE_IDEAL - 5):
            rpm_motor = 0
            if st.session_state.tiempo_min > 0: falla_activa = "Atasco Motor: Mezcla no homogénea"
        elif st.session_state.torque > (TORQUE_IDEAL + 15):
            rpm_motor = 0
            if st.session_state.tiempo_min > 0: falla_activa = "Rotura de Reductor por Sobretorque"

        col_c, col_v = st.columns([1, 1.5])
        
        with col_c:
            st.markdown("<div class='hmi-panel'>", unsafe_allow_html=True)
            st.markdown("**Panel del Operador**")
            vapor = st.slider("Apertura Válvula de Vapor (%)", 0, 100, st.session_state.valvula_vapor, step=10)
            
            st.markdown(f"<div class='lcd-screen'>Tiempo: {st.session_state.tiempo_min} / 30 Min</div><br>", unsafe_allow_html=True)
            
            if st.session_state.tiempo_min < 30 and not st.session_state.lote_terminado:
                if st.button("⏱️ Avanzar 5 Minutos", type="primary", use_container_width=True):
                    st.session_state.valvula_vapor = vapor
                    
                    # Física Térmica de la Marmita (La temperatura real)
                    dT = (vapor * 0.5) - ((st.session_state.temp_real - 25.0) * 0.1)
                    st.session_state.temp_real += dT
                    st.session_state.temp_real = max(25.0, st.session_state.temp_real)
                    st.session_state.tiempo_min += 5
                    
                    # Evaluación de quemado real (independiente de lo que diga el HMI)
                    if st.session_state.temp_real > 105.0:
                        falla_activa = "Salsa Quemada por Sobretemperatura"
                        
                    st.session_state.falla_critica = falla_activa
                    st.rerun()
            else:
                if st.button("⏹️ Finalizar Lote y Evaluar Calidad", use_container_width=True):
                    st.session_state.lote_terminado = True
                    st.rerun()
                    
            st.markdown("</div>", unsafe_allow_html=True)
            
            if st.session_state.lote_terminado:
                st.info("Lote finalizado. Diríjase a la Pestaña 3 para enviar los datos a Gerencia (Power BI).")

        with col_v:
            components.html(render_marmita_hmi(temp_hmi, vapor, rpm_motor, falla_activa), height=420)
            
            if st.session_state.tiempo_min > 0:
                st.caption("*Nota: El Display HMI muestra la temperatura basada en la calibración eléctrica. La realidad del tanque podría ser distinta.*")

# ---------------------------------------------------------
# PESTAÑA 3: REPORTE GERENCIAL (POWER BI)
# ---------------------------------------------------------
with tab3:
    st.markdown("### 📊 Extrapolación a Turno de Producción")
    
    if not st.session_state.lote_terminado:
        st.warning("Debe completar los 30 minutos de operación del lote en la Pestaña 2.")
    else:
        st.markdown("El comportamiento de su lote piloto ha sido analizado y extrapolado a un turno completo de 10 Lotes.")
        
        # --- LÓGICA DE CALIDAD Y FINANZAS ---
        # Si la temp real no estuvo entre 85 y 100 al final, o hubo falla de motor, el lote es malo.
        lotes_producidos = 10
        falla = st.session_state.falla_critica
        
        if falla == "Ninguna":
            if st.session_state.temp_real < 80.0:
                falla = "Salsa Cruda (Temperatura Real Baja)"
            elif st.session_state.temp_real > 105.0:
                falla = "Salsa Quemada (Temperatura Real Alta)"
                
        if falla != "Ninguna":
            lotes_defectuosos = 10  # Si configuraron mal el equipo, arruinan todo el turno
        else:
            # Margen de error por variabilidad normal
            lotes_defectuosos = random.choice([0, 0, 1]) 
            
        oee = ((lotes_producidos - lotes_defectuosos) / lotes_producidos) * 100
        
        ingresos = (lotes_producidos - lotes_defectuosos) * 5000000 
        penalidad = lotes_defectuosos * 2000000 
        rentabilidad = ingresos - penalidad
        
        col1, col2, col3 = st.columns(3)
        col1.metric("OEE (Eficiencia Global)", f"{oee:.1f} %", f"{-lotes_defectuosos} Defectos")
        col2.metric("Rentabilidad Neta", f"${rentabilidad:,.0f} COP", f"-${penalidad:,.0f} COP" if penalidad>0 else "Óptimo", delta_color="inverse")
        col3.metric("Falla Crítica de Turno", falla)
        
        if falla != "Ninguna":
            st.error("💡 **Retroalimentación Técnica:** Su lote piloto falló. Revise si calculó correctamente la resistencia (1200 Ω) y el Torque (60 Nm). Si sus cálculos estaban bien, asegúrese de haber controlado la válvula de vapor para mantener la temperatura HMI alrededor de 90°C.")
            
        st.markdown("---")
        if st.button("📡 ENVIAR DATOS A POWER BI", type="primary"):
            timestamp_actual = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%S.000Z")
            
            # Formato exacto requerido por el usuario
            payload = [{
                "Grupo": str(st.session_state.grupo),
                "Calibracion_Temperatura_Ohm": float(st.session_state.resistencia),
                "Calibracion_Torque_Nm": float(st.session_state.torque),
                "Lotes_Producidos": int(lotes_producidos),
                "Lotes_Defectuosos": int(lotes_defectuosos),
                "OEE_Porcentaje": float(oee),
                "Rentabilidad_COP": float(rentabilidad),
                "Falla_Critica": str(falla),
                "Timestamp": timestamp_actual
            }]
            
            with st.spinner("Transmitiendo datos a la nube..."):
                try:
                    response = requests.post(POWER_BI_URL, json=payload)
                    if response.status_code == 200:
                        st.success("✅ ¡Datos transmitidos exitosamente! Revise el Dashboard en Power BI.")
                    else:
                        st.error(f"Error de API. Código: {response.status_code}")
                except Exception as e:
                    st.error(f"Error de conexión: {e}")