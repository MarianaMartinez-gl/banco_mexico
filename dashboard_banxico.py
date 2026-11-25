# Tablero del SIE de Banxico
#
#     pip install -r requirements.txt
#     streamlit run dashboard_banxico.py
#
# Configura el token en .streamlit/secrets.toml:
#     banxico_token = "tu-token"
# El archivo de secretos no debe subirse al repositorio.

import os
from datetime import date, datetime

import matplotlib.pyplot as plt
import pandas as pd
import requests
import seaborn as sns
import streamlit as st

GRIS = "#B9C3D1"
AZUL = "#1C4C9A"
ROJO = "#B2182B"
AZUL_POS = "#2166AC"
CUALI = ["#E69F00", "#56B4E9", "#009E73", "#0072B2"]
VENTANA_VOLATILIDAD = 30
sns.set_theme(style="whitegrid")

SIE = "https://www.banxico.org.mx/SieAPIRest/service/v1/series"

st.set_page_config(page_title="Tablero del SIE", layout="wide")


def leer_token():
    try:
        if "banxico_token" in st.secrets:
            return str(st.secrets["banxico_token"]).strip()
    except Exception:
        pass
    if os.environ.get("BANXICO_TOKEN"):
        return os.environ["BANXICO_TOKEN"].strip()
    return None


TOKEN = leer_token()

if TOKEN and len(TOKEN) < 32:
    st.error(
        f"El token tiene {len(TOKEN)} caracteres y deberían ser 64. "
        "Revisa que esté completo y sin comillas."
    )
    st.stop()

if not TOKEN:
    st.error("Falta el token del SIE.")
    st.markdown(
        "1. Pídelo gratis en "
        "https://www.banxico.org.mx/SieAPIRest/service/v1/token\n"
        "2. Crea la carpeta `.streamlit` junto a este archivo.\n"
        "3. Dentro, crea `secrets.toml` con la línea:\n"
        '   `banxico_token = "tu-token"`\n'
        "4. Vuelve a cargar esta página."
    )
    st.stop()


@st.cache_data(ttl=3600, show_spinner=False)
def consultar(claves, inicio, fin, token):
    url = f"{SIE}/{','.join(claves)}/datos/{inicio}/{fin}"
    respuesta = requests.get(
        url,
        headers={
            "Bmx-Token": token,
            "Accept": "application/json",
            "User-Agent": "UPQ-IDIA224/1.0",
        },
        timeout=60,
    )

    if respuesta.status_code == 401:
        raise PermissionError("El token no fue aceptado.")
    if respuesta.status_code == 429:
        raise PermissionError("Demasiadas peticiones. Espera un momento.")
    respuesta.raise_for_status()

    tipo = respuesta.headers.get("Content-Type") or ""
    if "json" not in tipo:
        raise ValueError(
            f"El servidor no devolvió JSON sino {tipo}. "
            "Suele ser el token o una clave inexistente."
        )

    tablas = []
    faltantes = {}

    for serie in respuesta.json()["bmx"]["series"]:
        if "datos" not in serie:
            continue
        tabla = pd.DataFrame(serie["datos"])
        tabla["Fecha"] = pd.to_datetime(
            tabla.pop("fecha"), format="%d/%m/%Y"
        )
        faltantes[serie["idSerie"]] = int((tabla["dato"] == "N/E").sum())
        tabla["Valor"] = pd.to_numeric(
            tabla.pop("dato").str.replace(",", "", regex=False),
            errors="coerce",
        )
        tabla["Clave"] = serie["idSerie"]
        tabla["Serie"] = serie.get("titulo", serie["idSerie"])
        tablas.append(tabla)

    if not tablas:
        raise ValueError("Ninguna de las claves devolvió datos en ese rango.")

    df = pd.concat(tablas, ignore_index=True)
    df["Anio"] = df["Fecha"].dt.year
    df["Mes"] = df["Fecha"].dt.month
    return df, faltantes


with st.sidebar:
    st.header("Qué consultar")
    texto = st.text_input(
        "Claves de las series",
        "SF43718",
        help=(
            "Sepáralas con comas. Búscalas en el catálogo del SIE. "
            "SF43718 es el tipo de cambio FIX."
        ),
    )
    inicio = st.date_input("Desde", date(2021, 1, 1))
    fin = st.date_input("Hasta", date(2025, 12, 31))
    suavizado = st.slider("Días de media móvil", 1, 90, 30)
    st.caption("Fuente: SIE, Banco de México")

claves = [clave.strip().upper() for clave in texto.split(",") if clave.strip()]

if not claves:
    st.info("Escribe al menos una clave en el panel de la izquierda.")
    st.stop()
if inicio >= fin:
    st.error("La fecha inicial debe ser anterior a la final.")
    st.stop()

with st.spinner("Consultando el SIE..."):
    try:
        df, faltantes = consultar(tuple(claves), str(inicio), str(fin), TOKEN)
    except PermissionError as error:
        st.error(str(error))
        st.stop()
    except ValueError as error:
        st.warning(str(error))
        st.stop()
    except requests.exceptions.RequestException as error:
        st.error(f"No se pudo consultar el SIE: {error}")
        st.stop()

limpio = df.dropna(subset=["Valor"]).copy()
if limpio.empty:
    st.warning("No hay valores numéricos en ese rango.")
    st.stop()

principal = limpio[limpio["Clave"] == claves[0]].sort_values("Fecha").copy()
if principal.empty:
    st.warning(f"La serie principal {claves[0]} no devolvió datos numéricos.")
    st.stop()

