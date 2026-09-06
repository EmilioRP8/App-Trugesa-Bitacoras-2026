import os
import sqlite3
from datetime import datetime, date, timedelta

import pandas as pd
import streamlit as st


# ==========================================================
# CONFIGURACIÓN GENERAL
# ==========================================================

st.set_page_config(
    page_title="Bitácoras TRUGESA",
    layout="wide"
)

DB_NAME = "bitacoras_trugesa.db"


# ==========================================================
# RUTA DEL LOGO
# ==========================================================

img_path = os.path.join(
    os.path.dirname(__file__),
    "tr.png"
)


# ==========================================================
# BASE DE DATOS
# ==========================================================

def conectar():
    return sqlite3.connect(
        DB_NAME,
        check_same_thread=False
    )


def crear_bd():

    conn = conectar()
    cur = conn.cursor()

    # ------------------------------------------------------
    # BITÁCORAS / JORNADAS
    # ------------------------------------------------------

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

    # ------------------------------------------------------
    # EVENTOS
    # ------------------------------------------------------

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

            FOREIGN KEY(bitacora_id)
            REFERENCES bitacoras(id)
        )
    """)

    conn.commit()
    conn.close()


crear_bd()


# ==========================================================
# CATÁLOGOS
# ==========================================================

CLIENTES = [
    "SESÉ",
    "ADIENT",
    "VOLKSWAGEN",
    "DHL",
    "SKF",
    "OTRO"
]

UNIDADES = [
    "ECO-001",
    "ECO-002",
    "ECO-003",
    "ECO-004",
    "ECO-005"
]

OPERADORES = [
    "Operador 1",
    "Operador 2",
    "Operador 3"
]

SUPERVISORES = [
    "Supervisor 1",
    "Supervisor 2",
    "Supervisor 3"
]


# ==========================================================
# FUNCIONES GENERALES
# ==========================================================

def generar_identificador(
    cliente,
    fecha_servicio,
    unidad
):

    return (
        f"{cliente.upper()} - "
        f"{fecha_servicio.strftime('%d-%m-%Y')} - "
        f"{unidad.upper()}"
    )


def obtener_bitacoras(
    solo_abiertas=False
):

    conn = conectar()

    if solo_abiertas:

        df = pd.read_sql_query("""
            SELECT *
            FROM bitacoras
            WHERE estado = 'ABIERTA'
            ORDER BY id DESC
        """, conn)

    else:

        df = pd.read_sql_query("""
            SELECT *
            FROM bitacoras
            ORDER BY id DESC
        """, conn)

    conn.close()

    return df


def obtener_eventos(
    bitacora_id
):

    conn = conectar()

    df = pd.read_sql_query("""
        SELECT *
        FROM eventos
        WHERE bitacora_id = ?
        ORDER BY fecha_hora ASC
    """,
    conn,
    params=(bitacora_id,)
    )

    conn.close()

    return df


def calcular_desviacion(
    hora_programada_evento
):

    if not hora_programada_evento:
        return None

    ahora = datetime.now()

    hora_obj = datetime.strptime(
        hora_programada_evento,
        "%H:%M"
    ).time()

    programado = datetime.combine(
        ahora.date(),
        hora_obj
    )

    diferencia = (
        ahora - programado
    )

    return round(
        diferencia.total_seconds() / 60
    )


def formatear_duracion(
    segundos
):

    if segundos is None:
        return "00:00"

    segundos = int(segundos)

    horas = segundos // 3600
    minutos = (
        segundos % 3600
    ) // 60

    return f"{horas:02d}:{minutos:02d}"


def obtener_duracion_jornada(
    bitacora_id
):

    eventos = obtener_eventos(
        bitacora_id
    )

    if eventos.empty:
        return "00:00"

    eventos["fecha_hora_dt"] = pd.to_datetime(
        eventos["fecha_hora"]
    )

    inicio = eventos[
        "fecha_hora_dt"
    ].min()

    fin = eventos[
        "fecha_hora_dt"
    ].max()

    segundos = (
        fin - inicio
    ).total_seconds()

    return formatear_duracion(
        segundos
    )


def calcular_tiempos_eventos(
    eventos
):

    if eventos.empty:
        return {
            "movimiento": 0,
            "espera": 0,
            "incidencia": 0
        }

    eventos = eventos.copy()

    eventos[
        "fecha_hora_dt"
    ] = pd.to_datetime(
        eventos["fecha_hora"]
    )

    eventos = eventos.sort_values(
        "fecha_hora_dt"
    )

    movimiento = 0
    espera = 0
    incidencia = 0

    for i in range(
        len(eventos) - 1
    ):

        actual = eventos.iloc[i]
        siguiente = eventos.iloc[i + 1]

        diferencia = (
            siguiente["fecha_hora_dt"]
            - actual["fecha_hora_dt"]
        ).total_seconds()

        tipo = actual[
            "tipo_evento"
        ]

        if tipo in [
            "Inicio de movimiento",
            "Reinicio de movimiento"
        ]:

            movimiento += diferencia

        elif tipo in [
            "Inicio de espera",
            "Detención"
        ]:

            if actual[
                "incidencia"
            ] == 1:

                incidencia += diferencia

            else:

                espera += diferencia

    return {
        "movimiento": movimiento,
        "espera": espera,
        "incidencia": incidencia
    }


# ==========================================================
# ENCABEZADO
# ==========================================================

col_logo, col_titulo = st.columns(
    [1, 5]
)

with col_logo:

    if os.path.exists(
        img_path
    ):

        st.image(
            img_path,
            use_container_width=True
        )

with col_titulo:

    st.markdown(
        """
        # **TRUGESA TRANSPORTACIÓN ESPECIALIZADA**
        ## Sistema de Bitácoras Operativas
        """
    )

    st.caption(
        "Control de jornadas, movimientos, tiempos de espera, "
        "estado de carga, incidencias y cierre de unidad."
    )


st.divider()


# ==========================================================
# NAVEGACIÓN INTERNA
# ==========================================================

tab1, tab2, tab3, tab4 = st.tabs(
    [
        "Crear jornada",
        "Registrar evento",
        "Editar evento",
        "Consultar / Cerrar"
    ]
)


# ==========================================================
# TAB 1 - CREAR JORNADA
# ==========================================================

with tab1:

    st.header(
        "Crear nueva jornada"
    )

    st.info(
        "La jornada debe ser creada por el supervisor "
        "antes de iniciar la operación."
    )

    col1, col2, col3 = st.columns(3)

    with col1:

        cliente = st.selectbox(
            "Cliente",
            CLIENTES,
            key="crear_cliente"
        )

        if cliente == "OTRO":

            cliente = st.text_input(
                "Nombre del cliente",
                key="crear_otro_cliente"
            )

    with col2:

        fecha_servicio = st.date_input(
            "Fecha del servicio",
            value=date.today(),
            key="crear_fecha"
        )

    with col3:

        unidad = st.selectbox(
            "¿En qué unidad se realizará el servicio?",
            UNIDADES,
            key="crear_unidad"
        )


    col4, col5, col6 = st.columns(3)

    with col4:

        operador = st.selectbox(
            "Operador asignado",
            OPERADORES,
            key="crear_operador"
        )

    with col5:

        supervisor = st.selectbox(
            "Supervisor responsable",
            SUPERVISORES,
            key="crear_supervisor"
        )

    with col6:

        hora_programada = st.time_input(
            "Hora programada de inicio",
            key="crear_hora"
        )


    ruta = st.text_input(
        "Ruta / servicio asignado",
        placeholder="Ej. SESÉ Puebla → Planta Querétaro",
        key="crear_ruta"
    )


    identificador = generar_identificador(
        cliente,
        fecha_servicio,
        unidad
    )


    st.info(
        f"**Bitácora:** {identificador}"
    )


    if st.button(
        "Crear bitácora",
        type="primary",
        use_container_width=True,
        key="btn_crear"
    ):

        if not cliente:

            st.error(
                "Debes indicar un cliente."
            )

        elif not ruta:

            st.error(
                "Debes indicar la ruta o servicio."
            )

        else:

            conn = conectar()
            cur = conn.cursor()

            try:

                cur.execute("""
                    INSERT INTO bitacoras (
                        identificador,
                        cliente,
                        fecha,
                        unidad,
                        operador,
                        supervisor,
                        ruta,
                        hora_programada,
                        estado
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
                    hora_programada.strftime(
                        "%H:%M"
                    )
                ))

                conn.commit()

                st.success(
                    "Bitácora creada correctamente."
                )

            except sqlite3.IntegrityError:

                st.error(
                    "Ya existe una bitácora para esa combinación "
                    "Cliente + Fecha + Unidad."
                )

            finally:

                conn.close()


