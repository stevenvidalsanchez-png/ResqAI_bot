import os
import logging
from flask import Flask, request
from telegram import Update, ReplyKeyboardMarkup, ReplyKeyboardRemove
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, ConversationHandler

# Configuración de Logging
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

# Estados del flujo conversacional
ROL, INCIDENTE, TRIAGE_PRO, CONCIENCIA_CIVIL, SANGRADO_CIVIL, UBICACION = range(6)

app = Flask(__name__)
TOKEN = os.getenv("TELEGRAM_TOKEN")
telegram_app = Application.builder().token(TOKEN).build() if TOKEN else None

# --- RED HOSPITALARIA DE ALTA COMPLEJIDAD (CALI) ---
RED_HOSPITALARIA = {
    "CRITICO_TRAUMA": {"nombre": "Hospital Universitario del Valle (HUV)", "nivel": 3, "zona": "Centro/Sur", "especialidad": "Trauma Mayor / Alta Complejidad"},
    "ALTA_COMPLEJIDAD_SUR": {"nombre": "Fundación Valle del Lili", "nivel": 3, "zona": "Sur", "especialidad": "Cuidado Crítico / Trauma / Politrauma"},
    "ALTA_COMPLEJIDAD_CENTRO": {"nombre": "Clínica Imbanaco", "nivel": 3, "zona": "Sur/Centro", "especialidad": "Trauma / Cirugía de Urgencias"},
    "BASICO": {"nombre": "Hospital Primitivo Iglesias / Red de Salud", "nivel": 1, "zona": "Urbana", "especialidad": "Estabilización / Baja Complejidad"}
}

# --- MOTOR LÓGICO DE TRADUCCIÓN DE TRIAGE Y DESPACHO ---
def procesar_despacho_resqai(datos):
    """
    Analiza los datos recolectados (ya sean profesionales o ciudadanos)
    y genera el dictamen inteligente de despacho y direccionamiento hospitalario.
    """
    rol = datos.get('rol', '')
    incidente = datos.get('incidente', '').lower()
    
    # Determinar Gravedad (Conversión de lenguaje ciudadano a Triage Internacional)
    if rol == "Ciudadano":
        conciencia = datos.get('conciencia_civil', '')
        sangrado = datos.get('sangrado_civil', '')
        # Si no responde o tiene sangrado masivo, es una prioridad crítica (Rojo)
        es_critico = (conciencia == "No responde / Está inconsciente") or (sangrado == "Sí, es abundante y no para")
    else:
        # Si es profesional, se evalúa según el estado de la vía aérea
        via_aerea = datos.get('triage_pro', '')
        es_critico = "Comprometida" in via_aerea

    # Lógica de asignación de recursos multi-agencia
    despacho = {
        "Ambulancia": "🚨 Soporte Vital Avanzado (Medicalizada - Prioridad 1)" if es_critico else "🚑 Soporte Vital Básico (Prioridad 2)",
        "Bomberos": "🚒 ACTIVADO (Rescate Vehicular/Extricación/Fuego)" if "tránsito" in incidente or "atrapado" in incidente else "NO requerido preliminarmente",
        "Policia": "🚓 ACTIVADO (Seguridad de Escena y Control de Orden Público)",
        "Movilidad/Transito": "🛵 ACTIVADO (Regulación de tráfico y desvíos)" if "tránsito" in incidente else "NO requerido"
    }
    
    # Selección Inteligente del Destino Médico en Cali
    if es_critico:
        # Distribución según tipo de incidente o gravedad extrema
        if "tránsito" in incidente:
            hospital_destino = RED_HOSPITALARIA["ALTA_COMPLEJIDAD_CENTRO"] # Imbanaco
        else:
            hospital_destino = RED_HOSPITALARIA["CRITICO_TRAUMA"] # HUV (Centro de referencia de trauma)
    else:
        # Para casos que requieren atención pero no están en riesgo inminente de muerte inmediato
        hospital_destino = RED_HOSPITALARIA["ALTA_COMPLEJIDAD_SUR"] # Valle del Lili (Evaluación general)

    return despacho, hospital_destino, es_critico

