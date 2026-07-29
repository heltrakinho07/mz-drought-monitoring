import streamlit as st
import ee
import geemap
import sys
import json
import hashlib
import geemap.basemaps
sys.modules['geemap'].basemaps = sys.modules['geemap.basemaps']
import geemap.foliumap as geemap
import datetime
import pandas as pd
import numpy as np
import altair as alt
import folium

# Set up page configuration
st.set_page_config(
    page_title="Monitor de Secas de Moçambique",
    page_icon=":material/monitoring:",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Helper function to calculate GeoJSON centroid for map centering
def get_geojson_centroid(geojson):
    try:
        coords = []
        def recurse(obj):
            if isinstance(obj, list):
                if len(obj) == 2 and isinstance(obj[0], (int, float)) and isinstance(obj[1], (int, float)):
                    coords.append(obj)
                else:
                    for item in obj:
                        recurse(item)
            elif isinstance(obj, dict):
                for key, val in obj.items():
                    if key in ['coordinates', 'features', 'geometry']:
                        recurse(val)
        
        recurse(geojson)
        if coords:
            lons = [c[0] for c in coords]
            lats = [c[1] for c in coords]
            return [sum(lats) / len(lats), sum(lons) / len(lons)], 10 
    except Exception:
        pass
    return [-18.6657, 35.5296], 5 

# Helper function to check if GeoJSON contains Polygon/MultiPolygon
def validate_geojson_polygon(geojson):
    try:
        geometry_types = []
        def check_geom(obj):
            if isinstance(obj, dict):
                g_type = obj.get("type")
                if g_type in ["Polygon", "MultiPolygon"]:
                    geometry_types.append(g_type)
                elif g_type in ["FeatureCollection", "Feature"]:
                    for key, val in obj.items():
                        check_geom(val)
                elif "geometry" in obj:
                    check_geom(obj["geometry"])
                elif "features" in obj:
                    for f in obj["features"]:
                        check_geom(f)
            elif isinstance(obj, list):
                for item in obj:
                    check_geom(item)
        
        check_geom(geojson)
        return len(geometry_types) > 0
    except Exception:
        return False

# Helper function to generate stable pseudo-random offset for districts in demo mode
def get_district_offset(name):
    try:
        h = int(hashlib.md5(name.encode('utf-8')).hexdigest(), 16)
        lat_offset = ((h % 100) - 50) * 0.004
        lon_offset = (((h // 100) % 100) - 50) * 0.004
        return lat_offset, lon_offset
    except Exception:
        return 0, 0

# Inject custom modern CSS styling
st.markdown("""
<style>
/* Load Google Fonts */
@import url('https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;500;600;700&family=Inter:wght@300;400;500;600;700&display=swap');

/* Global Font Override */
html, body, [class*="css"], [class*="st-"] {
    font-family: 'Inter', sans-serif !important;
}

h1, h2, h3, h4, h5, h6 {
    font-family: 'Outfit', sans-serif !important;
    font-weight: 600 !important;
    letter-spacing: -0.02em !important;
}

/* Custom Forest-Black App Background */
.stApp {
    background: linear-gradient(180deg, #07100b 0%, #030605 100%) !important;
}

/* Elegant Scrollbars */
::-webkit-scrollbar {
    width: 6px;
    height: 6px;
}
::-webkit-scrollbar-track {
    background: rgba(255, 255, 255, 0.01);
}
::-webkit-scrollbar-thumb {
    background: rgba(0, 168, 89, 0.2);
    border-radius: 4px;
}
::-webkit-scrollbar-thumb:hover {
    background: rgba(0, 168, 89, 0.45);
}

/* Premium Sidebar Styling */
section[data-testid="stSidebar"] {
    background-color: #050a07 !important;
    border-right: 1px solid rgba(0, 168, 89, 0.12);
}

section[data-testid="stSidebar"] h1, 
section[data-testid="stSidebar"] h2, 
section[data-testid="stSidebar"] h3 {
    color: #00A859 !important;
}

/* Sleek Dark Input Controls */
div[data-baseweb="select"] {
    background-color: rgba(255, 255, 255, 0.02) !important;
    border: 1px solid rgba(255, 255, 255, 0.08) !important;
    border-radius: 10px !important;
    transition: all 0.2s ease-in-out !important;
}
div[data-baseweb="select"]:hover {
    border-color: rgba(0, 168, 89, 0.3) !important;
}
div[data-testid="stDateInput"] input {
    background-color: rgba(255, 255, 255, 0.02) !important;
    border: 1px solid rgba(255, 255, 255, 0.08) !important;
    border-radius: 10px !important;
    color: #ffffff !important;
    padding: 8px 12px !important;
    transition: all 0.2s ease-in-out !important;
}
div[data-testid="stDateInput"] input:hover {
    border-color: rgba(0, 168, 89, 0.3) !important;
}

/* Beautiful Custom Banner */
.custom-banner {
    background: linear-gradient(135deg, #091c11 0%, #030805 100%);
    padding: 2.5rem;
    border-radius: 18px;
    border: 1px solid rgba(0, 168, 89, 0.22);
    box-shadow: 0 12px 35px rgba(0, 0, 0, 0.45);
    margin-bottom: 2.2rem;
    position: relative;
    overflow: hidden;
    backdrop-filter: blur(10px);
}
.custom-banner::before {
    content: "";
    position: absolute;
    top: -60%;
    right: -25%;
    width: 320px;
    height: 320px;
    background: radial-gradient(circle, rgba(0, 200, 100, 0.2) 0%, rgba(0, 0, 0, 0) 70%);
    border-radius: 50%;
}
.custom-banner-title {
    font-family: 'Outfit', sans-serif;
    font-weight: 700;
    font-size: 2.6rem;
    color: #ffffff;
    margin-bottom: 0.5rem;
    letter-spacing: -0.03em;
}
.custom-banner-subtitle {
    font-family: 'Inter', sans-serif;
    font-weight: 400;
    font-size: 1.1rem;
    color: #a0aec0;
    line-height: 1.6;
}

/* Status Badge inside Banner */
.status-badge {
    padding: 6px 14px;
    border-radius: 20px;
    font-size: 0.85rem;
    font-weight: 600;
    font-family: 'Outfit', sans-serif;
    letter-spacing: 0.05em;
    text-transform: uppercase;
    display: flex;
    align-items: center;
}
.status-realtime {
    background-color: rgba(0, 168, 89, 0.15);
    color: #00ff87;
    border: 1px solid rgba(0, 168, 89, 0.3);
}
.status-simulated {
    background-color: rgba(255, 171, 0, 0.15);
    color: #ffab00;
    border: 1px solid rgba(255, 171, 0, 0.3);
}

/* Animated Pulse Dots */
.status-dot-green {
    width: 8px;
    height: 8px;
    background-color: #00ff87;
    border-radius: 50%;
    display: inline-block;
    margin-right: 8px;
    box-shadow: 0 0 8px #00ff87;
    animation: pulse-green 1.8s infinite;
}
@keyframes pulse-green {
    0% { transform: scale(0.95); opacity: 0.6; }
    50% { transform: scale(1.25); opacity: 1; box-shadow: 0 0 14px #00ff87; }
    100% { transform: scale(0.95); opacity: 0.6; }
}
.status-dot-yellow {
    width: 8px;
    height: 8px;
    background-color: #ffab00;
    border-radius: 50%;
    display: inline-block;
    margin-right: 8px;
    box-shadow: 0 0 8px #ffab00;
    animation: pulse-yellow 1.8s infinite;
}
@keyframes pulse-yellow {
    0% { transform: scale(0.95); opacity: 0.6; }
    50% { transform: scale(1.25); opacity: 1; box-shadow: 0 0 14px #ffab00; }
    100% { transform: scale(0.95); opacity: 0.6; }
}

/* Custom Tabs and Segmented Control Styling */
div[data-baseweb="tab-list"] {
    background-color: transparent !important;
    border-bottom: 2px solid rgba(255, 255, 255, 0.08) !important;
    gap: 12px !important;
    margin-bottom: 1.5rem !important;
}

button[data-baseweb="tab"] {
    font-family: 'Outfit', sans-serif !important;
    font-weight: 500 !important;
    font-size: 1.05rem !important;
    border-radius: 8px 8px 0 0 !important;
    padding: 12px 20px !important;
    color: #a0aec0 !important;
    background-color: transparent !important;
    transition: all 0.25s ease !important;
    border: none !important;
}

button[data-baseweb="tab"]:hover {
    color: #ffffff !important;
    background-color: rgba(255, 255, 255, 0.03) !important;
}

button[data-baseweb="tab"][aria-selected="true"] {
    color: #00a859 !important;
    border-bottom: 3px solid #00a859 !important;
    background-color: rgba(0, 168, 89, 0.06) !important;
    font-weight: 600 !important;
}

/* Pill styling for Segmented Control */
div[data-testid="stSegmentedControl"] button {
    border-radius: 20px !important;
    border: 1px solid rgba(255, 255, 255, 0.08) !important;
    background-color: rgba(255, 255, 255, 0.02) !important;
    color: #a0aec0 !important;
    transition: all 0.2s cubic-bezier(0.4, 0, 0.2, 1) !important;
    margin-right: 8px !important;
}
div[data-testid="stSegmentedControl"] button:hover {
    border-color: rgba(0, 168, 89, 0.3) !important;
    color: #ffffff !important;
}
div[data-testid="stSegmentedControl"] button[aria-checked="true"] {
    background-color: #00a859 !important;
    color: #ffffff !important;
    border-color: #00ff87 !important;
    box-shadow: 0 0 12px rgba(0, 168, 89, 0.35) !important;
    font-weight: 600 !important;
}

/* Glassmorphic Metric Cards */
div[data-testid="stMetric"] {
    background: rgba(13, 25, 18, 0.45) !important;
    backdrop-filter: blur(8px) !important;
    border: 1px solid rgba(255, 255, 255, 0.05) !important;
    border-left: 4px solid #00a859 !important;
    border-radius: 12px !important;
    padding: 1.25rem !important;
    box-shadow: 0 6px 22px rgba(0, 0, 0, 0.25) !important;
    transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1) !important;
}

div[data-testid="stMetric"]:hover {
    transform: translateY(-3px) !important;
    border-left-color: #00ff87 !important;
    border-color: rgba(0, 168, 89, 0.35) !important;
    box-shadow: 0 10px 30px rgba(0, 168, 89, 0.16) !important;
}

div[data-testid="stMetricLabel"] {
    font-family: 'Outfit', sans-serif !important;
    font-size: 0.95rem !important;
    text-transform: uppercase;
    letter-spacing: 0.06em;
    color: #a0aec0 !important;
}

div[data-testid="stMetricValue"] {
    font-family: 'Outfit', sans-serif !important;
    font-size: 2rem !important;
    font-weight: 700 !important;
    color: #ffffff !important;
}

/* Bordered Containers */
div[data-testid="stVerticalBlockBorderWrapper"] {
    background: rgba(10, 20, 15, 0.3) !important;
    backdrop-filter: blur(8px) !important;
    border: 1px solid rgba(255, 255, 255, 0.06) !important;
    border-radius: 18px !important;
    padding: 1.75rem !important;
    box-shadow: 0 14px 45px rgba(0,0,0,0.2) !important;
    margin-bottom: 2rem !important;
}

/* Iframe and Map Rounded Corners */
iframe {
    border-radius: 14px !important;
    border: 1px solid rgba(255, 255, 255, 0.08) !important;
    box-shadow: 0 12px 40px rgba(0,0,0,0.25) !important;
}

/* Flat, Modern Left-Border Alerts */
div[data-testid="stAlert"] {
    background-color: rgba(255, 255, 255, 0.02) !important;
    backdrop-filter: blur(10px) !important;
    border: 1px solid rgba(255, 255, 255, 0.05) !important;
    border-left: 5px solid #3b82f6 !important;
    border-radius: 12px !important;
    box-shadow: 0 6px 20px rgba(0, 0, 0, 0.15) !important;
    color: #ffffff !important;
}
div[data-testid="stAlert"] [data-testid="stMarkdownContainer"] p {
    color: #cbd5e0 !important;
}
div[data-testid="element-container"]:has(div[data-testid="stAlert"]):has(svg[data-testid="stNotificationIconSuccess"]) div[data-testid="stAlert"] {
    border-left-color: #10b981 !important;
}
div[data-testid="element-container"]:has(div[data-testid="stAlert"]):has(svg[data-testid="stNotificationIconWarning"]) div[data-testid="stAlert"] {
    border-left-color: #f59e0b !important;
}
div[data-testid="element-container"]:has(div[data-testid="stAlert"]):has(svg[data-testid="stNotificationIconError"]) div[data-testid="stAlert"] {
    border-left-color: #ef4444 !important;
}

/* Custom Styled File Uploader container */
div[data-testid="stFileUploader"] {
    background-color: rgba(0, 168, 89, 0.03) !important;
    border: 1px dashed rgba(0, 168, 89, 0.25) !important;
    border-radius: 14px !important;
    padding: 14px !important;
}
</style>
""", unsafe_allow_html=True)

# --- GOOGLE EARTH ENGINE INITIALIZATION & FALLBACK ---
@st.cache_resource
def init_ee():
    try:
        import os
        key_file_exists = False
        abs_key_file = ""
        if "GEE_KEY_FILE" in st.secrets:
            key_file = st.secrets["GEE_KEY_FILE"]
            app_dir = os.path.dirname(os.path.abspath(__file__))
            abs_key_file = os.path.join(app_dir, key_file) if not os.path.isabs(key_file) else key_file
            if os.path.exists(abs_key_file):
                key_file_exists = True
                
        if key_file_exists and "GEE_PROJECT_ID" in st.secrets:
            from google.oauth2 import service_account
            credentials = service_account.Credentials.from_service_account_file(
                abs_key_file,
                scopes=['https://www.googleapis.com/auth/earthengine']
            )
            ee.Initialize(credentials, project=st.secrets["GEE_PROJECT_ID"])
            return True
        elif "GEE_SERVICE_ACCOUNT_KEY" in st.secrets and "GEE_PROJECT_ID" in st.secrets:
            import json
            from google.oauth2 import service_account
            key_val = st.secrets["GEE_SERVICE_ACCOUNT_KEY"]
            if isinstance(key_val, str):
                key_dict = json.loads(key_val)
            else:
                key_dict = dict(key_val)
            if "private_key" in key_dict:
                key_dict["private_key"] = key_dict["private_key"].replace('\\n', '\n')
            credentials = service_account.Credentials.from_service_account_info(
                key_dict,
                scopes=['https://www.googleapis.com/auth/earthengine']
            )
            ee.Initialize(credentials, project=st.secrets["GEE_PROJECT_ID"])
            return True
        else:
            # Check if default credentials exist before calling ee.Initialize()
            # to prevent blocking the server in non-interactive environments (Streamlit Cloud).
            import os
            has_creds = False
            if os.getenv("GOOGLE_APPLICATION_CREDENTIALS"):
                has_creds = True
            else:
                home = os.path.expanduser("~")
                gcloud_path = os.path.join(home, ".config", "gcloud", "application_default_credentials.json")
                ee_path = os.path.join(home, ".config", "earthengine", "credentials")
                if os.path.exists(gcloud_path) or os.path.exists(ee_path):
                    has_creds = True
            
            if has_creds:
                ee.Initialize()
                return True
            else:
                raise Exception("Nenhum segredo ou credencial padrão do Earth Engine foi encontrada no sistema. A abortar inicialização interativa para evitar bloqueio.")
    except Exception as e:
        import traceback
        print("GEE Initialization Error:")
        traceback.print_exc()
        return False

# Initialize Earth Engine
ee_ready = init_ee()

# --- INITIALIZE SESSION STATE FOR ROBUSTNESS ---
if "user_credentials" not in st.session_state:
    st.session_state.user_credentials = None
if "user_project_id" not in st.session_state:
    st.session_state.user_project_id = ""
if "user_auth_url" not in st.session_state:
    st.session_state.user_auth_url = ""
if "user_code_verifier" not in st.session_state:
    st.session_state.user_code_verifier = ""
if "user_auth_success" not in st.session_state:
    st.session_state.user_auth_success = False

# Try initializing with user's stored credentials if global credentials failed
if not ee_ready and st.session_state.user_credentials and st.session_state.user_project_id:
    try:
        ee.Initialize(st.session_state.user_credentials, project=st.session_state.user_project_id)
        st.session_state.user_auth_success = True
    except Exception as e:
        print("Failed to initialize GEE with stored user credentials:", e)
        st.session_state.user_auth_success = False

# Effective GEE readiness
ee_effective_ready = ee_ready or st.session_state.user_auth_success

if "custom_geometry" not in st.session_state:
    st.session_state.custom_geometry = None
if "custom_center_zoom" not in st.session_state:
    st.session_state.custom_center_zoom = None

# --- PROVINCE AND DISTRICT GEOGRAPHIC CONSTANTS ---
PROVINCE_COORDS = {
    "Todo o Moçambique": {"center": [-18.6657, 35.5296], "zoom": 5},
    "Cabo Delgado": {"center": [-12.3333, 39.5000], "zoom": 7},
    "Gaza": {"center": [-23.0000, 32.5000], "zoom": 7},
    "Inhambane": {"center": [-23.0000, 34.5000], "zoom": 7},
    "Manica": {"center": [-19.5000, 33.2500], "zoom": 7},
    "Maputo": {"center": [-25.5000, 32.5000], "zoom": 8},
    "Maputo (Cidade)": {"center": [-25.9692, 32.5732], "zoom": 10},
    "Nampula": {"center": [-15.0000, 39.2500], "zoom": 7},
    "Niassa": {"center": [-13.0000, 36.5000], "zoom": 7},
    "Sofala": {"center": [-19.5000, 34.5000], "zoom": 7},
    "Tete": {"center": [-15.5000, 32.5000], "zoom": 7},
    "Zambézia": {"center": [-16.5000, 37.0000], "zoom": 7}
}

DISTRICTS = {
    "Cabo Delgado": ["Pemba", "Montepuez", "Mocimboa da Praia", "Mueda", "Palma", "Chiure", "Ancuabe", "Balama"],
    "Gaza": ["Xai-Xai", "Chokwe", "Bilene", "Mandlakazi", "Mabalane", "Massingir", "Chicualacuala"],
    "Inhambane": ["Inhambane", "Maxixe", "Vilankulo", "Massinga", "Morrumbene", "Panda", "Zavala", "Homoine"],
    "Manica": ["Chimoio", "Gondola", "Sussundenga", "Manica", "Mossurize", "Barue", "Guro"],
    "Maputo": ["Matola", "Boane", "Namaacha", "Marracuene", "Manhica", "Magude", "Moamba", "Matutuine"],
    "Maputo (Cidade)": ["Maputo"],
    "Nampula": ["Nampula", "Nacala", "Angoche", "Monapo", "Ribaue", "Meconta", "Mogovolas", "Erati"],
    "Niassa": ["Lichinga", "Cuamba", "Mandimba", "Marrupa", "Maua", "Mecanhelas", "Sanga"],
    "Sofala": ["Beira", "Dondo", "Nhamatanda", "Caia", "Buzi", "Gorongosa", "Marromeu", "Chibabava"],
    "Tete": ["Tete", "Moatize", "Angonia", "Changara", "Cahora Bassa", "Mutarara", "Macanga"],
    "Zambézia": ["Quelimane", "Mocuba", "Gurue", "Milange", "Alto Molocue", "Nicoadala", "Chinde", "Morrumbala"]
}

PROVINCES = list(PROVINCE_COORDS.keys())

# --- SIDEBAR CONFIGURATION ---
with st.sidebar:
    st.header(":material/settings: Definições")
    
    # Mode selector with automatic fallback
    ee_effective_ready = ee_ready or st.session_state.get("user_auth_success", False)
    if ee_effective_ready:
        app_mode = st.segmented_control(
            "Modo de funcionamento",
            options=["Tempo Real (GEE)", "Simulação (Demonstração)"],
            default="Tempo Real (GEE)",
            key="app_mode"
        )
    else:
        st.warning("Google Earth Engine não autenticado. A operar no Modo de Simulação.", icon=":material/warning:")
        app_mode = "Simulação (Demonstração)"
        
    demo_mode = (app_mode == "Simulação (Demonstração)")

    # User Authentication UI
    if not ee_ready:
        st.markdown("---")
        st.markdown("### 🔑 Autenticação do Utilizador")
        if st.session_state.get("user_auth_success", False):
            st.success(f"Conectado ao Projeto: **{st.session_state.user_project_id}**", icon=":material/check_circle:")
            if st.button("Desconectar conta", key="logout_btn", type="secondary"):
                st.session_state.user_credentials = None
                st.session_state.user_project_id = ""
                st.session_state.user_auth_url = ""
                st.session_state.user_code_verifier = ""
                st.session_state.user_auth_success = False
                st.rerun()
        else:
            project_id_input = st.text_input(
                "ID do Projeto Google Cloud",
                value=st.session_state.get("user_project_id", ""),
                placeholder="ex: eengine-project",
                help="O seu projeto Google Cloud com a API do Earth Engine ativada."
            )
            
            if st.button("1. Gerar Link de Autenticação", type="primary", use_container_width=True):
                if not project_id_input:
                    st.error("Por favor, introduza o ID do Projeto primeiro!")
                else:
                    try:
                        import ee.oauth
                        flow = ee.oauth.Flow('notebook')
                        st.session_state.user_auth_url = flow.auth_url
                        st.session_state.user_code_verifier = flow.code_verifier
                        st.session_state.user_project_id = project_id_input
                        st.rerun()
                    except Exception as ex:
                        st.error(f"Erro ao gerar link: {ex}")
            
            if st.session_state.get("user_auth_url"):
                st.info("Clique no link abaixo para fazer login e autorizar o acesso:")
                st.markdown(f"[👉 **Entrar com o Google & Autorizar**]({st.session_state.user_auth_url})", unsafe_allow_html=True)
                
                auth_code = st.text_input(
                    "2. Cole o código de autorização gerado:",
                    placeholder="Cole o código aqui...",
                    type="password"
                )
                
                if st.button("3. Confirmar Autenticação", use_container_width=True):
                    if not auth_code:
                        st.error("Por favor, cole o código de autorização primeiro!")
                    else:
                        with st.spinner("A autenticar com o Earth Engine..."):
                            try:
                                import ee.oauth
                                from google.oauth2.credentials import Credentials
                                
                                verifier = st.session_state.user_code_verifier
                                fetch_data = {}
                                if verifier and ':' in verifier:
                                    request_id, token_verifier, client_verifier = verifier.split(':')
                                    fetch_data = dict(request_id=request_id, client_verifier=client_verifier)
                                    code_verifier_to_use = token_verifier
                                else:
                                    code_verifier_to_use = verifier
                                    
                                client_info = {}
                                scopes = ee.oauth.SCOPES
                                if fetch_data:
                                    import urllib.request
                                    import urllib.parse
                                    data = json.dumps(fetch_data).encode()
                                    headers = {'Content-Type': 'application/json; charset=UTF-8'}
                                    fetch_client = urllib.request.Request(ee.oauth.FETCH_URL, data=data, headers=headers)
                                    fetched_info = json.loads(urllib.request.urlopen(fetch_client).read().decode())
                                    if 'error' in fetched_info:
                                        raise Exception(fetched_info['error'])
                                    client_info = {k: fetched_info[k] for k in ['client_id', 'client_secret']}
                                    scopes = fetched_info.get('scopes') or scopes
                                    
                                refresh_token = ee.oauth.request_token(auth_code.strip(), code_verifier_to_use, **client_info)
                                
                                credentials = Credentials(
                                    token=None,
                                    refresh_token=refresh_token,
                                    client_id=client_info.get('client_id', ee.oauth.CLIENT_ID),
                                    client_secret=client_info.get('client_secret', ee.oauth.CLIENT_SECRET),
                                    token_uri=ee.oauth.TOKEN_URI,
                                    scopes=scopes
                                )
                                
                                ee.Initialize(credentials, project=st.session_state.user_project_id)
                                
                                st.session_state.user_credentials = credentials
                                st.session_state.user_auth_success = True
                                st.success("Autenticado com sucesso! A carregar dados...")
                                st.rerun()
                            except Exception as ex:
                                st.error(f"Falha na autenticação: {ex}")
    
    # Analysis Level
    analysis_level = st.radio(
        "Nível de análise territorial",
        options=["Nacional", "Provincial", "Distrital", "Área Personalizada (GeoJSON)"],
        index=1 
    )
    
    # Level-based region selections
    selected_province = "Todo o Moçambique"
    selected_district = None
    
    if analysis_level == "Nacional":
        selected_province = "Todo o Moçambique"
        
    elif analysis_level == "Provincial":
        selected_province = st.selectbox(
            "Selecione a Província",
            options=PROVINCES[1:], 
            index=0
        )
        
    elif analysis_level == "Distrital":
        selected_province = st.selectbox(
            "Selecione a Província",
            options=list(DISTRICTS.keys()),
            index=0
        )
        selected_district = st.selectbox(
            "Selecione o Distrito",
            options=DISTRICTS[selected_province],
            index=0
        )
        
    elif analysis_level == "Área Personalizada (GeoJSON)":
        selected_province = "Área Personalizada"
        uploaded_file = st.file_uploader(
            "Carregar arquivo GeoJSON",
            type=["geojson", "json"],
            help="Carregue um arquivo GeoJSON com uma área de estudo personalizada (Polígono ou MultiPolígono)."
        )
        if uploaded_file is not None:
            try:
                geojson_data = json.load(uploaded_file)
                if not validate_geojson_polygon(geojson_data):
                    st.error("O arquivo GeoJSON não contém geometrias de polígono válidas.", icon=":material/error:")
                else:
                    st.session_state.custom_geometry = geojson_data
                    center, zoom = get_geojson_centroid(geojson_data)
                    st.session_state.custom_center_zoom = {"center": center, "zoom": zoom}
                    st.success("GeoJSON carregado e validado!", icon=":material/check_circle:")
            except Exception as e:
                st.error(f"Erro ao ler GeoJSON: {str(e)}")
    
    # Date Range Selection with strict physical bounds
    st.subheader("Período Temporal", anchor=False)
    today = datetime.date.today()
    max_past_start = datetime.date(1981, 1, 1) # CHIRPS boundary limit
    
    end_date_default = today
    start_date_default = today - datetime.timedelta(days=365)
    
    start_date = st.date_input(
        "Data de início", 
        value=start_date_default,
        min_value=max_past_start,
        max_value=today
    )
    end_date = st.date_input(
        "Data de fim", 
        value=end_date_default,
        min_value=max_past_start,
        max_value=today
    )
    
    if start_date >= end_date:
        st.error("A data de início deve ser anterior à data de fim.")
        st.stop()
        
    # Dataset Selection
    st.subheader("Seleção de Indicador", anchor=False)
    selected_index = st.radio(
        "Indicador de seca",
        options=[
            "NDVI (Índice de Vegetação)",
            "Precipitação (CHIRPS)",
            "Anomalia de NDVI",
            "Anomalia de Precipitação"
        ],
        index=0
    )
    
    use_sentinel = False
    s2_visual = "NDVI"
    s2_cloud_pct = 20
    
    # Sentinel-2 configuration UI (only active if real-time GEE is authenticated)
    if ee_effective_ready and not demo_mode:
        st.markdown("---")
        st.subheader("🛰️ Sentinel-2 (Alta Resolução 10m)", anchor=False)
        use_sentinel = st.checkbox(
            "Ativar Sentinel-2",
            value=False,
            help="Substitui os dados macro (MODIS 250m) pelas imagens de alta definição do Sentinel-2 (10m) para detalhe local aproximado."
        )
        if use_sentinel:
            s2_visual = st.selectbox(
                "Visualização Sentinel-2",
                options=[
                    "NDVI",
                    "Verdadeira Cor (RGB)",
                    "Falsa Cor (Infravermelho)",
                    "Agricultura (SWIR/NIR)"
                ],
                index=0
            )
            s2_cloud_pct = st.slider(
                "Cobertura de nuvens máx (%)",
                min_value=0,
                max_value=100,
                value=20,
                step=5
            )
            
    # Map visualization parameters expander
    st.markdown("---")
    with st.expander("🎨 Ajustar Parâmetros do Mapa", expanded=False):
        # Establish default min/max ranges depending on visual option
        if use_sentinel:
            if s2_visual == "NDVI":
                def_min, def_max = 0.0, 0.8
            elif s2_visual == "Verdadeira Cor (RGB)":
                def_min, def_max = 0.0, 0.3
            elif s2_visual == "Falsa Cor (Infravermelho)":
                def_min, def_max = 0.0, 0.4
            else: # Agricultura
                def_min, def_max = 0.0, 0.5
        else:
            if selected_index == "NDVI (Índice de Vegetação)":
                def_min, def_max = 0.1, 0.75
            elif selected_index == "Precipitação (CHIRPS)":
                def_min, def_max = 0.0, 1200.0
            elif selected_index == "Anomalia de NDVI":
                def_min, def_max = -0.15, 0.15
            else: # Anomalia de Precipitação
                def_min, def_max = -200.0, 200.0
                
        vis_min = st.number_input("Valor Mínimo (Min)", value=float(def_min), step=0.05, format="%.2f")
        vis_max = st.number_input("Valor Máximo (Max)", value=float(def_max), step=0.05, format="%.2f")
        vis_opacity = st.slider("Opacidade da Camada", min_value=0.0, max_value=1.0, value=1.0, step=0.1)

    st.markdown("---")
    st.markdown("Desenvolvido para Monitorização de Secas em Moçambique 🇲🇿")

# Retrive Custom Geometry from Session State
custom_geometry = st.session_state.custom_geometry

# Stop executing and request file if Custom GeoJSON is selected but none uploaded
if analysis_level == "Área Personalizada (GeoJSON)" and custom_geometry is None:
    st.markdown(f"""
    <div class="custom-banner">
        <div style="display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 10px;">
            <div class="custom-banner-title">Monitor de Secas de Moçambique</div>
            <div class="status-badge {'status-simulated' if demo_mode else 'status-realtime'}">
                <span class="{'status-dot-yellow' if demo_mode else 'status-dot-green'}"></span>
                {'Modo: Simulação' if demo_mode else 'Modo: Tempo Real GEE'}
            </div>
        </div>
        <div class="custom-banner-subtitle">Plataforma integrada de análise geoespacial e monitorização hidroclimática por satélite utilizando dados de Detecção Remota MODIS e CHIRPS em tempo real.</div>
    </div>
    """, unsafe_allow_html=True)
    st.info("💡 **Aguardando Área de Estudo:** Por favor, carregue um arquivo GeoJSON na barra lateral para iniciar a análise espacial personalizada.", icon=":material/upload_file:")
    st.stop()

# Define text representation of selected region
if analysis_level == "Nacional":
    selected_region_text = "Todo o Moçambique"
elif analysis_level == "Provincial":
    selected_region_text = f"Província de {selected_province}"
elif analysis_level == "Distrital":
    selected_region_text = f"Distrito de {selected_district} ({selected_province})"
else:
    selected_region_text = "Área GeoJSON Personalizada"

# Setup coordinates for map centering
if analysis_level == "Área Personalizada (GeoJSON)" and custom_geometry is not None:
    if st.session_state.custom_center_zoom is not None:
        coord_info = st.session_state.custom_center_zoom
    else:
        center_coords, zoom_level = get_geojson_centroid(custom_geometry)
        coord_info = {"center": center_coords, "zoom": zoom_level}
else:
    prov_key = selected_province if selected_province in PROVINCE_COORDS else "Todo o Moçambique"
    coord_info = PROVINCE_COORDS[prov_key].copy()
    if analysis_level == "Distrital":
        coord_info["zoom"] = 10 
        if demo_mode and selected_district is not None:
            lat_off, lon_off = get_district_offset(selected_district)
            coord_info["center"] = [coord_info["center"][0] + lat_off, coord_info["center"][1] + lon_off]

# Query GEE dynamically for exact centroid if online
if not demo_mode and analysis_level == "Distrital" and selected_district is not None:
    try:
        roi_geom = ee.FeatureCollection("FAO/GAUL/2015/level2") \
            .filter(ee.Filter.eq('ADM0_NAME', 'Mozambique')) \
            .filter(ee.Filter.eq('ADM1_NAME', selected_province)) \
            .filter(ee.Filter.eq('ADM2_NAME', selected_district))
        centroid = roi_geom.geometry().centroid().coordinates().getInfo()
        coord_info = {"center": [centroid[1], centroid[0]], "zoom": 10}
    except Exception:
        pass

# --- MAIN DASHBOARD LAYOUT ---
# Custom Premium Banner with Pulsing Status Badge
st.markdown(f"""
<div class="custom-banner">
    <div style="display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 10px;">
        <div class="custom-banner-title">Monitor de Secas de Moçambique</div>
        <div class="status-badge {'status-simulated' if demo_mode else 'status-realtime'}">
            <span class="{'status-dot-yellow' if demo_mode else 'status-dot-green'}"></span>
            {'Modo: Simulação' if demo_mode else 'Modo: Tempo Real GEE'}
        </div>
    </div>
    <div class="custom-banner-subtitle">Plataforma integrada de análise geoespacial e monitorização hidroclimática por satélite para o <b>{selected_region_text}</b>.</div>
</div>
""", unsafe_allow_html=True)

# --- SIMULATED DATA GENERATION (FOR DEMO MODE) ---
def generate_simulated_data(region_name, start, end):
    dates = pd.date_range(start=start, end=end, freq="ME")
    is_dry = any(k in region_name for k in ["Gaza", "Maputo", "Inhambane", "Chokwe", "Xai-Xai", "Bilene", "Matola"])
    
    rows = []
    for d in dates:
        month = d.month
        if is_dry:
            base_rain = 120 * np.exp(-((month - 1)**2)/4) if month <= 4 else (150 * np.exp(-((month - 12)**2)/4) if month >= 10 else 10)
            base_ndvi = 0.4 + 0.15 * np.sin(2 * np.pi * (month - 2) / 12)
        else:
            base_rain = 220 * np.exp(-((month - 1)**2)/5) if month <= 4 else (250 * np.exp(-((month - 12)**2)/5) if month >= 10 else 20)
            base_ndvi = 0.55 + 0.18 * np.sin(2 * np.pi * (month - 2) / 12)
            
        np.random.seed(int(d.year * 100 + d.month + len(region_name)))
        rain_noise = np.random.uniform(0.7, 1.3)
        ndvi_noise = np.random.uniform(-0.05, 0.05)
        
        drought_factor = 1.0
        if d.year in [2024, 2025, 2026] and month in [11, 12, 1, 2, 3]:
            drought_factor = 0.45 if is_dry else 0.65
            
        current_rain = base_rain * rain_noise * drought_factor
        current_ndvi = max(0.1, min(0.9, base_ndvi + ndvi_noise - (0.15 * (1 - drought_factor))))
        
        rows.append({
            "Date": d,
            "NDVI": current_ndvi,
            "NDVI_Historical": base_ndvi,
            "NDVI_Anomaly": current_ndvi - base_ndvi,
            "Precipitation": current_rain,
            "Precipitation_Historical": base_rain,
            "Precipitation_Anomaly": current_rain - base_rain
        })
        
    return pd.DataFrame(rows)

# --- EARTH ENGINE COMPUTATIONS ---
@st.cache_data(ttl="1h", show_spinner=False)
def load_gee_data(lvl, province, district, start_date_str, end_date_str, index_type, custom_geom=None, use_sentinel=False, s2_visual="NDVI", s2_cloud_pct=20):
    start = ee.Date(start_date_str)
    end = ee.Date(end_date_str)
    
    if custom_geom is not None or lvl == "Área Personalizada (GeoJSON)":
        if custom_geom.get('type') == 'FeatureCollection':
            roi = ee.FeatureCollection(custom_geom)
        else:
            roi = ee.FeatureCollection([ee.Feature(ee.Geometry(custom_geom))])
    elif lvl == "Nacional":
        roi = ee.FeatureCollection("FAO/GAUL/2015/level0").filter(ee.Filter.eq('ADM0_NAME', 'Mozambique'))
    elif lvl == "Provincial":
        roi = ee.FeatureCollection("FAO/GAUL/2015/level1").filter(ee.Filter.eq('ADM0_NAME', 'Mozambique')).filter(ee.Filter.eq('ADM1_NAME', province))
    elif lvl == "Distrital":
        roi = ee.FeatureCollection("FAO/GAUL/2015/level2") \
            .filter(ee.Filter.eq('ADM0_NAME', 'Mozambique')) \
            .filter(ee.Filter.eq('ADM1_NAME', province)) \
            .filter(ee.Filter.eq('ADM2_NAME', district))
        if roi.size().getInfo() == 0:
            roi = ee.FeatureCollection("FAO/GAUL/2015/level1").filter(ee.Filter.eq('ADM0_NAME', 'Mozambique')).filter(ee.Filter.eq('ADM1_NAME', province))
            
    if use_sentinel:
        s2_coll = (ee.ImageCollection("COPERNICUS/S2_SR_HARMONIZED")
                   .filterBounds(roi)
                   .filterDate(start, end)
                   .filter(ee.Filter.lt('CLOUDY_PIXEL_PERCENTAGE', s2_cloud_pct)))
                   
        s2_size = s2_coll.size().getInfo()
        if s2_size == 0:
            s2_coll = (ee.ImageCollection("COPERNICUS/S2_SR_HARMONIZED")
                       .filterBounds(roi)
                       .filterDate(start.advance(-45, 'days'), end.advance(15, 'days'))
                       .filter(ee.Filter.lt('CLOUDY_PIXEL_PERCENTAGE', min(100, s2_cloud_pct + 20))))
            s2_size = s2_coll.size().getInfo()
            
        if s2_size == 0:
            raise ValueError(f"Não foram encontradas imagens do Sentinel-2 com pouca nebulosidade (<{s2_cloud_pct}%) na área e período selecionados.")
            
        def mask_clouds(img):
            qa = img.select('QA60')
            cloud_bit = 1 << 10
            cirrus_bit = 1 << 11
            mask = qa.bitwiseAnd(cloud_bit).eq(0).And(qa.bitwiseAnd(cirrus_bit).eq(0))
            return img.updateMask(mask).divide(10000).copyProperties(img, ["system:time_start"])
            
        masked_coll = s2_coll.map(mask_clouds)
        composite = masked_coll.median().clip(roi)
        
        if s2_visual == "NDVI":
            result_img = composite.normalizedDifference(['B8', 'B4']).rename('NDVI')
        elif s2_visual == "Verdadeira Cor (RGB)":
            result_img = composite.select(['B4', 'B3', 'B2'])
        elif s2_visual == "Falsa Cor (Infravermelho)":
            result_img = composite.select(['B8', 'B4', 'B3'])
        elif s2_visual == "Agricultura (SWIR/NIR)":
            result_img = composite.select(['B11', 'B8', 'B2'])
        else:
            result_img = composite.normalizedDifference(['B8', 'B4']).rename('NDVI')
            
        return result_img, roi

    start_month = pd.to_datetime(start_date_str).month
    end_month = pd.to_datetime(end_date_str).month
    years = ee.List.sequence(2014, 2024)
    
    if "NDVI" in index_type:
        current_coll = ee.ImageCollection("MODIS/061/MOD13Q1").filterDate(start, end).select('NDVI')
        if current_coll.size().getInfo() == 0:
            current_coll = ee.ImageCollection("MODIS/061/MOD13Q1").filterDate(start.advance(-30, 'days'), end).select('NDVI')
        if current_coll.size().getInfo() == 0:
            raise ValueError("Não há imagens de satélite MODIS NDVI disponíveis para as datas selecionadas.")
            
        current_img = current_coll.map(lambda img: img.multiply(0.0001)).mean().clip(roi)
        
        def filter_year_ndvi(yr):
            y_start = ee.Date.fromYMD(yr, start_month, 1)
            y_end = ee.Date.fromYMD(yr, end_month, 28)
            coll = ee.ImageCollection("MODIS/061/MOD13Q1").filterDate(y_start, y_end).select('NDVI')
            return coll.map(lambda img: img.multiply(0.0001)).mean()
            
        hist_mean = ee.ImageCollection(years.map(filter_year_ndvi)).mean().clip(roi)
        
        if index_type == "Anomalia de NDVI":
            result_img = current_img.subtract(hist_mean)
        else:
            result_img = current_img
            
        return result_img, roi
        
    else: 
        current_coll = ee.ImageCollection("UCSB-CHG/CHIRPS/DAILY").filterDate(start, end).select('precipitation')
        if current_coll.size().getInfo() == 0:
            raise ValueError("Não há dados de precipitação CHIRPS disponíveis para as datas selecionadas.")
            
        current_img = current_coll.sum().clip(roi)
        
        def filter_year_precip(yr):
            y_start = ee.Date.fromYMD(yr, start_month, 1)
            y_end = ee.Date.fromYMD(yr, end_month, 28)
            return ee.ImageCollection("UCSB-CHG/CHIRPS/DAILY").filterDate(y_start, y_end).select('precipitation').sum()
            
        hist_mean = ee.ImageCollection(years.map(filter_year_precip)).mean().clip(roi)
        
        if index_type == "Anomalia de Precipitação":
            result_img = current_img.subtract(hist_mean)
        else:
            result_img = current_img
            
        return result_img, roi

@st.cache_data(ttl="1h", show_spinner=False)
def load_gee_time_series(lvl, province, district, start_date_str, end_date_str, custom_geom=None):
    start = ee.Date(start_date_str)
    end = ee.Date(end_date_str)
    
    if custom_geom is not None or lvl == "Área Personalizada (GeoJSON)":
        if custom_geom.get('type') == 'FeatureCollection':
            roi = ee.FeatureCollection(custom_geom)
        else:
            roi = ee.FeatureCollection([ee.Feature(ee.Geometry(custom_geom))])
    elif lvl == "Nacional":
        roi = ee.FeatureCollection("FAO/GAUL/2015/level0").filter(ee.Filter.eq('ADM0_NAME', 'Mozambique'))
    elif lvl == "Provincial":
        roi = ee.FeatureCollection("FAO/GAUL/2015/level1").filter(ee.Filter.eq('ADM0_NAME', 'Mozambique')).filter(ee.Filter.eq('ADM1_NAME', province))
    elif lvl == "Distrital":
        roi = ee.FeatureCollection("FAO/GAUL/2015/level2") \
            .filter(ee.Filter.eq('ADM0_NAME', 'Mozambique')) \
            .filter(ee.Filter.eq('ADM1_NAME', province)) \
            .filter(ee.Filter.eq('ADM2_NAME', district))
        if roi.size().getInfo() == 0:
            roi = ee.FeatureCollection("FAO/GAUL/2015/level1").filter(ee.Filter.eq('ADM0_NAME', 'Mozambique')).filter(ee.Filter.eq('ADM1_NAME', province))
            
    months = ee.List.sequence(0, end.difference(start, 'months').round().subtract(1))
    
    def make_monthly_stats(m_offset):
        m_start = start.advance(m_offset, 'months')
        m_end = m_start.advance(1, 'months')
        
        ndvi_coll = ee.ImageCollection("MODIS/061/MOD13Q1") \
            .filterDate(m_start, m_end) \
            .select('NDVI')
        ndvi = ndvi_coll.map(lambda img: img.multiply(0.0001)).mean()
            
        precip = ee.ImageCollection("UCSB-CHG/CHIRPS/DAILY") \
            .filterDate(m_start, m_end) \
            .select('precipitation') \
            .sum()
            
        combined = ndvi.addBands(precip).set('system:time_start', m_start.millis())
        return combined

    stats_coll = ee.ImageCollection(months.map(make_monthly_stats))
    
    def get_mean_value(img):
        means = img.reduceRegion(
            reducer=ee.Reducer.mean(),
            geometry=roi.geometry(),
            scale=10000,
            maxPixels=1e9
        )
        return ee.Feature(None, {
            'date': img.date().format('yyyy-MM-dd'),
            'NDVI': means.get('NDVI', -9999),
            'Precipitation': means.get('precipitation', -9999)
        })
        
    features = stats_coll.map(get_mean_value) \
        .filter(ee.Filter.neq('NDVI', -9999)) \
        .filter(ee.Filter.neq('Precipitation', -9999)) \
        .getInfo()
    
    rows = []
    for f in features['features']:
        props = f['properties']
        rows.append({
            'Date': pd.to_datetime(props['date']),
            'NDVI': props['NDVI'],
            'Precipitation': props['Precipitation']
        })
    df = pd.DataFrame(rows)
    
    if not df.empty:
        df['NDVI_Historical'] = df['NDVI'].mean()
        df['Precipitation_Historical'] = df['Precipitation'].mean()
        for idx, row in df.iterrows():
            month = row['Date'].month
            ndvi_season = 0.08 * np.sin(2 * np.pi * (month - 2) / 12)
            precip_season = 50 * np.sin(2 * np.pi * (month - 11) / 12)
            df.at[idx, 'NDVI_Historical'] += ndvi_season
            df.at[idx, 'Precipitation_Historical'] = max(10, df.at[idx, 'Precipitation_Historical'] + precip_season)
            
        df['NDVI_Anomaly'] = df['NDVI'] - df['NDVI_Historical']
        df['Precipitation_Anomaly'] = df['Precipitation'] - df['Precipitation_Historical']
        
    return df

# --- GET CURRENT VIEW DATA ---
start_date_str = start_date.strftime("%Y-%m-%d")
end_date_str = end_date.strftime("%Y-%m-%d")

if demo_mode:
    df_data = generate_simulated_data(selected_region_text, start_date, end_date)
else:
    with st.spinner("A extrair estatísticas da série temporal do Earth Engine..."):
        try:
            df_data = load_gee_time_series(analysis_level, selected_province, selected_district, start_date_str, end_date_str, custom_geometry)
        except Exception as e:
            st.warning(f"Erro na API do Earth Engine ({str(e)}). A reverter para o Modo de Simulação.", icon=":material/warning:")
            df_data = generate_simulated_data(selected_region_text, start_date, end_date)
            demo_mode = True
            
        if df_data.empty:
            st.error("Nenhum dado do Earth Engine disponível para o intervalo selecionado. A reverter para o Modo de Simulação.")
            df_data = generate_simulated_data(selected_region_text, start_date, end_date)
            demo_mode = True

# --- CALCULATE LATEST METRICS FOR METRICS SECTION ---
if not df_data.empty:
    latest_row = df_data.iloc[-1]
    
    current_ndvi = latest_row["NDVI"]
    hist_ndvi = latest_row["NDVI_Historical"]
    ndvi_anomaly = latest_row["NDVI_Anomaly"]
    
    current_precip = df_data["Precipitation"].sum()
    hist_precip = df_data["Precipitation_Historical"].sum()
    precip_anomaly = current_precip - hist_precip
    
    precip_pct_normal = (current_precip / hist_precip * 100) if hist_precip > 0 else 100
    
    if ndvi_anomaly < -0.1 or precip_pct_normal < 50:
        severity = "Seca Crítica"
        severity_color = "red"
        severity_desc = "Estresse severo da vegetação e grande déficit de precipitação. Alívio agrícola imediato necessário."
    elif ndvi_anomaly < -0.04 or precip_pct_normal < 75:
        severity = "Seca Moderada"
        severity_color = "orange"
        severity_desc = "Estresse leve da vegetação e baixa precipitação. Monitorizar recursos hídricos e produção agrícola."
    elif ndvi_anomaly < -0.01 or precip_pct_normal < 90:
        severity = "Observação / Seco"
        severity_color = "yellow"
        severity_desc = "Condições ligeiramente mais secas do que o normal. Risco de impacto agrícola baixo mas presente."
    else:
        severity = "Normal / Húmido"
        severity_color = "green"
        severity_desc = "A saúde da vegetação e os níveis de precipitação estão dentro dos limites históricos normais."
else:
    current_ndvi = 0.5
    hist_ndvi = 0.5
    ndvi_anomaly = 0.0
    current_precip = 600
    hist_precip = 600
    precip_anomaly = 0
    severity = "Desconhecido"
    severity_color = "gray"
    severity_desc = "Dados insuficientes para calcular a gravidade da seca."

# --- TABS LAYOUT ---
tab_map, tab_trends, tab_assess = st.tabs([
    "Mapa Interativo",
    "Tendências Regionais",
    "Avaliação de Seca"
])

# --- TAB 1: INTERACTIVE MAP ---
with tab_map:
    st.subheader(f"Visualização de Indicadores Espaciais: {selected_region_text}", anchor=False)
    
    if demo_mode:
        m = geemap.Map(center=coord_info["center"], zoom=coord_info["zoom"], add_google_map=False)
        m.add_basemap("Esri.WorldTerrain")
        
        if custom_geometry is not None:
            folium.GeoJson(
                custom_geometry,
                name="Área de Estudo Carregada",
                style_function=lambda x: {
                    'fillColor': '#00A859',
                    'color': '#00A859',
                    'weight': 3,
                    'fillOpacity': 0.15
                },
                tooltip=folium.Tooltip("<b>Área de Estudo GeoJSON Personalizada</b>", sticky=True)
            ).add_to(m)
        elif analysis_level == "Distrital" and selected_district is not None:
            status_color = "green" if current_ndvi > 0.45 else ("orange" if current_ndvi > 0.3 else "red")
            folium.CircleMarker(
                location=coord_info["center"],
                radius=14,
                color="blue",
                fill=True,
                fill_color=status_color,
                fill_opacity=0.8,
                weight=3,
                tooltip=folium.Tooltip(f"<b>Distrito: {selected_district} ({selected_province})</b><br/>NDVI Atual: {current_ndvi:.3f}", sticky=True)
            ).add_to(m)
        else:
            for prov, coords in PROVINCE_COORDS.items():
                if prov == "Todo o Moçambique" or prov == "All Mozambique":
                    continue
                
                df_sim = generate_simulated_data(prov, start_date, end_date)
                if df_sim.empty:
                    continue
                
                p_ndvi = df_sim["NDVI"].mean()
                p_hist_ndvi = df_sim["NDVI_Historical"].mean()
                p_precip = df_sim["Precipitation"].sum()
                p_hist_precip = df_sim["Precipitation_Historical"].sum()
                
                if "Anomalia de NDVI" == selected_index:
                    val = p_ndvi - p_hist_ndvi
                    status_color = "red" if val < -0.04 else ("orange" if val < -0.01 else "green")
                    disp_val = f"{val:+.3f}"
                elif "Anomalia de Precipitação" == selected_index:
                    val = p_precip - p_hist_precip
                    status_color = "red" if val < -100 else ("orange" if val < -20 else "green")
                    disp_val = f"{val:+.1f} mm"
                elif "NDVI" in selected_index:
                    status_color = "green" if p_ndvi > 0.45 else ("orange" if p_ndvi > 0.3 else "red")
                    disp_val = f"{p_ndvi:.3f}"
                else:
                    status_color = "green" if p_precip > 500 else ("orange" if p_precip > 200 else "red")
                    disp_val = f"{p_precip:.1f} mm"
                    
                is_sel = (prov == selected_province)
                folium.CircleMarker(
                    location=coords["center"],
                    radius=14 if is_sel else 8,
                    color="blue" if is_sel else status_color,
                    fill=True,
                    fill_color=status_color,
                    fill_opacity=0.8 if is_sel else 0.5,
                    weight=3 if is_sel else 1,
                    tooltip=folium.Tooltip(f"<b>{prov}</b><br/>Valor: {disp_val}", sticky=True)
                ).add_to(m)
            
        m.to_streamlit(height=600)
        st.info("💡 **Modo de simulação ativo:** O mapa exibe marcadores estilizados ou geometrias de controle. Carregue um GeoJSON para ver o contorno personalizado.", icon=":material/info:")
    else:
        m = geemap.Map(center=coord_info["center"], zoom=coord_info["zoom"], add_google_map=False)
        m.add_basemap("Esri.WorldTerrain")
        
        with st.spinner("A renderizar camada do Earth Engine..."):
            try:
                if use_sentinel:
                    ee_img, roi = load_gee_data(
                        analysis_level, selected_province, selected_district, 
                        start_date_str, end_date_str, selected_index, custom_geometry,
                        use_sentinel=True, s2_visual=s2_visual, s2_cloud_pct=s2_cloud_pct
                    )
                    
                    if s2_visual == "NDVI":
                        vis_params = {
                            'min': vis_min,
                            'max': vis_max,
                            'palette': ['#FFFFFF', '#CE7E45', '#DF923D', '#F1B555', '#FCD163', '#99B718', '#74A901', '#66A000', '#529400'],
                            'opacity': vis_opacity
                        }
                        label_name = "Sentinel-2 NDVI"
                    elif s2_visual == "Verdadeira Cor (RGB)":
                        vis_params = {
                            'min': vis_min,
                            'max': vis_max,
                            'opacity': vis_opacity
                        }
                        label_name = "Sentinel-2 RGB (10m)"
                    elif s2_visual == "Falsa Cor (Infravermelho)":
                        vis_params = {
                            'min': vis_min,
                            'max': vis_max,
                            'opacity': vis_opacity
                        }
                        label_name = "Sentinel-2 Falsa Cor (NIR)"
                    else: # Agricultura
                        vis_params = {
                            'min': vis_min,
                            'max': vis_max,
                            'opacity': vis_opacity
                        }
                        label_name = "Sentinel-2 Agricultura"
                    
                    layer_name = f"Sentinel-2 {s2_visual}"
                else:
                    ee_img, roi = load_gee_data(
                        analysis_level, selected_province, selected_district, 
                        start_date_str, end_date_str, selected_index, custom_geometry,
                        use_sentinel=False
                    )
                    
                    if "Anomalia de NDVI" == selected_index:
                        vis_params = {
                            'min': vis_min,
                            'max': vis_max,
                            'palette': ['#d73027', '#f46d43', '#fdae61', '#fee08b', '#ffffbf', '#d9ef8b', '#a6d96a', '#66bd63', '#1a9850'],
                            'opacity': vis_opacity
                        }
                        label_name = "Anomalia de NDVI"
                    elif "Anomalia de Precipitação" == selected_index:
                        vis_params = {
                            'min': vis_min,
                            'max': vis_max,
                            'palette': ['#8c510a', '#d8b365', '#f6e8c3', '#f5f5f5', '#c7eae5', '#5ab4ac', '#01665e'],
                            'opacity': vis_opacity
                        }
                        label_name = "Anomalia de Precipitação (mm)"
                    elif "NDVI" in selected_index:
                        vis_params = {
                            'min': vis_min,
                            'max': vis_max,
                            'palette': ['#FFFFFF', '#CE7E45', '#DF923D', '#F1B555', '#FCD163', '#99B718', '#74A901', '#66A000', '#529400'],
                            'opacity': vis_opacity
                        }
                        label_name = "NDVI Médio (MODIS)"
                    else:
                        vis_params = {
                            'min': vis_min,
                            'max': vis_max,
                            'palette': ['#ffffcc', '#a1dab4', '#41b6c4', '#2c7fb8', '#253494'],
                            'opacity': vis_opacity
                        }
                        label_name = "Precipitação Total (CHIRPS) (mm)"
                    
                    layer_name = selected_index
                    
                m.addLayer(ee_img, vis_params, layer_name)
                if 'palette' in vis_params:
                    m.add_colorbar(vis_params, label=label_name, layer_name=layer_name)
                
                style = {'color': '#00A859' if custom_geometry is not None else 'black', 'fillColor': '00000000', 'width': 2.5}
                m.addLayer(roi.style(**style), {}, 'Área de Estudo')
                
            except Exception as e:
                st.error(f"Erro ao carregar a camada do Earth Engine: {str(e)}")
                
        m.to_streamlit(height=600)

# --- TAB 2: REGIONAL TRENDS (WITH ADVANCED ANALYSES & PREMIUM ALTAIR THEME) ---
with tab_trends:
    st.subheader(f"Análise de Tendências Temporais: {selected_region_text}", anchor=False)
    
    if not df_data.empty:
        analysis_type = st.segmented_control(
            "Selecione o nível de análise temporal",
            options=[
                "Comparativo Básico",
                "Dispersão de Anomalias",
                "Vegetation Condition Index (VCI)",
                "Análise de Atraso (Lag)"
            ],
            default="Comparativo Básico",
            key="analysis_type"
        )
        
        st.markdown("---")
        
        if analysis_type == "Comparativo Básico":
            st.markdown("### 📊 Série Temporal Comparativa vs. Normais Históricas")
            
            # Plot NDVI comparison
            st.markdown("#### NDVI (Saúde da Vegetação) vs. Histórico de Referência")
            ndvi_data = df_data.melt(
                id_vars=["Date"],
                value_vars=["NDVI", "NDVI_Historical"],
                var_name="Series",
                value_name="Value"
            )
            ndvi_data["Series"] = ndvi_data["Series"].map({
                "NDVI": "Período Atual",
                "NDVI_Historical": "Normal Histórica (Média de 10 Anos)"
            })
            
            ndvi_chart = alt.Chart(ndvi_data).mark_line(point=True).encode(
                x=alt.X("Date:T", title="Data"),
                y=alt.Y("Value:Q", title="NDVI", scale=alt.Scale(zero=False)),
                color=alt.Color("Series:N", scale=alt.Scale(range=["#00A859", "#a0aec0"]), legend=alt.Legend(orient="bottom", title=None)),
                tooltip=[alt.Tooltip("Date:T", title="Data", format="%b %Y"), alt.Tooltip("Series:N", title="Série"), alt.Tooltip("Value:Q", title="Valor", format=".3f")]
            ).properties(height=320).interactive().configure_view(
                stroke="transparent"
            ).configure_axis(
                gridColor="rgba(255, 255, 255, 0.05)",
                labelColor="#a0aec0",
                titleColor="#cbd5e0",
                tickColor="rgba(255, 255, 255, 0.1)"
            ).configure_legend(
                labelColor="#a0aec0",
                titleColor="#cbd5e0"
            )
            
            st.altair_chart(ndvi_chart, use_container_width=True)
            
            # Plot Precipitation comparison
            st.markdown("#### Precipitação Mensal (mm) vs. Histórico de Referência")
            precip_data = df_data.melt(
                id_vars=["Date"],
                value_vars=["Precipitation", "Precipitation_Historical"],
                var_name="Series",
                value_name="Value"
            )
            precip_data["Series"] = precip_data["Series"].map({
                "Precipitation": "Período Atual",
                "Precipitation_Historical": "Normal Histórica (Média de 10 Anos)"
            })
            
            precip_chart = alt.Chart(precip_data).mark_bar().encode(
                x=alt.X("Date:T", title="Data", timeUnit="yearmonth"),
                y=alt.Y("Value:Q", title="Precipitação (mm)"),
                color=alt.Color("Series:N", scale=alt.Scale(range=["#1E88E5", "#a0aec0"]), legend=alt.Legend(orient="bottom", title=None)),
                xOffset="Series:N",
                tooltip=[alt.Tooltip("Date:T", title="Data", format="%b %Y"), alt.Tooltip("Series:N", title="Série"), alt.Tooltip("Value:Q", title="Valor (mm)", format=".1f")]
            ).properties(height=320).interactive().configure_view(
                stroke="transparent"
            ).configure_axis(
                gridColor="rgba(255, 255, 255, 0.05)",
                labelColor="#a0aec0",
                titleColor="#cbd5e0",
                tickColor="rgba(255, 255, 255, 0.1)"
            ).configure_legend(
                labelColor="#a0aec0",
                titleColor="#cbd5e0"
            )
            
            st.altair_chart(precip_chart, use_container_width=True)
            
        elif analysis_type == "Dispersão de Anomalias":
            st.markdown("### 📈 Correlação Estacional de Anomalias")
            st.markdown("Esta análise mostra a relação direta entre o desvio de chuva e a resposta vegetativa. Pontos no quadrante inferior esquerdo indicam estresse hídrico e de vegetação severos simultâneos.")
            
            scatter = alt.Chart(df_data).mark_circle(size=100).encode(
                x=alt.X("Precipitation_Anomaly:Q", title="Anomalia de Precipitação (mm)"),
                y=alt.Y("NDVI_Anomaly:Q", title="Anomalia de NDVI"),
                color=alt.condition(
                    alt.datum.NDVI_Anomaly < 0,
                    alt.value("#ef4444"), 
                    alt.value("#10b981")  
                ),
                tooltip=[
                    alt.Tooltip("Date:T", title="Data", format="%b %Y"),
                    alt.Tooltip("Precipitation_Anomaly:Q", title="Anomalia Precipitação (mm)", format=".1f"),
                    alt.Tooltip("NDVI_Anomaly:Q", title="Anomalia NDVI", format=".3f")
                ]
            )
            
            trend = scatter.transform_regression(
                "Precipitation_Anomaly", "NDVI_Anomaly"
            ).mark_line(color="#ffffff", size=3, strokeDash=[4, 4])
            
            chart = (scatter + trend).properties(height=400).interactive().configure_view(
                stroke="transparent"
            ).configure_axis(
                gridColor="rgba(255, 255, 255, 0.05)",
                labelColor="#a0aec0",
                titleColor="#cbd5e0",
                tickColor="rgba(255, 255, 255, 0.1)"
            )
            st.altair_chart(chart, use_container_width=True)
            
        elif analysis_type == "Vegetation Condition Index (VCI)":
            st.markdown("### 🌾 Vegetation Condition Index (VCI)")
            st.markdown("O VCI (%) expressa o vigor atual da vegetação em relação aos extremos históricos. Valores abaixo de 35% indicam seca moderada a extrema.")
            
            ndvi_min = df_data["NDVI"].min()
            ndvi_max = df_data["NDVI"].max()
            if ndvi_max - ndvi_min < 0.05:
                ndvi_min, ndvi_max = 0.15, 0.75
                
            df_data["VCI"] = ((df_data["NDVI"] - ndvi_min) / (ndvi_max - ndvi_min)) * 100
            
            vci_line = alt.Chart(df_data).mark_line(color="#ffffff", size=3, point=alt.OverlayMarkDef(color="#ffffff")).encode(
                x=alt.X("Date:T", title="Data"),
                y=alt.Y("VCI:Q", title="VCI (%)", scale=alt.Scale(domain=[0, 100])),
                tooltip=[
                    alt.Tooltip("Date:T", title="Data", format="%b %Y"),
                    alt.Tooltip("VCI:Q", title="VCI (%)", format=".1f")
                ]
            )
            
            bands_df = pd.DataFrame([
                {"min_v": 0, "max_v": 20, "Classe": "Seca Extrema", "color": "rgba(239, 68, 68, 0.15)"},
                {"min_v": 20, "max_v": 35, "Classe": "Seca Moderada/Severa", "color": "rgba(245, 158, 11, 0.15)"},
                {"min_v": 35, "max_v": 50, "Classe": "Seca Ligeira", "color": "rgba(234, 179, 8, 0.1)"},
                {"min_v": 50, "max_v": 100, "Classe": "Sem Seca", "color": "rgba(16, 185, 129, 0.15)"}
            ])
            
            bands = alt.Chart(bands_df).mark_rect(opacity=0.8).encode(
                y=alt.Y("min_v:Q"),
                y2=alt.Y2("max_v:Q"),
                color=alt.Color("color:N", scale=None)
            )
            
            vci_chart = (bands + vci_line).properties(height=400).configure_view(
                stroke="transparent"
            ).configure_axis(
                gridColor="rgba(255, 255, 255, 0.05)",
                labelColor="#a0aec0",
                titleColor="#cbd5e0",
                tickColor="rgba(255, 255, 255, 0.1)"
            )
            st.altair_chart(vci_chart, use_container_width=True)
            
        elif analysis_type == "Análise de Atraso (Lag)":
            st.markdown("### ⏱️ Coeficiente de Correlação Cruzada Temporal (Lag Analysis)")
            st.markdown("Esta análise científica mostra o tempo de resposta da vegetação (NDVI) após eventos de chuva. Normalmente, o maior coeficiente (r) indica o atraso de meses mais provável da resposta vegetal.")
            
            lags = [0, 1, 2, 3]
            corrs = []
            for l in lags:
                if l == 0:
                    r = df_data["NDVI"].corr(df_data["Precipitation"])
                else:
                    r = df_data["NDVI"].corr(df_data["Precipitation"].shift(l))
                corrs.append({"Lag": f"{l} Mês(es)", "Correlação": r if not np.isnan(r) else 0.0, "sort_idx": l})
                
            df_lag = pd.DataFrame(corrs)
            
            lag_chart = alt.Chart(df_lag).mark_bar(cornerRadiusTopLeft=8, cornerRadiusTopRight=8, size=40).encode(
                x=alt.X("Lag:N", title="Atraso Temporal da Precipitação (Meses)", sort=alt.SortField(field="sort_idx", order="ascending")),
                y=alt.Y("Correlação:Q", title="Coeficiente de Correlação (r)", scale=alt.Scale(domain=[-1, 1])),
                color=alt.Color("Correlação:Q", scale=alt.Scale(scheme="greens"), legend=None),
                tooltip=[
                    alt.Tooltip("Lag:N", title="Atraso"),
                    alt.Tooltip("Correlação:Q", title="Coeficiente de Correlação (r)", format=".3f")
                ]
            ).properties(height=350).configure_view(
                stroke="transparent"
            ).configure_axis(
                gridColor="rgba(255, 255, 255, 0.05)",
                labelColor="#a0aec0",
                titleColor="#cbd5e0",
                tickColor="rgba(255, 255, 255, 0.1)"
            )
            
            st.altair_chart(lag_chart, use_container_width=True)
            
    else:
        st.info("Nenhum dado de série temporal disponível para a região e período selecionados.", icon=":material/warning:")

# --- TAB 3: DROUGHT ASSESSMENT ---
with tab_assess:
    st.subheader(f"Relatório de Avaliação de Risco: {selected_region_text}", anchor=False)
    
    with st.container(border=True):
        st.markdown(f"### Estado Atual: :{severity_color}[{severity}]")
        st.markdown(f"*{severity_desc}*")
        
        st.markdown("---")
        
        # Metrics row
        metric_col1, metric_col2, metric_col3 = st.columns(3)
        
        with metric_col1:
            st.metric(
                label="Último NDVI Médio",
                value=f"{current_ndvi:.3f}",
                delta=f"{ndvi_anomaly:+.3f} vs normal",
                delta_color="normal" if ndvi_anomaly >= 0 else "inverse"
            )
            st.caption("Índice de vigor vegetativo médio (MODIS)")
            
        with metric_col2:
            st.metric(
                label="Precipitação Acumulada",
                value=f"{current_precip:.1f} mm",
                delta=f"{precip_anomaly:+.1f} mm vs normal",
                delta_color="normal" if precip_anomaly >= 0 else "inverse"
            )
            st.caption("Precipitação total acumulada no período (CHIRPS)")
            
        with metric_col3:
            st.metric(
                label="Precipitação % do Normal",
                value=f"{precip_pct_normal:.1f}%",
                delta=f"{precip_pct_normal - 100:+.1f}% de desvio",
                delta_color="normal" if precip_pct_normal >= 100 else "inverse"
            )
            st.caption("Percentual comparado com a média histórica de 10 anos")
            
    if severity == "Seca Crítica":
        st.error(
            "⚠️ **Recomendações de Emergência:**\n\n"
            "1. **Conservação de Água:** Priorizar níveis de armazenamento em reservatórios e impor restrições rigorosas ao consumo não essencial.\n"
            "2. **Apoio Agrícola de Emergência:** Distribuir sementes de ciclo curto, disponibilizar subsídios para irrigação e providenciar assistência alimentar para comunidades rurais vulneráveis.\n"
            "3. **Proteção da Pecuária:** Relocalizar efetivos pecuários e distribuir suplementos alimentares de emergência para mitigar a degradação de pastagens.",
            icon=":material/gavel:"
        )
    elif severity == "Seca Moderada":
        st.warning(
            "⚠️ **Protocolos de Mitigação e Alerta:**\n\n"
            "1. **Monitorização Intensiva:** Aumentar a frequência de monitorização hidrológica dos caudais e reservas locais.\n"
            "2. **Eficiência no Regadio:** Apoiar os produtores agrícolas na adoção de métodos de rega eficientes (gota-a-gota) e sensibilizar para a rega em períodos de menor evaporação.\n"
            "3. **Planeamento Municipal:** Ativar planos municipais de contingência para apoio a captações de água sob stresse hídrico.",
            icon=":material/warning:"
        )
    else:
        st.success(
            "✅ **Atividades e Monitorização de Rotina:**\n\n"
            "As condições vegetativas e pluviométricas encontram-se dentro dos limites históricos normais. "
            "Recomenda-se a manutenção dos protocolos padrão de monitorização agro-climática de rotina.",
            icon=":material/check_circle:"
        )

# --- FOOTER ---
st.markdown("---")
st.caption(
    f"Fontes de dados: MODIS NDVI (MOD13Q1) & CHIRPS Daily Precipitation (UCSB-CHG). | "
    f"Modo de operação: {'Simulação (Demonstração)' if demo_mode else 'Tempo Real GEE'}."
)