# ==========================================================
# TAB 2 - REGISTRAR EVENTO
# ==========================================================

with tab2:

    st.header(
        "Registrar evento"
    )

    bitacoras_abiertas = obtener_bitacoras(
        solo_abiertas=True
    )

    if bitacoras_abiertas.empty:

        st.warning(
            "No existen jornadas abiertas."
        )

    else:

        opciones = {
            row["identificador"]:
            row["id"]

            for _, row
            in bitacoras_abiertas.iterrows()
        }

        seleccion = st.selectbox(
            "Seleccionar bitácora",
            list(opciones.keys()),
            key="evento_bitacora"
        )

        bitacora_id = opciones[
            seleccion
        ]

        datos = bitacoras_abiertas[
            bitacoras_abiertas["id"]
            == bitacora_id
        ].iloc[0]


        st.divider()


        col_info1, col_info2, col_info3 = st.columns(3)

        with col_info1:

            st.metric(
                "Unidad",
                datos["unidad"]
            )

        with col_info2:

            st.metric(
                "Operador",
                datos["operador"]
            )

        with col_info3:

            st.metric(
                "Supervisor",
                datos["supervisor"]
            )


        st.write(
            f"**Ruta:** {datos['ruta']}"
        )


        st.divider()


        col_evento, col_lugar = st.columns(2)

        with col_evento:

            tipo_evento = st.selectbox(
                "Tipo de evento",
                [
                    "Inicio de jornada",
                    "Inicio de movimiento",
                    "Llegada a punto",
                    "Inicio de espera",
                    "Fin de espera",
                    "Inicio de carga",
                    "Carga finalizada",
                    "Inicio de descarga",
                    "Descarga finalizada",
                    "Detención",
                    "Reinicio de movimiento",
                    "Otro"
                ],
                key="evento_tipo"
            )

        with col_lugar:

            lugar = st.text_input(
                "Lugar",
                placeholder="Ej. Planta SESÉ Puebla",
                key="evento_lugar"
            )


        st.markdown(
            "### Estado de carga"
        )

        estado_carga = st.radio(
            "Seleccionar estado de la caja",
            [
                "Material / mercancía",
                "Empaque vacío",
                "Caja vacía",
                "No aplica"
            ],
            horizontal=True,
            key="evento_carga"
        )


        motivo_espera = None
        detalle_espera = None


        if tipo_evento in [
            "Inicio de espera",
            "Detención"
        ]:

            st.markdown(
                "### Motivo de espera o detención"
            )

            motivo_espera = st.selectbox(
                "Motivo",
                [
                    "Esperando andén",
                    "Carga",
                    "Descarga",
                    "Documentación",
                    "Acceso a planta",
                    "Cliente",
                    "Tráfico",
                    "Revisión",
                    "Falla mecánica",
                    "Llanta / neumático",
                    "Autoridad / retén",
                    "Descanso",
                    "Otro"
                ],
                key="evento_motivo"
            )

            detalle_espera = st.text_area(
                "Descripción",
                placeholder="Ej. Esperando disponibilidad de andén.",
                key="evento_detalle"
            )


        st.markdown(
            "### Control de horario"
        )

        comparar_horario = st.checkbox(
            "Este evento tenía una hora programada",
            key="evento_comparar"
        )

        hora_programada_evento = None

        if comparar_horario:

            hora_temp = st.time_input(
                "Hora programada del evento",
                key="evento_hora_programada"
            )

            hora_programada_evento = (
                hora_temp.strftime(
                    "%H:%M"
                )
            )


        st.markdown(
            "### Incidencias"
        )

        incidencia = st.checkbox(
            "Existe una incidencia durante este evento",
            key="evento_incidencia"
        )

        tipo_incidencia = None
        descripcion_incidencia = None

        if incidencia:

            tipo_incidencia = st.selectbox(
                "Tipo de incidencia",
                [
                    "Falla mecánica",
                    "Llanta / neumático",
                    "Accidente",
                    "Daño",
                    "Mercancía",
                    "Documentación",
                    "Cliente",
                    "Rechazo de mercancía",
                    "Seguridad",
                    "Autoridad / retén",
                    "Otro"
                ],
                key="evento_tipo_incidencia"
            )

            descripcion_incidencia = st.text_area(
                "Descripción de la incidencia",
                key="evento_desc_incidencia"
            )


        st.markdown(
            "### Confirmación de reporte"
        )

        notificado = st.checkbox(
            (
                f"Confirmo que notifiqué al supervisor "
                f"{datos['supervisor']} por WhatsApp."
            ),
            key="evento_notificado"
        )


        ahora = datetime.now()


        col_hora1, col_hora2, col_hora3 = st.columns(3)

        with col_hora1:

            st.metric(
                "Fecha",
                ahora.strftime(
                    "%d/%m/%Y"
                )
            )

        with col_hora2:

            st.metric(
                "Hora del sistema",
                ahora.strftime(
                    "%H:%M:%S"
                )
            )

        with col_hora3:

            duracion_actual = obtener_duracion_jornada(
                bitacora_id
            )

            st.metric(
                "Tiempo registrado",
                duracion_actual
            )


        if st.button(
            "Registrar evento",
            type="primary",
            use_container_width=True,
            key="btn_evento"
        ):

            if not lugar:

                st.error(
                    "Debes indicar el lugar."
                )

            elif not notificado:

                st.error(
                    "Debes confirmar el aviso al supervisor."
                )

            else:

                desviacion = None

                if hora_programada_evento:

                    desviacion = calcular_desviacion(
                        hora_programada_evento
                    )


                conn = conectar()
                cur = conn.cursor()


                ahora_registro = datetime.now()


                cur.execute("""
                    INSERT INTO eventos (
                        bitacora_id,
                        fecha_hora,
                        tipo_evento,
                        lugar,
                        estado_carga,
                        motivo_espera,
                        detalle_espera,
                        incidencia,
                        tipo_incidencia,
                        descripcion_incidencia,
                        supervisor_notificado,
                        hora_programada_evento,
                        desviacion_minutos
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    bitacora_id,
                    ahora_registro.isoformat(
                        timespec="seconds"
                    ),
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
                        SET fecha_hora_inicio = ?
                        WHERE id = ?
                    """, (
                        ahora_registro.isoformat(
                            timespec="seconds"
                        ),
                        bitacora_id
                    ))


                conn.commit()
                conn.close()


                st.success(
                    "Evento registrado correctamente."
                )

                st.rerun()