# --- FLUJO DE INTERACCIÓN DEL BOT ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Inicio del sistema. Identifica el tipo de usuario."""
    reply_keyboard = [['Ciudadano (Presencio una emergencia)'], ['Personal de Emergencias (APH / Bomberos)']]
    await update.message.reply_text(
        "🚨 **ResqAI - Sistema de Optimización de Rescate con IA** 🚨\n\n"
        "Bienvenido al asistente de despacho de emergencias.\n"
        "Para guiarlo de forma correcta, por favor indique quién reporta:",
        reply_markup=ReplyKeyboardMarkup(reply_keyboard, one_time_keyboard=True, resize_keyboard=True),
        parse_mode="Markdown"
    )
    return ROL

async def rol_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Guarda el rol y pregunta por el tipo de escenario."""
    seleccion = update.message.text
    context.user_data['rol'] = "Ciudadano" if "Ciudadano" in seleccion else "Profesional"
    
    reply_keyboard = [['Accidente de Tránsito', 'Persona Inconsciente/Enferma'], ['Caída/Trauma Grave', 'Herido (Arma/Pelea)']]
    await update.message.reply_text(
        "📝 **¿Qué tipo de emergencia está ocurriendo?**\n"
        "Seleccione la opción que mejor describa la situación actual:",
        reply_markup=ReplyKeyboardMarkup(reply_keyboard, one_time_keyboard=True, resize_keyboard=True),
        parse_mode="Markdown"
    )
    return INCIDENTE

async def incidente_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Deriva el flujo según el nivel de conocimiento del usuario."""
    context.user_data['incidente'] = update.message.text
    
    if context.user_data['rol'] == "Profesional":
        reply_keyboard = [['Despejada / Normal'], ['Obstruida / Comprometida (Triage Rojo)']]
        await update.message.reply_text(
            "🫁 **Evaluación Profesional de Vía Aérea:**\n"
            "Indique el estado ventilatorio del paciente:",
            reply_markup=ReplyKeyboardMarkup(reply_keyboard, one_time_keyboard=True, resize_keyboard=True),
            parse_mode="Markdown"
        )
        return TRIAGE_PRO
    else:
        # Flujo Ciudadano - Preguntas en lenguaje sumamente sencillo
        reply_keyboard = [['Sí, habla o se mueve'], ['No responde / Está inconsciente'], ['No estoy seguro']]
        await update.message.reply_text(
            "🗣️ **Pregunta de ayuda rápida:**\n"
            "¿La persona herida o enferma te responde, habla o se mueve al llamarla?",
            reply_markup=ReplyKeyboardMarkup(reply_keyboard, one_time_keyboard=True, resize_keyboard=True),
            parse_mode="Markdown"
        )
        return CONCIENCIA_CIVIL

async def triage_pro_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Guarda datos del profesional y salta directo a pedir la ubicación."""
    context.user_data['triage_pro'] = update.message.text
    return await solicitar_ubicacion(update)

async def conciencia_civil_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Guarda el estado de conciencia y pregunta por sangrados (Flujo Ciudadano)."""
    context.user_data['conciencia_civil'] = update.message.text
    
    reply_keyboard = [['Sí, es abundante y no para'], ['No tiene sangre / Es muy poca']]
    await update.message.reply_text(
        "🩸 **Siguiente pregunta visual:**\n"
        "¿La persona tiene alguna herida donde se vea brotar mucha sangre de forma continua?",
        reply_markup=ReplyKeyboardMarkup(reply_keyboard, one_time_keyboard=True, resize_keyboard=True),
        parse_mode="Markdown"
    )
    return SANGRADO_CIVIL

