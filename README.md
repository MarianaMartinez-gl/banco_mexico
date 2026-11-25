# Herramientas de Visualización

Dashboard interactivo de series económicas del Sistema de Información Económica
(SIE) de Banco de México, implementado con Streamlit.

## Instalación y ejecución

1. Instala las dependencias:

   ```powershell
   pip install -r requirements.txt
   ```

2. Guarda tu token de Banxico en `.streamlit/secrets.toml`:

   ```toml
   banxico_token = "tu-token"
   ```

   También puedes definir la variable de entorno `BANXICO_TOKEN`.

3. Inicia el dashboard:

   ```powershell
   streamlit run dashboard_banxico.py
   ```

El token se obtiene en el [servicio SIE de Banco de México](https://www.banxico.org.mx/SieAPIRest/service/v1/token).
No compartas ni subas el token al repositorio.

## Gráficas

El tablero permite visualizar la serie y su tendencia, el cambio mensual y la
variación diaria por año. Se retiró el mapa de calor del promedio mensual y se
añadió la volatilidad móvil de 30 observaciones, calculada como la desviación
estándar de las variaciones porcentuales diarias. Esta gráfica ayuda a
identificar periodos en que una serie se vuelve más o menos variable.
