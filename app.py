import streamlit as st
from google import genai
import sqlite3
from datetime import date, datetime, timedelta
import calendar
from PIL import Image
import pandas as pd

# --- 1. CONFIGURACIÓN DE PÁGINA Y ESTILOS VISUALES ---
st.set_page_config(page_title="Argón Fit Pro", page_icon="💪", layout="wide")

# Gestión híbrida de API Key (Funciona en local y en Streamlit Cloud de forma segura)
if "API_KEY_GOOGLE" in st.secrets:
    API_KEY_GOOGLE = st.secrets["API_KEY_GOOGLE"]
else:
    API_KEY_GOOGLE = ""

def obtener_cliente_ia():
    return genai.Client(api_key=API_KEY_GOOGLE)

# Objetivos base diarios
OBJETIVOS_BASE = {'calorias': 2400, 'proteina': 150, 'hidratos': 250, 'grasas': 70}

# Estilos CSS para la interfaz y el calendario
st.markdown("""
<style>
.cal-header {
    text-align: center; font-weight: bold; background-color: #1E1E2E; 
    color: #CDD6F4; padding: 8px; border-radius: 6px; margin-bottom: 8px;
}
.cal-day-box {
    border: 1px solid #313244; border-radius: 8px; padding: 8px;
    min-height: 110px; background-color: #181825; margin-bottom: 8px;
}
.cal-today {
    border: 2px solid #F38BA8 !important; background-color: #1E1E2E !important;
}
.cal-num {
    font-weight: bold; font-size: 1.05em; color: #CDD6F4; margin-bottom: 4px;
}
.badge-act {
    background-color: #89B4FA; color: #11111B; padding: 2px 6px;
    border-radius: 4px; font-size: 0.72em; font-weight: 600;
    display: block; margin-top: 4px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
}
.badge-sal {
    background-color: #F9E2AF; color: #11111B; padding: 2px 6px;
    border-radius: 4px; font-size: 0.72em; font-weight: 600;
    display: block; margin-top: 4px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
}
</style>
""", unsafe_allow_html=True)

# --- 2. BASE DE DATOS PERMANENTE (SQLite) ---
def init_db():
    conn = sqlite3.connect('nutricion_argon.db')
    c = conn.cursor()
    # Tabla de comidas
    c.execute('''CREATE TABLE IF NOT EXISTS comidas
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, 
                  fecha TEXT, hora TEXT, descripcion TEXT, 
                  calorias INTEGER, proteina INTEGER, hidratos INTEGER, grasas INTEGER)''')
    
    c.execute("PRAGMA table_info(comidas)")
    columnas = [col[1] for col in c.fetchall()]
    if 'hora' not in columnas:
        c.execute("ALTER TABLE comidas ADD COLUMN hora TEXT DEFAULT '12:00'")

    # Tabla de calendario / eventos
    c.execute('''CREATE TABLE IF NOT EXISTS eventos
                 (fecha TEXT PRIMARY KEY, 
                  actividad TEXT, salida_evento TEXT, estrategia_ia TEXT)''')
    
    # NUEVA TABLA: Registro corporal (Peso, % Grasa, Masa Muscular)
    c.execute('''CREATE TABLE IF NOT EXISTS corporal
                 (fecha TEXT PRIMARY KEY, 
                  peso REAL, grasa REAL, musculo REAL, notas TEXT)''')
    conn.commit()
    conn.close()

init_db()

# --- 3. FUNCIONES DE BASE DE DATOS ---
def obtener_comidas(fecha_str):
    conn = sqlite3.connect('nutricion_argon.db')
    c = conn.cursor()
    c.execute("SELECT id, hora, descripcion, calorias, proteina, hidratos, grasas FROM comidas WHERE fecha = ?", (fecha_str,))
    datos = c.fetchall()
    conn.close()
    return datos

def agregar_comida(fecha_str, descripcion, kcal, prot, ch, grasas):
    conn = sqlite3.connect('nutricion_argon.db')
    c = conn.cursor()
    hora_actual = datetime.now().strftime("%H:%M")
    c.execute("INSERT INTO comidas (fecha, hora, descripcion, calorias, proteina, hidratos, grasas) VALUES (?, ?, ?, ?, ?, ?, ?)",
              (fecha_str, hora_actual, descripcion, kcal, prot, ch, grasas))
    conn.commit()
    conn.close()

