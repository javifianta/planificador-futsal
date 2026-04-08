import streamlit as st
import google.generativeai as genai
from dotenv import load_dotenv
import os
import json
import pandas as pd
from pathlib import Path
import datetime
import uuid
import firebase_admin
from firebase_admin import credentials, firestore
try:
    from pypdf import PdfReader
    import io
    import re
except ImportError:
    pass

# --- 1. Configuración y Seguridad ---
load_dotenv()

st.set_page_config(
    page_title="Planificador Físico Futsal",
    page_icon="logo.jpg",
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- CSS Personalizado (UI Estilo Dark Mode + Fix Dropdowns) ---
st.markdown("""
<style>
    /* Ocultar menú de Streamlit */
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    
    /* Configuración Base */
    .stApp {
        background-color: #0e1117;
    }
    
    /* Texto General */
    h1, h2, h3, h4, h5, h6, p, li, span, div, label {
        color: #e6e6e6 !important;
        font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
    }
    
    /* === FIX DEFINITIVO DROPDOWNS: NUCLEAR OPTION === */
    /* Apuntar a cualquier contenedor de menú desplegable de Streamlit/BaseWeb */
    div[data-baseweb="popover"] > div, div[data-baseweb="menu"], div[role="listbox"] {
        background-color: #ffffff !important;
    }
    
    /* Forzar TEXTO NEGRO en todo lo que esté dentro del popover */
    div[data-baseweb="popover"] * {
        color: #000000 !important;
        background-color: transparent !important; /* Heredar blanco del padre */
    }
    
    /* Excepción para el hover/selected para que se vea bonito */
    div[role="listbox"] li:hover, div[role="listbox"] li[aria-selected="true"] {
        background-color: #00ff41 !important; /* Verde Neón */
    }
    
    /* Asegurarse que el texto en hover siga siendo negro */
    div[role="listbox"] li:hover *, div[role="listbox"] li[aria-selected="true"] * {
        color: #000000 !important;
        background-color: transparent !important;
    }

    /* === FIX INPUTS CERRADOS (Selectbox & Multiselect) === */
    /* El contenedor principal del input cuando está cerrado */
    .stSelectbox div[data-baseweb="select"] > div,
    .stMultiSelect div[data-baseweb="select"] > div {
        background-color: #ffffff !important;
        color: #000000 !important;
        border: 1px solid #ccc !important;
    }
    
    /* Texto interno y flecha (SVG) */
    .stSelectbox div[data-baseweb="select"] *,
    .stMultiSelect div[data-baseweb="select"] *,
    .stSelectbox svg, .stMultiSelect svg {
        color: #000000 !important;
        fill: #000000 !important;
    }
    
  

    /* Multiselect Tags */
    .stMultiSelect div[data-baseweb="tag"] {
        background-color: #00ff41 !important;
        color: black !important;
    }

    /* Sidebar */
    [data-testid="stSidebar"] {
        background-color: #161b22;
        border-right: 1px solid #30363d;
    }
    [data-testid="stSidebar"] h1, [data-testid="stSidebar"] h2 {
        color: #00ff41 !important;
    }
    
    /* Botones */
    .stButton>button {
        background-color: #00ff41;
        color: #000000 !important;
        border-radius: 8px;
        border: none;
        font-weight: bold;
    }
    .stButton>button:hover {
        background-color: #00cc33;
        box-shadow: 0 0 10px rgba(0, 255, 65, 0.5);
    }
    button.delete-btn {
        background-color: #ff4b4b !important;
        color: white !important;
    }
    
    /* Inputs */
    .stTextInput input, .stNumberInput input, .stTextArea textarea {
        background-color: #0d1117 !important;
        color: #ffffff !important;
        border: 1px solid #30363d;
        border-radius: 8px;
    }
    
    /* Headers */
    .main-header {
        color: #00ff41 !important;
        font-size: 2.5rem;
        font-weight: 700;
        margin-bottom: 1rem;
    }
    .section-header {
        color: #00ff41 !important;
        font-size: 1.5rem;
        margin-top: 2rem;
        border-bottom: 2px solid #30363d;
        padding-bottom: 0.5rem;
    }
    
    .stChatMessage {
        background-color: #1c2128;
        border: 1px solid #30363d;
        border-radius: 10px;
        padding: 15px;
    }

    /* === FIX TABLAS MARKDOWN === */
    th, td {
        border: 1px solid #4a4a4a !important;
        padding: 8px !important;
    }
    thead tr th {
        background-color: #0e1117 !important;
        color: #00ff41 !important;
        font-weight: bold !important;
    }
    tbody tr:nth-child(even) {
        background-color: #161b22 !important;
    }
</style>
""", unsafe_allow_html=True)

# --- Gestión de API Key ---
api_key = os.getenv("GOOGLE_API_KEY")

# --- Persistencia y Firebase ---
DB_EQUIPOS = "equipos_db.json"
DB_PLANES = "planificaciones_db.json"

def init_firebase():
    if not firebase_admin._apps:
        try:
            if "firebase" in st.secrets:
                cred_dict = dict(st.secrets["firebase"])
                cred = credentials.Certificate(cred_dict)
                firebase_admin.initialize_app(cred)
                return True
        except: pass
        
        fb_cert = os.getenv("FIREBASE_CERT")
        if fb_cert:
            try:
                cred_dict = json.loads(fb_cert)
                cred = credentials.Certificate(cred_dict)
                firebase_admin.initialize_app(cred)
                return True
            except: pass
                
        if os.path.exists("firebase_credentials.json"):
            try:
                cred = credentials.Certificate("firebase_credentials.json")
                firebase_admin.initialize_app(cred)
                return True
            except: pass
    return bool(firebase_admin._apps)

FIREBASE_ENABLED = init_firebase()
if FIREBASE_ENABLED:
    db = firestore.client()


with st.sidebar:
    st.image("logo.jpg", use_container_width=True)
    st.title("PF Futsal Pro")
    st.markdown("---")
    if api_key:
        st.success("🟢 Licencia Activada")
        if FIREBASE_ENABLED:
            st.success("☁️ Firebase Conectado (Nube)")
        else:
            st.warning("⚠️ Guardando Localmente (Firebase Inactivo)")
            with st.expander("Configurar Nube"):
                st.info("Tus datos se borrarán al reiniciar la app local. Para guardar permanentemente, añade FIREBASE_CERT al archivo .env")
        genai.configure(api_key=api_key)
    else:
        st.warning("⚠️ Clave API requerida")
        manual_key = st.text_input("API Key:", type="password")
        if manual_key:
            os.environ["GOOGLE_API_KEY"] = manual_key
            genai.configure(api_key=manual_key)
            st.rerun()

# --- Helper: Model ---
def get_available_models():
    # Intenta obtener de manera dinámica priorizando Flash/Lite sobre Pro 
    # (Pro tira error 429 limit:0, y 1.5 tira error 404)
    try:
        available = [m.name for m in genai.list_models() if "generateContent" in m.supported_generation_methods]
        models_to_try = []
        preferencias = [
            "gemini-3.1-flash-lite",
            "gemini-2.5-flash", 
            "gemini-3-flash",
            "gemini-flash"
        ]
        for pref in preferencias:
            for a in available:
                if pref in a and "pro" not in a.lower() and a not in models_to_try:
                    models_to_try.append(a)
        
        # Fallback de seguridad usando nombres completos
        if not models_to_try:
            return ["models/gemini-2.5-flash", "models/gemini-3.1-flash-lite"]
        return models_to_try
    except:
        return ["models/gemini-2.5-flash"]




# --- Helper: PDF RAG ---
@st.cache_resource(show_spinner=False)
def load_library_context(max_chars=100000):
    """Lee PDFs de /biblioteca_futsal extrae texto hasta un límite de caracteres."""
    path = Path("biblioteca_futsal")
    full_text = ""
    file_count = 0
    
    if not path.exists():
        return "", 0
    
    files = list(path.glob("*.pdf"))
    for pdf_file in files:
        if len(full_text) >= max_chars:
            break
            
        try:
            reader = PdfReader(pdf_file)
            text = ""
            for page in reader.pages:
                text += page.extract_text() + "\n"
                if len(full_text) + len(text) >= max_chars:
                    break
            
            full_text += f"\n--- INFORMACIÓN DEL LIBRO: {pdf_file.name} ---\n{text}\n"
            file_count += 1
        except Exception as e:
            print(f"Error leyendo {pdf_file}: {e}")
            
    return full_text[:max_chars], file_count

# --- Helper: PDF Generator ---
# --- Helper: PDF Generator (Advanced) ---
def create_pdf(title, content):
    try:
        from xhtml2pdf import pisa
        import markdown
        import base64
        
        # Codificar logo en base64
        logo_path = "logo.jpg"
        logo_base64 = ""
        if os.path.exists(logo_path):
            with open(logo_path, "rb") as image_file:
                logo_base64 = base64.b64encode(image_file.read()).decode()
    except ImportError:
        return None
        
    # Convertir Markdown a HTML
    html_text = markdown.markdown(content, extensions=['tables'])
    
    # --- LOGICA DINAMICA DE ANCHOS DE COLUMNA ---
    # Detectamos las tablas y asignamos anchos segun el contenido de los headers.
    parts = html_text.split("<table>")
    new_html = parts[0]
    
    for part in parts[1:]:
        colgroup = ""
        # Buscar headers en los primeros 2000 caracteres del fragmento de tabla
        search_area = part[:2000]
        # Regex para encontrar contenido entre <th>...</th>
        headers = re.findall(r'<th.*?>(.*?)</th>', search_area, re.IGNORECASE | re.DOTALL)
        
        if headers:
            # Limpiar tags HTML internos de los headers si los hay
            clean_headers = [re.sub(r'<[^>]+>', '', h).strip().lower() for h in headers]
            
            weights = []
            for h in clean_headers:
                w = 12 # Peso base
                # Asignación de pesos heurística
                if any(x in h for x in ["ejercicio", "tarea", "actividad"]): w = 22
                elif any(x in h for x in ["foco", "descripción", "observaciones", "notas", "logística"]): w = 45 # Mucho espacio para texto largo
                elif any(x in h for x in ["intensidad", "intensity", "objetivo", "capacidades"]): w = 25
                elif any(x in h for x in ["series", "sets", "reps", "repeticiones", "nº", "grupo", "g1", "g2"]): w = 8 # Columnas estrechas
                elif any(x in h for x in ["pausa", "rest", "recup", "tiempo", "duración", "distancia", "vel", "vam"]): w = 12
                elif any(x in h for x in ["fase", "mes", "semana"]): w = 18
                weights.append(w)
            
            total_w = sum(weights)
            # Calcular porcentajes
            col_widths = [f"{(w/total_w)*100:.1f}%" for w in weights]
            
            colgroup = "<colgroup>" + "".join([f'<col width="{w}">' for w in col_widths]) + "</colgroup>"
        
        new_html += f"<table>{colgroup}" + part

    html_text = new_html
    
    # Estilos CSS para el PDF
    css_style = """
    <style>
        @page { size: A4 landscape; margin: 1cm; }
        body { font-family: Helvetica, sans-serif; font-size: 10pt; color: #333; }
        h1 { color: #2E7D32; font-size: 16pt; margin-bottom: 15px; text-align: center; font-weight: bold; }
        h2 { color: #1565C0; font-size: 13pt; margin-top: 15px; border-bottom: 2px solid #EEE; padding-bottom: 5px; }
        h3 { color: #444; font-size: 11pt; margin-top: 10px; font-weight: bold; }
        p { line-height: 1.4; margin-bottom: 8px; text-align: justify; }
        
        /* Tablas */
        table { width: 100%; border-collapse: collapse; margin-top: 10px; margin-bottom: 15px; table-layout: fixed; }
        th { background-color: #004d40; color: white; padding: 6px; border: 1px solid #444; font-weight: bold; text-align: center; font-size: 9pt; }
        td { padding: 6px; border: 1px solid #CCC; text-align: left; vertical-align: top; font-size: 9pt; word-wrap: break-word; }
        
        /* Listas */
        ul, ol { margin-bottom: 8px; padding-left: 15px; }
        li { margin-bottom: 3px; }
        
        strong { color: #000; font-weight: bold; }

        /* Logo en esquina superior derecha */
        #header-logo {
            position: absolute;
            top: -20px;
            right: 0px;
            width: 80px;
            height: auto;
        }
    </style>
    """
    
    # HTML Completo
    img_tag = f'<img id="header-logo" src="data:image/jpeg;base64,{logo_base64}"/>' if logo_base64 else ""

    full_html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="utf-8">
        {css_style}
    </head>
    <body>
        {img_tag}
        <h1>{title}</h1>
        <hr/>
        {html_text}
    </body>
    </html>
    """
    
    # Generar PDF en memoria
    pdf_buffer = io.BytesIO()
    pisa_status = pisa.CreatePDF(io.BytesIO(full_html.encode("utf-8")), dest=pdf_buffer)
    
    if pisa_status.err:
        return None
    
    return pdf_buffer.getvalue()



def load_json(filepath):
    if FIREBASE_ENABLED:
        try:
            doc_id = "equipos" if filepath == DB_EQUIPOS else "planes"
            doc = db.collection("futsal_data").document(doc_id).get()
            if doc.exists:
                data = doc.to_dict().get("data", [])
                if data: return data
        except Exception as e:
            print("Error cargando Firebase:", e)

    if not os.path.exists(filepath): return []
    try:
        with open(filepath, "r", encoding="utf-8") as f: return json.load(f)
    except: return []

def save_json(filepath, data):
    local_saved = False
    try:
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=4, ensure_ascii=False)
        local_saved = True
    except: pass
    
    if FIREBASE_ENABLED:
        try:
            doc_id = "equipos" if filepath == DB_EQUIPOS else "planes"
            db.collection("futsal_data").document(doc_id).set({"data": data})
            return True
        except: pass
        
    return local_saved

if "equipos" not in st.session_state: st.session_state.equipos = load_json(DB_EQUIPOS)
if "planes" not in st.session_state: st.session_state.planes = load_json(DB_PLANES)
if "messages" not in st.session_state: st.session_state.messages = []
if "confirm_delete" not in st.session_state: st.session_state.confirm_delete = False

# Inicializamos límite de caracteres (se puede modificar en la UI)
if "max_context_chars" not in st.session_state:
    st.session_state.max_context_chars = 10000

# Cargamos contexto PDF al iniciar (cacheado)
library_text, library_count = load_library_context(st.session_state.max_context_chars)

# --- Layout ---
# Header con Logo y Título
c_logo, c_title = st.columns([1, 12])
with c_logo:
    st.image("logo.jpg", width=85)
with c_title:
    st.markdown('<h1 class="main-header" style="text-align: left; margin-top: 0;">Planificador Físico Futsal</h1>', unsafe_allow_html=True)

tab1, tab2, tab3 = st.tabs(["🏢 Gestión de Club", "📋 Planificador IA (Chat)", "🗂️ Mis Planificaciones"])

# --- TAB 1: GESTIÓN DE CLUB ---
with tab1:
    st.markdown('<h2 class="section-header">Gestión de Equipos</h2>', unsafe_allow_html=True)
    
    c_sel, c_del = st.columns([4, 1])
    opciones = ["Nueva Categoría"] + [e["categoria"] for e in st.session_state.equipos]
    seleccion = c_sel.selectbox("Seleccionar Categoría:", opciones)
    
    equipo_actual = {}
    idx_actual = -1
    
    if seleccion != "Nueva Categoría":
        if c_del.button("❌ Borrar"): st.session_state.confirm_delete = True
            
        if st.session_state.confirm_delete:
            st.warning(f"¿Eliminar '{seleccion}'?")
            if st.button("✅ Confirmar Eliminación"):
                st.session_state.equipos = [e for e in st.session_state.equipos if e["categoria"] != seleccion]
                save_json(DB_EQUIPOS, st.session_state.equipos)
                st.session_state.confirm_delete = False
                st.rerun()

        for i, eq in enumerate(st.session_state.equipos):
            if eq["categoria"] == seleccion:
                equipo_actual = eq
                idx_actual = i
                break
    
    with st.form("form_equipo"):
        st.markdown("### Información")
        c1, c2, c3 = st.columns(3)
        nombre_cat = c1.text_input("Nombre Categoría", value=equipo_actual.get("categoria", ""))
        profe = c2.text_input("PF a Cargo", value=equipo_actual.get("profe", ""))
        nivel = c3.selectbox("Nivel", ["Amateur", "Formativo", "Elite/Pro"], index=["Amateur", "Formativo", "Elite/Pro"].index(equipo_actual.get("nivel", "Amateur")))
        
        c4, c5, c5b = st.columns(3)
        cant_jugadors = c4.number_input("Nº Jugadores", min_value=5, value=equipo_actual.get("cantidad", 12))
        dias_entreno = c5.multiselect("Días Entreno", ["Lu", "Ma", "Mi", "Ju", "Vi", "Sa", "Do"], default=equipo_actual.get("dias", []))
        dias_partido = c5b.multiselect("Días Partido", ["Lu", "Ma", "Mi", "Ju", "Vi", "Sa", "Do"], default=equipo_actual.get("dias_partido", []))
        
        c6, c7 = st.columns(2)
        tiempo_disp = c6.text_input("Tiempo (Total/PF)", value=equipo_actual.get("tiempo", "90' / 30' PF"))
        materiales = c7.text_input("Recursos", value=equipo_actual.get("materiales", "Pista 40x20, Conos"))
        
        st.markdown("### 📊 Tests Físicos (m/s)")
        
        # Toggle para activar/desactivar RSA y Velocidad
        show_advanced = st.checkbox("Incluir Tests de Velocidad y RSA", value=any(v > 0 for v in equipo_actual.get("velocidad", {}).values()) or any(v > 0 for v in equipo_actual.get("rsa", {}).values()))

        t1, t2, t3 = st.columns(3)
        def input_stats(label, k, d, disabled=False):
            st.markdown(f"**{label}**")
            if disabled:
                st.caption("Desactivado")
                return {"g1": 0.0, "g2": 0.0, "g3": 0.0}
            # Generar KEY única combinando etiqueta y nombre de categoría para forzar refresco
            unique_suffix = f"{k}_{equipo_actual.get('categoria', 'new')}"
            return {
                "g1": st.number_input(f"G1", key=f"{unique_suffix}_1", value=float(d.get("g1", 0.0)), format="%.2f"),
                "g2": st.number_input(f"G2", key=f"{unique_suffix}_2", value=float(d.get("g2", 0.0)), format="%.2f"),
                "g3": st.number_input(f"G3", key=f"{unique_suffix}_3", value=float(d.get("g3", 0.0)), format="%.2f")
            }
        
        with t1: 
            if show_advanced:
                vel = input_stats("Velocidad Max (m/s)", "v", equipo_actual.get("velocidad", {}))
            else:
                vel = {"g1": 0.0, "g2": 0.0, "g3": 0.0}
                st.info("Velocidad: Desactivado")

        with t2: vam = input_stats("VAM (m/s)", "vm", equipo_actual.get("vam", {})) # VAM siempre activo
        
        with t3: 
            if show_advanced:
                rsa = input_stats("RSA (m/s)", "rs", equipo_actual.get("rsa", {}))
            else:
                rsa = {"g1": 0.0, "g2": 0.0, "g3": 0.0}
                st.info("RSA: Desactivado")
            
        st.markdown("### 🚑 Parte Médico")
        lesiones = st.text_area("Lesionados", value=equipo_actual.get("lesiones", "Sin novedades"))
        
        if st.form_submit_button("Guardar Datos"):
            if not nombre_cat:
                st.error("Nombre requerido")
            else:
                new_data = {
                    "categoria": nombre_cat, "profe": profe, "nivel": nivel, "cantidad": cant_jugadors,
                    "dias": dias_entreno, "dias_partido": dias_partido, "tiempo": tiempo_disp, 
                    "materiales": materiales, "velocidad": vel, "vam": vam, "rsa": rsa, "lesiones": lesiones
                }
                if idx_actual >= 0: st.session_state.equipos[idx_actual] = new_data
                else: st.session_state.equipos.append(new_data)
                save_json(DB_EQUIPOS, st.session_state.equipos)
                st.success("Guardado")
                st.rerun()

# --- TAB 2: CHAT ---
with tab2:
    st.markdown('<h2 class="section-header">Asistente de Planificación</h2>', unsafe_allow_html=True)
    if not st.session_state.equipos:
        st.info("⚠️ Crea un equipo primero.")
    else:
        with st.container():
            c_eq, c_tp, c_ctx = st.columns(3)
            ename = [e["categoria"] for e in st.session_state.equipos]
            sel_eq = c_eq.selectbox("Equipo", ename)
            # Quitamos "Trimestral"
            sel_tipo = c_tp.selectbox("Tipo", ["Sesión Diaria", "Semanal", "Mensual", "Semestral", "Anual"])
            
            # --- SELECTOR DE CONTEXTO SIMPLIFICADO ---
            # 1. Filtro de Tipo para Contexto
            filtro_tipo_ctx = c_ctx.selectbox("Filtrar Contexto por Tipo", ["Todos", "Sesión Diaria", "Semanal", "Mensual", "Semestral", "Anual"])
            
            # 2. Filtrar planes por Equipo Y Tipo
            relevant_plans = []
            for p in st.session_state.planes:
                # Chequeo de Equipo
                if sel_eq not in p['titulo']: continue
                
                # Chequeo de Tipo
                p_tipo = p.get("tipo", "")
                if not p_tipo: # Retro-compatibilidad: buscar en título
                    if "Mensual" in p['titulo']: p_tipo = "Mensual"
                    elif "Semanal" in p['titulo']: p_tipo = "Semanal"
                    elif "Semestral" in p['titulo']: p_tipo = "Semestral"
                    elif "Anual" in p['titulo']: p_tipo = "Anual"
                    elif "Diaria" in p['titulo']: p_tipo = "Sesión Diaria"
                
                if filtro_tipo_ctx == "Todos" or filtro_tipo_ctx == p_tipo:
                    relevant_plans.append(p)

            plan_opts = {f"{p['titulo']}": p for p in relevant_plans}
            
            ctx_options = ["Ninguno (General)"] + list(plan_opts.keys())
            sel_plan_key = c_ctx.selectbox("Contexto / Plan Base", ctx_options)
            
            selected_prev_plan_content = ""
            if sel_plan_key != "Ninguno (General)":
                selected_prev_plan_content = plan_opts[sel_plan_key]["contenido"]
                st.info(f"🔗 Usando plan base: {sel_plan_key}")

            eq_data = next((e for e in st.session_state.equipos if e["categoria"] == sel_eq), {})
        
        # Mostrar info de biblioteca
        if library_count > 0:
            st.caption(f"📚 {library_count} Documentos cargados. Longitud límite actual: {st.session_state.max_context_chars} caracteres.")
        else:
            st.caption("⚠️ No se detectaron documentos en 'biblioteca_futsal'. Se usará conocimiento general.")

        # === SLIDER DE TOKENS VISIBLE AQUÍ ===
        with st.expander("⚙️ Opciones de Consumo de IA (Límites de Lectura)", expanded=True):
            st.markdown("Si tienes el error **Quota 429**, baja radicalmente esta barra a 0 o a 1000.")
            nuevo_limite = st.slider(
                "Límite de lectura de libros (Caracteres)", 
                min_value=0, 
                max_value=150000, 
                value=st.session_state.max_context_chars, 
                step=5000, 
                help="Limita lo que la IA lee de tus libros para ahorrar cuota de la API gratuita."
            )
            if nuevo_limite != st.session_state.max_context_chars:
                st.session_state.max_context_chars = nuevo_limite
                # Limpiamos caché forzadamente y recargamos
                st.cache_resource.clear()
                st.rerun()
        # =====================================

        # Chat logic
        for msg in st.session_state.messages:
            with st.chat_message(msg["role"]): st.markdown(msg["content"])
            
        if st.session_state.messages and st.session_state.messages[-1]["role"] == "assistant":
            with st.expander("💾 Guardar esta Planificación (Opcional)", expanded=True):
                st.write("**Personaliza el Título** (Ej: 'Enero', 'Semana 1', 'Día 5')")
                custom_label = st.text_input("Etiqueta / Detalle", placeholder="Escribe aquí para identificar mejor el plan...")
                
                if st.button("Confirmar Guardado"):
                    pid = str(uuid.uuid4())
                    
                    # Construcción Inteligente del Título
                    final_title = f"{sel_tipo} - {sel_eq}"
                    if custom_label:
                        final_title += f" | {custom_label}"
                    final_title += f" ({datetime.date.today()})"
                    
                    st.session_state.planes.append({
                        "id": pid, 
                        "titulo": final_title,
                        "tipo": sel_tipo, # Guardamos el tipo explícitamente
                        "fecha": str(datetime.date.today()), 
                        "contenido": st.session_state.messages[-1]["content"]
                    })
                    save_json(DB_PLANES, st.session_state.planes)
                    st.success(f"✅ Guardado como: {final_title}")
                    # Limpiar chat tras guardar para evitar scroll infinito
                    if st.session_state.messages and st.session_state.messages[-1]["role"] == "assistant":
                        st.session_state.messages.pop()
                    st.rerun()

        if prompt := st.chat_input("Escribe tu solicitud..."):
            st.session_state.messages.append({"role": "user", "content": prompt})
            with st.chat_message("user"): st.markdown(prompt)
            
            # --- CONSTRUCCIÓN DEL CONTEXTO RAG ---
            # Definir instrucciones de formato según el tipo de plan
            format_instructions = ""
            
            # --- TIPO 1: MACRO PLANES (ANUAL / SEMESTRAL) ---
            if sel_tipo in ["Anual", "Semestral"]:
                format_instructions = """
                FORMATO OBLIGATORIO (MACRO - VISIÓN GENERAL):
                1. Breve Introducción del ciclo.
                2. TABLA ÚNICA (Fases y Objetivos):
                   | FASE | MES | OBJETIVO GENERAL | CAPACIDADES (Fuerza, Velocidad, Resistencia) |
                
                PROHIBIDO:
                - NO pongas ejercicios específicos.
                - NO pongas ejemplos de microciclos ni sesiones.
                """

            # --- TIPO 2: MENSUAL ---
            elif sel_tipo == "Mensual":
                format_instructions = """
                FORMATO OBLIGATORIO (MENSUAL - MATRIZ DETALLADA):
                1. TABLA RESUMEN DE OBJETIVOS (Semana 1-4).
                
                2. GRAN MATRIZ DE TRABAJO (Crucial):
                Genera una tabla detallada donde:
                - Columnas: SEMANA 1 | SEMANA 2 | SEMANA 3 | SEMANA 4.
                - Filas: DÍAS DE ENTRENO (Lunes, Miércoles, etc. según datos del equipo).
                - Celdas: Contenido específico de la sesión (Foco y Ejercicio Principal).
                
                Ejemplo Visual:
                | DÍA | SEMANA 1 (Adaptación) | SEMANA 2 (Carga) | ... |
                |---|---|---|---|
                | Lunes (Fuerza) | Circuito General con Autocargas... | Fuerza Máxima 85% 3x5... | ... |
                
                IMPORTANTE: Quiero ver el detalle día por día para todo el mes, no solo un resumen general.
                """

            # --- TIPO 3: SEMANAL ---
            elif sel_tipo == "Semanal":
                format_instructions = """
                FORMATO OBLIGATORIO (SEMANAL - DOSIFICACIÓN DETALLADA):
                Genera una tabla por CADA DÍA DE ENTRENO.
                - Campos: Ejercicio | Series | Repeticiones | Pausa | Intensidad Exacta.
                - Sé muy preciso con los números (Dosis de entreno).
                - FOCO: Fuerza, Velocidad y HIIT detallado.
                """

            # --- TIPO 4: SESIÓN DIARIA / SEMANAL (DETALLE MATEMÁTICO) ---
            else: 
                format_instructions = """
                FORMATO OBLIGATORIO (CALCULADORA VAM + TIMING INTELIGENTE):
                
                1. DECISIÓN DE TIMING (CRUCIAL):
                Analiza el objetivo fisiológico y DECIDE dónde ubicar la sesión PF:
                - CASO A (ANTES DEL TÁCTICO): Para Velocidad, Fuerza Máxima/Potencia o Pliometría (Frescura necesaria). -> DEBES INCLUIR CALENTAMIENTO (5-8 min).
                - CASO B (DESPUÉS DEL TÁCTICO): Para Resistencia Metabólica, HIIT de fatiga o Fuerza Resistencia. -> NO INCLUYAS CALENTAMIENTO (Asume que vienen activos del táctico).
                * INICIA TU RESPUESTA EXTRICTAMENTE CON: "**UBICACIÓN SUGERIDA:** [ANTES/DESPUÉS] del DT. **Motivo:** [Justificación breve]."
                
                2. VUELTA A LA CALMA (COOL DOWN):
                - NO ASIGNES TIEMPO. Ponla SOLO como una nota al pie ("Sugerencia: Estirar..."). 
                - Tiempo asignado: 0 MINUTOS. (No restes tiempo de la sesión principal).

                3. ESTRUCTURA CENTRAL (HIIT/Resistencia):
                Para ejercicios de Resistencia/HIIT, DEBES usar este formato exacto:
                
                **[Nombre Ejercicio]**
                - Estructura: **SERIES x (REPETICIONES x TIEMPO_TRABAJO" x TIEMPO_PAUSA")**.
                - Macro-Pausa entre Series: **TIEMPO_MACRO_PAUSA**.
                
                TABLA DE CARGAS (OBLIGATORIA SI HAY DATOS VAM):
                | GRUPO | % VAM | Vel (m/s) | Distancia a Recorrer (por rep) | Logística (Conos) |
                |---|---|---|---|---|
                | G1 | ... | ... | ... | Ida y Vuelta: Conos a X metros |
                
                IMPORTANTE "LOGISTICA":
                - Calcula EXACTAMENTE los metros: (Vel m/s * Tiempo Trabajo).
                - Si es IDA Y VUELTA, divide la distancia / 2 para decir a cuántos metros poner el cono.
                - Ejemplo: "G1 (4.5 m/s) x 15 seg = 67.5m. Logística: Ida y Vuelta (67.5m / 2) -> Conos a 33-34 metros."
                """

            # Construir contexto de planes guardados
            # A) Si seleccionó un PLAN ESPECÍFICO en el UI, ese es el contexto REY.
            specific_plan_context = ""
            if selected_prev_plan_content:
                specific_plan_context = (
                    "\n=== PLAN BASE SELECCIONADO (PRIORIDAD ABSOLUTA) ===\n"
                    "El usuario ha seleccionado explícitamente continuar o basarse en este plan previo:\n"
                    f"{selected_prev_plan_content}\n"
                    "==========================================================\n"
                )
            
            # B) Si no, usamos la lista de referencia general (lo que ya teniamos)
            saved_plans_str = ""
            if not selected_prev_plan_content and relevant_plans:
                saved_plans_str = "=== PLANIFICACIONES PREVIAS DEL EQUIPO (ÚLTIMAS 3) ===\n"
                for p in relevant_plans[-3:]: # Solo las últimas 3 planificaciones para evitar límite de Tokens Gratuitos
                    saved_plans_str += f"\n--- TÍTULO: {p['titulo']} ---\n{p['contenido']}\n"
                saved_plans_str += "======================================================================\n"

            # Construir historial (Contexto)
            history_str = ""
            for msg in st.session_state.messages[:-1]:
                r = "USUARIO" if msg["role"] == "user" else "ASISTENTE"
                history_str += f"{r}: {msg['content']}\n\n"

            # Definir ROL y CONTEXTO según tipo de plan
            if sel_tipo == "Sesión Diaria":
                role_instruction = "ERES UN PREPARADOR FISICO EXPERTO EN FUTSAL. TIENES 30 MINUTOS POR DEFECTO (SALVO QUE EL USUARIO INDIQUE OTRO TIEMPO)."
            else:
                role_instruction = f"ERES EL DIRECTOR DE RENDIMIENTO DEL CLUB. TU OBJETIVO ES DISEÑAR UNA PLANIFICACION {sel_tipo.upper()} ESTRUCTURAL Y COHERENTE."

            # ==========================================
            # CONSTRUCCION DE PROMPT (SIN TRIPLE COMILLAS PARA EVITAR ERRORES)
            # ==========================================
            sys_parts = []
            sys_parts.append(f"{role_instruction}")
            
            if specific_plan_context:
                sys_parts.append(specific_plan_context)
            
            if library_text:
                sys_parts.append("=== BIBLIOTECA TECNICA (Contexto Real de Archivos) ===")
                # Asegurar envío acorde al slider
                sys_parts.append(f"{library_text}")
                sys_parts.append("(Nota: Texto truncado si es excesivo, usa esto como base teorica prioritaria).")
                sys_parts.append("=====================================================")
            
            if saved_plans_str:
                sys_parts.append(saved_plans_str)
            
            sys_parts.append("CONTEXTO EQUIPO:")
            sys_parts.append(f"- Equipo: {eq_data.get('categoria')} (Nivel {eq_data.get('nivel')})")
            sys_parts.append(f"- Jugadores: {eq_data.get('cantidad')}")
            sys_parts.append(f"- Dias Entreno: {eq_data.get('dias')}")
            sys_parts.append(f"- Dias Partido: {eq_data.get('dias_partido')}")
            sys_parts.append(f"- Tiempo: {eq_data.get('tiempo')}")
            sys_parts.append(f"- Recursos Disponibles: {eq_data.get('materiales')}")
            sys_parts.append(f"- Sanidad: {eq_data.get('lesiones')}")
            # Filtrar datos físicos vacíos (0.0) para no ensuciar el prompt
            def format_pdata(label, data):
                if not data: return ""
                # Si todos son 0, retornar vacio
                if all(v == 0 for v in data.values()): return ""
                return f"{label}: {data}"

            phys_info = []
            phys_info.append(f"VAM: {eq_data.get('vam')}") # VAM siempre
            
            p_vel = format_pdata("Velocidad", eq_data.get('velocidad'))
            if p_vel: phys_info.append(p_vel)
            
            p_rsa = format_pdata("RSA", eq_data.get('rsa'))
            if p_rsa: phys_info.append(p_rsa)

            sys_parts.append(f"- DATOS FISICOS: {', '.join(phys_info)} (Todo en m/s).")
            
            sys_parts.append("=== HISTORIAL DE CONVERSACION (MEMORIA) ===")
            sys_parts.append(f"{history_str}")
            sys_parts.append("===========================================")
            
            sys_parts.append(f"TAREA ACTUAL: Crear planificacion {sel_tipo}.")
            
            sys_parts.append("REGLAS DE ORO (CRITICAS):")
            sys_parts.append("1. MATERIALES Y FUERZA (MUY IMPORTANTE):")
            sys_parts.append('   - Revisa "Recursos Disponibles".')
            sys_parts.append("   - SI NO HAY GIMNASIO/PESAS: PROHIBIDO poner Fuerza Maxima o Hipertrofia pesada en cancha. Haz trabajos de fuerza preventiva/reactiva con peso corporal.")
            sys_parts.append('   - SUGERENCIA EXTERNA: Si toca fuerza pesada y no hay material, añade una nota: "Recomendado realizar trabajo de gimnasio individual fuera de sesion".')
            
            sys_parts.append(f"2. FORMATO SEGUN TIPO: {format_instructions}")
            
            sys_parts.append("3. ROL PF: Prioridad a la Dosis Fisica Exacta. Tiempo base 30 min (o lo que pida el usuario).")
            sys_parts.append("4. ROL DT: Solo sugiere intensidad/tipo de SSG si aplica.")
            sys_parts.append(f"5. INTENSIDAD: Resistencia SIEMPRE en % de VAM ({eq_data.get('vam')} m/s).")
            sys_parts.append("6. CONTINUIDAD: Si existen PLANES PREVIOS GUARDADOS, usalos como base para mantener coherencia (ej. si hay un mensual, respetalo al hacer la semana).")
            sys_parts.append("7. FORMATO VISUAL: PROHIBIDO USAR LATEX EN TABLAS (ej. no uses \\multirow, \\multicolumn). Usa tablas Markdown estandar.")
            
            sys_parts.append(f"Solicitud Usuario: {prompt}")
            
            sys = "\n".join(sys_parts)

            
            with st.chat_message("assistant"):
                ph = st.empty()
                if not api_key and "GOOGLE_API_KEY" not in os.environ:
                    st.error("Falta API Key")
                else:
                    try:
                        models_to_try = get_available_models()
                        success = False
                        last_error = ""
                        for mname in models_to_try:
                            try:
                                model = genai.GenerativeModel(mname)
                                resp = model.generate_content(sys)
                                txt = resp.text
                                ph.markdown(txt)
                                st.session_state.messages.append({"role": "assistant", "content": txt})
                                success = True
                                break # Salir del loop si funciona correctamente
                            except Exception as e:
                                last_error = str(e)
                                if "429" in last_error or "Quota" in last_error or "quota" in last_error:
                                    break # No intentar otros modelos si es límite de cuota (evitar errores extraños)
                                continue # Intentar el siguiente modelo si es otro error
                        
                        if success:
                            st.rerun()
                        else:
                            st.error(f"Error AI: Límite de cuota o bloqueado en capa gratuita. Intenta bajar el Límite de Contexto. Error Técnico: {last_error}")
                    except Exception as e: 
                        st.error(f"Error AI Crítico: {e}")

# --- TAB 3: MIS PLANES ---
with tab3:
    c_logo_tab3, c_title_tab3 = st.columns([1, 12])
    with c_logo_tab3:
        st.image("logo.jpg", width=60)
    with c_title_tab3:
         st.markdown('<h2 class="section-header" style="margin-top: 0;">Mis Planificaciones</h2>', unsafe_allow_html=True)

    if st.button("🔄 Refrescar Listado"):
        st.session_state.planes = load_json(DB_PLANES)
        st.success("Listado actualizado correctamente.")
        st.rerun()
    
    # --- FILTRO POR EQUIPO ---
    if not st.session_state.planes:
        st.info("Sin planes guardados.")
    else:
        # Obtener lista de equipos disponibles + "Todos"
        all_teams = ["Todos"] + [e["categoria"] for e in st.session_state.equipos]
        
        c_fill_team, c_fill_cat = st.columns(2)
        filter_team = c_fill_team.selectbox("Filtrar por Equipo:", all_teams)
        filter_cat = c_fill_cat.selectbox("Filtrar por Categoría:", ["Todos", "Sesión Diaria", "Semanal", "Mensual", "Semestral", "Anual"])
        
        # Filtro de Texto
        search_text = st.text_input("🔍 Buscar por texto (Título o Contenido)", placeholder="Escribe para buscar...")

        # Filtrar lista
        filtered_planes = []
        for p in st.session_state.planes:
             # Lógica Filtro Equipo
             match_team = False
             if filter_team == "Todos": match_team = True
             elif filter_team in p['titulo']: match_team = True
             
             # Lógica Filtro Categoría
             match_cat = False
             p_tipo = p.get("tipo", "")
             if not p_tipo: # Retro-compatibilidad
                if "Mensual" in p['titulo']: p_tipo = "Mensual"
                elif "Semanal" in p['titulo']: p_tipo = "Semanal"
                elif "Semestral" in p['titulo']: p_tipo = "Semestral"
                elif "Anual" in p['titulo']: p_tipo = "Anual"
                elif "Diaria" in p['titulo']: p_tipo = "Sesión Diaria"
            
             if filter_cat == "Todos": match_cat = True
             elif filter_cat == p_tipo: match_cat = True

             # Lógica Filtro Texto
             match_text = True
             if search_text:
                 stxt = search_text.lower()
                 if stxt not in p['titulo'].lower() and stxt not in p['contenido'].lower():
                     match_text = False
             
             if match_team and match_cat and match_text:
                 filtered_planes.append(p)
        
        if not filtered_planes:
            st.warning(f"No hay planes para '{filter_team}'.")
        else:
            # Dropdown con items filtrados
            titles = [f"{p['fecha']} | {p['titulo']}" for p in filtered_planes]
            # Mapeamos selección local al índice global real si necesitamos editar
            sel_idx_local = st.selectbox("Seleccionar Plan", range(len(titles)), format_func=lambda x: titles[x])
            
            # Recuperar el objeto real
            cur = filtered_planes[sel_idx_local]
            
            # Buscamos el índice real en st.session_state.planes para poder guardar/borrar
            real_idx = st.session_state.planes.index(cur)
            
            # Botón de Eliminación Rápida
            col_actions = st.columns([1, 5])
            if col_actions[0].button("🗑️ Eliminar", key=f"del_btn_{cur['id']}"):
                st.session_state[f"confirm_del_{cur['id']}"] = True
            
            if st.session_state.get(f"confirm_del_{cur['id']}", False):
                st.warning(f"¿Estás seguro de que quieres borrar '{cur['titulo']}'?")
                if st.button("✅ Confirmar Borrado", key=f"conf_del_{cur['id']}"):
                    st.session_state.planes.pop(real_idx)
                    save_json(DB_PLANES, st.session_state.planes)
                    st.success("Plan eliminado.")
                    st.rerun()

        # Tabs para Editar o Ver
        sub_t1, sub_t2, sub_t3 = st.tabs(["👁️ Vista Previa Renderizada", "📝 Editar Código (Markdown)", "✨ Refinar con IA"])
        
        with sub_t1:
             st.markdown(f"### 📄 {cur['titulo']}")
             st.markdown("---")
             st.markdown(cur["contenido"])
             
        with sub_t2:
            with st.form("edit_p"):
                nt = st.text_input("Título", value=cur["titulo"])
                nc = st.text_area("Contenido (Markdown)", value=cur["contenido"], height=400)
                c_b1, c_b2 = st.columns([1,5])
                
                if c_b1.form_submit_button("💾 Guardar Cambios"):
                    st.session_state.planes[real_idx]["titulo"] = nt
                    st.session_state.planes[real_idx]["contenido"] = nc
                    save_json(DB_PLANES, st.session_state.planes)
                    st.success("✅ Plan Actualizado")
                    st.rerun()
                    
                if c_b2.form_submit_button("❌ Eliminar Plan"):
                    st.session_state.planes.pop(real_idx)
                    save_json(DB_PLANES, st.session_state.planes)
                    st.rerun()

        with sub_t3:
            st.info("💡 Describe el cambio. La IA generará una PROPUESTA que podrás revisar antes de guardar.")
            refine_prompt = st.text_area("Instrucción de Edición", placeholder="Ej: Agrega un ejercicio de zona media al calentamiento...")
            
            # Inicializar estado de propuesta si no existe
            if 'refine_proposal' not in st.session_state:
                st.session_state.refine_proposal = None
            
            # 1. Botón Generar
            if st.button("✨ Generar Propuesta"):
                if not refine_prompt:
                    st.error("Escribe una instrucción primero.")
                else:
                    with st.spinner("Generando propuesta de cambios..."):
                        try:
                            # Prompt de refinamiento
                            sys_refine = f"""
                            ACTUA COMO UN EDITOR EXPERTO DE PLANIFICACIONES DE PHYSICAL FITNESS (FUTSAL).
                            TU TAREA ES MODIFICAR EL SIGUIENTE PLAN EXISTENTE SEGUN LA SOLICITUD DEL USUARIO.
                            
                            PLAN ORIGINAL:
                            {cur["contenido"]}
                            
                            SOLICITUD DE CAMBIO (USUARIO):
                            "{refine_prompt}"
                            
                            INSTRUCCIONES CRÍTICAS DE FORMATO:
                            1. TU OBJETIVO ES EDITAR EL CONTENIDO, NO CAMBIAR LA ESTRUCTURA.
                            2. SI HAY TABLAS EN EL PLAN ORIGINAL, DEBES MANTENERLAS COMO TABLAS MARKDOWN (`| Col |...`). PROHIBIDO CONVERTIRLAS A LISTAS O TEXTO PLANO.
                            3. Aplica el cambio solicitado de forma coherente dentro del formato existente.
                            4. MANTEN las negritas, cursivas y encabezados.
                            5. NO SALUDES. EMPIEZA DIRECTAMENTE con el Título del Plan (`# ...` o `## ...`).
                            
                            FORMATO DE RESPUESTA OBLIGATORIO:
                               [CONTENIDO MARKDOWN DEL PLAN (LIMPIO Y FORMATEADO)]
                               ---JUSTIFICACION---
                               [Breve explicación técnica de por qué hiciste estos cambios]
                            """
                            
                            # Intentar usar el modelo preferido
                            try:
                                mname = get_available_models()[0]
                                model_refine = genai.GenerativeModel(mname)
                            except:
                                # Fallback extremo si falla la funcion
                                model_refine = genai.GenerativeModel("models/gemini-2.5-flash")
                                
                            resp_refine = model_refine.generate_content(sys_refine)
                            full_text = resp_refine.text
                            
                            # Parsear respuesta (Separar Plan de Justificación)
                            if "---JUSTIFICACION---" in full_text:
                                parts = full_text.split("---JUSTIFICACION---")
                                new_content = parts[0].strip()
                                reasoning = parts[1].strip()
                            else:
                                new_content = full_text
                                reasoning = "La IA no proporcionó una justificación explícita."
                            
                            # GUARDAR EN ESTADO TEMPORAL (NO EN BD)
                            st.session_state.refine_proposal = {
                                "idx": real_idx,
                                "content": new_content,
                                "reasoning": reasoning,
                                "prompt": refine_prompt
                            }
                            st.rerun()
                            
                        except Exception as e:
                            st.error(f"Error al refinar: {e}")

            # 2. Mostrar Propuesta si existe para este plan
            if st.session_state.refine_proposal and st.session_state.refine_proposal.get("idx") == real_idx:
                st.markdown("---")
                st.warning("⚠️ **PROPUESTA PENDIENTE DE APROBACIÓN**")
                
                # Mostrar Justificación
                st.info(f"🤖 **RAZÓN DEL CAMBIO (IA):** {st.session_state.refine_proposal['reasoning']}")
                
                st.markdown(f"> *Tu Solicitud: {st.session_state.refine_proposal['prompt']}*")
                
                with st.expander("📄 Ver Plan Completo (Clic para desplegar)", expanded=False):
                    st.markdown(st.session_state.refine_proposal["content"])
                
                col_accept, col_discard = st.columns(2)
                
                if col_accept.button("✅ ACEPTAR Y GUARDAR CAMBIOS"):
                    # Comprometer cambios
                    st.session_state.planes[real_idx]["contenido"] = st.session_state.refine_proposal["content"]
                    save_json(DB_PLANES, st.session_state.planes)
                    st.session_state.refine_proposal = None # Limpiar
                    st.success("✅ Plan Actualizado y Guardado.")
                    st.rerun()
                
                if col_discard.button("❌ DESCARTAR PROPUESTA"):
                    st.session_state.refine_proposal = None # Limpiar
                    st.info("Propuesta descartada.")
                    st.rerun()
                    
            elif st.session_state.refine_proposal:
                st.info(f"Tienes una propuesta pendiente en otro plan (Índice {st.session_state.refine_proposal['idx']}).")
        
        # Botón descarga PDF fuera del form para evitar recargas incorrectas
        st.markdown("---")
        st.markdown("---")
        try:
            pdf_bytes = create_pdf(cur["titulo"], cur["contenido"])
            if pdf_bytes:
                st.download_button(
                    label="📥 Descargar Planificación (PDF)",
                    data=pdf_bytes,
                    file_name=f"Plan_{cur['id'][:8]}.pdf",
                    mime="application/pdf"
                )
            else:
                st.warning("El módulo PDF no está disponible o falló la generación.")
        except Exception as e:
            st.error(f"Error generando PDF: {e}")