# ==========================================================
# TAB 3 - EDITAR EVENTO
# ==========================================================

with tab3:

    st.header(
        "Editar evento"
    )

    st.warning(
        "El operador solo puede modificar un evento "
        "durante los primeros 5 minutos."
    )


    bitacoras_abiertas = obtener_bitacoras(
        solo_abiertas=True
    )


    if bitacoras_abiertas.empty:

        st.warning(
            "No existen jornadas abiertas."
        )

    else:

        opciones = {
            row["identificador"]:
            row["id"]

            for _, row
            in bitacoras_abiertas.iterrows()
        }


        seleccion = st.selectbox(
            "Seleccionar bitácora",
            list(opciones.keys()),
            key="editar_bitacora"
        )


        bitacora_id = opciones[
            seleccion
        ]


        eventos = obtener_eventos(
            bitacora_id
        )


        if eventos.empty:

            st.info(
                "Esta jornada no tiene eventos."
            )

        else:

            ahora = datetime.now()

            eventos_editables = []


            for _, row in eventos.iterrows():

                fecha_evento = datetime.fromisoformat(
                    row["fecha_hora"]
                )

                diferencia = (
                    ahora - fecha_evento
                )

                if diferencia <= timedelta(
                    minutes=5
                ):

                    eventos_editables.append(
                        row
                    )


            if not eventos_editables:

                st.info(
                    "No existen eventos editables."
                )

            else:

                opciones_evento = {}


                for row in eventos_editables:

                    etiqueta = (
                        f"{row['id']} | "
                        f"{row['tipo_evento']} | "
                        f"{row['lugar']} | "
                        f"{row['fecha_hora'][11:19]}"
                    )

                    opciones_evento[
                        etiqueta
                    ] = row["id"]


                evento_sel = st.selectbox(
                    "Evento a corregir",
                    list(
                        opciones_evento.keys()
                    ),
                    key="evento_editar"
                )


                evento_id = opciones_evento[
                    evento_sel
                ]


                registro = eventos[
                    eventos["id"]
                    == evento_id
                ].iloc[0]


                nuevo_tipo = st.selectbox(
                    "Tipo de evento",
                    [
                        "Inicio de jornada",
                        "Inicio de movimiento",
                        "Llegada a punto",
                        "Inicio de espera",
                        "Fin de espera",
                        "Inicio de carga",
                        "Carga finalizada",
                        "Inicio de descarga",
                        "Descarga finalizada",
                        "Detención",
                        "Reinicio de movimiento",
                        "Otro"
                    ],
                    index=0,
                    key="editar_tipo"
                )


                nuevo_lugar = st.text_input(
                    "Lugar",
                    value=registro[
                        "lugar"
                    ],
                    key="editar_lugar"
                )


                nuevo_estado_carga = st.selectbox(
                    "Estado de carga",
                    [
                        "Material / mercancía",
                        "Empaque vacío",
                        "Caja vacía",
                        "No aplica"
                    ],
                    key="editar_carga"
                )


                if st.button(
                    "Guardar corrección",
                    type="primary",
                    use_container_width=True,
                    key="btn_editar"
                ):

                    fecha_evento = datetime.fromisoformat(
                        registro["fecha_hora"]
                    )


                    if (
                        datetime.now()
                        - fecha_evento
                    ) > timedelta(
                        minutes=5
                    ):

                        st.error(
                            "El periodo de edición ya terminó."
                        )

                    else:

                        conn = conectar()
                        cur = conn.cursor()


                        cur.execute("""
                            UPDATE eventos
                            SET
                                tipo_evento = ?,
                                lugar = ?,
                                estado_carga = ?,
                                editado = 1,
                                fecha_hora_edicion = ?
                            WHERE id = ?
                        """, (
                            nuevo_tipo,
                            nuevo_lugar,
                            nuevo_estado_carga,
                            datetime.now().isoformat(
                                timespec="seconds"
                            ),
                            evento_id
                        ))


                        conn.commit()
                        conn.close()


                        st.success(
                            "Evento corregido."
                        )

                        st.rerun()