titulo_principal = principal["Serie"].iloc[0]

st.title("Tablero de series del SIE")
st.caption(
    f"{titulo_principal} · del {inicio} al {fin} · "
    f"consultado el {datetime.now():%d/%m/%Y %H:%M}"
)

primero = principal["Valor"].iloc[0]
ultimo = principal["Valor"].iloc[-1]

c1, c2, c3, c4 = st.columns(4)
c1.metric("Días con dato", len(principal))
c2.metric("Días inhábiles (N/E)", faltantes.get(claves[0], 0))
c3.metric(
    "Último valor",
    f"{ultimo:,.4f}",
    delta=f"{(ultimo / primero - 1) * 100:+.1f} % en el periodo",
)
c4.metric(
    "Mínimo y máximo",
    f"{principal['Valor'].min():,.2f} – {principal['Valor'].max():,.2f}",
)

st.divider()

izquierda, derecha = st.columns(2)

with izquierda:
    if len(claves) == 1:
        st.subheader("La serie y su tendencia")
        principal["Suave"] = principal["Valor"].rolling(suavizado).mean()

        fig, ax = plt.subplots(figsize=(6, 3.4))
        ax.plot(
            principal["Fecha"],
            principal["Valor"],
            color=GRIS,
            linewidth=0.9,
            label="Valor diario",
        )
        ax.plot(
            principal["Fecha"],
            principal["Suave"],
            color=AZUL,
            linewidth=2,
            label=f"Media móvil {suavizado} días",
        )
        ax.set_xlabel("Fecha")
        ax.set_ylabel("Valor de la serie")
        ax.legend(frameon=False)
        st.pyplot(fig)
    else:
        st.subheader("Comparación en base 100")
        limpio = limpio.sort_values("Fecha")
        limpio["Base100"] = limpio.groupby("Clave")["Valor"].transform(
            lambda serie: serie / serie.iloc[0] * 100
        )

        fig, ax = plt.subplots(figsize=(6, 3.4))
        for i, clave in enumerate(claves):
            parte = limpio[limpio["Clave"] == clave]
            if parte.empty:
                continue
            ax.plot(
                parte["Fecha"],
                parte["Base100"],
                color=CUALI[i % len(CUALI)],
                linewidth=1.8,
                label=clave,
            )
        ax.axhline(100, color="gray", linewidth=0.8)
        ax.set_xlabel("Fecha")
        ax.set_ylabel("Índice base 100")
        ax.legend(frameon=False)
        st.pyplot(fig)

with derecha:
    st.subheader("Cambio de un mes a otro")
    mensual = principal.set_index("Fecha")["Valor"].resample("ME").last()
    cambio = (mensual.pct_change() * 100).dropna()

    fig, ax = plt.subplots(figsize=(6, 3.4))
    ax.bar(
        cambio.index,
        cambio.values,
        color=[ROJO if valor > 0 else AZUL_POS for valor in cambio.values],
        width=20,
    )
    ax.axhline(0, color="gray", linewidth=0.8)
    ax.set_xlabel("Mes")
    ax.set_ylabel("Cambio respecto al mes anterior (%)")
    st.pyplot(fig)
    st.caption(
        "Rojo: el valor subió. Azul: bajó. Para un tipo de cambio, "
        "subir significa que el peso se debilitó."
    )

abajo_izq, abajo_der = st.columns(2)
principal["Variacion"] = principal["Valor"].pct_change() * 100

with abajo_izq:
    st.subheader("Qué tan movido estuvo cada año")
    por_anio = principal.dropna(subset=["Variacion"])

    fig, ax = plt.subplots(figsize=(6, 3.4))
    sns.boxplot(data=por_anio, x="Anio", y="Variacion", color=GRIS, ax=ax)
    ax.axhline(0, color=ROJO, linewidth=1, linestyle="--")
    ax.set_xlabel("Año")
    ax.set_ylabel("Variación diaria (%)")
    st.pyplot(fig)

with abajo_der:
    st.subheader(f"Volatilidad móvil ({VENTANA_VOLATILIDAD} días)")
    volatilidad = principal["Variacion"].rolling(
        window=VENTANA_VOLATILIDAD,
        min_periods=VENTANA_VOLATILIDAD,
    ).std()
    volatilidad_valida = volatilidad.notna()

    if volatilidad_valida.any():
        fig, ax = plt.subplots(figsize=(6, 3.4))
        ax.plot(
            principal.loc[volatilidad_valida, "Fecha"],
            volatilidad.loc[volatilidad_valida],
            color=AZUL,
            linewidth=1.8,
        )
        ax.set_xlabel("Fecha")
        ax.set_ylabel("Desviación estándar diaria (%)")
        st.pyplot(fig)
        st.caption(
            "Calculada sobre las variaciones porcentuales diarias de las "
            "últimas 30 observaciones. Un valor mayor indica más variabilidad."
        )
    else:
        st.info(
            f"Se necesitan al menos {VENTANA_VOLATILIDAD + 1} observaciones "
            "para calcular la primera volatilidad móvil."
        )

with st.expander("Ver y descargar los datos"):
    st.write("Días marcados como N/E por serie:", faltantes)
    st.dataframe(df)
    st.download_button(
        "Descargar CSV",
        df.to_csv(index=False).encode("utf-8"),
        file_name=f"sie_{'_'.join(claves)}_{inicio}_{fin}.csv",
        mime="text/csv",
    )