def borrar_comida(id_comida):
    conn = sqlite3.connect('nutricion_argon.db')
    c = conn.cursor()
    c.execute("DELETE FROM comidas WHERE id = ?", (id_comida,))
    conn.commit()
    conn.close()

def guardar_rango_eventos(fecha_inicio, fecha_fin, actividad, salida, estrategia):
    conn = sqlite3.connect('nutricion_argon.db')
    c = conn.cursor()
    delta = (fecha_fin - fecha_inicio).days
    for i in range(delta + 1):
        dia_actual = (fecha_inicio + timedelta(days=i)).isoformat()
        c.execute("INSERT OR REPLACE INTO eventos (fecha, actividad, salida_evento, estrategia_ia) VALUES (?, ?, ?, ?)",
                  (dia_actual, actividad, salida, estrategia))
    conn.commit()
    conn.close()

def borrar_rango_eventos(fecha_inicio, fecha_fin):
    conn = sqlite3.connect('nutricion_argon.db')
    c = conn.cursor()
    delta = (fecha_fin - fecha_inicio).days
    for i in range(delta + 1):
        dia_actual = (fecha_inicio + timedelta(days=i)).isoformat()
        c.execute("DELETE FROM eventos WHERE fecha = ?", (dia_actual,))
    conn.commit()
    conn.close()

def obtener_evento(fecha_str):
    conn = sqlite3.connect('nutricion_argon.db')
    c = conn.cursor()
    c.execute("SELECT actividad, salida_evento, estrategia_ia FROM eventos WHERE fecha = ?", (fecha_str,))
    dato = c.fetchone()
    conn.close()
    return dato if dato else ("Descanso", "", "")

def obtener_todos_eventos_mes(anio, mes):
    conn = sqlite3.connect('nutricion_argon.db')
    c = conn.cursor()
    prefijo = f"{anio}-{mes:02d}-%"
    c.execute("SELECT fecha, actividad, salida_evento, estrategia_ia FROM eventos WHERE fecha LIKE ?", (prefijo,))
    filas = c.fetchall()
    conn.close()
    return {fila[0]: (fila[1], fila[2], fila[3]) for fila in filas}

def guardar_corporal(fecha_str, peso, grasa, musculo, notas):
    conn = sqlite3.connect('nutricion_argon.db')
    c = conn.cursor()
    c.execute("INSERT OR REPLACE INTO corporal (fecha, peso, grasa, musculo, notas) VALUES (?, ?, ?, ?, ?)",
              (fecha_str, peso, grasa, musculo, notas))
    conn.commit()
    conn.close()

def obtener_historial_corporal():
    conn = sqlite3.connect('nutricion_argon.db')
    df = pd.read_sql_query("SELECT fecha, peso, grasa, musculo, notas FROM corporal ORDER BY fecha ASC", conn)
    conn.close()
    return df

def obtener_historial_macros_dias(dias=7):
    conn = sqlite3.connect('nutricion_argon.db')
    fecha_limite = (date.today() - timedelta(days=dias-1)).isoformat()
    query = """
        SELECT fecha, SUM(calorias) as calorias, SUM(proteina) as proteina, 
               SUM(hidratos) as hidratos, SUM(grasas) as grasas 
        FROM comidas 
        WHERE fecha >= ? 
        GROUP BY fecha 
        ORDER BY fecha ASC
    """
    df = pd.read_sql_query(query, conn, params=(fecha_limite,))
    conn.close()
    return df

# --- 4. BARRA LATERAL ---
with st.sidebar:
    st.title("⚙️ Argón Fit Pro")
    fecha_activa = st.date_input("📍 Día de registro:", date.today())
    fecha_activa_str = fecha_activa.isoformat()
    
    # Cálculo rápido de racha de proteína en los últimos 7 días
    df_sem = obtener_historial_macros_dias(7)
    dias_cumplidos = len(df_sem[df_sem['proteina'] >= OBJETIVOS_BASE['proteina'] * 0.9]) if not df_sem.empty else 0
    st.metric("🔥 Racha Proteína (7d)", f"{dias_cumplidos} / 7 días")
    
    st.divider()
    act_hoy, sal_hoy, est_hoy = obtener_evento(fecha_activa_str)
    st.subheader("📌 Plan del Día")
    st.write(f"**🏃 Actividad:** {act_hoy}")
    if sal_hoy:
        st.write(f"**🍕 Evento:** {sal_hoy}")
    else:
        st.caption("Sin salidas especiales hoy.")

