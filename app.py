import streamlit as st
import pandas as pd
import requests
import plotly.graph_objects as go
from datetime import timedelta, datetime
import os

# --- CONFIGURACIÓN ---
st.set_page_config(page_title="Predicción Panadería AI", layout="wide")

# 1. URL de tu API en Cloud Run
DEFAULT_API_URL = "https://panaderia-api-service-81011197894.us-central1.run.app/predict"

# 2. Nombre exacto de tu archivo CSV local
# Asegúrate de que este archivo esté en la MISMA CARPETA que app.py
LOCAL_CSV_PATH = "ventas_reales_poblacion_final.csv"  # <--- CAMBIA ESTO POR EL NOMBRE REAL
LOCAL_LOGO_PATH = "rodoltte_logo.png"

c_logo, c_titulo = st.columns([1, 5])
# --- TÍTULO Y SIDEBAR ---
#st.title("🥐 Forecast de Rodoltte con IA")
#st.markdown("Sistema de predicción de demanda basado en histórico local.")
with c_logo:
    # Verifica si existe la imagen para no mostrar error
    if os.path.exists(LOCAL_LOGO_PATH):
        # Ajusta el width según el tamaño real de tu imagen
        st.image(LOCAL_LOGO_PATH, width=120) 
    else:
        # Emoji de respaldo si no encuentra la imagen
        st.header("🥐")

with c_titulo:
    # Usamos markdown con HTML para alinear mejor el texto verticalmente con la imagen
    st.markdown("""
        <h1 style='margin-top: -10px;'>Forecast de Rodoltte con IA</h1>
        <p style='font-size: 1.2em; color: gray;'>Sistema de predicción de demanda basado en histórico local.</p>
    """, unsafe_allow_html=True)

with st.sidebar:
    st.header("Configuración")
    api_url = st.text_input("URL del Endpoint", value=DEFAULT_API_URL)
    
    # Estado del archivo
    if os.path.exists(LOCAL_CSV_PATH):
        st.success(f"✅ Archivo histórico cargado: {LOCAL_CSV_PATH}")
    else:
        st.error(f"❌ No se encontró el archivo: {LOCAL_CSV_PATH}")
        st.info("Asegúrate de poner el CSV en la misma carpeta que este script.")

# --- LÓGICA PRINCIPAL ---

# Intentamos cargar el CSV local automáticamente
if os.path.exists(LOCAL_CSV_PATH):
    try:
        df = pd.read_csv(LOCAL_CSV_PATH)
        
        # --- LIMPIEZA DE COLUMNAS ---
        df.columns = [c.upper().strip() for c in df.columns]
        
        # Mapeo automático de columnas
        col_fecha = next((c for c in df.columns if "FECHA" in c or "DATE" in c), None)
        col_prod = next((c for c in df.columns if "PRODUCTO" in c or "ITEM" in c or "NOMBRE" in c), None)
        col_venta = next((c for c in df.columns if "UNIDADES" in c or "VENTA" in c or "CANTIDAD" in c or "QTY" in c), None)

        if not (col_fecha and col_prod and col_venta):
            st.error(f"Error: No se detectaron las columnas FECHA, PRODUCTO y VENTA en {LOCAL_CSV_PATH}.")
            st.write("Columnas encontradas:", df.columns.tolist())
            st.stop()
            
        # Convertir fecha
        df[col_fecha] = pd.to_datetime(df[col_fecha])
        
        # --- INTERFAZ DE USUARIO ---
        col1, col2 = st.columns(2)
        
        with col1:
            lista_productos = sorted(df[col_prod].unique().astype(str))
            producto_seleccionado = st.selectbox("Selecciona el Producto", lista_productos)
            
        with col2:
            fecha_prediccion = st.date_input("Fecha a Predecir", value=datetime.today() + timedelta(days=1))

        # Botón de acción
        if st.button("🔮 Generar Predicción", type="primary"):
            with st.spinner('Consultando al modelo...'):
                
                # Filtrar datos
                df_prod = df[df[col_prod].astype(str) == producto_seleccionado].copy()
                df_prod = df_prod.sort_values(col_fecha)
                
                # Extraer historia (últimos 14 días ANTES de la fecha elegida)
                mask_fecha = df_prod[col_fecha].dt.date < fecha_prediccion
                df_history = df_prod[mask_fecha].tail(14)
                
                if len(df_history) < 14:
                    st.warning(f"⚠️ Historia incompleta ({len(df_history)} días). Se rellenará con promedios.")
                
                sales_history_list = df_history[col_venta].tolist()
                
                # Payload
                payload = {
                    "product_name": producto_seleccionado,
                    "prediction_date": str(fecha_prediccion),
                    "sales_history": sales_history_list
                }
                
                # Llamada API
                try:
                    response = requests.post(
                        api_url, 
                        json=payload,
                        headers={"Content-Type": "application/json"}
                    )
                    
                    if response.status_code == 200:
                        data = response.json()
                        prediccion_valor = data.get("prediction") or data.get("prediction_d_plus_2")
                        
                        # --- RESULTADOS ---
                        st.divider()
                        c_metric, c_chart = st.columns([1, 3])
                        
                        with c_metric:
                            st.subheader("Producción Sugerida")
                            st.metric(label=f"Para el {fecha_prediccion}", value=f"{prediccion_valor} uds")
                            with st.expander("Detalles JSON"):
                                st.json(data)

                        with c_chart:
                            fig = go.Figure()
                            
                            # Histórico (últimos 30 días para no saturar la gráfica)
                            df_viz = df_prod[mask_fecha].tail(30)
                            
                            fig.add_trace(go.Scatter(
                                x=df_viz[col_fecha], y=df_viz[col_venta],
                                mode='lines+markers', name='Histórico',
                                line=dict(color='#1f77b4')
                            ))
                            
                            # Predicción
                            fig.add_trace(go.Scatter(
                                x=[fecha_prediccion], y=[prediccion_valor],
                                mode='markers+text', name='Predicción',
                                marker=dict(color='#ff7f0e', size=15, symbol='star'),
                                text=[f"{prediccion_valor:.1f}"], textposition="top center"
                            ))
                            
                            # Conector
                            if not df_viz.empty:
                                fig.add_trace(go.Scatter(
                                    x=[df_viz[col_fecha].iloc[-1], fecha_prediccion],
                                    y=[df_viz[col_venta].iloc[-1], prediccion_valor],
                                    mode='lines', line=dict(color='gray', dash='dash'),
                                    showlegend=False
                                ))

                            fig.update_layout(
                                title=f"Pronóstico: {producto_seleccionado}",
                                xaxis_title="Fecha", yaxis_title="Ventas",
                                hovermode="x unified", template="plotly_white"
                            )
                            st.plotly_chart(fig, use_container_width=True)
                            
                    else:
                        st.error(f"Error API: {response.text}")
                        
                except Exception as e:
                    st.error(f"Fallo de conexión: {e}")

    except Exception as e:
        st.error(f"Error leyendo el CSV local: {e}")
else:
    st.warning(f"⚠️ Archivo no encontrado. Por favor coloca '{LOCAL_CSV_PATH}' en la carpeta.")