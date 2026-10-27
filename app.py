import streamlit as st
from google import genai
import sqlite3
from datetime import date, datetime, timedelta
import calendar
from PIL import Image
import pandas as pd
import requests

# --- 1. CONFIGURACIÓN DE PÁGINA ---
st.set_page_config(page_title="Argón Fit Pro", page_icon="💪", layout="wide")

if "API_KEY_GOOGLE" in st.secrets:
    API_KEY_GOOGLE = st.secrets["API_KEY_GOOGLE"]
else:
    API_KEY_GOOGLE = ""

def obtener_cliente_ia():
    return genai.Client(api_key=API_KEY_GOOGLE)

def llamar_ia(contenidos):
    """Usa directamente los modelos activos de 2026 sin pasar por modelos retirados."""
    cliente = obtener_cliente_ia()
    modelos = [
        'gemini-3.8-flash',
        'gemini-3.1-pro-preview',
        'gemini-3.8-flash'
    ]
    ultimo_err = None
    for m in modelos:
        try:
            return cliente.models.generate_content(model=m, contents=contenidos)
        except Exception as e:
            ultimo_err = e
            continue
    raise ultimo_err

OBJETIVOS_BASE = {'calorias': 2400, 'proteina': 150, 'hidratos': 250, 'grasas': 70}

# Estilos CSS incluyendo tabla de calendario horizontal para móvil
st.markdown("""
<style>
.cal-table {
    width: 100%; border-collapse: collapse; table-layout: fixed; margin-top: 8px;
}
.cal-table th {
    background-color: #1E1E2E; color: #CDD6F4; text-align: center;
    padding: 6px 2px; font-size: 0.78rem; border: 1px solid #313244;
}
.cal-table td {
    background-color: #181825; color: #CDD6F4; vertical-align: top;
    height: 68px; padding: 3px; border: 1px solid #313244; font-size: 0.72rem;
    overflow: hidden; word-wrap: break-word;
}
.cal-today-cell {
    border: 2px solid #F38BA8 !important; background-color: #252538 !important;
}
.cal-day-num {
    font-weight: bold; font-size: 0.8rem; margin-bottom: 2px;
}
.tag-act {
    background-color: #89B4FA; color: #11111B; padding: 1px 3px;
    border-radius: 3px; font-size: 0.62rem; font-weight: 700;
    display: block; margin-top: 2px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
}
.tag-sal {
    background-color: #F9E2AF; color: #11111B; padding: 1px 3px;
    border-radius: 3px; font-size: 0.62rem; font-weight: 700;
    display: block; margin-top: 2px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
}
</style>
""", unsafe_allow_html=True)