# --- 5. NAVEGACIÓN PRINCIPAL (5 PESTAÑAS) ---
tab_panel, tab_calendario, tab_nevera, tab_progreso, tab_coach = st.tabs([
    "📊 Panel y Foto IA", 
    "📅 Calendario", 
    "🍳 Cocinero de Nevera",
    "⚖️ Peso y Gráficas",
    "🧠 Entrenador IA"
])

# Pre-cálculo de macros del día activo (se usa en varias pestañas)
comidas_hoy = obtener_comidas(fecha_activa_str)
consumido = {'calorias': 0, 'proteina': 0, 'hidratos': 0, 'grasas': 0}
for c in comidas_hoy:
    consumido['calorias'] += c[3]
    consumido['proteina'] += c[4]
    consumido['hidratos'] += c[5]
    consumido['grasas'] += c[6]

rest_kcal = OBJETIVOS_BASE['calorias'] - consumido['calorias']
rest_prot = OBJETIVOS_BASE['proteina'] - consumido['proteina']
rest_ch = OBJETIVOS_BASE['hidratos'] - consumido['hidratos']
rest_gr = OBJETIVOS_BASE['grasas'] - consumido['grasas']

# ==========================================
# PESTAÑA 1: PANEL DIARIO + ESCÁNER POR FOTO
# ==========================================
with tab_panel:
    st.header(f"📊 Balance Nutricional ({fecha_activa.strftime('%d/%m/%Y')})")
    
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("🔥 Calorías", f"{consumido['calorias']} / {OBJETIVOS_BASE['calorias']} kcal", f"{rest_kcal} libres", delta_color="off")
        st.progress(min(consumido['calorias'] / OBJETIVOS_BASE['calorias'], 1.0))
    with col2:
        st.metric("🍗 Proteína", f"{consumido['proteina']} / {OBJETIVOS_BASE['proteina']} g", f"Faltan {rest_prot} g", delta_color="off")
        st.progress(min(consumido['proteina'] / OBJETIVOS_BASE['proteina'], 1.0))
    with col3:
        st.metric("🍚 Hidratos", f"{consumido['hidratos']} / {OBJETIVOS_BASE['hidratos']} g", f"{rest_ch} g libres", delta_color="off")
        st.progress(min(consumido['hidratos'] / OBJETIVOS_BASE['hidratos'], 1.0))
    with col4:
        st.metric("🥑 Grasas", f"{consumido['grasas']} / {OBJETIVOS_BASE['grasas']} g", f"{rest_gr} g libres", delta_color="off")
        st.progress(min(consumido['grasas'] / OBJETIVOS_BASE['grasas'], 1.0))

    if est_hoy:
        st.info(f"💡 **Estrategia IA activa para hoy ({act_hoy} | {sal_hoy}):**\n\n{est_hoy}")

    st.divider()
    
    col_input, col_hist = st.columns([1.1, 1])
    with col_input:
        st.subheader("🍽️ Registrar Comida")
        
        modo_registro = st.radio(
            "Elige cómo registrar tu plato:", 
            ["✍️ Por Texto", "📸 Por Foto (IA Multimodal)"], 
            horizontal=True
        )
        
        if modo_registro == "✍️ Por Texto":
            comida_texto = st.text_area("Describe qué has comido:", placeholder="Ej: 150g de arroz blanco con 2 latas de atún...", height=100)
            if st.button("➕ Calcular y Registrar Texto", type="primary", use_container_width=True):
                if comida_texto:
                    with st.spinner("🧠 Calculando macros con IA..."):
                        try:
                            cliente_ia = obtener_cliente_ia()
                            prompt = f"El usuario ha comido: '{comida_texto}'. Calcula calorías, proteínas, hidratos y grasas totales. Devuelve ÚNICAMENTE 4 números enteros separados por espacio: Calorias Proteinas Hidratos Grasas."
                            resp = cliente_ia.models.generate_content(model='gemini-3.8-flash', contents=prompt)
                            valores = resp.text.strip().split()
                            if len(valores) == 4:
                                kcal, prot, ch, gr = map(int, valores)
                                agregar_comida(fecha_activa_str, comida_texto, kcal, prot, ch, gr)
                                st.success(f"Registrado: {kcal} kcal | {prot}g P | {ch}g CH | {gr}g G")
                                st.rerun()
                            else:
                                st.error("Especifica un poco mejor las cantidades.")
                        except Exception as e:
                            st.error(f"Error de IA: {e}")
                else:
                    st.warning("Escribe algo antes de registrar.")
                    
        else:
            foto_subida = st.file_uploader("Sube una foto de tu plato o hazla desde el móvil:", type=["jpg", "jpeg", "png", "webp"])
            nota_foto = st.text_input("Nota opcional (ej: 'lleva 1 cucharada de aceite' o 'son 200g de carne'):")
            
            if foto_subida is not None:
                imagen_pil = Image.open(foto_subida)
                st.image(imagen_pil, caption="Vista previa de tu plato", use_container_width=True)
                
                if st.button("📸 Analizar Foto y Registrar", type="primary", use_container_width=True):
                    with st.spinner("👁️ Escaneando alimentos y tamaños de ración en la imagen..."):
                        try:
                            cliente_ia = obtener_cliente_ia()
                            prompt_foto = (
                                f"Analiza la comida de esta imagen. Contexto extra del usuario: '{nota_foto}'. "
                                "Estima el peso de cada ingrediente visible y calcula las calorías, proteínas, hidratos y grasas totales. "
                                "Responde EXACTAMENTE en este formato de 2 líneas:\n"
                                "LINEA 1: Breve nombre del plato y pesos estimados (máximo 12 palabras)\n"
                                "LINEA 2: 4 números enteros separados únicamente por un espacio: Calorias Proteinas Hidratos Grasas"
                            )
                            resp = cliente_ia.models.generate_content(
                                model='gemini-3.8-flash',
                                contents=[imagen_pil, prompt_foto]
                            )
                            lineas = [l.strip() for l in resp.text.strip().split('\n') if l.strip()]
                            if len(lineas) >= 2:
                                desc_detectada = lineas[0].replace("LINEA 1:", "").strip()
                                valores = lineas[-1].replace("LINEA 2:", "").strip().split()
                                if len(valores) == 4:
                                    kcal, prot, ch, gr = map(int, valores)
                                    agregar_comida(fecha_activa_str, f"📸 {desc_detectada}", kcal, prot, ch, gr)
                                    st.success(f"Detectado: {desc_detectada} ({kcal} kcal | {prot}g P)")
                                    st.rerun()
                                else:
                                    st.error("No se pudieron extraer los 4 números exactos. Intenta añadir una nota.")
                            else:
                                st.error("Formato no reconocido al analizar la imagen.")
                        except Exception as e:
                            st.error(f"Error al analizar foto: {e}")

    with col_hist:
        st.subheader("📋 Registro del Día")
        if comidas_hoy:
            for item in comidas_hoy:
                id_c, hora_c, desc_c, k_c, p_c, ch_c, g_c = item
                with st.container(border=True):
                    c_txt, c_del = st.columns([5, 1])
                    c_txt.markdown(f"**⏰ {hora_c}** - {desc_c}")
                    c_txt.caption(f"🔥 {k_c} kcal | 🍗 {p_c}g Prot | 🍚 {ch_c}g CH | 🥑 {g_c}g Grasas")
                    if c_del.button("🗑️", key=f"del_{id_c}"):
                        borrar_comida(id_c)
                        st.rerun()
        else:
            st.caption("Aún no has registrado comidas en esta fecha.")

