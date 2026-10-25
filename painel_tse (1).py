import streamlit as st
import pandas as pd
import requests
from datetime import datetime

st.set_page_config(page_title='Painel TSE — Lula x Flávio', layout='wide')
st.markdown("""<style>
.stApp {background: #0b1220; color: #e2e8f0;}
.block-container {padding-top: 2rem; max-width: 1500px;}
h1,h2,h3 {color: #f8fafc !important;}
[data-testid="stMetric"] {background:#172338; border:1px solid #30415b; border-radius:14px; padding:16px;}
[data-testid="stMetricLabel"] {color:#a9bdd6;}
[data-testid="stSidebar"] {background:#111c2f;}
div[data-testid="stDataFrame"] {border-radius:12px; overflow:hidden;}
</style>""", unsafe_allow_html=True)
st.markdown('### ELEIÇÕES 2026 · ACOMPANHAMENTO')
st.title('Painel de apuração | Lula × Flávio')
st.caption('Fonte: arquivos públicos do TSE, quando disponíveis. Comparação proporcional por votos válidos apurados; não é previsão eleitoral.')

# Referência de diferenças e votos válidos informada na tabela anterior.
BASE = '''AC,-168037,469066
AL,259741,1818856
AP,225,464858
AM,70232,2170763
BA,3222186,8560291
CE,1798413,5617814
DF,-233989,1772808
ES,-383166,2251078
GO,-863008,3827823
MA,1327261,4010439
MT,-716900,1993288
MS,-356496,1490278
MG,-588612,11976235
PA,263280,4863172
PB,709750,2513747
PR,-1890748,6585243
PE,1815928,5601017
PI,1006682,2146394
RJ,-1273823,9369700
RN,517470,2071898
RS,-1279024,6423046
RO,-402321,968059
RR,-156902,325545
SC,-1872852,4500897
SP,-3416610,24882948
SE,438180,1364196
TO,-65312,930447'''
rows = [line.split(',') for line in BASE.splitlines()]
base = pd.DataFrame(rows, columns=['UF','Diferença 1º turno','Válidos 1º turno'])
base[['Diferença 1º turno','Válidos 1º turno']] = base[['Diferença 1º turno','Válidos 1º turno']].astype(int)

st.sidebar.header('Configurações')
eleicao = st.sidebar.text_input('Código da eleição federal — 2º turno', '6258')
intervalo = st.sidebar.selectbox('Atualização automática', [0, 30, 60, 120], index=2, format_func=lambda n: 'Desativada' if n == 0 else f'{n} segundos')
st.sidebar.caption('A URL é formada conforme o padrão oficial EA20. A fonte pode não ter publicado determinado arquivo ainda.')
if intervalo:
    try:
        from streamlit_autorefresh import st_autorefresh
        st_autorefresh(interval=intervalo*1000, key='refresh')
    except ImportError:
        st.sidebar.warning('Instale streamlit-autorefresh para atualização automática.')

@st.cache_data(ttl=25, show_spinner=False)
def obter(uf, codigo):
    codigo = str(codigo).strip()
    if not codigo.isdigit():
        raise ValueError('Código de eleição inválido')
    url = f'https://resultados.tse.jus.br/oficial/ele2026/{codigo}/dados/{uf.lower()}/{uf.lower()}-c0001-e{int(codigo):06d}-u.json'
    r = requests.get(url, timeout=12, headers={'User-Agent':'PainelEleitoral/1.0'})
    r.raise_for_status()
    return r.json(), url

def numero(obj, *keys):
    for k in keys:
        if k in obj:
            try: return int(float(str(obj[k]).replace(',','.')))
            except (ValueError, TypeError): pass
    return None

def extrair(d):
    # Total de votos válidos = soma dos votos nominais de TODOS os candidatos
    # à Presidência no EA20, não apenas Lula e Flávio.
    cargos = d.get('car', [])
    cargo = next((c for c in cargos if str(c.get('cd', '')).lstrip('0') == '1'), None)
    if cargo is None:
        raise ValueError('Cargo de presidente ausente no EA20')
    candidatos = cargo.get('cand', [])
    if not candidatos:
        raise ValueError('Lista de candidatos ausente')
    votos = {}
    for c in candidatos:
        n = str(c.get('n', '')).strip()
        v = numero(c, 'vap', 'vv', 'v')
        if v is None or v < 0:
            raise ValueError('Votação nominal de candidato ausente ou inválida')
        votos[n] = v
    if '13' not in votos or '22' not in votos:
        raise ValueError('Candidatos 13 e 22 não encontrados')
    validos_apurados = sum(votos.values())
    return validos_apurados, votos['13'], votos['22']

