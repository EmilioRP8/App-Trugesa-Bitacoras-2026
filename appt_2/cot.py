import os, sqlite3
from datetime import datetime, date, timedelta
from io import BytesIO

import pandas as pd
import streamlit as st

st.set_page_config(page_title="Bitácoras TRUGESA", layout="wide")

DB_NAME = "bitacoras_trugesa.db"
img_path = os.path.join(os.path.dirname(__file__), "tr.png")

CLIENTES = ["SESÉ", "ADIENT", "VOLKSWAGEN", "DHL", "SKF", "OTRO"]

TIPOS_EVENTO = [
    "Inicio de jornada", "Inicio de movimiento", "Llegada a punto",
    "Inicio de espera", "Fin de espera", "Inicio de carga",
    "Carga finalizada", "Inicio de descarga", "Descarga finalizada",
    "Detención", "Reinicio de movimiento", "Otro"
]

ESTADOS_CARGA = [
    "Material / mercancía", "Empaque vacío", "Caja vacía", "No aplica"
]

MOTIVOS_ESPERA = [
    "Esperando andén", "Carga", "Descarga", "Documentación",
    "Acceso a planta", "Cliente", "Tráfico", "Revisión",
    "Falla mecánica", "Llanta / neumático", "Autoridad / retén",
    "Descanso", "Otro"
]

TIPOS_INCIDENCIA = [
    "Falla mecánica", "Llanta / neumático", "Accidente", "Daño",
    "Mercancía", "Documentación", "Cliente", "Rechazo de mercancía",
    "Seguridad", "Autoridad / retén", "Otro"
]


# ==========================================================
# BASE DE DATOS
# ==========================================================

def conectar():
    return sqlite3.connect(DB_NAME, check_same_thread=False)

def crear_bd():
    conn = conectar()
    cur = conn.cursor()

    cur.execute("""
        CREATE TABLE IF NOT EXISTS bitacoras (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            identificador TEXT UNIQUE,
            cliente TEXT NOT NULL,
            fecha TEXT NOT NULL,
            unidad TEXT NOT NULL,
            operador TEXT NOT NULL,
            supervisor TEXT NOT NULL,
            ruta TEXT,
            hora_programada TEXT,
            estado TEXT DEFAULT 'ABIERTA',
            fecha_hora_inicio TEXT,
            lugar_cierre TEXT,
            fecha_hora_cierre TEXT
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS eventos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            bitacora_id INTEGER NOT NULL,
            fecha_hora TEXT NOT NULL,
            tipo_evento TEXT NOT NULL,
            lugar TEXT NOT NULL,
            estado_carga TEXT,
            motivo_espera TEXT,
            detalle_espera TEXT,
            incidencia INTEGER DEFAULT 0,
            tipo_incidencia TEXT,
            descripcion_incidencia TEXT,
            supervisor_notificado INTEGER DEFAULT 0,
            hora_programada_evento TEXT,
            desviacion_minutos INTEGER,
            editado INTEGER DEFAULT 0,
            fecha_hora_edicion TEXT,
            FOREIGN KEY(bitacora_id) REFERENCES bitacoras(id)
        )
    """)

    conn.commit()
    conn.close()

crear_bd()


# ==========================================================
# FUNCIONES
# ==========================================================

def generar_identificador(cliente, fecha_servicio, unidad):
    return f"{cliente.strip().upper()} - {fecha_servicio.strftime('%d-%m-%Y')} - {unidad.strip().upper()}"

def obtener_bitacoras(solo_abiertas=False):
    conn = conectar()
    query = "SELECT * FROM bitacoras"
    if solo_abiertas:
        query += " WHERE estado='ABIERTA'"
    query += " ORDER BY id DESC"
    df = pd.read_sql_query(query, conn)
    conn.close()
    return df

def obtener_bitacoras_operador(operador, solo_abiertas=False):
    conn = conectar()
    query = "SELECT * FROM bitacoras WHERE LOWER(TRIM(operador))=LOWER(TRIM(?))"
    if solo_abiertas:
        query += " AND estado='ABIERTA'"
    query += " ORDER BY id DESC"
    df = pd.read_sql_query(query, conn, params=(operador,))
    conn.close()
    return df

def obtener_eventos(bitacora_id):
    conn = conectar()
    df = pd.read_sql_query(
        "SELECT * FROM eventos WHERE bitacora_id=? ORDER BY fecha_hora ASC",
        conn, params=(bitacora_id,)
    )
    conn.close()
    return df