# ==========================================
# PESTAÑA 2: CALENDARIO VISUAL Y RANGOS
# ==========================================
with tab_calendario:
    st.header("🗓️ Planificador de Actividad, Salidas y Viajes")
    col_form, col_cal = st.columns([1, 2.3])
    
    with col_form:
        with st.container(border=True):
            st.subheader("➕ Programar Rango de Días")
            Hoy = date.today()
            rango_fechas = st.date_input(
                "📆 Fecha de Inicio y Fin:",
                value=(Hoy, Hoy + timedelta(days=2)),
                format="DD/MM/YYYY"
            )
            actividad_sel = st.selectbox(
                "🏋️ Actividad física:",
                ["Descanso", "Gimnasio (Fuerza/Pesas)", "Partido de Fútbol", "Entreno de Fútbol", "Circuito en casa", "Caminata / Cardio", "Doble Sesión (Gym + Fútbol)"]
            )
            salida_txt = st.text_input("🍕 Salida o evento:", placeholder="Ej: Viaje de finde, Cena fuera...")
            generar_plan_ia = st.checkbox("🤖 Generar estrategia nutricional con IA", value=True)
            
            c_guardar, c_limpiar = st.columns(2)
            if c_guardar.button("💾 Guardar", type="primary", use_container_width=True):
                if isinstance(rango_fechas, tuple) and len(rango_fechas) == 2:
                    f_ini, f_fin = rango_fechas
                elif isinstance(rango_fechas, tuple) and len(rango_fechas) == 1:
                    f_ini = f_fin = rango_fechas[0]
                else:
                    f_ini = f_fin = rango_fechas
                
                estrategia_generada = ""
                if generar_plan_ia:
                    with st.spinner("🧠 Diseñando hoja de ruta nutricional..."):
                        try:
                            cliente_ia = obtener_cliente_ia()
                            num_dias = (f_fin - f_ini).days + 1
                            prompt_plan = (
                                f"Objetivos diarios: 2400 kcal y 150g proteína. "
                                f"Del {f_ini.strftime('%d/%m')} al {f_fin.strftime('%d/%m')} ({num_dias} días) haré: '{actividad_sel}' "
                                f"y evento: '{salida_txt if salida_txt else 'Ninguno'}'. "
                                f"Dame una estrategia directa en 3 puntos breves sobre cómo ajustar mis comidas esos días."
                            )
                            resp = cliente_ia.models.generate_content(model='gemini-3.8-flash', contents=prompt_plan)
                            estrategia_generada = resp.text
                        except Exception as e:
                            st.error(f"Error IA: {e}")
                
                guardar_rango_eventos(f_ini, f_fin, actividad_sel, salida_txt, estrategia_generada)
                st.rerun()

            if c_limpiar.button("🗑️ Limpiar Rango", use_container_width=True):
                if isinstance(rango_fechas, tuple) and len(rango_fechas) == 2:
                    borrar_rango_eventos(rango_fechas[0], rango_fechas[1])
                elif isinstance(rango_fechas, tuple) and len(rango_fechas) == 1:
                    borrar_rango_eventos(rango_fechas[0], rango_fechas[0])
                st.rerun()

    with col_cal:
        c_mes, c_anio = st.columns([2, 1])
        nombres_meses = ["Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio", "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"]
        mes_nombre = c_mes.selectbox("Mes", nombres_meses, index=date.today().month - 1)
        mes_num = nombres_meses.index(mes_nombre) + 1
        anio_num = c_anio.number_input("Año", min_value=2025, max_value=2030, value=date.today().year)
        
        cal_matriz = calendar.monthcalendar(anio_num, mes_num)
        eventos_mes = obtener_todos_eventos_mes(anio_num, mes_num)
        
        dias_sem = ["Lun", "Mar", "Mié", "Jue", "Vie", "Sáb", "Dom"]
        cols_cabecera = st.columns(7)
        for i, d_nombre in enumerate(dias_sem):
            cols_cabecera[i].markdown(f"<div class='cal-header'>{d_nombre}</div>", unsafe_allow_html=True)
            
        for semana in cal_matriz:
            cols_sem = st.columns(7)
            for i, dia in enumerate(semana):
                if dia == 0:
                    cols_sem[i].markdown("<div class='cal-day-box' style='opacity: 0.15;'></div>", unsafe_allow_html=True)
                else:
                    fecha_celda_str = f"{anio_num}-{mes_num:02d}-{dia:02d}"
                    es_hoy = (fecha_celda_str == date.today().isoformat())
                    clase_extra = "cal-today" if es_hoy else ""
                    html_badges = ""
                    if fecha_celda_str in eventos_mes:
                        act_ev, sal_ev, _ = eventos_mes[fecha_celda_str]
                        if act_ev and act_ev != "Descanso":
                            html_badges += f"<span class='badge-act'>💪 {act_ev}</span>"
                        if sal_ev:
                            html_badges += f"<span class='badge-sal'>🍕 {sal_ev}</span>"
                    cols_sem[i].markdown(f"""
                    <div class='cal-day-box {clase_extra}'>
                        <div class='cal-num'>{dia} {'📍' if es_hoy else ''}</div>
                        {html_badges}
                    </div>
                    """, unsafe_allow_html=True)

        if eventos_mes:
            with st.expander("📋 Ver detalles y estrategias de este mes", expanded=False):
                for f_ev, (act_ev, sal_ev, est_ev) in sorted(eventos_mes.items()):
                    fecha_bonita = datetime.strptime(f_ev, "%Y-%m-%d").strftime("%d/%m/%Y")
                    st.markdown(f"**📅 {fecha_bonita}** — 🏃 *{act_ev}* " + (f"| 🎉 *{sal_ev}*" if sal_ev else ""))
                    if est_ev:
                        st.caption(est_ev)
                    st.divider()