registros = []
for row in base.to_dict('records'):
    uf = row['UF']
    rec = dict(row)
    try:
        dado, url = obter(uf, eleicao)
        validos_apurados, lula, flavio = extrair(dado)
        fracao = validos_apurados / row['Válidos 1º turno']
        esperado = round(row['Diferença 1º turno'] * fracao)
        rec.update({'Válidos apurados 2º':validos_apurados,'Proporção válidos (%)':round(fracao*100,2),'Lula (2º)':lula,'Flávio (2º)':flavio,
                    'Diferença real':lula-flavio,'Diferença esperada':esperado,
                    'Desvio da referência':(lula-flavio)-esperado,
                    'Situação':'Atualizado'})
    except (requests.RequestException, ValueError, KeyError, TypeError) as e:
        rec.update({'Válidos apurados 2º':None,'Proporção válidos (%)':None,'Lula (2º)':None,'Flávio (2º)':None,
                    'Diferença real':None,'Diferença esperada':None,'Desvio da referência':None,
                    'Situação':f'Indisponível: {str(e)[:85]}'})
    registros.append(rec)

df = pd.DataFrame(registros)
validos = df[df['Situação']=='Atualizado'].copy()
st.markdown('### Visão geral')
c1,c2,c3,c4 = st.columns(4)
c1.metric('Estados com dados', f'{len(validos)}/27')
c2.metric('Votos válidos apurados', f"{int(validos['Válidos apurados 2º'].sum()):,.0f}".replace(',','.') if len(validos) else '—')
c3.metric('Diferença real (Lula − Flávio)', f"{int(validos['Diferença real'].sum()):+,}".replace(',','.') if len(validos) else '—')
c4.metric('Desvio da referência', f"{int(validos['Desvio da referência'].sum()):+,}".replace(',','.') if len(validos) else '—')
st.caption(f'Última tentativa de consulta: {datetime.now().strftime("%d/%m/%Y %H:%M:%S")} (horário do servidor). Números agregados apenas dos estados disponíveis.')

st.markdown('### Comparação por estado')
f1, f2 = st.columns([2,1])
with f1:
    estados = st.multiselect('Filtrar estados', sorted(df['UF'].tolist()), default=sorted(df['UF'].tolist()))
with f2:
    ordem = st.selectbox('Ordenar por', ['UF', 'Desvio da referência', 'Diferença real', 'Proporção válidos (%)'])
exibicao = df[df['UF'].isin(estados)].copy()
exibicao = exibicao.sort_values(ordem, ascending=(ordem == 'UF'), na_position='last')
st.dataframe(exibicao, use_container_width=True, hide_index=True, height=490,
    column_config={'Proporção válidos (%)':st.column_config.ProgressColumn('Válidos 2º / válidos 1º (%)', min_value=0, max_value=100, format='%.1f%%'),
                   'Situação':st.column_config.TextColumn('Status da consulta', width='large')})

if not validos.empty:
    st.markdown('### Diferença real × diferença proporcional esperada')
    grafico = validos[validos['UF'].isin(estados)].set_index('UF')[['Diferença esperada','Diferença real']].sort_index()
    if not grafico.empty:
        st.bar_chart(grafico, horizontal=True, color=['#60a5fa','#fb923c'], height=max(340, len(grafico)*28))
    st.caption('Valores positivos favorecem Lula; negativos favorecem Flávio. As barras comparam diferenças, não percentuais de intenção de voto.')
else:
    st.warning('Nenhum estado apresentou dados oficiais válidos nesta consulta. Confira o código da eleição e a disponibilidade dos arquivos do TSE.')

st.download_button('⬇️ Baixar tabela CSV', df.to_csv(index=False,sep=';',decimal=',').encode('utf-8-sig'), 'apuracao_tse.csv', 'text/csv')
with st.expander('Entenda o cálculo e as limitações'):
    st.write('Diferença esperada = diferença do 1º turno × (votos válidos apurados no 2º turno ÷ votos válidos totais do 1º turno).')
    st.write('Essa proporção pode superar 100% caso o segundo turno tenha mais votos válidos que o primeiro. A ordem da apuração pode distorcer a comparação. Não é uma previsão nem uma estimativa estatística.')
    st.write('O programa não substitui resultados ausentes por valores simulados. A integração com os arquivos do TSE ainda precisa ser validada durante a apuração oficial.')
st.markdown('[Consultar os resultados oficiais do TSE](https://resultados.tse.jus.br/)')
