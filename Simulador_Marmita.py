import streamlit as st
import streamlit.components.v1 as components
import pandas as pd
import time
import random
import requests
from datetime import datetime

# ==========================================
# 1. CONFIGURACIÓN DEL SISTEMA Y API
# ==========================================
POWER_BI_URL = "https://api.powerbi.com/beta/cbc2c381-2f2e-4d93-91d1-506c9316ace7/datasets/ccbd2ba0-336f-4cdc-b478-9e2398efc114/rows?experience=power-bi&clientSideAuth=0&key=A%2FgUPAJw6SQrGOeFO3lPI3sIDWoMzTa%2F%2FpPD5zUwpByzUAWihgH%2FX6%2FZ4NvUiyF3s0RirNAQ0Ku7BRiQLpKjug%3D%3D"

st.set_page_config(page_title="SCADA Marmita", page_icon="🏭", layout="wide")

# CSS para Fondo Blanco e Interfaz Industrial Clara
st.markdown("""
<style>
    .stApp { background-color: #FFFFFF; color: #333333; font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;}
    .hmi-panel { background-color: #F8F9FA; padding: 20px; border-radius: 8px; border-top: 5px solid #39A900; box-shadow: 0 4px 8px rgba(0,0,0,0.1); margin-bottom: 20px;}
    .lcd-screen { background-color: #E8F8F5; color: #0E6251; font-family: 'Courier New', monospace; font-size: 24px; font-weight: bold; padding: 10px; border-radius: 5px; text-align: center; border: 2px solid #1ABC9C;}
    .alert-box { background-color: #FDEDEC; border: 2px solid #E74C3C; padding: 15px; border-radius: 5px; color: #C0392B; font-weight: bold; text-align: center; margin-bottom: 15px;}
    h1, h2, h3, h4 { color: #00324D; }
    hr { border-color: #BDC3C7; }
</style>
""", unsafe_allow_html=True)

# ==========================================
# 2. CONSTANTES TEÓRICAS (CALIBRACIÓN)
# ==========================================
VOLTAJE_PLC = 24.0 
CORRIENTE_OBJETIVO = 0.02 
R_IDEAL = VOLTAJE_PLC / CORRIENTE_OBJETIVO # 1200 Ohm

FUERZA_MOTOR = 150.0 
RADIO_AGITADOR = 0.4 
TORQUE_IDEAL = FUERZA_MOTOR * RADIO_AGITADOR # 60 Nm

# Receta Ideal
RECETA_AGUA = 200 # Litros
RECETA_TOMATE = 300 # Kg
RECETA_ESPECIAS = 10 # Kg

# ==========================================
# 3. MEMORIA RAM (st.session_state)
# ==========================================
if 'grupo' not in st.session_state: st.session_state.grupo = ""
if 'resistencia' not in st.session_state: st.session_state.resistencia = 0.0
if 'torque' not in st.session_state: st.session_state.torque = 0.0

# Variables de Materia Prima
if 'agua_actual' not in st.session_state: st.session_state.agua_actual = 0
if 'tomate_actual' not in st.session_state: st.session_state.tomate_actual = 0
if 'especias_actual' not in st.session_state: st.session_state.especias_actual = 0
if 'materia_prima_ok' not in st.session_state: st.session_state.materia_prima_ok = False

# Variables de Tiempo Real
if 'corriendo' not in st.session_state: st.session_state.corriendo = False
if 'tiempo_min' not in st.session_state: st.session_state.tiempo_min = 0
if 'temp_real' not in st.session_state: st.session_state.temp_real = 25.0
if 'lote_terminado' not in st.session_state: st.session_state.lote_terminado = False
if 'falla_critica' not in st.session_state: st.session_state.falla_critica = "Ninguna"

# Variables de Eventos Aleatorios (Fallas)
if 'falla_en_vivo' not in st.session_state: st.session_state.falla_en_vivo = ""
if 'tiempo_falla' not in st.session_state: st.session_state.tiempo_falla = random.randint(10, 25)