def formatear_duracion(segundos):
    segundos = int(max(segundos or 0, 0))
    return f"{segundos//3600:02d}:{(segundos%3600)//60:02d}"

def calcular_desviacion(hora_programada):
    if not hora_programada:
        return None

    ahora = datetime.now()
    hora_obj = datetime.strptime(hora_programada, "%H:%M").time()
    programado = datetime.combine(ahora.date(), hora_obj)

    return round((ahora - programado).total_seconds() / 60)

def calcular_duracion_total(eventos):
    if eventos.empty:
        return 0

    df = eventos.copy()
    df["dt"] = pd.to_datetime(df["fecha_hora"])
    return (df["dt"].max() - df["dt"].min()).total_seconds()

def calcular_tiempos_eventos(eventos):
    tiempos = {"movimiento": 0, "espera": 0, "incidencia": 0}

    if eventos.empty:
        return tiempos

    df = eventos.copy()
    df["dt"] = pd.to_datetime(df["fecha_hora"])
    df = df.sort_values("dt").reset_index(drop=True)

    for i in range(len(df) - 1):
        actual = df.iloc[i]
        siguiente = df.iloc[i + 1]
        duracion = (siguiente["dt"] - actual["dt"]).total_seconds()

        if actual["tipo_evento"] in ["Inicio de movimiento", "Reinicio de movimiento"]:
            tiempos["movimiento"] += duracion

        elif actual["tipo_evento"] in ["Inicio de espera", "Detención"]:
            if int(actual["incidencia"] or 0) == 1:
                tiempos["incidencia"] += duracion
            else:
                tiempos["espera"] += duracion

    return tiempos

def preparar_eventos_reporte(eventos):
    columnas = [
        "Fecha", "Hora", "Evento", "Lugar", "Estado de carga",
        "Motivo de espera", "Detalle", "Incidencia",
        "Tipo incidencia", "Descripción incidencia",
        "Supervisor notificado", "Hora programada",
        "Desviación min", "Editado"
    ]

    if eventos.empty:
        return pd.DataFrame(columns=columnas)

    df = eventos.copy()
    df["dt"] = pd.to_datetime(df["fecha_hora"])

    return pd.DataFrame({
        "Fecha": df["dt"].dt.strftime("%d/%m/%Y"),
        "Hora": df["dt"].dt.strftime("%H:%M:%S"),
        "Evento": df["tipo_evento"],
        "Lugar": df["lugar"],
        "Estado de carga": df["estado_carga"],
        "Motivo de espera": df["motivo_espera"],
        "Detalle": df["detalle_espera"],
        "Incidencia": df["incidencia"].map({1: "Sí", 0: "No"}),
        "Tipo incidencia": df["tipo_incidencia"],
        "Descripción incidencia": df["descripcion_incidencia"],
        "Supervisor notificado": df["supervisor_notificado"].map({1: "Sí", 0: "No"}),
        "Hora programada": df["hora_programada_evento"],
        "Desviación min": df["desviacion_minutos"],
        "Editado": df["editado"].map({1: "Sí", 0: "No"})
    })


# ==========================================================
# EXCEL INDIVIDUAL
# ==========================================================