async def sangrado_civil_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Guarda datos de sangrado del ciudadano y solicita ubicación."""
    context.user_data['sangrado_civil'] = update.message.text
    return await solicitar_ubicacion(update)

async def solicitar_ubicacion(update: Update) -> int:
    """Solicitud unificada de geolocalización."""
    await update.message.reply_text(
        "📍 **Último paso: Ubicación del Incidente**\n"
        "Para enviar la ayuda y trazar la ruta por GPS, por favor envíe la **Ubicación en tiempo real** o actual desde el botón de adjuntar (icono de clip 📎 > Ubicación):",
        reply_markup=ReplyKeyboardRemove(),
        parse_mode="Markdown"
    )
    return UBICACION

async def ubicacion_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Procesa todo el algoritmo de ResqAI y emite reportes en paralelo."""
    user_location = update.message.location
    lat = user_location.latitude
    lon = user_location.longitude
    
    # Procesar lógica inteligente con el motor de IA de ResqAI
    despacho, hospital, es_critico = procesar_despacho_resqai(context.user_data)
    
    # Generación de rutas dinámicas de navegación GPS
    url_ruta_escena = f"https://www.google.com/maps/dir/?api=1&destination={lat},{lon}"
    url_ruta_clinica = f"https://www.google.com/maps/search/?api=1&query={hospital['nombre']}".replace(" ", "+")

    # REPORTES AUTOMÁTICOS GENERADOS POR RESQAI
    
    # 1. Reporte para las Unidades de Rescate en Ruta
    reporte_operador = (
        "🚒 **DESPACHO MULTI-AGENCIA ACTIVADO** 🚒\n"
        f"👤 *Reportado por:* {context.user_data['rol']}\n"
        f"🚨 *Suceso:* {context.user_data['incidente']}\n\n"
        "📋 **Asignación de Recursos en Campo:**\n"
        f"• **Ambulancia:** {despacho['Ambulancia']}\n"
        f"• **Bomberos:** {despacho['Bomberos']}\n"
        f"• **Policía:** {despacho['Policia']}\n"
        f"• **Tránsito/Movilidad:** {despacho['Movilidad/Transito']}\n\n"
        f"🗺️ **Ruta de Respuesta Rápida (GPS):**\n"
        f"[Navegar hacia la Escena del Incidente]({url_ruta_escena})\n"
    )
    
    # 2. Reporte Clínico de Pre-alerta Hospitalaria (Módulo institucional para Clínicas)
    reporte_hospital = (
        "🏥 **SISTEMA DE PRE-ALERTA INTRAHOSPITALARIA** 🏥\n"
        f"🔔 **Centro Médico Receptor Alertado:** __{hospital['nombre']}__\n"
        f"📍 **Sector:** Cali ({hospital['zona']}) | **Complejidad Requerida:** Nivel {hospital['nivel']}\n\n"
        "📊 **Ficha del Paciente en camino:**\n"
        f"• **Mecanismo de Lesión:** {context.user_data['incidente']}\n"
        f"• **Estado de Gravedad:** {'🔴 CRÍTICO / Prioridad Alta' if es_critico else '🟡 ESTABLE / Prioridad Media-Baja'}\n"
        f"• **Triage Inicial:** Clasificado automáticamente por algoritmo ResqAI dual.\n"
        "💬 *Recomendación:* Alistar sala de reanimación y/o especialistas de guardia.\n\n"
        f"🗺️ **Logística de Transferencia:**\n"
        f"[Ver Ubicación del Hospital Receptor]({url_ruta_clinica})\n\n"
        "🧠 _ResqAI unificando la respuesta ciudadana con la red de salud pública y privada._"
    )
    
    await update.message.reply_text(reporte_operador, parse_mode="Markdown", disable_web_page_preview=True)
    await update.message.reply_text(reporte_hospital, parse_mode="Markdown", disable_web_page_preview=True)
    
    return ConversationHandler.END

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.message.reply_text("❌ Evaluación cancelada.", reply_markup=ReplyKeyboardRemove())
    return ConversationHandler.END

# Inyección de manejadores al Bot
if telegram_app:
    conv_handler = ConversationHandler(
        entry_points=[CommandHandler('start', start)],
        states={
            ROL: [MessageHandler(filters.TEXT & ~filters.COMMAND, rol_callback)],
            INCIDENTE: [MessageHandler(filters.TEXT & ~filters.COMMAND, incidente_callback)],
            TRIAGE_PRO: [MessageHandler(filters.TEXT & ~filters.COMMAND, triage_pro_callback)],
            CONCIENCIA_CIVIL: [MessageHandler(filters.TEXT & ~filters.COMMAND, conciencia_civil_callback)],
            SANGRADO_CIVIL: [MessageHandler(filters.TEXT & ~filters.COMMAND, sangrado_civil_callback)],
            UBICACION: [MessageHandler(filters.LOCATION, ubicacion_callback)],
        },
        fallbacks=[CommandHandler('cancel', cancel)]
    )
    telegram_app.add_handler(conv_handler)

# --- ENDPOINTS DEL SERVIDOR ---
@app.route('/')
def index():
    return "🚀 ResqAI Core V2: Triage Dual Ciudadano-Profesional y Red Hospitalaria Activa."

@app.route('/webhook', methods=['POST'])
def webhook():
    if telegram_app:
        update = Update.de_json(request.get_json(force=True), telegram_app.bot)
        import asyncio
        loop = asyncio.get_event_loop()
        loop.run_until_complete(telegram_app.process_update(update))
    return 'OK', 200

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)