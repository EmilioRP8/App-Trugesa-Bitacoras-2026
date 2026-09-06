import streamlit as st
import sqlite3
from datetime import datetime, date, timedelta
import pandas as pd

# =========================================================
# CONFIGURACIÓN
# =========================================================

st.set_page_config(
    page_title="TRUGESA | Bitácoras Operativas",
    page_icon="🚛",
    layout="wide"
)

DB_NAME = "bitacoras_trugesa.db"


# =========================================================
# BASE DE DATOS
# =========================================================

def conectar():
    return sqlite3.connect(DB_NAME, check_same_thread=False)


def crear_bd():
    conn = conectar()
    cur = conn.cursor()

    # ---------------------------------------------
    # BITÁCORAS
    # ---------------------------------------------
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
            lugar_cierre TEXT,
            fecha_hora_cierre TEXT
        )
    """)

    # ---------------------------------------------
    # EVENTOS
    # ---------------------------------------------
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


# =========================================================
# CATÁLOGOS INICIALES
# =========================================================

# Más adelante estos se pueden cargar desde Excel
# o desde un módulo administrativo.

UNIDADES = [
    "ECO-001",
    "ECO-002",
    "ECO-003",
    "ECO-004",
    "ECO-005",
]

CLIENTES = [
    "SESÉ",
    "ADIENT",
    "VOLKSWAGEN",
    "DHL",
    "SKF",
    "OTRO"
]

OPERADORES = [
    "Operador 1",
    "Operador 2",
    "Operador 3",
]

SUPERVISORES = [
    "Supervisor 1",
    "Supervisor 2",
    "Supervisor 3",
]


# =========================================================
# FUNCIONES
# =========================================================

def generar_identificador(cliente, fecha, unidad):
    fecha_txt = fecha.strftime("%d-%m-%Y")
    return f"{cliente.upper()} - {fecha_txt} - {unidad.upper()}"


def obtener_bitacoras(solo_abiertas=False):
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


def obtener_eventos(bitacora_id):
    conn = conectar()

    df = pd.read_sql_query("""
        SELECT *
        FROM eventos
        WHERE bitacora_id = ?
        ORDER BY fecha_hora ASC
    """, conn, params=(bitacora_id,))

    conn.close()
    return df


def calcular_desviacion(hora_programada):
    if not hora_programada:
        return None

    ahora = datetime.now()

    try:
        hora_obj = datetime.strptime(hora_programada, "%H:%M").time()

        programado = datetime.combine(
            ahora.date(),
            hora_obj
        )

        diferencia = ahora - programado

        return round(diferencia.total_seconds() / 60)

    except:
        return None


# =========================================================
# CABECERA
# =========================================================

st.title("🚛 TRUGESA")
st.subheader("Sistema de Bitácoras Operativas")

st.caption(
    "Control de jornadas, movimientos, tiempos de espera, "
    "estado de carga, incidencias y cierre de unidad."
)

st.divider()


# =========================================================
# MENÚ PRINCIPAL
# =========================================================

pagina = st.sidebar.radio(
    "Módulo",
    [
        "Supervisor | Crear bitácora",
        "Operador | Registrar evento",
        "Operador | Editar evento",
        "Cerrar jornada",
        "Consultar bitácoras"
    ]
)


# =========================================================
# 1. SUPERVISOR CREA BITÁCORA
# =========================================================

if pagina == "Supervisor | Crear bitácora":

    st.header("Crear nueva bitácora")

    st.info(
        "La bitácora debe ser creada por el supervisor "
        "antes de que el operador inicie la jornada."
    )

    col1, col2 = st.columns(2)

    with col1:

        cliente = st.selectbox(
            "Cliente",
            CLIENTES
        )

        if cliente == "OTRO":
            cliente = st.text_input(
                "Nombre del cliente"
            )

        fecha_servicio = st.date_input(
            "Fecha",
            value=date.today()
        )

        unidad = st.selectbox(
            "¿En qué unidad se realizará el servicio?",
            UNIDADES
        )

        operador = st.selectbox(
            "Operador asignado",
            OPERADORES
        )

    with col2:

        supervisor = st.selectbox(
            "Supervisor responsable",
            SUPERVISORES
        )

        ruta = st.text_input(
            "Ruta / servicio asignado",
            placeholder="Ej. SESÉ Puebla → Planta Querétaro"
        )

        hora_programada = st.time_input(
            "Hora programada de inicio"
        )

    if cliente:
        identificador = generar_identificador(
            cliente,
            fecha_servicio,
            unidad
        )

        st.success(
            f"Bitácora: **{identificador}**"
        )

    if st.button(
        "Crear bitácora",
        type="primary",
        use_container_width=True
    ):

        if not cliente:
            st.error("Debes indicar un cliente.")

        elif not ruta:
            st.error("Debes indicar la ruta o servicio.")

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
                    hora_programada.strftime("%H:%M")
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


# =========================================================
# 2. OPERADOR REGISTRA EVENTOS
# =========================================================

elif pagina == "Operador | Registrar evento":

    st.header("Registrar evento")

    bitacoras = obtener_bitacoras(
        solo_abiertas=True
    )

    if bitacoras.empty:

        st.warning(
            "No existen bitácoras abiertas."
        )

    else:

        opciones = {
            row["identificador"]: row["id"]
            for _, row in bitacoras.iterrows()
        }

        seleccion = st.selectbox(
            "Seleccionar bitácora",
            opciones.keys()
        )

        bitacora_id = opciones[seleccion]

        datos = bitacoras[
            bitacoras["id"] == bitacora_id
        ].iloc[0]

        st.write(
            f"**Operador:** {datos['operador']}"
        )

        st.write(
            f"**Supervisor:** {datos['supervisor']}"
        )

        st.write(
            f"**Ruta:** {datos['ruta']}"
        )

        st.divider()

        # -----------------------------------------
        # TIPO DE EVENTO
        # -----------------------------------------

        tipo_evento = st.selectbox(
            "¿Qué está ocurriendo?",
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
            ]
        )

        lugar = st.text_input(
            "¿Dónde se encuentra?",
            placeholder="Ej. Planta SESÉ Puebla"
        )

        # -----------------------------------------
        # ESTADO DE CARGA
        # -----------------------------------------

        estado_carga = st.selectbox(
            "Estado de la caja",
            [
                "Material / mercancía",
                "Empaque vacío",
                "Caja vacía",
                "No aplica"
            ]
        )

        # -----------------------------------------
        # ESPERAS
        # -----------------------------------------

        motivo_espera = None
        detalle_espera = None

        if tipo_evento in [
            "Inicio de espera",
            "Detención"
        ]:

            motivo_espera = st.selectbox(
                "Motivo de la detención / espera",
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
                ]
            )

            detalle_espera = st.text_area(
                "Detalle",
                placeholder=(
                    "Ej. Unidad esperando disponibilidad "
                    "de andén en planta."
                )
            )

        # -----------------------------------------
        # HORARIO PROGRAMADO
        # -----------------------------------------

        comparar_horario = st.checkbox(
            "Este evento tenía una hora programada"
        )

        hora_programada_evento = None

        if comparar_horario:

            hora_temp = st.time_input(
                "Hora programada del evento"
            )

            hora_programada_evento = (
                hora_temp.strftime("%H:%M")
            )

        # -----------------------------------------
        # INCIDENCIA
        # -----------------------------------------

        incidencia = st.checkbox(
            "⚠️ Existe una incidencia"
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
                ]
            )

            descripcion_incidencia = st.text_area(
                "Describe la incidencia"
            )

            st.info(
                "En una versión posterior podremos agregar "
                "carga de fotografías únicamente cuando "
                "exista una incidencia."
            )

        # -----------------------------------------
        # AVISO AL SUPERVISOR
        # -----------------------------------------

        supervisor_notificado = st.checkbox(
            f"Confirmo que notifiqué a "
            f"{datos['supervisor']} por WhatsApp."
        )

        st.divider()

        hora_actual = datetime.now()

        st.write(
            "**Hora del sistema:** "
            + hora_actual.strftime(
                "%d/%m/%Y %H:%M:%S"
            )
        )

        # -----------------------------------------
        # GUARDAR
        # -----------------------------------------

        if st.button(
            "Registrar evento",
            type="primary",
            use_container_width=True
        ):

            if not lugar:

                st.error(
                    "Debes indicar el lugar."
                )

            elif not supervisor_notificado:

                st.error(
                    "Debes confirmar que notificaste "
                    "al supervisor."
                )

            else:

                desviacion = None

                if hora_programada_evento:

                    desviacion = calcular_desviacion(
                        hora_programada_evento
                    )

                conn = conectar()
                cur = conn.cursor()

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
                    datetime.now().isoformat(
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

                conn.commit()
                conn.close()

                st.success(
                    "✅ Evento registrado."
                )

                st.rerun()


# =========================================================
# 3. EDITAR EVENTOS
# =========================================================

elif pagina == "Operador | Editar evento":

    st.header("Editar evento")

    st.warning(
        "Un evento solo puede modificarse durante "
        "los primeros 5 minutos después de su registro."
    )

    bitacoras = obtener_bitacoras(
        solo_abiertas=True
    )

    if bitacoras.empty:

        st.warning(
            "No existen bitácoras abiertas."
        )

    else:

        opciones = {
            row["identificador"]: row["id"]
            for _, row in bitacoras.iterrows()
        }

        seleccion = st.selectbox(
            "Seleccionar bitácora",
            opciones.keys()
        )

        bitacora_id = opciones[seleccion]

        eventos = obtener_eventos(
            bitacora_id
        )

        if eventos.empty:

            st.info(
                "Esta bitácora todavía no tiene eventos."
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
                    "No hay eventos dentro del "
                    "periodo permitido de edición."
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
                    opciones_evento.keys()
                )

                evento_id = opciones_evento[
                    evento_sel
                ]

                registro = eventos[
                    eventos["id"] == evento_id
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
                    ]
                )

                nuevo_lugar = st.text_input(
                    "Lugar",
                    value=registro["lugar"]
                )

                if st.button(
                    "Guardar corrección",
                    type="primary"
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
                            "El periodo de edición "
                            "ya terminó."
                        )

                    else:

                        conn = conectar()
                        cur = conn.cursor()

                        cur.execute("""
                            UPDATE eventos
                            SET
                                tipo_evento = ?,
                                lugar = ?,
                                editado = 1,
                                fecha_hora_edicion = ?
                            WHERE id = ?
                        """, (
                            nuevo_tipo,
                            nuevo_lugar,
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


# =========================================================
# 4. CERRAR JORNADA
# =========================================================

elif pagina == "Cerrar jornada":

    st.header("Cerrar jornada")

    bitacoras = obtener_bitacoras(
        solo_abiertas=True
    )

    if bitacoras.empty:

        st.success(
            "No existen jornadas pendientes."
        )

    else:

        opciones = {
            row["identificador"]: row["id"]
            for _, row in bitacoras.iterrows()
        }

        seleccion = st.selectbox(
            "Seleccionar bitácora",
            opciones.keys()
        )

        bitacora_id = opciones[
            seleccion
        ]

        datos = bitacoras[
            bitacoras["id"]
            == bitacora_id
        ].iloc[0]

        st.write(
            f"**Unidad:** {datos['unidad']}"
        )

        st.write(
            f"**Operador:** {datos['operador']}"
        )

        lugar_cierre = st.text_input(
            "¿Dónde quedará la unidad para descanso?",
            placeholder=(
                "Ej. Casa del operador, "
                "Patio TRUGESA, Parador..."
            )
        )

        supervisor_notificado = st.checkbox(
            f"Confirmo que notifiqué a "
            f"{datos['supervisor']} "
            "la ubicación final de la unidad."
        )

        if st.button(
            "Finalizar jornada",
            type="primary",
            use_container_width=True
        ):

            if not lugar_cierre:

                st.error(
                    "Debes indicar dónde quedó "
                    "la unidad."
                )

            elif not supervisor_notificado:

                st.error(
                    "Debes confirmar el aviso "
                    "al supervisor."
                )

            else:

                conn = conectar()
                cur = conn.cursor()

                # Evento automático final
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
                    datetime.now().isoformat(
                        timespec="seconds"
                    ),
                    "Fin de jornada",
                    lugar_cierre,
                    "No aplica",
                    1
                ))

                # Cierre de bitácora
                cur.execute("""
                    UPDATE bitacoras
                    SET
                        estado = 'CERRADA',
                        lugar_cierre = ?,
                        fecha_hora_cierre = ?
                    WHERE id = ?
                """, (
                    lugar_cierre,
                    datetime.now().isoformat(
                        timespec="seconds"
                    ),
                    bitacora_id
                ))

                conn.commit()
                conn.close()

                st.success(
                    "🏁 Jornada finalizada."
                )

                st.rerun()


# =========================================================
# 5. CONSULTA
# =========================================================

elif pagina == "Consultar bitácoras":

    st.header("Consulta de bitácoras")

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
            row["identificador"]: row["id"]
            for _, row in bitacoras.iterrows()
        }

        seleccion = st.selectbox(
            "Ver detalle",
            opciones.keys()
        )

        bitacora_id = opciones[
            seleccion
        ]

        eventos = obtener_eventos(
            bitacora_id
        )

        if not eventos.empty:

            # -----------------------------------------
            # TIEMPO TRANSCURRIDO
            # -----------------------------------------

            eventos["fecha_hora_dt"] = pd.to_datetime(
                eventos["fecha_hora"]
            )

            inicio = eventos[
                "fecha_hora_dt"
            ].min()

            fin = eventos[
                "fecha_hora_dt"
            ].max()

            duracion = fin - inicio

            col1, col2, col3 = st.columns(3)

            col1.metric(
                "Eventos",
                len(eventos)
            )

            col2.metric(
                "Inicio",
                inicio.strftime(
                    "%H:%M"
                )
            )

            col3.metric(
                "Tiempo registrado",
                str(duracion).split(".")[0]
            )

            st.subheader(
                "Línea de tiempo"
            )

            vista = eventos.copy()

            vista["Hora"] = (
                vista["fecha_hora_dt"]
                .dt.strftime("%H:%M:%S")
            )

            vista["Supervisor"] = vista[
                "supervisor_notificado"
            ].map({
                1: "Sí",
                0: "No"
            })

            vista["Incidencia"] = vista[
                "incidencia"
            ].map({
                1: "Sí",
                0: "No"
            })

            columnas = [
                "Hora",
                "tipo_evento",
                "lugar",
                "estado_carga",
                "motivo_espera",
                "Incidencia",
                "Supervisor",
                "desviacion_minutos"
            ]

            st.dataframe(
                vista[columnas],
                use_container_width=True,
                hide_index=True
            )

            # -----------------------------------------
            # DESCARGA
            # -----------------------------------------

            csv = vista[
                columnas
            ].to_csv(
                index=False
            ).encode(
                "utf-8-sig"
            )

            st.download_button(
                "Descargar bitácora CSV",
                csv,
                file_name=(
                    seleccion
                    .replace(" ", "_")
                    + ".csv"
                ),
                mime="text/csv"
            )