def generar_excel_bitacora(datos, eventos):
    output = BytesIO()
    tiempos = calcular_tiempos_eventos(eventos)
    total = calcular_duracion_total(eventos)
    incidencias = int(eventos["incidencia"].sum()) if not eventos.empty else 0

    resumen = pd.DataFrame({
        "Campo": [
            "Bitácora", "Cliente", "Fecha", "Unidad", "Operador",
            "Supervisor", "Ruta / Servicio", "Hora programada",
            "Estado", "Inicio registrado", "Cierre registrado",
            "Lugar de cierre", "Tiempo total", "Tiempo en movimiento",
            "Tiempo de espera", "Tiempo por incidencias",
            "Número de eventos", "Número de incidencias"
        ],
        "Información": [
            datos["identificador"], datos["cliente"], datos["fecha"],
            datos["unidad"], datos["operador"], datos["supervisor"],
            datos["ruta"], datos["hora_programada"], datos["estado"],
            datos["fecha_hora_inicio"], datos["fecha_hora_cierre"],
            datos["lugar_cierre"], formatear_duracion(total),
            formatear_duracion(tiempos["movimiento"]),
            formatear_duracion(tiempos["espera"]),
            formatear_duracion(tiempos["incidencia"]),
            len(eventos), incidencias
        ]
    })

    eventos_excel = preparar_eventos_reporte(eventos)

    if not eventos.empty:
        especiales = eventos[
            eventos["tipo_evento"].isin(["Inicio de espera", "Detención"]) |
            (eventos["incidencia"] == 1)
        ]
    else:
        especiales = pd.DataFrame()

    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        resumen.to_excel(writer, sheet_name="Resumen", index=False)
        eventos_excel.to_excel(writer, sheet_name="Eventos", index=False)
        preparar_eventos_reporte(especiales).to_excel(
            writer, sheet_name="Esperas_Incidencias", index=False
        )

        for nombre in ["Resumen", "Eventos", "Esperas_Incidencias"]:
            ws = writer.book[nombre]
            ws.freeze_panes = "A2"

            for cell in ws[1]:
                cell.font = cell.font.copy(bold=True)

            for columna in ws.columns:
                letra = columna[0].column_letter
                largo = max(len(str(c.value or "")) for c in columna)
                ws.column_dimensions[letra].width = min(max(largo + 2, 12), 45)

    output.seek(0)
    return output


# ==========================================================
# EXCEL HISTÓRICO
# ==========================================================

def generar_excel_historial(bitacoras):
    output = BytesIO()
    resumen = []
    eventos_totales = []

    for _, bitacora in bitacoras.iterrows():
        eventos = obtener_eventos(bitacora["id"])
        tiempos = calcular_tiempos_eventos(eventos)
        total = calcular_duracion_total(eventos)
        incidencias = int(eventos["incidencia"].sum()) if not eventos.empty else 0

        resumen.append({
            "Bitácora": bitacora["identificador"],
            "Cliente": bitacora["cliente"],
            "Fecha": bitacora["fecha"],
            "Unidad": bitacora["unidad"],
            "Operador": bitacora["operador"],
            "Supervisor": bitacora["supervisor"],
            "Ruta / Servicio": bitacora["ruta"],
            "Estado": bitacora["estado"],
            "Lugar de cierre": bitacora["lugar_cierre"],
            "Tiempo total": formatear_duracion(total),
            "Tiempo movimiento": formatear_duracion(tiempos["movimiento"]),
            "Tiempo espera": formatear_duracion(tiempos["espera"]),
            "Tiempo incidencias": formatear_duracion(tiempos["incidencia"]),
            "Eventos": len(eventos),
            "Incidencias": incidencias
        })

        if not eventos.empty:
            ev = preparar_eventos_reporte(eventos)
            ev.insert(0, "Bitácora", bitacora["identificador"])
            ev.insert(1, "Cliente", bitacora["cliente"])
            ev.insert(2, "Unidad", bitacora["unidad"])
            ev.insert(3, "Operador", bitacora["operador"])
            eventos_totales.append(ev)

    df_resumen = pd.DataFrame(resumen)
    df_eventos = pd.concat(eventos_totales, ignore_index=True) if eventos_totales else pd.DataFrame()

    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        df_resumen.to_excel(writer, sheet_name="Historial", index=False)
        df_eventos.to_excel(writer, sheet_name="Todos_Eventos", index=False)

    output.seek(0)
    return output


# ==========================================================
# SESIÓN
# ==========================================================

if "operador_actual" not in st.session_state:
    st.session_state["operador_actual"] = ""


# ==========================================================
# ENCABEZADO
# ==========================================================

col_logo, col_titulo = st.columns([1, 5])

with col_logo:
    if os.path.exists(img_path):
        st.image(img_path, use_container_width=True)

with col_titulo:
    st.markdown("# **TRUGESA TRANSPORTACIÓN ESPECIALIZADA**")
    st.markdown("## Sistema de Bitácoras Operativas")
    st.caption("Control de jornadas, movimientos, tiempos de espera, incidencias y cierre de unidad.")

st.divider()


# ==========================================================
# IDENTIFICACIÓN OPERADOR
# ==========================================================

st.subheader("Identificación del operador")

col1, col2 = st.columns([4, 1])

with col1:
    operador_ingresado = st.text_input(
        "Nombre completo del operador",
        value=st.session_state["operador_actual"],
        placeholder="Ej. Juan Pérez López"
    )