def reset_planta():
    st.session_state.clear()
    st.rerun()

# ==========================================
# 4. MOTOR GRÁFICO SVG (Fondo Claro)
# ==========================================
def render_marmita_hmi(temp_hmi, vapor_pct, rpm_motor, falla_scada, agua, tomate, especias):
    color_salsa = "#E67E22" if temp_hmi < 95 else "#A04000" 
    color_camisa = "#E74C3C" if vapor_pct > 50 else ("#F39C12" if vapor_pct > 0 else "#BDC3C7")
    giro = "spin 1s linear infinite" if rpm_motor > 0 else "none"
    burbujas = '<g style="animation: rise 1s infinite;"><circle cx="150" cy="180" r="10" fill="#FAD7A1" opacity="0.6"/><circle cx="130" cy="200" r="15" fill="#FAD7A1" opacity="0.6"/></g>' if temp_hmi > 85 else ""
    
    # Nivel de llenado visual
    total_kg = agua + tomate + especias
    nivel_y = max(130, 275 - (total_kg / 510) * 145)

    alerta_ui = f'<rect x="20" y="340" width="360" height="40" fill="#E74C3C" rx="5"/><text x="200" y="365" text-anchor="middle" font-family="Arial" font-weight="bold" fill="white">⚠️ {falla_scada.upper()}</text>' if falla_scada else ""

    html = f"""<!DOCTYPE html><html><head><style>
        body {{ margin: 0; display: flex; justify-content: center; background: #FFFFFF; font-family: 'Courier New', monospace; }}
        @keyframes spin {{ 100% {{ transform: rotate(360deg); }} }}
        @keyframes rise {{ 0% {{ transform: translateY(0) scale(1); opacity:0.8;}} 100% {{ transform: translateY(-30px) scale(1.5); opacity:0;}} }}
    </style></head><body>
    <svg viewBox="0 0 400 400" width="100%" height="400">
        <path d="M 30,100 L 90,100 L 90,150" fill="none" stroke="#7F8C8D" stroke-width="8"/>
        <circle cx="60" cy="100" r="15" fill="#C0392B"/>
        <text x="60" y="80" text-anchor="middle" font-size="12" fill="#333" font-weight="bold" font-family="Arial">VAPOR {vapor_pct}%</text>
        <path d="M 90,120 L 90,280 A 60 60 0 0 0 210,280 L 210,120 Z" fill="{color_camisa}" stroke="#2C3E50" stroke-width="4"/>
        <path d="M 100,120 L 100,275 A 50 50 0 0 0 200,275 L 200,120 Z" fill="#ECF0F1" stroke="#2C3E50" stroke-width="2"/>
        
        <path d="M 102,{nivel_y} L 102,275 A 48 48 0 0 0 198,275 L 198,{nivel_y} Z" fill="{color_salsa}"/>
        {burbujas}
        
        <rect x="130" y="50" width="40" height="50" fill="#2980B9" stroke="#2C3E50" stroke-width="2" rx="5"/>
        <rect x="145" y="100" width="10" height="150" fill="#7F8C8D"/>
        <g style="transform-box: fill-box; transform-origin: center; animation: {giro};">
            <path d="M 115,240 L 185,240 L 185,260 L 115,260 Z" fill="#2C3E50"/>
        </g>
        
        <rect x="230" y="120" width="150" height="80" fill="#F8F9FA" rx="5" stroke="#2C3E50" stroke-width="2"/>
        <text x="240" y="145" font-size="14" font-weight="bold" fill="#27AE60">TT-101 (Temp)</text>
        <text x="240" y="175" font-size="24" font-weight="bold" fill="#27AE60">{temp_hmi:.1f} °C</text>
        
        <rect x="230" y="210" width="150" height="60" fill="#F8F9FA" rx="5" stroke="#2C3E50" stroke-width="2"/>
        <text x="240" y="235" font-size="14" font-weight="bold" fill="#2980B9">MT-101 (RPM)</text>
        <text x="240" y="255" font-size="20" font-weight="bold" fill="#2980B9">{rpm_motor} RPM</text>
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
    reset_planta()

st.title("🏭 SCADA Avanzado: Planta de Salsas")

# ==========================================
# 6. ESTRUCTURA DE PESTAÑAS
# ==========================================
tab1, tab2, tab3, tab4, tab5 = st.tabs(["⚙️ 1. Calibración", "🍅 2. Dosificación", "⏱️ 3. Operación en Vivo", "📝 4. Evaluación", "📊 5. Power BI"])

# ---------------------------------------------------------
# PESTAÑA 1: MANTENIMIENTO (CALIBRACIÓN)
# ---------------------------------------------------------
with tab1:
    st.info("💡 **Instrucción:** Calibre los instrumentos usando la Ley de Ohm y la fórmula de Torque Mecánico.")
    col_e, col_m = st.columns(2)
    with col_e:
        st.markdown("""<div class="hmi-panel">
        <h4>⚡ Calibración Eléctrica (PT100)</h4>
        <p>Voltaje PLC: <b>24 V</b> | Corriente esperada: <b>0.02 A</b></p>
        </div>""", unsafe_allow_html=True)
        r_input = st.number_input("Resistencia (Ω):", min_value=0.0, step=10.0, value=st.session_state.resistencia)
        
    with col_m:
        st.markdown("""<div class="hmi-panel">
        <h4>⚙️ Calibración Mecánica</h4>
        <p>Fuerza de la salsa: <b>150 N</b> | Radio del eje: <b>0.4 m</b></p>
        </div>""", unsafe_allow_html=True)
        t_input = st.number_input("Torque (Nm):", min_value=0.0, step=1.0, value=st.session_state.torque)
        
    if st.button("💾 Guardar Calibración", type="primary"):
        st.session_state.resistencia = r_input
        st.session_state.torque = t_input
        st.success("✅ Parámetros guardados.")

# ---------------------------------------------------------
# PESTAÑA 2: DOSIFICACIÓN (MATERIA PRIMA)
# ---------------------------------------------------------
with tab2:
    st.markdown("### Dosificación de Ingredientes")
    st.write("Añade la materia prima al tanque. **Receta requerida:** 200 L Agua, 300 Kg Tomate, 10 Kg Especias.")
    
    c1, c2, c3 = st.columns(3)
    with c1:
        if st.button("💧 Añadir 50 L Agua"): st.session_state.agua_actual += 50; st.rerun()
        st.metric("Agua (L)", st.session_state.agua_actual)
    with c2:
        if st.button("🍅 Añadir 100 Kg Tomate"): st.session_state.tomate_actual += 100; st.rerun()
        st.metric("Tomate (Kg)", st.session_state.tomate_actual)
    with c3:
        if st.button("🧂 Añadir 5 Kg Especias"): st.session_state.especias_actual += 5; st.rerun()
        st.metric("Especias (Kg)", st.session_state.especias_actual)
        
    if st.button("✅ Confirmar Mezcla"):
        if st.session_state.agua_actual == RECETA_AGUA and st.session_state.tomate_actual == RECETA_TOMATE and st.session_state.especias_actual == RECETA_ESPECIAS:
            st.session_state.materia_prima_ok = True
            st.success("Formulación correcta. Pase a la pestaña de Operación.")
        else:
            st.session_state.falla_critica = "Mala Formulación de Ingredientes"
            st.error("❌ Error en la receta. El lote se ha arruinado antes de empezar.")

# ---------------------------------------------------------
# PESTAÑA 3: SCADA EN TIEMPO REAL
# ---------------------------------------------------------
with tab3:
    if not st.session_state.materia_prima_ok and st.session_state.falla_critica == "Ninguna":
        st.warning("⚠️ Debes completar la dosificación correcta en la Pestaña 2.")
    else:
        # TRAMPAS DE CALIBRACIÓN
        temp_hmi = 0.0
        if st.session_state.resistencia > 0:
            temp_hmi = st.session_state.temp_real * (R_IDEAL / st.session_state.resistencia)
            
        rpm_motor = 60
        if st.session_state.torque < (TORQUE_IDEAL - 5) or st.session_state.torque > (TORQUE_IDEAL + 15):
            rpm_motor = 0
            if st.session_state.tiempo_min > 0 and st.session_state.falla_critica == "Ninguna":
                st.session_state.falla_critica = "Falla de Motor por mal Torque"

        # INTERFAZ SCADA
        col_ctrl, col_svg = st.columns([1, 1.5])
        
        with col_ctrl:
            st.markdown("<div class='hmi-panel'>", unsafe_allow_html=True)
            vapor = st.slider("Válvula de Vapor (%)", 0, 100, 0, step=10, key="vapor_slider")
            
            st.markdown(f"<div class='lcd-screen'>⏳ Minuto: {st.session_state.tiempo_min} / 30</div><br>", unsafe_allow_html=True)
            
            if not st.session_state.lote_terminado:
                if not st.session_state.corriendo:
                    if st.button("▶️ INICIAR PRODUCCIÓN (TIEMPO REAL)", type="primary"):
                        st.session_state.corriendo = True
                        st.rerun()
                else:
                    if st.button("⏸️ DETENER EMERGENCIA"):
                        st.session_state.corriendo = False
                        st.rerun()

            # MANEJO DE FALLAS EN VIVO
            if st.session_state.falla_en_vivo:
                st.markdown(f"<div class='alert-box'>⚠️ {st.session_state.falla_en_vivo}</div>", unsafe_allow_html=True)
                if st.button("🔧 Resolver Falla Rápidamente"):
                    st.session_state.falla_en_vivo = ""
                    st.rerun()
            st.markdown("</div>", unsafe_allow_html=True)

        with col_svg:
            components.html(render_marmita_hmi(temp_hmi, vapor if not st.session_state.falla_en_vivo else 0, rpm_motor if not st.session_state.falla_en_vivo else 0, st.session_state.falla_en_vivo, st.session_state.agua_actual, st.session_state.tomate_actual, st.session_state.especias_actual), height=420)

        # LÓGICA DE TIEMPO REAL (RERUN LOOP)
        if st.session_state.corriendo and st.session_state.tiempo_min < 30:
            time.sleep(1) # 1 segundo = 1 minuto de proceso
            st.session_state.tiempo_min += 1
            
            # Física térmica
            if not st.session_state.falla_en_vivo:
                dT = (vapor * 0.6) - ((st.session_state.temp_real - 25.0) * 0.1)
                st.session_state.temp_real = max(25.0, st.session_state.temp_real + dT)
            else:
                # Si hay falla, se enfría
                st.session_state.temp_real = max(25.0, st.session_state.temp_real - 2.0)
                
            # Disparar falla aleatoria
            if st.session_state.tiempo_min == st.session_state.tiempo_falla:
                fallas = ["Bomba de recirculación atascada", "Caída de presión de vapor", "Sobrecarga en el motor"]
                st.session_state.falla_en_vivo = random.choice(fallas)
                
            if st.session_state.temp_real > 105.0:
                st.session_state.falla_critica = "Salsa Quemada (Sobretemperatura)"
                
            if st.session_state.tiempo_min >= 30:
                st.session_state.corriendo = False
                st.session_state.lote_terminado = True
                
            st.rerun()

# ---------------------------------------------------------
# PESTAÑA 4: EVALUACIÓN TÉCNICA (10 PREGUNTAS)
# ---------------------------------------------------------
with tab4:
    st.subheader("📝 Evaluación: Fundamentos y Mecánica")
    st.write("Responde estas 10 preguntas para autorizar tu reporte final.")
    
    qs = [
        {"q": "1. Según la Ley de Ohm, ¿cómo se calcula la Resistencia?", "o": ["R = V / I", "R = V * I", "R = I / V"], "a": "R = V / I"},
        {"q": "2. ¿Qué es el Torque o Par Mecánico?", "o": ["Velocidad de giro", "Fuerza que produce rotación (F * d)", "Presión hidráulica"], "a": "Fuerza que produce rotación (F * d)"},
        {"q": "3. Para medir la corriente (Amperios), el multímetro debe conectarse en:", "o": ["Paralelo", "Serie", "Mixto"], "a": "Serie"},
        {"q": "4. Componente electrónico que actúa como interruptor sin partes mecánicas:", "o": ["Relé", "Condensador", "Transistor"], "a": "Transistor"},
        {"q": "5. ¿Qué mecanismo transforma movimiento circular en lineal?", "o": ["Piñón y cadena", "Engranajes rectos", "Tornillo y tuerca"], "a": "Tornillo y tuerca"},
        {"q": "6. ¿Qué función principal tiene un diodo?", "o": ["Almacenar energía", "Dejar pasar la corriente en un solo sentido", "Aumentar el voltaje"], "a": "Dejar pasar la corriente en un solo sentido"},
        {"q": "7. En la industria 4.0, ¿qué significa IIoT?", "o": ["Internet Industrial de las Cosas", "Interfaz Interna de Operación", "Instituto de Innovación Tecnológica"], "a": "Internet Industrial de las Cosas"},
        {"q": "8. Los robots colaborativos diseñados para trabajar junto a humanos se llaman:", "o": ["Drones", "Cobots", "Autómatas"], "a": "Cobots"},
        {"q": "9. ¿Qué magnitud física se mide en Pascales (Pa) o Bares?", "o": ["Caudal", "Fuerza", "Presión"], "a": "Presión"},
        {"q": "10. El PLC en un sistema SCADA actúa como:", "o": ["El actuador final", "El cerebro lógico", "El sensor"], "a": "El cerebro lógico"}
    ]
    
    score = 0
    for i, item in enumerate(qs):
        res = st.radio(item['q'], item['o'], key=f"q_{i}")
        if res == item['a']: score += 1
        st.write("---")
        
    if st.button("Calificar Evaluación"):
        if score >= 7:
            st.success(f"✅ ¡Aprobado! Puntuación: {score}/10.")
            st.session_state.evaluacion_aprobada = True
        else:
            st.error(f"❌ Reprobado. Puntuación: {score}/10. Repasa la teoría.")

# ---------------------------------------------------------
# PESTAÑA 5: REPORTE Y POWER BI
# ---------------------------------------------------------
with tab5:
    st.markdown("### 📊 Extrapolación a Turno de Producción")
    
    if not st.session_state.lote_terminado:
        st.warning("Debe finalizar la producción en la Pestaña 3.")
    else:
        lotes_producidos = 10
        falla = st.session_state.falla_critica
        
        if falla == "Ninguna":
            if st.session_state.temp_real < 80.0:
                falla = "Salsa Cruda (Temperatura Baja)"
            elif st.session_state.temp_real > 105.0:
                falla = "Salsa Quemada (Temperatura Alta)"
                
        if falla != "Ninguna":
            lotes_defectuosos = 10  
        else:
            lotes_defectuosos = random.choice([0, 0, 1]) 
            
        oee = ((lotes_producidos - lotes_defectuosos) / lotes_producidos) * 100
        ingresos = (lotes_producidos - lotes_defectuosos) * 5000000 
        penalidad = lotes_defectuosos * 2000000 
        rentabilidad = ingresos - penalidad
        
        col1, col2, col3 = st.columns(3)
        col1.metric("OEE (Eficiencia Global)", f"{oee:.1f} %", f"{-lotes_defectuosos} Defectos")
        col2.metric("Rentabilidad Neta", f"${rentabilidad:,.0f} COP", f"-${penalidad:,.0f} COP" if penalidad>0 else "Óptimo", delta_color="inverse")
        col3.metric("Falla Crítica de Turno", falla)
        
        st.markdown("---")
        if st.button("📡 ENVIAR DATOS A POWER BI", type="primary"):
            timestamp_actual = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%S.000Z")
            
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