# --- 2. BASE DE DATOS PERMANENTE (SQLite) ---
def init_db():
    conn = sqlite3.connect('nutricion_argon.db')
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS comidas
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, 
                  fecha TEXT, hora TEXT, descripcion TEXT, 
                  calorias INTEGER, proteina INTEGER, hidratos INTEGER, grasas INTEGER)''')
    
    c.execute('''CREATE TABLE IF NOT EXISTS eventos
                 (fecha TEXT PRIMARY KEY, 
                  actividad TEXT, salida_evento TEXT, estrategia_ia TEXT)''')
    
    c.execute('''CREATE TABLE IF NOT EXISTS corporal
                 (fecha TEXT PRIMARY KEY, 
                  peso REAL, grasa REAL, musculo REAL, notas TEXT)''')

    c.execute('''CREATE TABLE IF NOT EXISTS ajustes
                 (clave TEXT PRIMARY KEY, valor TEXT)''')

    c.execute('''CREATE TABLE IF NOT EXISTS entrenos
                 (fecha TEXT PRIMARY KEY, grupo_muscular TEXT, notas TEXT, rutina_ia TEXT)''')

    c.execute('''CREATE TABLE IF NOT EXISTS mis_productos
                 (codigo TEXT PRIMARY KEY, nombre TEXT, 
                  kcal_100 REAL, prot_100 REAL, ch_100 REAL, gr_100 REAL)''')
    conn.commit()
    conn.close()

init_db()

# --- 3. FUNCIONES DE DATOS ---
def obtener_ajuste(clave, por_defecto=""):
    conn = sqlite3.connect('nutricion_argon.db')
    c = conn.cursor()
    c.execute("SELECT valor FROM ajustes WHERE clave = ?", (clave,))
    fila = c.fetchone()
    conn.close()
    return fila[0] if fila else por_defecto

def guardar_ajuste(clave, valor):
    conn = sqlite3.connect('nutricion_argon.db')
    c = conn.cursor()
    c.execute("INSERT OR REPLACE INTO ajustes (clave, valor) VALUES (?, ?)", (clave, valor))
    conn.commit()
    conn.close()

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

def guardar_entreno(fecha_str, grupo, notas, rutina=""):
    conn = sqlite3.connect('nutricion_argon.db')
    c = conn.cursor()
    c.execute("INSERT OR REPLACE INTO entrenos (fecha, grupo_muscular, notas, rutina_ia) VALUES (?, ?, ?, ?)",
              (fecha_str, grupo, notas, rutina))
    conn.commit()
    conn.close()

def obtener_historial_entrenos(limite=10):
    conn = sqlite3.connect('nutricion_argon.db')
    c = conn.cursor()
    c.execute("SELECT fecha, grupo_muscular, notas FROM entrenos ORDER BY fecha DESC LIMIT ?", (limite,))
    filas = c.fetchall()
    conn.close()
    return filas

def buscar_codigo_barras_global(codigo):
    """Busca en Open Food Facts España, Mundial y base de datos local del usuario."""
    conn = sqlite3.connect('nutricion_argon.db')
    c = conn.cursor()
    c.execute("SELECT nombre, kcal_100, prot_100, ch_100, gr_100 FROM mis_productos WHERE codigo = ?", (codigo,))
    local = c.fetchone()
    conn.close()
    if local:
        return {"encontrado": True, "nombre": local[0], "marca": "Guardado por ti", 
                "k100": local[1], "p100": local[2], "c100": local[3], "g100": local[4]}

    Variantes = [codigo]
    if len(codigo) == 12:
        Variantes.append("0" + codigo)

    endpoints = [
        "https://es.openfoodfacts.org/api/v2/product/{}.json",
        "https://world.openfoodfacts.org/api/v2/product/{}.json",
        "https://world.openfoodfacts.org/api/v0/product/{}.json"
    ]
    headers = {"User-Agent": "ArgonFitPro/2.0 (Android; ES)"}
    
    for cod in Variantes:
        for url_base in endpoints:
            try:
                r = requests.get(url_base.format(cod), headers=headers, timeout=4)
                if r.status_code == 200:
                    data = r.json()
                    if data.get("status") == 1 and "product" in data:
                        p = data["product"]
                        nom = p.get("product_name_es") or p.get("product_name") or p.get("generic_name_es") or "Producto detectado"
                        marca = p.get("brands", "")
                        nut = p.get("nutriments", {})
                        k100 = float(nut.get("energy-kcal_100g") or nut.get("energy-kcal_value") or (float(nut.get("energy_100g", 0)) / 4.184) or 0)
                        p100 = float(nut.get("proteins_100g") or 0)
                        c100 = float(nut.get("carbohydrates_100g") or 0)
                        g100 = float(nut.get("fat_100g") or 0)
                        return {"encontrado": True, "nombre": nom, "marca": marca, 
                                "k100": k100, "p100": p100, "c100": c100, "g100": g100}
            except Exception:
                continue
    return {"encontrado": False}

# --- 4. BARRA LATERAL ---
with st.sidebar:
    st.title("⚙️ Argón Fit Pro")
    fecha_activa = st.date_input("📍 Día de registro:", date.today())
    fecha_activa_str = fecha_activa.isoformat()
    
    df_sem = obtener_historial_macros_dias(7)
    dias_cumplidos = len(df_sem[df_sem['proteina'] >= OBJETIVOS_BASE['proteina'] * 0.9]) if not df_sem.empty else 0
    st.metric("🔥 Racha Proteína (7d)", f"{dias_cumplidos} / 7 días")
    
    st.divider()
    act_hoy, sal_hoy, est_hoy = obtener_evento(fecha_activa_str)
    st.subheader("📌 Plan del Día")
    st.write(f"**🏃 Actividad:** {act_hoy}")
    if sal_hoy:
        st.write(f"**🍕 Evento:** {sal_hoy}")

# --- 5. CÁLCULO DE MACROS DEL DÍA ---
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

# --- 6. PESTAÑAS PRINCIPALES ---
tab_panel, tab_calendario, tab_nevera, tab_progreso, tab_coach = st.tabs([
    "📊 Panel y Foto IA", 
    "📅 Calendario", 
    "🍳 Cocinero",
    "⚖️ Peso y Gráficas",
    "🏋️ Entrenador y Rutina"
])

# ==============================================================================
# PESTAÑA 1: PANEL DIARIO (EL REGISTRO DE COMIDAS SOLO APARECE AQUÍ)
# ==============================================================================
with tab_panel:
    st.header(f"📊 Balance ({fecha_activa.strftime('%d/%m/%Y')})")
    
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("🔥 Calorías", f"{consumido['calorias']} / {OBJETIVOS_BASE['calorias']}", f"{rest_kcal} libres", delta_color="off")
        st.progress(min(consumido['calorias'] / OBJETIVOS_BASE['calorias'], 1.0))
    with col2:
        st.metric("🍗 Proteína", f"{consumido['proteina']} / {OBJETIVOS_BASE['proteina']}g", f"Faltan {rest_prot}g", delta_color="off")
        st.progress(min(consumido['proteina'] / OBJETIVOS_BASE['proteina'], 1.0))
    with col3:
        st.metric("🍚 Hidratos", f"{consumido['hidratos']} / {OBJETIVOS_BASE['hidratos']}g", f"{rest_ch}g libres", delta_color="off")
        st.progress(min(consumido['hidratos'] / OBJETIVOS_BASE['hidratos'], 1.0))
    with col4:
        st.metric("🥑 Grasas", f"{consumido['grasas']} / {OBJETIVOS_BASE['grasas']}g", f"{rest_gr}g libres", delta_color="off")
        st.progress(min(consumido['grasas'] / OBJETIVOS_BASE['grasas'], 1.0))

    if est_hoy:
        st.info(f"💡 **Estrategia activa hoy ({act_hoy}):**\n\n{est_hoy}")

    st.divider()
    col_input, col_hist = st.columns([1.1, 1])
    
    with col_input:
        st.subheader("🍽️ Registrar Comida")
        modo_registro = st.radio(
            "Elige el método de entrada:", 
            ["✍️ Por Texto", "📸 Por Foto / Etiqueta", "🏷️ Código de Barras"], 
            horizontal=True
        )
        
        if modo_registro == "✍️ Por Texto":
            comida_texto = st.text_area("Describe tu plato:", placeholder="Ej: 150g de arroz con 2 latas de atún...", height=90)
            if st.button("➕ Calcular y Añadir", type="primary", use_container_width=True):
                if comida_texto:
                    with st.spinner("Calculando macros..."):
                        try:
                            instruccion = f"Plato: '{comida_texto}'. Devuelve ÚNICAMENTE 4 números enteros separados por espacio: Calorias Proteinas Hidratos Grasas."
                            res = llamar_ia(instruccion)
                            nums = [int(s) for s in res.text.strip().split() if s.isdigit()]
                            if len(nums) >= 4:
                                k, p, c, g = nums[:4]
                                agregar_comida(fecha_activa_str, comida_texto, k, p, c, g)
                                st.rerun()
                            else:
                                st.error("Detalla un poco más las cantidades.")
                        except Exception as err:
                            st.error(f"Error temporal de conexión: {err}")

        elif modo_registro == "📸 Por Foto / Etiqueta":
            st.caption("Sube o haz foto a tu plato, o directamente a la tabla nutricional de un envase.")
            archivo_img = st.file_uploader("Seleccionar o hacer foto:", type=["jpg", "jpeg", "png", "webp"])
            contexto_extra = st.text_input("Nota opcional (ej: '250g', '1 envase entero', 'con 1 cucharada de aceite'):")
            if archivo_img is not None:
                img_abierta = Image.open(archivo_img)
                st.image(img_abierta, use_container_width=True)
                if st.button("📸 Analizar Imagen y Guardar", type="primary", use_container_width=True):
                    with st.spinner("Analizando imagen..."):
                        try:
                            p_img = (
                                f"Analiza este alimento o tabla nutricional (Nota del usuario: '{contexto_extra}'). "
                                "Responde EXACTAMENTE en 2 líneas:\n"
                                "L1: Nombre corto del plato/producto y cantidad estimada\n"
                                "L2: 4 enteros separados por espacio (Calorias Proteinas Hidratos Grasas)"
                            )
                            res = llamar_ia([img_abierta, p_img])
                            partes = [x.strip() for x in res.text.strip().split('\n') if x.strip()]
                            if len(partes) >= 2:
                                nombre_plato = partes[0].replace("L1:", "").strip()
                                nums = [int(s) for s in partes[-1].replace("L2:", "").strip().split() if s.isdigit()]
                                if len(nums) >= 4:
                                    k, p, c, g = nums[:4]
                                    agregar_comida(fecha_activa_str, f"📸 {nombre_plato}", k, p, c, g)
                                    st.rerun()
                        except Exception as err:
                            st.error(f"Fallo al procesar: {err}")

        elif modo_registro == "🏷️ Código de Barras":
            foto_ean = st.camera_input("📷 Capturar código de barras")
            ean_escrito = st.text_input("🔢 O escribe / corrige los 13 dígitos (ej: 8480000...):")
            
            if ean_escrito.strip():
                st.session_state['ean_actual'] = "".join(filter(str.isdigit, ean_escrito.strip()))
            elif foto_ean is not None:
                id_foto = foto_ean.size
                if st.session_state.get('ultima_foto_id') != id_foto:
                    with st.spinner("Leyendo los 13 dígitos del código..."):
                        try:
                            img_ean = Image.open(foto_ean)
                            prompt_ean = (
                                "Lee todos los números impresos debajo de las barras de este código EAN-13. "
                                "Une el primer dígito suelto de la izquierda con los dos bloques siguientes (13 dígitos en total). "
                                "Devuelve ÚNICAMENTE los 13 números seguidos sin espacios."
                            )
                            res_ean = llamar_ia([img_ean, prompt_ean])
                            st.session_state['ean_actual'] = "".join(filter(str.isdigit, res_ean.text))
                            st.session_state['ultima_foto_id'] = id_foto
                        except Exception as err:
                            st.error(f"Error al leer imagen, escríbelo manualmente arriba: {err}")
            else:
                st.session_state['ean_actual'] = ""

            codigo_activo = st.session_state.get('ean_actual', '')

            if codigo_activo:
                st.info(f"🔢 Código activo: **{codigo_activo}**")
                info_prod = buscar_codigo_barras_global(codigo_activo)

                if info_prod.get("encontrado"):
                    nom = info_prod["nombre"]
                    marca = info_prod["marca"]
                    k100, p100, c100, g100 = info_prod["k100"], info_prod["p100"], info_prod["c100"], info_prod["g100"]
                    
                    st.success(f"🛒 **{nom}** {f'({marca})' if marca else ''}")
                    st.caption(f"Por 100g/ml: 🔥 {int(k100)} kcal | 🍗 {p100:.1f}g P | 🍚 {c100:.1f}g CH | 🥑 {g100:.1f}g G")
                    
                    peso_racion = st.number_input("⚖️ Gramos o ml consumidos:", min_value=1, max_value=2000, value=100, step=10)
                    ratio = peso_racion / 100.0
                    k_fin, p_fin, c_fin, g_fin = int(k100 * ratio), int(p100 * ratio), int(c100 * ratio), int(g100 * ratio)
                    
                    if st.button("➕ Guardar Producto", type="primary", use_container_width=True):
                        agregar_comida(fecha_activa_str, f"🏷️ {peso_racion}g {nom}", k_fin, p_fin, c_fin, g_fin)
                        st.session_state['ean_actual'] = ""
                        st.rerun()
                else:
                    st.warning("⚠️ Este código de marca propia aún no está en la base de datos pública. Regístralo una sola vez aquí (o haz foto a su tabla nutricional) y tu app lo recordará para siempre:")
                    nom_nuevo = st.text_input("Nombre del producto:", placeholder="Ej: Batido frutas Mercadona")
                    c_a, c_b, c_c, c_d = st.columns(4)
                    k_n = c_a.number_input("Kcal/100g", 0, 900, 65)
                    p_n = c_b.number_input("Prot/100g", 0.0, 100.0, 3.0, step=0.5)
                    ch_n = c_c.number_input("CH/100g", 0.0, 100.0, 10.0, step=0.5)
                    g_n = c_d.number_input("Grasa/100g", 0.0, 100.0, 1.0, step=0.5)
                    gramos_ahora = st.number_input("Gramos o ml que vas a tomar ahora:", 1, 2000, 250, step=10)
                    
                    if st.button("💾 Guardar para siempre y Añadir hoy", type="primary", use_container_width=True):
                        if nom_nuevo:
                            conn = sqlite3.connect('nutricion_argon.db')
                            c = conn.cursor()
                            c.execute("INSERT OR REPLACE INTO mis_productos VALUES (?, ?, ?, ?, ?, ?)",
                                      (codigo_activo, nom_nuevo, k_n, p_n, ch_n, g_n))
                            conn.commit()
                            conn.close()
                            r_ahora = gramos_ahora / 100.0
                            agregar_comida(fecha_activa_str, f"🏷️ {gramos_ahora}g {nom_nuevo}", int(k_n*r_ahora), int(p_n*r_ahora), int(ch_n*r_ahora), int(g_n*r_ahora))
                            st.session_state['ean_actual'] = ""
                            st.rerun()

    with col_hist:
        st.subheader("📋 Registro del Día")
        if comidas_hoy:
            for item in comidas_hoy:
                id_c, hora_c, desc_c, k_c, p_c, ch_c, g_c = item
                with st.container(border=True):
                    c_txt, c_del = st.columns([5, 1])
                    c_txt.markdown(f"**⏰ {hora_c}** - {desc_c}")
                    c_txt.caption(f"🔥 {k_c} kcal | 🍗 {p_c}g P | 🍚 {ch_c}g CH | 🥑 {g_c}g G")
                    if c_del.button("🗑️", key=f"del_{id_c}"):
                        borrar_comida(id_c)
                        st.rerun()
        else:
            st.caption("Aún no has registrado comidas en esta fecha.")
    st.markdown("<br><br>", unsafe_allow_html=True)

# ==============================================================================
# PESTAÑA 2: CALENDARIO HORIZONTAL (VISTA MENSUAL COMPLETA EN MÓVIL Y PC)
# ==============================================================================
with tab_calendario:
    st.subheader("🗓️ Calendario Mensual")

    # Función auxiliar para dibujar el mes como una tabla HTML real (siempre 7 columnas en horizontal, incluso en móvil)
    def render_calendario_compacto(anio, mes, dic_eventos):
        matriz = calendar.monthcalendar(anio, mes)
        cabeceras = ["L", "M", "X", "J", "V", "S", "D"]
        html = "<table style='width:100%; border-collapse:collapse; table-layout:fixed; text-align:center; background:#181825; color:#CDD6F4; border-radius:8px; overflow:hidden;'>"
        html += "<tr style='background:#1E1E2E; font-size:0.8rem;'>" + "".join([f"<th style='padding:6px; border:1px solid #313244;'>{d}</th>" for d in cabeceras]) + "</tr>"
        
        hoy_iso = date.today().isoformat()
        for sem in matriz:
            html += "<tr>"
            for d in sem:
                if d == 0:
                    html += "<td style='height:58px; border:1px solid #313244; background:#11111B; opacity:0.3;'></td>"
                else:
                    f_iso = f"{anio}-{mes:02d}-{d:02d}"
                    borde_hoy = "border:2px solid #F38BA8; background:#1E1E2E;" if f_iso == hoy_iso else "border:1px solid #313244;"
                    etiquetas = ""
                    if f_iso in dic_eventos:
                        act_e, sal_e, _ = dic_eventos[f_iso]
                        if act_e and act_e != "Descanso":
                            corto = act_e.split()[0][:6]
                            etiquetas += f"<div style='background:#89B4FA; color:#11111B; font-size:0.6rem; border-radius:3px; margin:1px; padding:1px; font-weight:bold; overflow:hidden; white-space:nowrap;'>{corto}</div>"
                        if sal_e:
                            corto_s = sal_e[:6]
                            etiquetas += f"<div style='background:#F9E2AF; color:#11111B; font-size:0.6rem; border-radius:3px; margin:1px; padding:1px; font-weight:bold; overflow:hidden; white-space:nowrap;'>{corto_s}</div>"
                    html += f"<td style='height:58px; vertical-align:top; padding:2px; {borde_hoy}'><div style='font-size:0.75rem; font-weight:bold;'>{d}</div>{etiquetas}</td>"
            html += "</tr>"
        html += "</table>"
        return html

    lista_meses = ["Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio", "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"]
    col_m1, col_m2 = st.columns([2, 1])
    mes_elegido = col_m1.selectbox("Mes", lista_meses, index=date.today().month - 1)
    num_mes = lista_meses.index(mes_elegido) + 1
    num_anio = col_m2.number_input("Año", min_value=2025, max_value=2030, value=date.today().year)

    eventos_del_mes = obtener_todos_eventos_mes(num_anio, num_mes)
    st.markdown(render_calendario_compacto(num_anio, num_mes, eventos_del_mes), unsafe_allow_html=True)

    st.write("")
    with st.expander("➕ Programar o Modificar Días en el Calendario", expanded=False):
        rango_sel = st.date_input("Fechas (Inicio y Fin):", value=(date.today(), date.today()), format="DD/MM/YYYY")
        act_input = st.selectbox(
            "Actividad física:",
            ["Descanso", "Gimnasio (Pecho/Tríceps)", "Gimnasio (Espalda/Bíceps)", "Gimnasio (Pierna/Hombro)", "Gimnasio (Full Body)", "Fútbol", "Cardio / Caminata"]
        )
        evento_input = st.text_input("Evento o comida especial:", placeholder="Ej: Cena fuera, Cumpleaños...")
        pedir_ia_cal = st.checkbox("Generar consejo nutricional con IA", value=False)

        b_save, b_del = st.columns(2)
        if b_save.button("💾 Guardar Rango", type="primary", use_container_width=True):
            f_i, f_f = (rango_sel[0], rango_sel[1]) if isinstance(rango_sel, tuple) and len(rango_sel) == 2 else (rango_sel[0] if isinstance(rango_sel, tuple) else rango_sel, rango_sel[0] if isinstance(rango_sel, tuple) else rango_sel)
            plan_txt = ""
            if pedir_ia_cal:
                with st.spinner("Generando estrategia..."):
                    try:
                        cli = obtener_cliente_ia()
                        p_cal = f"Meta: 2400kcal, 150g P. Del {f_i} al {f_f} haré {act_input} y evento '{evento_input}'. Dame 3 pautas breves."
                        for m_name in ['gemini-3.8-flash', 'gemini-3.8-flash', 'gemini-3.8-flash']:
                            try:
                                plan_txt = cli.models.generate_content(model=m_name, contents=p_cal).text
                                break
                            except Exception:
                                continue
                    except Exception as e:
                        st.error(f"Error IA: {e}")
            guardar_rango_eventos(f_i, f_f, act_input, evento_input, plan_txt)
            st.rerun()

        if b_del.button("🗑️ Borrar Rango", use_container_width=True):
            f_i, f_f = (rango_sel[0], rango_sel[1]) if isinstance(rango_sel, tuple) and len(rango_sel) == 2 else (rango_sel[0] if isinstance(rango_sel, tuple) else rango_sel, rango_sel[0] if isinstance(rango_sel, tuple) else rango_sel)
            borrar_rango_eventos(f_i, f_f)
            st.rerun()

# ==============================================================================
# PESTAÑA 3: COCINERO DE NEVERA (ULTRA-RÁPIDO CON STREAMING)
# ==============================================================================
with tab_nevera:
    st.subheader("🍳 Cocinero Inteligente Express")

    conn_d = sqlite3.connect('nutricion_argon.db')
    cur_d = conn_d.cursor()
    cur_d.execute("CREATE TABLE IF NOT EXISTS config_usuario (clave TEXT PRIMARY KEY, valor TEXT)")
    cur_d.execute("SELECT valor FROM config_usuario WHERE clave = 'mi_despensa'")
    fila_desp = cur_d.fetchone()
    despensa_actual = fila_desp[0] if fila_desp else "Pechuga de pollo, huevos, arroz, pasta, patatas, atún, leche, yogur griego, espinacas, champiñones"
    conn_d.close()

    with st.expander("🗄️ Mi Nevera y Despensa", expanded=False):
        nueva_despensa = st.text_area("Ingredientes disponibles:", value=despensa_actual, height=80)
        if st.button("💾 Guardar despensa"):
            conn_d = sqlite3.connect('nutricion_argon.db')
            conn_d.execute("INSERT OR REPLACE INTO config_usuario VALUES ('mi_despensa', ?)", (nueva_despensa,))
            conn_d.commit()
            conn_d.close()
            st.success("¡Despensa actualizada!")
            st.rerun()

    c_toma, c_tiempo = st.columns(2)
    toma_elegida = c_toma.selectbox("🍽️ Comida:", ["Comida (600-750 kcal)", "Cena (500-650 kcal)", "Desayuno / Merienda (350-450 kcal)"])
    tiempo_max = c_tiempo.selectbox("⏱️ Tiempo:", ["10 min (Express)", "20 min (Normal)"])

    if st.button("⚡ Generar 2 Platos al Instante", type="primary", use_container_width=True):
        prompt_chef = (
            f"Sé directo y conciso. Dame 2 recetas rápidas para {toma_elegida} en máximo {tiempo_max}. "
            f"Usa principalmente estos ingredientes: {nueva_despensa}. "
            f"Formato por plato: Nombre, Ingredientes en gramos (para 1 persona), 3 pasos cortos y Macros totales."
        )
        cli = obtener_cliente_ia()
        with st.container(border=True):
            try:
                # Usamos directamente el modelo Flash en modo streaming para respuesta inmediata
                respuesta_stream = cli.models.generate_content_stream(
                    model='gemini-3.8-flash',
                    contents=prompt_chef
                )
                texto_completo = st.write_stream(chunk.text for chunk in respuesta_stream if chunk.text)
                st.session_state['receta_activa'] = texto_completo
            except Exception as e:
                st.error(f"Error de conexión: {e}")

    elif 'receta_activa' in st.session_state:
        with st.container(border=True):
            st.markdown(st.session_state['receta_activa'])

# ==============================================================================
# PESTAÑA 4: BÁSCULA + IMPORTADOR ZEPP LIFE
# ==============================================================================
with tab_progreso:
    st.subheader("⚖️ Evolución Corporal y Conexión Zepp Life")
    col_p1, col_p2 = st.columns([1.1, 1.7])

    with col_p1:
        with st.container(border=True):
            st.markdown("#### ✍️ Registro Manual")
            f_pesaje = st.date_input("Fecha:", date.today(), key="f_peso_tab")
            v_peso = st.number_input("Peso (kg):", 40.0, 160.0, 75.0, 0.1)
            v_grasa = st.number_input("% Grasa:", 3.0, 50.0, 15.0, 0.1)
            v_musc = st.number_input("Masa Muscular (kg):", 20.0, 100.0, 58.0, 0.1)
            if st.button("💾 Guardar Pesaje", type="primary", use_container_width=True):
                guardar_corporal(f_pesaje.isoformat(), v_peso, v_grasa, v_musc, "Manual")
                st.success("Guardado.")
                st.rerun()

        with st.expander("📲 Sincronizar con Zepp Life (CSV)"):
            st.caption("En Zepp Life ve a: **Perfil > Ajustes > Seguridad de la cuenta > Exportar datos > Corporal (Body)** y sube aquí el archivo `.csv` generado.")
            archivo_zepp = st.file_uploader("Sube el CSV de Zepp Life", type=["csv"])
            if archivo_zepp is not None:
                df_z = pd.read_csv(archivo_zepp)
                st.dataframe(df_z.tail(3), use_container_width=True)
                if st.button("📥 Importar todo el historial de Zepp Life", use_container_width=True):
                    conn_z = sqlite3.connect('nutricion_argon.db')
                    importados = 0
                    for _, row in df_z.iterrows():
                        try:
                            # Detecta las columnas estándar del exportador de Zepp Life / Xiaomi
                            f_raw = str(row.get('time', row.get('date', row.iloc[0])))[:10]
                            p_val = float(row.get('weight', row.iloc[1]))
                            g_val = float(row.get('fatRate', row.get('bodyFat', 15.0))) if pd.notna(row.get('fatRate', row.get('bodyFat', None))) else 15.0
                            m_val = float(row.get('muscleRate', row.get('muscle', 58.0))) if pd.notna(row.get('muscleRate', row.get('muscle', None))) else 58.0
                            conn_z.execute("INSERT OR REPLACE INTO corporal VALUES (?, ?, ?, ?, ?)", (f_raw, p_val, g_val, m_val, "Zepp Life"))
                            importados += 1
                        except Exception:
                            continue
                    conn_z.commit()
                    conn_z.close()
                    st.success(f"¡{importados} pesajes de tu báscula importados!")
                    st.rerun()

    with col_p2:
        df_c = obtener_historial_corporal()
        if not df_c.empty:
            st.line_chart(df_c.set_index('fecha')[['peso', 'grasa']])
            with st.expander("Ver tabla de registros"):
                st.dataframe(df_c, use_container_width=True, hide_index=True)
        else:
            st.info("Aún no hay pesajes registrados.")

# ==============================================================================
# PESTAÑA 5: ENTRENAMIENTO POR DESPLEGABLES Y PESOS (+ BACKUP DE SEGURIDAD)
# ==============================================================================
with tab_coach:
    st.subheader("🏋️‍♂️ Control de Cargas por Grupo Muscular")

    # Catálogo base de tus ejercicios habituales por grupo
    CATALOGO_EJERCICIOS = {
        "Espalda": ["Jalón al pecho", "Remo en polea baja", "Remo con mancuerna", "Remo en máquina", "Pull-over en polea"],
        "Pecho": ["Press de banca", "Press inclinado mancuernas", "Press en máquina", "Cruce de poleas", "Pec-Deck (Aperturas)"],
        "Hombro": ["Press de hombro en máquina", "Press militar mancuernas", "Elevaciones laterales", "Pájaros (Deltoides post.)"],
        "Bíceps y Tríceps": ["Curl de bíceps con mancuernas", "Curl martillo", "Curl en polea", "Extensión de tríceps en polea", "Press francés / Tras nuca"],
        "Pierna": ["Prensa inclinada", "Extensión de cuádriceps", "Curl femoral", "Máquina de abductores", "Elevación de gemelos"]
    }

    conn_w = sqlite3.connect('nutricion_argon.db')
    cur_w = conn_w.cursor()
    # Tabla para guardar el peso actual de cada ejercicio y el historial
    cur_w.execute("CREATE TABLE IF NOT EXISTS pesos_ejercicios (ejercicio TEXT PRIMARY KEY, grupo TEXT, peso REAL, series_reps TEXT, fecha_mod TEXT)")
    cur_w.execute("CREATE TABLE IF NOT EXISTS log_series (id INTEGER PRIMARY KEY AUTOINCREMENT, fecha TEXT, grupo TEXT, ejercicio TEXT, peso REAL, series_reps TEXT)")
    cur_w.execute("SELECT ejercicio, peso, series_reps, fecha_mod FROM pesos_ejercicios")
    guardados = {fila[0]: (fila[1], fila[2], fila[3]) for fila in cur_w.fetchall()}
    conn_w.close()

    st.caption("Ajusta el peso con los botones **- / +** y pulsa Guardar en el bloque que hayas entrenado hoy. El último peso se queda memorizado para tu próximo día.")

    # Desplegables divididos por grupo muscular
    for grupo, lista_ejs in CATALOGO_EJERCICIOS.items():
        with st.expander(f"💪 {grupo}", expanded=(grupo in ["Espalda", "Pecho"])):
            cambios_grupo = []
            for ej in lista_ejs:
                peso_previo, reps_previas, ult_fecha = guardados.get(ej, (20.0, "3x10", "Sin registro"))
                c1, c2, c3 = st.columns([2.2, 1.5, 1.3])
                c1.markdown(f"**{ej}**  \n<span style='font-size:0.75rem; color:#A6ADC8;'>Última vez: {ult_fecha}</span>", unsafe_allow_html=True)
                nuevo_peso = c2.number_input("Peso (kg)", min_value=0.0, max_value=300.0, value=float(peso_previo), step=2.5, key=f"peso_{ej}", label_visibility="collapsed")
                nuevas_reps = c3.selectbox("Series", ["4x8", "4x10", "3x10", "3x12", "3x15"], index=["4x8", "4x10", "3x10", "3x12", "3x15"].index(reps_previas) if reps_previas in ["4x8", "4x10", "3x10", "3x12", "3x15"] else 2, key=f"reps_{ej}", label_visibility="collapsed")
                cambios_grupo.append((ej, nuevo_peso, nuevas_reps))

            if st.button(f"💾 Guardar sesión de {grupo}", key=f"btn_save_{grupo}", type="primary", use_container_width=True):
                hoy_str = date.today().isoformat()
                conn_w = sqlite3.connect('nutricion_argon.db')
                for ej_nom, p_val, r_val in cambios_grupo:
                    conn_w.execute("INSERT OR REPLACE INTO pesos_ejercicios VALUES (?, ?, ?, ?, ?)", (ej_nom, grupo, p_val, r_val, hoy_str))
                    conn_w.execute("INSERT INTO log_series (fecha, grupo, ejercicio, peso, series_reps) VALUES (?, ?, ?, ?, ?)", (hoy_str, grupo, ej_nom, p_val, r_val))
                conn_w.commit()
                conn_w.close()
                guardar_rango_eventos(date.today(), date.today(), f"Gimnasio ({grupo})", sal_hoy, est_hoy)
                st.success(f"¡Pesos de {grupo} actualizados y sesión registrada en el calendario!")
                st.rerun()

    st.divider()
    # Sistema de seguridad para evitar el borrado de Streamlit Cloud
    with st.expander("🛡️ Copia de Seguridad de tus Datos (Evitar borrados de la nube)"):
        st.caption("Streamlit Cloud borra el archivo local cuando reinicia el servidor. Descarga tu archivo al terminar la semana o súbelo aquí si ves que la app se ha reiniciado.")
        c_b1, c_b2 = st.columns(2)
        with open("nutricion_argon.db", "rb") as fp:
            c_b1.download_button("⬇️ Descargar mis datos (.db)", data=fp, file_name=f"backup_argon_{date.today().isoformat()}.db", mime="application/octet-stream", use_container_width=True)
        db_subida = c_b2.file_uploader("⬆️ Restaurar copia (.db)", type=["db"], label_visibility="collapsed")
        if db_subida is not None:
            if st.button("🔄 Aplicar copia restaurada", use_container_width=True):
                with open("nutricion_argon.db", "wb") as f_out:
                    f_out.write(db_subida.getbuffer())
                st.success("¡Base de datos restaurada al 100%!")
                st.rerun()

# ==============================================================================
# PESTAÑA 5: ENTRENADOR DE GIMNASIO (RUTINAS, VARIANTES Y REORGANIZACIÓN)
# ==============================================================================
with tab_coach:
    st.subheader("🏋️‍♂️ Entrenador Personal y Planificador de Rutina")

    conn_e = sqlite3.connect('nutricion_argon.db')
    cur_e = conn_e.cursor()
    cur_e.execute("CREATE TABLE IF NOT EXISTS historial_entrenos (fecha TEXT PRIMARY KEY, grupo_muscular TEXT, notas TEXT)")
    cur_e.execute("SELECT fecha, grupo_muscular, notas FROM historial_entrenos ORDER BY fecha DESC LIMIT 7")
    ultimos_entrenos = cur_e.fetchall()
    conn_e.close()

    col_e1, col_e2 = st.columns([1, 1.4])

    with col_e1:
        with st.container(border=True):
            st.markdown("#### ✅ ¿Qué has entrenado hoy?")
            f_ent = st.date_input("Día de entreno:", fecha_activa, key="f_entreno_coach")
            grupo_hecho = st.selectbox(
                "Grupo muscular / Actividad realizada:",
                [
                    "Empuje (Pecho, Hombro, Tríceps)",
                    "Tirón (Espalda, Bíceps, Deltoides post.)",
                    "Pierna Completa y Core",
                    "Torso (Pecho y Espalda)",
                    "Brazos y Hombros",
                    "Full Body",
                    "Partido / Entreno de Fútbol",
                    "Descanso / No pude ir"
                ]
            )
            notas_ent = st.text_input("Notas (ej: Molestia en hombro, subí peso en banca...):")
            if st.button("💾 Registrar Entreno Realizado", type="primary", use_container_width=True):
                conn_e = sqlite3.connect('nutricion_argon.db')
                conn_e.execute("INSERT OR REPLACE INTO historial_entrenos VALUES (?, ?, ?)", (f_ent.isoformat(), grupo_hecho, notas_ent))
                conn_e.commit()
                conn_e.close()
                guardar_rango_eventos(f_ent, f_ent, grupo_hecho, sal_hoy, est_hoy)
                st.success("¡Entreno guardado en tu historial y calendario!")
                st.rerun()

        st.markdown("#### 📜 Tus últimos entrenamientos")
        if ultimos_entrenos:
            for fe_h, gr_h, no_h in ultimos_entrenos:
                st.caption(f"📅 **{fe_h}**: {gr_h} {f'({no_h})' if no_h else ''}")
        else:
            st.caption("Aún no has registrado entrenos. Registra qué hiciste ayer u hoy para que el entrenador adapte tu semana.")

    with col_e2:
        with st.container(border=True):
            st.markdown("#### 🧠 Generar Rutina del Día y Reorganizar Semana")
            forzar_grupo = st.selectbox(
                "¿Qué quieres entrenar hoy?",
                ["🤖 Que la IA decida según mi historial reciente", "Pecho y Tríceps", "Espalda y Bíceps", "Pierna y Hombro", "Torso Completo", "Full Body", "Cambiar plan: Hoy no puedo hacer lo que tocaba"]
            )
            material_disp = st.text_input("Preferencias o máquinas ocupadas hoy:", placeholder="Ej: No quiero hacer peso muerto libre, dame alternativas en máquina...")

            if st.button("⚡ Generar Entreno con Alternativas + Plan Nutricional", type="primary", use_container_width=True):
                with st.spinner("Analizando tu historial muscular y preparando ejercicios y variantes..."):
                    resumen_hist = "; ".join([f"{x[0]}: {x[1]}" for x in ultimos_entrenos]) if ultimos_entrenos else "Sin registros previos"
                    prompt_rutina = (
                        f"Actúa como entrenador personal de hipertrofia y rendimiento. Hoy es {fecha_activa_str}.\n"
                        f"- Historial real de mis últimos entrenamientos: {resumen_hist}.\n"
                        f"- Elección para hoy: {forzar_grupo}.\n"
                        f"- Condición especial hoy: {material_disp if material_disp else 'Gimnasio completo disponible'}.\n"
                        f"- Macros que llevo hoy: {consumido['calorias']}/2400 kcal y {consumido['proteina']}/150g proteína.\n\n"
                        f"Responde con esta estructura clara:\n"
                        f"1. **QUÉ TOCA HOY Y REAJUSTE SEMANAL**: Explica qué grupo muscular toca hoy según lo que hice los días anteriores y cómo quedan reorganizados los próximos 4 días si he cambiado el orden.\n"
                        f"2. **RUTINA PRINCIPAL DE HOY (5-6 ejercicios)**: Indica series, repeticiones y RIR/descanso.\n"
                        f"3. **BANCO DE EJERCICIOS ALTERNATIVOS (3-4 variantes extra)**: Para cada ejercicio principal, dame al menos 1 o 2 variantes equivalentes (mancuernas, poleas o máquinas) por si está ocupado o no me apetece hacerlo.\n"
                        f"4. **CONSEJO RÁPIDO PRE/POST ENTRENO**: Qué comer hoy según los macros que me faltan."
                    )
                    cli = obtener_cliente_ia()
                    respuesta_coach = None
                    for m_name in ['gemini-3.8-flash', 'gemini-3.8-flash', 'gemini-3.8-flash']:
                        try:
                            respuesta_coach = cli.models.generate_content(model=m_name, contents=prompt_rutina).text
                            break
                        except Exception:
                            continue
                    if respuesta_coach:
                        st.session_state['rutina_ia_actual'] = respuesta_coach
                    else:
                        st.error("Servidores saturados temporalmente. Inténtalo de nuevo en unos segundos.")

            if 'rutina_ia_actual' in st.session_state:
                st.markdown(st.session_state['rutina_ia_actual'])

    st.markdown("<br><br>", unsafe_allow_html=True)