# ==========================================
# PESTAÑA 3: COCINERO DE NEVERA (RECETAS A MEDIDA)
# ==========================================
with tab_nevera:
    st.header("🍳 Cocinero de Nevera Inteligente")
    st.write("Dime qué ingredientes tienes por casa y te crearé una receta exacta para cuadrar los macros que te faltan hoy.")
    
    st.info(f"🎯 **Macros pendientes para clavar el día de hoy:** 🔥 {max(0, rest_kcal)} kcal | 🍗 {max(0, rest_prot)}g Proteína | 🍚 {max(0, rest_ch)}g Hidratos | 🥑 {max(0, rest_gr)}g Grasas")
    
    col_nev1, col_nev2 = st.columns([1.2, 1])
    with col_nev1:
        ingredientes_disp = st.text_area(
            "🥦 ¿Qué tienes en la nevera o despensa?",
            placeholder="Ej: Pechuga de pollo, huevos, yogur griego, arroz, patatas, espinacas, queso rallado, atún...",
            height=110
        )
        tiempo_cocina = st.select_slider(
            "⏱️ Tiempo máximo para cocinar:",
            options=["5 min (Express)", "15 min (Rápido)", "30 min (Elaborado)"],
            value="15 min (Rápido)"
        )
        tipo_comida_nev = st.selectbox("🍽️ ¿Para qué comida es?", ["Comida principal / Almuerzo", "Cena", "Desayuno / Merienda / Post-entreno", "Tartera para llevar"])
        
        if st.button("👨‍🍳 Crear Receta Exacta con mis Macros", type="primary", use_container_width=True):
            if ingredientes_disp:
                with st.spinner("🍳 Calculando pesos en crudo y diseñando receta..."):
                    try:
                        cliente_ia = obtener_cliente_ia()
                        prompt_nevera = (
                            f"Actúa como un chef nutricionista deportivo. El usuario tiene estos ingredientes: '{ingredientes_disp}'.\n"
                            f"Quiere preparar: {tipo_comida_nev} en máximo {tiempo_cocina}.\n"
                            f"Sus macros restantes para terminar el día son: {max(0, rest_kcal)} kcal, {max(0, rest_prot)}g proteína, {max(0, rest_ch)}g hidratos y {max(0, rest_gr)}g grasas.\n"
                            f"Diseña 2 opciones de recetas deliciosas y fáciles usando solo esos ingredientes (y básicos como sal/especias/aceite). "
                            f"Incluye: Nombre del plato, lista de ingredientes con GRAMOS EXACTOS para cuadrar sus macros pendientes, pasos rápidos de preparación y los macros totales del plato."
                        )
                        resp_nev = cliente_ia.models.generate_content(model='gemini-3.8-flash', contents=prompt_nevera)
                        st.session_state['ultima_receta'] = resp_nev.text
                    except Exception as e:
                        st.error(f"Error al generar receta: {e}")
            else:
                st.warning("Escribe al menos 2 o 3 ingredientes que tengas a mano.")

    with col_nev2:
        st.subheader("📖 Tu Receta a Medida")
        if 'ultima_receta' in st.session_state:
            with st.container(border=True):
                st.markdown(st.session_state['ultima_receta'])
        else:
            st.caption("Introduce tus ingredientes a la izquierda y pulsa el botón para ver el paso a paso con cantidades exactas.")