with col2:
    st.write("")
    st.write("")

    if st.button("Entrar", type="primary", use_container_width=True):
        if operador_ingresado.strip():
            st.session_state["operador_actual"] = operador_ingresado.strip()
            st.rerun()
        else:
            st.error("Captura tu nombre.")

if st.session_state["operador_actual"]:
    st.success(f"Operador activo: **{st.session_state['operador_actual']}**")

st.divider()


# ==========================================================
# PESTAÑAS
# ==========================================================

tab1, tab2, tab3, tab4, tab5 = st.tabs([
    "Crear jornada",
    "Registrar evento",
    "Editar evento",
    "Mis bitácoras / Cerrar",
    "Historial general"
])


# ==========================================================
# CREAR JORNADA
# ==========================================================

with tab1:
    st.header("Crear nueva jornada")
    st.info("Esta sección es para que el supervisor asigne el servicio.")

    c1, c2, c3 = st.columns(3)

    with c1:
        cliente_sel = st.selectbox("Cliente", CLIENTES, key="crear_cliente")
        cliente = st.text_input("Nombre del cliente", key="crear_cliente_otro").strip() if cliente_sel == "OTRO" else cliente_sel

    with c2:
        fecha_servicio = st.date_input("Fecha", value=date.today(), key="crear_fecha")

    with c3:
        unidad = st.text_input(
            "¿En qué unidad se realizará el servicio?",
            placeholder="Ej. T-20",
            key="crear_unidad"
        ).strip().upper()

    c4, c5, c6 = st.columns(3)

    with c4:
        operador = st.text_input(
            "Operador asignado",
            placeholder="Ej. Juan Pérez López",
            key="crear_operador"
        ).strip()

    with c5:
        supervisor = st.text_input(
            "Supervisor responsable",
            placeholder="Ej. Carlos Hernández",
            key="crear_supervisor"
        ).strip()

    with c6:
        hora_programada = st.time_input("Hora programada de inicio", key="crear_hora")

    ruta = st.text_input(
        "Ruta / servicio asignado",
        placeholder="Ej. Puebla → Querétaro",
        key="crear_ruta"
    ).strip()

    if cliente and unidad:
        identificador = generar_identificador(cliente, fecha_servicio, unidad)
        st.info(f"**Bitácora:** {identificador}")

    if st.button("Crear bitácora", type="primary", use_container_width=True, key="btn_crear"):

        if not cliente:
            st.error("Debes indicar el cliente.")
        elif not unidad:
            st.error("Debes indicar la unidad.")
        elif not operador:
            st.error("Debes indicar el operador.")
        elif not supervisor:
            st.error("Debes indicar el supervisor.")
        elif not ruta:
            st.error("Debes indicar la ruta.")
        else:
            identificador = generar_identificador(cliente, fecha_servicio, unidad)

            conn = conectar()
            cur = conn.cursor()

            try:
                cur.execute("""
                    INSERT INTO bitacoras (
                        identificador, cliente, fecha, unidad,
                        operador, supervisor, ruta,
                        hora_programada, estado
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'ABIERTA')
                """, (
                    identificador,
                    cliente,
                    fecha_servicio.isoformat(),
                    unidad,
                    operador,
                    supervisor,
                    ruta,
                    hora_programada.strftime("%H:%M")
                ))

                conn.commit()
                st.success("Bitácora creada correctamente.")

            except sqlite3.IntegrityError:
                st.error("Ya existe una bitácora con ese cliente, fecha y unidad.")

            finally:
                conn.close()


# ==========================================================
# REGISTRAR EVENTO
# ==========================================================