# ==========================================================
# TAB 4 - CONSULTAR / CERRAR
# ==========================================================

with tab4:

    st.header(
        "Consultar jornadas"
    )

    bitacoras = obtener_bitacoras()


    if bitacoras.empty:

        st.info(
            "Todavía no existen bitácoras."
        )

    else:

        st.dataframe(
            bitacoras[
                [
                    "identificador",
                    "cliente",
                    "fecha",
                    "unidad",
                    "operador",
                    "supervisor",
                    "ruta",
                    "estado",
                    "lugar_cierre"
                ]
            ],
            use_container_width=True,
            hide_index=True
        )


        opciones = {
            row["identificador"]:
            row["id"]

            for _, row
            in bitacoras.iterrows()
        }


        seleccion = st.selectbox(
            "Seleccionar bitácora",
            list(
                opciones.keys()
            ),
            key="consulta_bitacora"
        )


        bitacora_id = opciones[
            seleccion
        ]


        datos_bitacora = bitacoras[
            bitacoras["id"]
            == bitacora_id
        ].iloc[0]


        eventos = obtener_eventos(
            bitacora_id
        )


        st.divider()


        if eventos.empty:

            st.info(
                "Esta bitácora todavía no tiene eventos."
            )

        else:

            eventos[
                "fecha_hora_dt"
            ] = pd.to_datetime(
                eventos["fecha_hora"]
            )


            inicio = eventos[
                "fecha_hora_dt"
            ].min()

            fin = eventos[
                "fecha_hora_dt"
            ].max()


            duracion = (
                fin - inicio
            ).total_seconds()


            tiempos = calcular_tiempos_eventos(
                eventos
            )


            col1, col2, col3, col4 = st.columns(4)

            with col1:

                st.metric(
                    "Eventos",
                    len(eventos)
                )

            with col2:

                st.metric(
                    "Tiempo total",
                    formatear_duracion(
                        duracion
                    )
                )

            with col3:

                st.metric(
                    "Movimiento",
                    formatear_duracion(
                        tiempos[
                            "movimiento"
                        ]
                    )
                )

            with col4:

                st.metric(
                    "Espera",
                    formatear_duracion(
                        tiempos[
                            "espera"
                        ]
                    )
                )


            col5, col6 = st.columns(2)

            with col5:

                st.metric(
                    "Tiempo por incidencias",
                    formatear_duracion(
                        tiempos[
                            "incidencia"
                        ]
                    )
                )

            with col6:

                incidencias_total = int(
                    eventos[
                        "incidencia"
                    ].sum()
                )

                st.metric(
                    "Incidencias",
                    incidencias_total
                )


            st.subheader(
                "Línea de tiempo"
            )


            vista = eventos.copy()


            vista["Hora"] = (
                vista[
                    "fecha_hora_dt"
                ].dt.strftime(
                    "%H:%M:%S"
                )
            )


            vista["Supervisor"] = (
                vista[
                    "supervisor_notificado"
                ].map({
                    1: "Sí",
                    0: "No"
                })
            )


            vista["Incidencia"] = (
                vista[
                    "incidencia"
                ].map({
                    1: "Sí",
                    0: "No"
                })
            )


            vista["Editado"] = (
                vista[
                    "editado"
                ].map({
                    1: "Sí",
                    0: "No"
                })
            )


            columnas_vista = [
                "Hora",
                "tipo_evento",
                "lugar",
                "estado_carga",
                "motivo_espera",
                "Incidencia",
                "Supervisor",
                "desviacion_minutos",
                "Editado"
            ]


            st.dataframe(
                vista[
                    columnas_vista
                ],
                use_container_width=True,
                hide_index=True
            )


            csv = vista[
                columnas_vista
            ].to_csv(
                index=False
            ).encode(
                "utf-8-sig"
            )


            st.download_button(
                "Descargar bitácora",
                csv,
                file_name=(
                    seleccion
                    .replace(
                        " ",
                        "_"
                    )
                    + ".csv"
                ),
                mime="text/csv"
            )


        # ==================================================
        # CIERRE
        # ==================================================

        if (
            datos_bitacora[
                "estado"
            ] == "ABIERTA"
        ):

            st.divider()

            st.subheader(
                "Cerrar jornada"
            )

            st.info(
                "La jornada termina cuando el operador deja "
                "la unidad en el lugar donde descansará."
            )


            lugar_cierre = st.text_input(
                "¿Dónde quedará la unidad?",
                placeholder=(
                    "Ej. Casa del operador, Patio TRUGESA, "
                    "Parador San Luis..."
                ),
                key="cierre_lugar"
            )


            cierre_notificado = st.checkbox(
                (
                    f"Confirmo que notifiqué al supervisor "
                    f"{datos_bitacora['supervisor']} "
                    "la ubicación final de la unidad."
                ),
                key="cierre_notificado"
            )


            if st.button(
                "Finalizar jornada",
                type="primary",
                use_container_width=True,
                key="btn_cerrar"
            ):

                if not lugar_cierre:

                    st.error(
                        "Debes indicar dónde quedó la unidad."
                    )

                elif not cierre_notificado:

                    st.error(
                        "Debes confirmar el aviso al supervisor."
                    )

                else:

                    ahora_cierre = datetime.now()

                    conn = conectar()
                    cur = conn.cursor()


                    cur.execute("""
                        INSERT INTO eventos (
                            bitacora_id,
                            fecha_hora,
                            tipo_evento,
                            lugar,
                            estado_carga,
                            supervisor_notificado
                        )
                        VALUES (?, ?, ?, ?, ?, ?)
                    """, (
                        bitacora_id,
                        ahora_cierre.isoformat(
                            timespec="seconds"
                        ),
                        "Fin de jornada",
                        lugar_cierre,
                        "No aplica",
                        1
                    ))


                    cur.execute("""
                        UPDATE bitacoras
                        SET
                            estado = 'CERRADA',
                            lugar_cierre = ?,
                            fecha_hora_cierre = ?
                        WHERE id = ?
                    """, (
                        lugar_cierre,
                        ahora_cierre.isoformat(
                            timespec="seconds"
                        ),
                        bitacora_id
                    ))


                    conn.commit()
                    conn.close()


                    st.success(
                        "Jornada finalizada correctamente."
                    )

                    st.rerun()

        else:

            st.success(
                f"Jornada cerrada. "
                f"Unidad ubicada en: "
                f"{datos_bitacora['lugar_cierre']}"
            )
