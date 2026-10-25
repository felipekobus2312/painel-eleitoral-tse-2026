import streamlit as st
import pandas as pd
import requests
from datetime import datetime

st.set_page_config(page_title='Painel TSE — Lula x Flávio', layout='wide')
st.title('Painel eleitoral TSE — Lula x Flávio Bolsonaro')
st.caption('Comparação proporcional do 1º turno com a apuração do 2º turno de 2026. Dados ao vivo somente quando confirmados pela fonte oficial.')

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
    # EA20: abrangência com lista 'car' de cargos e 'cand' de candidatos.
    cargos = d.get('car', [])
    cargo = next((c for c in cargos if str(c.get('cd','')).lstrip('0') == '1'), None)
    if cargo is None:
        raise ValueError('Cargo presidente não localizado no JSON oficial')
    candidatos = cargo.get('cand', [])
    votos = {}
    for c in candidatos:
        numero_cand = str(c.get('n','')).strip()
        if numero_cand in ('13','22'):
            votos[numero_cand] = numero(c, 'vap','vv','v')
    if '13' not in votos or '22' not in votos or any(v is None for v in votos.values()):
        raise ValueError('Votos dos candidatos 13 e 22 não disponíveis neste arquivo')
    # 'pst' = percentual de seções totalizadas, usualmente representado como string percentual.
    pct = d.get('pst')
    if pct is None:
        s_total = numero(d,'s','st')
        s_ap = numero(d,'st','s')
        if s_total and s_ap is not None and s_ap <= s_total:
            pct = 100*s_ap/s_total
    if pct is None:
        raise ValueError('Percentual de seções totalizadas indisponível')
    pct = float(str(pct).replace(',','.'))
    if not 0 <= pct <= 100:
        raise ValueError('Percentual de seções fora do intervalo esperado')
    return pct, votos['13'], votos['22']

registros = []
for row in base.to_dict('records'):
    uf = row['UF']
    rec = dict(row)
    try:
        dado, url = obter(uf, eleicao)
        pct, lula, flavio = extrair(dado)
        rec.update({'Seções apuradas (%)':pct,'Lula (2º)':lula,'Flávio (2º)':flavio,
                    'Diferença real':lula-flavio,'Diferença esperada':round(row['Diferença 1º turno']*pct/100),
                    'Desvio da referência':(lula-flavio)-round(row['Diferença 1º turno']*pct/100),
                    'Situação':'Atualizado'})
    except (requests.RequestException, ValueError, KeyError, TypeError) as e:
        rec.update({'Seções apuradas (%)':None,'Lula (2º)':None,'Flávio (2º)':None,
                    'Diferença real':None,'Diferença esperada':None,'Desvio da referência':None,
                    'Situação':f'Indisponível: {str(e)[:85]}'})
    registros.append(rec)

df = pd.DataFrame(registros)
validos = df[df['Situação']=='Atualizado']
c1,c2,c3 = st.columns(3)
c1.metric('Estados com dados válidos',f'{len(validos)}/27')
c2.metric('Diferença real (estados disponíveis)',f"{int(validos['Diferença real'].sum()):+,}" if len(validos) else '—')
c3.metric('Desvio da referência',f"{int(validos['Desvio da referência'].sum()):+,}" if len(validos) else '—')
st.caption(f'Última consulta: {datetime.now().strftime("%d/%m/%Y %H:%M:%S")} (horário do computador/servidor). Diferença = Lula menos Flávio.')
st.dataframe(df, use_container_width=True, hide_index=True)
st.download_button('Baixar tabela CSV',df.to_csv(index=False,sep=';',decimal=',').encode('utf-8-sig'), 'apuracao_tse.csv','text/csv')
st.info('A diferença esperada = diferença final do 1º turno × percentual de seções totalizadas no 2º turno. Os votos válidos do 1º turno são uma referência histórica, não os votos válidos já apurados no 2º. Não preenchemos falhas com valores inventados.')
st.markdown('[Consultar resultados oficiais do TSE](https://resultados.tse.jus.br/)')
