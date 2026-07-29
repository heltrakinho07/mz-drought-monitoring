# Mozambique Drought Monitoring Dashboard 🇲🇿 🌍 🛰️

[![Streamlit App](https://static.streamlit.io/badge_cdn.svg)](https://share.streamlit.io)
[![Google Earth Engine](https://img.shields.io/badge/Google_Earth_Engine-Active-green?logo=google-earth-engine&logoColor=white)](https://earthengine.google.com/)
[![Python](https://img.shields.io/badge/Python-3.12-blue?logo=python&logoColor=white)](https://www.python.org/)
[![License](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

🇺🇸 **English Documentation Below** | 🇵🇹 **Documentação em Português Abaixo**

---

## 🇵🇹 Versão em Português

O **Monitor de Secas de Moçambique** é uma plataforma de análise geoespacial de alta performance desenvolvida em Python e integrada com o **Google Earth Engine (GEE)**. O sistema monitoriza a saúde da vegetação e anomalias pluviométricas em tempo real para apoiar a tomada de decisões agrícolas e a gestão de recursos hídricos face a eventos climáticos extremos.

### 🌟 Funcionalidades Principais

- **Hierarquia Territorial Multinível (ADM2):** Análise geoespacial nos níveis Nacional, Provincial (ADM1) e Distrital (ADM2) utilizando limites oficiais do GAUL (FAO).
- **Área Personalizada via GeoJSON:** Suporte a drag-and-drop de arquivos GeoJSON customizados com extração dinâmica de centróide para enquadramento automático do mapa.
- **Análises Temporais Avançadas:**
  - *Comparativo Básico:* Relação mensal de NDVI e precipitação atual vs. médias históricas de 10 anos.
  - *Dispersão de Anomalias:* Gráfico de dispersão cruzada com linha de tendência linear identificando anomalias estacionais.
  - *Vegetation Condition Index (VCI):* Análise histórica com faixas de severidade de seca (Seca Extrema, Moderada, Ligeira e Sem Seca).
  - *Análise de Atraso Pluviométrico (Lag Analysis):* Correlação cruzada de Pearson ($r$) variando o atraso (0 a 3 meses) para medir o tempo de resposta da vegetação à precipitação.
- **Interface Glassmorphic Premium:** Tema personalizado com fontes modernas (Outfit/Inter), cartões métricos translúcidos com efeitos hover, crachás de estado animados (pulsing status) e gráficos Altair transparentes integrados.
- **Resiliência e Robustez:**
  - *Modo Simulação (Offline):* Fallback automático caso a autenticação do GEE falhe ou a quota de requisições exceda.
  - *Validador de GeoJSON:* Verificação estrutural matemática para garantir o carregamento apenas de geometrias poligonais válidas.
  - *Restrições Temporais:* Limites de datas físicos baseados na operação dos satélites (MODIS > 2000, CHIRPS > 1981).

### 🛠️ Fontes de Dados e Tecnologia
- **Vegetação (NDVI):** MODIS/061/MOD13Q1 (250m de resolução, a cada 16 dias).
- **Precipitação:** UCSB-CHG/CHIRPS/DAILY (0.05° de resolução, diária).
- **Fronteiras:** FAO/GAUL/2015 (Níveis 0, 1 e 2).
- **Visualização Espacial:** Geemap / Folium.
- **Gráficos:** Altair (Declarative Statistical Visualization).

---

### ⚙️ Instalação e Execução

#### 1. Clonar o Repositório
```bash
git clone https://github.com/heltrakinho07/mz-drought-monitoring.git
cd mz-drought-monitoring
```

#### 2. Configurar o Ambiente Virtual
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

#### 3. Configurar Credenciais do GEE
Crie um arquivo `.streamlit/secrets.toml` na raiz do projeto contendo a sua chave do Earth Engine:
```toml
GEE_PROJECT_ID = "seu-projeto-gee"
GEE_SERVICE_ACCOUNT_KEY = '{"type": "service_account", "project_id": "seu-projeto-gee", ...}'
```

#### 4. Executar o Dashboard
```bash
streamlit run streamlit_app.py
```

---

## 🇺🇸 English Version

The **Mozambique Drought Monitor** is a high-performance geospatial analysis platform built in Python and integrated with **Google Earth Engine (GEE)**. The system monitors vegetation health and rainfall anomalies in real time to support agricultural decision-making and water resource management during extreme climate events.

### 🌟 Key Features

- **Multi-Level Territorial Hierarchy (ADM2):** Spatial analysis at National, Provincial (ADM1), and District (ADM2) levels using official FAO GAUL administrative boundaries.
- **Custom Study Area (GeoJSON):** Drag-and-drop support for custom GeoJSON files with automatic centroid extraction and map auto-centering.
- **Advanced Temporal Analyses:**
  - *Basic Comparison:* Monthly time series comparing current NDVI and precipitation against 10-year historical means.
  - *Anomaly Scatter Plots:* Cross-correlation scatter plot with a linear regression trend line to study seasonal anomalies.
  - *Vegetation Condition Index (VCI):* Normalized historical index plotted against scientific drought severity bands (Extreme, Moderate, Light, No Drought).
  - *Precipitation Lag Analysis:* Pearson cross-correlation ($r$) with temporal shifts (0 to 3 months) to calculate vegetation response times to rainfall.
- **Premium Glassmorphic UI:** Custom theme featuring modern typography (Outfit/Inter), translucent metric cards with hover transitions, animated pulsing status badges, and transparent floating Altair charts.
- **Robustness & Resilience:**
  - *Simulation Mode (Offline):* Automatic fallback if GEE credentials fail or request quotas are exceeded.
  - *GeoJSON Validator:* Mathematical structure check ensuring only valid polygonal shapes (Polygon/MultiPolygon) are processed.
  - *Temporal Boundary Safety:* Hard limits on date inputs based on sensor operations (MODIS > 2000, CHIRPS > 1981).

### 🛠️ Data Sources & Technology
- **Vegetation (NDVI):** MODIS/061/MOD13Q1 (250m resolution, 16-day product).
- **Precipitation:** UCSB-CHG/CHIRPS/DAILY (0.05° resolution, daily product).
- **Boundaries:** FAO/GAUL/2015 (Levels 0, 1, and 2).
- **Map Rendering:** Geemap / Folium.
- **Charts:** Altair (Declarative Statistical Visualization).

---

### ⚙️ Setup and Installation

#### 1. Clone the Repository
```bash
git clone https://github.com/heltrakinho07/mz-drought-monitoring.git
cd mz-drought-monitoring
```

#### 2. Configure Virtual Environment
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

#### 3. Setup GEE Credentials
Create a `.streamlit/secrets.toml` file in the project root folder:
```toml
GEE_PROJECT_ID = "your-gee-project"
GEE_SERVICE_ACCOUNT_KEY = '{"type": "service_account", "project_id": "your-gee-project", ...}'
```

#### 4. Run the Dashboard
```bash
streamlit run streamlit_app.py
```