with tab2:
    st.header("Registrar evento")

    operador_actual = st.session_state["operador_actual"].strip()

    if not operador_actual:
        st.warning("Primero identifica al operador.")

    else:
        abiertas = obtener_bitacoras_operador(operador_actual, solo_abiertas=True)

        if abiertas.empty:
            st.info("No tienes bitácoras abiertas asignadas.")

        else:
            opciones = {r["identificador"]: r["id"] for _, r in abiertas.iterrows()}

            seleccion = st.selectbox("Bitácora asignada", list(opciones.keys()), key="evento_bitacora")
            bitacora_id = opciones[seleccion]
            datos = abiertas[abiertas["id"] == bitacora_id].iloc[0]

            i1, i2, i3 = st.columns(3)
            i1.metric("Unidad", datos["unidad"])
            i2.metric("Operador", datos["operador"])
            i3.metric("Supervisor", datos["supervisor"])

            st.write(f"**Cliente:** {datos['cliente']}")
            st.write(f"**Ruta:** {datos['ruta']}")
            st.divider()

            e1, e2 = st.columns(2)

            with e1:
                tipo_evento = st.selectbox("Tipo de evento", TIPOS_EVENTO, key="evento_tipo")

            with e2:
                lugar = st.text_input(
                    "Lugar",
                    placeholder="Ej. Planta SESÉ Puebla",
                    key="evento_lugar"
                ).strip()

            estado_carga = st.radio(
                "Estado de la caja",
                ESTADOS_CARGA,
                horizontal=True,
                key="evento_estado"
            )

            motivo_espera = None
            detalle_espera = None

            if tipo_evento in ["Inicio de espera", "Detención"]:
                motivo_espera = st.selectbox("Motivo", MOTIVOS_ESPERA, key="evento_motivo")
                detalle_espera = st.text_area("Detalle", key="evento_detalle")

            comparar_horario = st.checkbox(
                "Este evento tenía una hora programada",
                key="evento_horario"
            )

            hora_programada_evento = None

            if comparar_horario:
                hora_temp = st.time_input("Hora programada", key="evento_hora")
                hora_programada_evento = hora_temp.strftime("%H:%M")

            incidencia = st.checkbox("Existe una incidencia", key="evento_incidencia")

            tipo_incidencia = None
            descripcion_incidencia = None

            if incidencia:
                tipo_incidencia = st.selectbox(
                    "Tipo de incidencia",
                    TIPOS_INCIDENCIA,
                    key="evento_tipo_incidencia"
                )
                descripcion_incidencia = st.text_area(
                    "Descripción de la incidencia",
                    key="evento_desc_incidencia"
                )

            notificado = st.checkbox(
                f"Confirmo que notifiqué al supervisor {datos['supervisor']} por WhatsApp.",
                key="evento_notificado"
            )

            ahora = datetime.now()

            h1, h2 = st.columns(2)
            h1.metric("Fecha", ahora.strftime("%d/%m/%Y"))
            h2.metric("Hora", ahora.strftime("%H:%M:%S"))

            if st.button("Registrar evento", type="primary", use_container_width=True, key="btn_evento"):

                if not lugar:
                    st.error("Debes indicar el lugar.")

                elif not notificado:
                    st.error("Debes confirmar el aviso al supervisor.")

                else:
                    desviacion = calcular_desviacion(hora_programada_evento) if hora_programada_evento else None
                    ahora_registro = datetime.now()

                    conn = conectar()
                    cur = conn.cursor()

                    cur.execute("""
                        INSERT INTO eventos (
                            bitacora_id, fecha_hora, tipo_evento, lugar,
                            estado_carga, motivo_espera, detalle_espera,
                            incidencia, tipo_incidencia, descripcion_incidencia,
                            supervisor_notificado, hora_programada_evento,
                            desviacion_minutos
                        )
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (
                        bitacora_id,
                        ahora_registro.isoformat(timespec="seconds"),
                        tipo_evento,
                        lugar,
                        estado_carga,
                        motivo_espera,
                        detalle_espera,
                        1 if incidencia else 0,
                        tipo_incidencia,
                        descripcion_incidencia,
                        1,
                        hora_programada_evento,
                        desviacion
                    ))

                    if tipo_evento == "Inicio de jornada":
                        cur.execute("""
                            UPDATE bitacoras
                            SET fecha_hora_inicio=?
                            WHERE id=?
                        """, (
                            ahora_registro.isoformat(timespec="seconds"),
                            bitacora_id
                        ))

                    conn.commit()
                    conn.close()

                    st.success("Evento registrado.")
                    st.rerun()


# ==========================================================
# EDITAR EVENTO
# ==========================================================

with tab3:
    st.header("Editar evento")

    operador_actual = st.session_state["operador_actual"].strip()

    if not operador_actual:
        st.warning("Primero identifica al operador.")

    else:
        abiertas = obtener_bitacoras_operador(operador_actual, solo_abiertas=True)

        if abiertas.empty:
            st.info("No tienes bitácoras abiertas.")

        else:
            opciones = {r["identificador"]: r["id"] for _, r in abiertas.iterrows()}

            seleccion = st.selectbox("Bitácora", list(opciones.keys()), key="editar_bitacora")
            bitacora_id = opciones[seleccion]
            eventos = obtener_eventos(bitacora_id)

            ahora = datetime.now()

            editables = [
                row for _, row in eventos.iterrows()
                if ahora - datetime.fromisoformat(row["fecha_hora"]) <= timedelta(minutes=5)
            ]

            if not editables:
                st.info("No hay eventos editables. El límite es de 5 minutos.")

            else:
                opciones_evento = {
                    f"{row['tipo_evento']} | {row['lugar']} | {row['fecha_hora'][11:19]}": row["id"]
                    for row in editables
                }

                evento_sel = st.selectbox("Evento", list(opciones_evento.keys()), key="editar_evento")
                evento_id = opciones_evento[evento_sel]
                registro = eventos[eventos["id"] == evento_id].iloc[0]

                indice_tipo = TIPOS_EVENTO.index(registro["tipo_evento"]) if registro["tipo_evento"] in TIPOS_EVENTO else 0
                indice_estado = ESTADOS_CARGA.index(registro["estado_carga"]) if registro["estado_carga"] in ESTADOS_CARGA else 0

                nuevo_tipo = st.selectbox("Tipo de evento", TIPOS_EVENTO, index=indice_tipo, key="editar_tipo")
                nuevo_lugar = st.text_input("Lugar", value=registro["lugar"], key="editar_lugar").strip()
                nuevo_estado = st.selectbox("Estado de carga", ESTADOS_CARGA, index=indice_estado, key="editar_estado")

                if st.button("Guardar corrección", type="primary", use_container_width=True, key="btn_editar"):

                    fecha_evento = datetime.fromisoformat(registro["fecha_hora"])

                    if datetime.now() - fecha_evento > timedelta(minutes=5):
                        st.error("El periodo de edición terminó.")

                    else:
                        conn = conectar()
                        cur = conn.cursor()

                        cur.execute("""
                            UPDATE eventos
                            SET tipo_evento=?, lugar=?, estado_carga=?,
                                editado=1, fecha_hora_edicion=?
                            WHERE id=?
                        """, (
                            nuevo_tipo,
                            nuevo_lugar,
                            nuevo_estado,
                            datetime.now().isoformat(timespec="seconds"),
                            evento_id
                        ))

                        conn.commit()
                        conn.close()

                        st.success("Evento actualizado.")
                        st.rerun()


# ==========================================================
# MIS BITÁCORAS
# ==========================================================

with tab4:
    st.header("Mis bitácoras")

    operador_actual = st.session_state["operador_actual"].strip()

    if not operador_actual:
        st.warning("Primero identifica al operador.")

    else:
        mis_bitacoras = obtener_bitacoras_operador(operador_actual)

        if mis_bitacoras.empty:
            st.info("No tienes bitácoras registradas.")

        else:
            opciones = {r["identificador"]: r["id"] for _, r in mis_bitacoras.iterrows()}

            seleccion = st.selectbox("Seleccionar bitácora", list(opciones.keys()), key="consulta_operador")
            bitacora_id = opciones[seleccion]
            datos = mis_bitacoras[mis_bitacoras["id"] == bitacora_id].iloc[0]
            eventos = obtener_eventos(bitacora_id)

            tiempos = calcular_tiempos_eventos(eventos)
            total = calcular_duracion_total(eventos)

            m1, m2, m3, m4 = st.columns(4)
            m1.metric("Tiempo total", formatear_duracion(total))
            m2.metric("Movimiento", formatear_duracion(tiempos["movimiento"]))
            m3.metric("Espera", formatear_duracion(tiempos["espera"]))
            m4.metric("Incidencias", int(eventos["incidencia"].sum()) if not eventos.empty else 0)

            if not eventos.empty:
                st.subheader("Línea de tiempo")
                st.dataframe(
                    preparar_eventos_reporte(eventos),
                    use_container_width=True,
                    hide_index=True
                )

            excel = generar_excel_bitacora(datos, eventos)

            st.download_button(
                "Descargar bitácora Excel",
                data=excel,
                file_name=f"{datos['identificador'].replace(' ', '_')}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                use_container_width=True
            )

            if datos["estado"] == "ABIERTA":
                st.divider()
                st.subheader("Cerrar jornada")

                lugar_cierre = st.text_input(
                    "¿Dónde quedará la unidad?",
                    placeholder="Casa del operador, Patio TRUGESA, Parador...",
                    key="cierre_lugar"
                ).strip()

                cierre_notificado = st.checkbox(
                    f"Confirmo que informé al supervisor {datos['supervisor']} dónde quedó la unidad.",
                    key="cierre_notificado"
                )

                if st.button("Finalizar jornada", type="primary", use_container_width=True, key="btn_cerrar"):

                    if not lugar_cierre:
                        st.error("Indica dónde quedó la unidad.")

                    elif not cierre_notificado:
                        st.error("Confirma el aviso al supervisor.")

                    else:
                        ahora_cierre = datetime.now()

                        conn = conectar()
                        cur = conn.cursor()

                        cur.execute("""
                            INSERT INTO eventos (
                                bitacora_id, fecha_hora, tipo_evento,
                                lugar, estado_carga, supervisor_notificado
                            )
                            VALUES (?, ?, ?, ?, ?, ?)
                        """, (
                            bitacora_id,
                            ahora_cierre.isoformat(timespec="seconds"),
                            "Fin de jornada",
                            lugar_cierre,
                            "No aplica",
                            1
                        ))

                        cur.execute("""
                            UPDATE bitacoras
                            SET estado='CERRADA',
                                lugar_cierre=?,
                                fecha_hora_cierre=?
                            WHERE id=?
                        """, (
                            lugar_cierre,
                            ahora_cierre.isoformat(timespec="seconds"),
                            bitacora_id
                        ))

                        conn.commit()
                        conn.close()

                        st.success("Jornada cerrada.")
                        st.rerun()


# ==========================================================
# HISTORIAL GENERAL
# ==========================================================

with tab5:
    st.header("Historial general")
    st.caption("Vista para supervisión y administración.")

    historial = obtener_bitacoras()

    if historial.empty:
        st.info("No existe historial.")

    else:
        historial["fecha_dt"] = pd.to_datetime(historial["fecha"]).dt.date

        f1, f2 = st.columns(2)

        with f1:
            fecha_desde = st.date_input(
                "Desde",
                value=min(historial["fecha_dt"]),
                key="hist_desde"
            )

        with f2:
            fecha_hasta = st.date_input(
                "Hasta",
                value=max(historial["fecha_dt"]),
                key="hist_hasta"
            )

        f3, f4, f5 = st.columns(3)

        with f3:
            filtro_cliente = st.text_input("Cliente contiene", key="hist_cliente").strip()

        with f4:
            filtro_unidad = st.text_input("Unidad contiene", key="hist_unidad").strip()

        with f5:
            filtro_operador = st.text_input("Operador contiene", key="hist_operador").strip()

        f6, f7 = st.columns(2)

        with f6:
            filtro_supervisor = st.text_input("Supervisor contiene", key="hist_supervisor").strip()

        with f7:
            filtro_estado = st.selectbox(
                "Estado",
                ["Todos", "ABIERTA", "CERRADA"],
                key="hist_estado"
            )

        filtradas = historial[
            (historial["fecha_dt"] >= fecha_desde) &
            (historial["fecha_dt"] <= fecha_hasta)
        ].copy()

        if filtro_cliente:
            filtradas = filtradas[filtradas["cliente"].str.contains(filtro_cliente, case=False, na=False)]

        if filtro_unidad:
            filtradas = filtradas[filtradas["unidad"].str.contains(filtro_unidad, case=False, na=False)]

        if filtro_operador:
            filtradas = filtradas[filtradas["operador"].str.contains(filtro_operador, case=False, na=False)]

        if filtro_supervisor:
            filtradas = filtradas[filtradas["supervisor"].str.contains(filtro_supervisor, case=False, na=False)]

        if filtro_estado != "Todos":
            filtradas = filtradas[filtradas["estado"] == filtro_estado]

        st.metric("Bitácoras encontradas", len(filtradas))

        st.dataframe(
            filtradas[
                [
                    "identificador", "cliente", "fecha", "unidad",
                    "operador", "supervisor", "ruta", "estado",
                    "lugar_cierre"
                ]
            ],
            use_container_width=True,
            hide_index=True
        )

        if not filtradas.empty:
            excel_historial = generar_excel_historial(filtradas)

            st.download_button(
                "Exportar historial a Excel",
                data=excel_historial,
                file_name="Historial_Bitacoras_TRUGESA.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                use_container_width=True
            )