# ==========================================
# PESTAÑA 4: PESO, BÁSCULA Y GRÁFICAS DE EVOLUCIÓN
# ==========================================
with tab_progreso:
    st.header("⚖️ Evolución Corporal y Gráficas Semanales")
    
    col_peso_form, col_peso_graf = st.columns([1, 2])
    
    with col_peso_form:
        with st.container(border=True):
            st.subheader("📝 Registrar Báscula")
            fecha_peso = st.date_input("Fecha del pesaje:", date.today(), key="fecha_pesaje")
            peso_val = st.number_input("⚖️ Peso (kg):", min_value=40.0, max_value=160.0, value=75.0, step=0.1)
            grasa_val = st.number_input("💧 % Grasa Corporal (opcional):", min_value=3.0, max_value=50.0, value=15.0, step=0.1)
            musculo_val = st.number_input("💪 Masa Muscular kg (opcional):", min_value=20.0, max_value=100.0, value=58.0, step=0.1)
            notas_peso = st.text_input("Notas (ej: En ayunas, post-partido...):")
            
            if st.button("💾 Guardar Pesaje", type="primary", use_container_width=True):
                guardar_corporal(fecha_peso.isoformat(), peso_val, grasa_val, musculo_val, notas_peso)
                st.success("¡Métricas corporales guardadas!")
                st.rerun()

    with col_peso_graf:
        st.subheader("📈 Evolución de Peso y % Grasa")
        df_corp = obtener_historial_corporal()
        if not df_corp.empty:
            df_corp_chart = df_corp.set_index('fecha')[['peso', 'grasa']]
            st.line_chart(df_corp_chart)
            with st.expander("Ver tabla histórica de pesajes"):
                st.dataframe(df_corp, use_container_width=True, hide_index=True)
        else:
            st.info("Registra tu primer pesaje a la izquierda para empezar a ver tu gráfica de evolución.")

    st.divider()
    st.subheader("📊 Cumplimiento de Macros (Últimos 14 días)")
    df_macros_hist = obtener_historial_macros_dias(14)
    if not df_macros_hist.empty:
        col_g1, col_g2 = st.columns(2)
        with col_g1:
            st.markdown("**🍗 Evolución de Proteína Diaria (Meta: 150g)**")
            st.bar_chart(df_macros_hist.set_index('fecha')['proteina'], color="#89B4FA")
        with col_g2:
            st.markdown("**🔥 Evolución de Calorías Diarias (Meta: 2400 kcal)**")
            st.bar_chart(df_macros_hist.set_index('fecha')['calorias'], color="#F38BA8")
    else:
        st.caption("A medida que registres comidas durante varios días, aquí aparecerán tus gráficas de barras comparativas.")

