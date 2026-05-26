import os
import logging
import asyncio
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

# Inicialización segura de la aplicación de Telegram
telegram_app = None
if TOKEN:
    telegram_app = Application.builder().token(TOKEN).build()
    
    # Configuración de la lógica interna del bot
    RED_HOSPITALARIA = {
        "CRITICO_TRAUMA": {"nombre": "Hospital Universitario del Valle (HUV)", "nivel": 3, "zona": "Centro/Sur", "especialidad": "Trauma Mayor / Alta Complejidad"},
        "ALTA_COMPLEJIDAD_SUR": {"nombre": "Fundación Valle del Lili", "nivel": 3, "zona": "Sur", "especialidad": "Cuidado Crítico / Trauma / Politrauma"},
        "ALTA_COMPLEJIDAD_CENTRO": {"nombre": "Clínica Imbanaco", "nivel": 3, "zona": "Sur/Centro", "especialidad": "Trauma / Cirugía de Urgencias"}
    }

    def procesar_despacho_resqai(datos):
        rol = datos.get('rol', '')
        incidente = datos.get('incidente', '').lower()
        if rol == "Ciudadano":
            conciencia = datos.get('conciencia_civil', '')
            sangrado = datos.get('sangrado_civil', '')
            es_critico = (conciencia == "No responde / Está inconsciente") or (sangrado == "Sí, es abundante y no para")
        else:
            via_aerea = datos.get('triage_pro', '')
            es_critico = "Comprometida" in via_aerea

        despacho = {
            "Ambulancia": "🚨 Soporte Vital Avanzado (Medicalizada)" if es_critico else "🚑 Soporte Vital Básico",
            "Bomberos": "🚒 ACTIVADO (Rescate Vehicular)" if "tránsito" in incidente or "atrapado" in incidente else "NO requerido",
            "Policia": "🚓 ACTIVADO (Seguridad de Escena)",
            "Movilidad/Transito": "🛵 ACTIVADO (Regulación de tráfico)" if "tránsito" in incidente else "NO requerido"
        }
        hospital_destino = RED_HOSPITALARIA["CRITICO_TRAUMA"] if es_critico else RED_HOSPITALARIA["ALTA_COMPLEJIDAD_SUR"]
        return despacho, hospital_destino, es_critico

    async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
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
        context.user_data['rol'] = "Ciudadano" if "Ciudadano" in update.message.text else "Profesional"
        reply_keyboard = [['Accidente de Tránsito', 'Persona Inconsciente/Enferma'], ['Caída/Trauma Grave', 'Herido (Arma/Pelea)']]
        await update.message.reply_text("📝 **¿Qué tipo de emergencia está ocurriendo?**", reply_markup=ReplyKeyboardMarkup(reply_keyboard, one_time_keyboard=True, resize_keyboard=True), parse_mode="Markdown")
        return INCIDENTE

    async def incidente_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        context.user_data['incidente'] = update.message.text
        if context.user_data['rol'] == "Profesional":
            reply_keyboard = [['Despejada / Normal'], ['Obstruida / Comprometida (Triage Rojo)']]
            await update.message.reply_text("🫁 **Evaluación Profesional de Vía Aérea:**", reply_markup=ReplyKeyboardMarkup(reply_keyboard, one_time_keyboard=True, resize_keyboard=True), parse_mode="Markdown")
            return TRIAGE_PRO
        else:
            reply_keyboard = [['Sí, habla o se mueve'], ['No responde / Está inconsciente'], ['No estoy seguro']]
            await update.message.reply_text("🗣️ **¿La persona herida o enferma te responde, habla o se mueve al llamarla?**", reply_markup=ReplyKeyboardMarkup(reply_keyboard, one_time_keyboard=True, resize_keyboard=True), parse_mode="Markdown")
            return CONCIENCIA_CIVIL

    async def triage_pro_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        context.user_data['triage_pro'] = update.message.text
        return await solicitar_ubicacion(update)

    async def conciencia_civil_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        context.user_data['conciencia_civil'] = update.message.text
        reply_keyboard = [['Sí, es abundante y no para'], ['No tiene sangre / Es muy poca']]
        await update.message.reply_text("🩸 **¿La persona tiene alguna herida donde se vea brotar mucha sangre?**", reply_markup=ReplyKeyboardMarkup(reply_keyboard, one_time_keyboard=True, resize_keyboard=True), parse_mode="Markdown")
        return SANGRADO_CIVIL

    async def sangrado_civil_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        context.user_data['sangrado_civil'] = update.message.text
        return await solicitar_ubicacion(update)

    async def solicitar_ubicacion(update: Update) -> int:
        await update.message.reply_text("📍 **Por favor, envíe la Ubicación actual desde el icono de clip 📎 > Ubicación:**", reply_markup=ReplyKeyboardRemove(), parse_mode="Markdown")
        return UBICACION

    async def ubicacion_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        user_location = update.message.location
        lat, lon = user_location.latitude, user_location.longitude
        despacho, hospital, es_critico = procesar_despacho_resqai(context.user_data)
        url_ruta_escena = f"https://www.google.com/maps?q={lat},{lon}"
        url_ruta_clinica = f"https://www.google.com/maps?q={hospital['nombre']}".replace(" ", "+")

        reporte_operador = (
            "🚒 **DESPACHO MULTI-AGENCIA ACTIVADO** 🚒\n"
            f"👤 *Reportado por:* {context.user_data['rol']}\n"
            f"🚨 *Suceso:* {context.user_data['incidente']}\n\n"
            "📋 **Asignación de Recursos en Campo:**\n"
            f"• **Ambulancia:** {despacho['Ambulancia']}\n"
            f"• **Bomberos:** {despacho['Bomberos']}\n"
            f"• **Policía:** {despacho['Policia']}\n"
            f"• **Tránsito:** {despacho['Movilidad/Transito']}\n\n"
            f"🗺️ [Navegar hacia la Escena]({url_ruta_escena})\n"
        )
        reporte_hospital = (
            "🏥 **PRE-ALERTA HOSPITALARIA** 🏥\n"
            f"🔔 **Centro:** {hospital['nombre']}\n"
            f"📊 **Estado:** {'🔴 CRÍTICO' if es_critico else '🟡 ESTABLE'}\n\n"
            f"🗺️ [Ver Ubicación de la Clínica]({url_ruta_clinica})\n"
        )
        await update.message.reply_text(reporte_operador, parse_mode="Markdown", disable_web_page_preview=True)
        await update.message.reply_text(reporte_hospital, parse_mode="Markdown", disable_web_page_preview=True)
        return ConversationHandler.END

    async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        await update.message.reply_text("❌ Evaluación cancelada.", reply_markup=ReplyKeyboardRemove())
        return ConversationHandler.END

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
    return "🚀 ResqAI Core V2 Activo."

@app.route('/webhook', methods=['POST'])
def webhook():
    if telegram_app:
        update = Update.de_json(request.get_json(force=True), telegram_app.bot)
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(telegram_app.process_update(update))
        loop.close()
    return 'OK', 200

# Removido el bloque local para evitar conflictos de hilos con Gunicorn en Render

