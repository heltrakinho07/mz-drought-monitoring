# Sistema de índice de seca e alerta precoce — Gaza, Moçambique

Projeto candidato à Special Issue *"Soil Moisture Retrieval and Drought Monitoring Based on Remote
Sensing"* (MDPI Remote Sensing, deadline 31/03/2027). Ver plano completo em
`~/.claude/plans/temos-chances-aqui-ver-rippling-canyon.md`.

## Ideia

Fundir umidade do solo (SMAP), backscatter SAR (Sentinel-1), vegetação/LST (MODIS) e precipitação
(CHIRPS) num índice de seca por ML para o sul de Moçambique (Gaza), validado indiretamente contra
ERA5-Land/GLEAM e boletins IPC/FEWS NET (não há rede densa de estações in-situ no país).

## Setup

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# autenticação do Earth Engine (abre o navegador para OAuth)
earthengine authenticate
```

Depois, criar um projeto no Google Cloud Console, ativar a Earth Engine API para ele, e usar o
project id em `ee.Initialize(project="...")` no notebook.

## Estrutura

- `notebooks/01_data_availability_check.ipynb` — primeiro passo: confirma cobertura de dados
  sobre Gaza antes de investir no pipeline completo.
- `src/gee_extract.py` — funções de extração de séries temporais via Google Earth Engine.
- `references/fews_net_ipc/` — boletins de classificação IPC / FEWS NET para validação indireta.
- `data/` — dados baixados/exportados (não versionado).

## Próximo passo

Rodar o notebook `01_data_availability_check.ipynb` para confirmar viabilidade técnica (cobertura
de SMAP/CHIRPS/Sentinel-1 sobre Gaza, 2023-2024) antes de avançar para o pipeline de features e
modelo.