# ==========================================
# PESTAÑA 5: ENTRENADOR IA (¿CÓMO VOY?)
# ==========================================
with tab_coach:
    st.header("🧠 Evaluación Integral en Tiempo Real")
    st.write("El entrenador IA cruza tus comidas de hoy, tu actividad del calendario y tu evolución de peso para darte feedback inmediato.")
    
    if st.button("🔍 Analizar mi día y recomendarme comidas", type="primary"):
        with st.spinner("🧠 Evaluando tus macros, tu entreno y tus planes..."):
            try:
                cliente_ia = obtener_cliente_ia()
                lista_platos = ", ".join([f"{c[2]} ({c[3]}kcal, {c[4]}g P)" for c in comidas_hoy]) if comidas_hoy else "Aún no he comido nada hoy"
                df_corp = obtener_historial_corporal()
                ultimo_peso_txt = f"{df_corp.iloc[-1]['peso']}kg ({df_corp.iloc[-1]['grasa']}% grasa)" if not df_corp.empty else "Sin registros aún"
                
                prompt_coach = (
                    f"Actúa como mi nutricionista deportivo personal. Hoy es {fecha_activa.strftime('%d/%m/%Y')}.\n"
                    f"- Mis objetivos diarios: 2400 kcal, 150g Proteína, 250g Hidratos, 70g Grasas.\n"
                    f"- Llevo consumido hoy: {consumido['calorias']} kcal, {consumido['proteina']}g Proteína, {consumido['hidratos']}g Hidratos, {consumido['grasas']}g Grasas.\n"
                    f"- Platos registrados hoy: {lista_platos}.\n"
                    f"- Mi último registro en báscula: {ultimo_peso_txt}.\n"
                    f"- Mi actividad física de hoy: {act_hoy}.\n"
                    f"- Mi evento/salida social de hoy: {sal_hoy if sal_hoy else 'Ninguno'}.\n\n"
                    f"Responde de forma directa y motivadora con:\n"
                    f"1. Diagnóstico rápido del día.\n"
                    f"2. Dos opciones de platos concretos (con gramos en crudo) para mi siguiente comida que claven los macros restantes."
                )
                resp_coach = cliente_ia.models.generate_content(model='gemini-3.8-flash', contents=prompt_coach)
                st.markdown(resp_coach.text)
            except Exception as e:
                st.error(f"Error al consultar al entrenador IA: {e}")
