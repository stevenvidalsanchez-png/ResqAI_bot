import os
import logging
import requests
from flask import Flask, request

# Configuración de Logging para ver eventos en Render
logging.basicConfig(format='%(asctime)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)

# Recuperar el Token de las variables de entorno de Render
TOKEN = os.getenv("TELEGRAM_TOKEN")
TELEGRAM_API_URL = f"https://api.telegram.org/bot{TOKEN}/sendMessage"

# Diccionario temporal para simular el estado de la conversación por usuario
# Nota: En producción avanzada usarías una base de datos, para el proyecto final esto es perfecto.
ESTADOS_USUARIO = {}

RED_HOSPITALARIA = {
    "CRITICO_TRAUMA": {"nombre": "Hospital Universitario del Valle (HUV)", "zona": "Centro/Sur", "especialidad": "Trauma Mayor"},
    "ALTA_COMPLEJIDAD_SUR": {"nombre": "Fundación Valle del Lili", "zona": "Sur", "especialidad": "Cuidado Crítico"},
    "ALTA_COMPLEJIDAD_CENTRO": {"nombre": "Clínica Imbanaco", "zona": "Centro", "especialidad": "Trauma / Urgencias"}
}

def enviar_mensaje_telegram(chat_id, texto, botones=None):
    """Función nativa usando solicitudes HTTP POST para enviar mensajes y teclados."""
    payload = {
        "chat_id": chat_id,
        "text": texto,
        "parse_mode": "Markdown"
    }
    if botones:
        payload["reply_markup"] = {
            "keyboard": botones,
            "one_time_keyboard": True,
            "resize_keyboard": True
        }
    else:
        payload["reply_markup"] = {"remove_keyboard": True}
        
    try:
        requests.post(TELEGRAM_API_URL, json=payload)
    except Exception as e:
        logger.error(f"Error enviando mensaje: {e}")

# --- ENLACE DEL SERVIDOR ---
@app.route('/')
def index():
    return "🚀 ResqAI Core V2 está en línea y optimizando despacho."

@app.route('/webhook', methods=['POST'])
def webhook():
    """Recibe los datos directamente desde los servidores de Telegram."""
    data = request.get_json(force=True)
    
    if "message" not in data:
        return "OK", 200
        
    message = data["message"]
    chat_id = message["chat"]["id"]
    text = message.get("text", "")
    
    # Manejo del comando inicial
    if text == "/start":
        ESTADOS_USUARIO[chat_id] = {"paso": "ROL"}
        botones = [["Ciudadano (Presencio una emergencia)"], ["Personal de Emergencias (APH)"]]
        enviar_mensaje_telegram(
            chat_id, 
            "🚨 **ResqAI - Sistema de Optimización de Rescate con IA** 🚨\n\nBienvenido al asistente de despacho. Por favor, indique quién reporta:", 
            botones
        )
        return "OK", 200

    # Si el usuario no ha iniciado el protocolo
    if chat_id not in ESTADOS_USUARIO:
        enviar_mensaje_telegram(chat_id, "Escribe /start para iniciar el sistema de triage ResqAI.")
        return "OK", 200

    estado = ESTADOS_USUARIO[chat_id]

    # FLUJO - PASO: ROL
    if estado["paso"] == "ROL":
        estado["rol"] = "Ciudadano" if "Ciudadano" in text else "Profesional"
        estado["paso"] = "INCIDENTE"
        botones = [["Accidente de Tránsito"], ["Persona Inconsciente/Enferma"], ["Herido (Arma/Pelea)"]]
        enviar_mensaje_telegram(chat_id, "📝 **¿Qué tipo de emergencia está ocurriendo?**", botones)

    # FLUJO - PASO: INCIDENTE
    elif estado["paso"] == "INCIDENTE":
        estado["incidente"] = text
        if estado["rol"] == "Profesional":
            estado["paso"] = "TRIAGE_PRO"
            botones = [["Despejada / Normal"], ["Obstruida / Comprometida"]]
            enviar_mensaje_telegram(chat_id, "🫁 **Evaluación de Vía Aérea:**", botones)
        else:
            estado["paso"] = "CONCIENCIA_CIVIL"
            botones = [["Sí, habla o se mueve"], ["No responde / Está inconsciente"]]
            enviar_mensaje_telegram(chat_id, "🗣️ **¿La persona herida te responde, habla o se mueve al llamarla?**", botones)

    # FLUJO - PASO: TRIAGE PROFESIONAL
    elif estado["paso"] == "TRIAGE_PRO":
        estado["es_critico"] = "Comprometida" in text
        estado["paso"] = "FINAL"
        solicitar_finalizacion(chat_id, estado)

    # FLUJO - PASO: CONCIENCIA CIUDADANO
    elif estado["paso"] == "CONCIENCIA_CIVIL":
        estado["conciencia"] = text
        estado["paso"] = "SANGRADO_CIVIL"
        botones = [["Sí, es abundante"], ["No tiene sangre / Es muy poca"]]
        enviar_mensaje_telegram(chat_id, "🩸 **¿La persona tiene alguna herida donde brote mucha sangre?**", botones)

    # FLUJO - PASO: SANGRADO CIUDADANO
    elif estado["paso"] == "SANGRADO_CIVIL":
        estado["es_critico"] = ("No responde" in estado["conciencia"]) or ("abundante" in text)
        estado["paso"] = "FINAL"
        solicitar_finalizacion(chat_id, estado)

    return "OK", 200

def solicitar_finalizacion(chat_id, estado):
    """Procesa el reporte final y despacha las agencias virtuales."""
    incidente = estado.get("incidente", "Emergencia")
    es_critico = estado.get("es_critico", False)
    
    # Lógica de asignación de recursos
    ambulancia = "🚨 Soporte Vital Avanzado" if es_critico else "🚑 Soporte Vital Básico"
    bomberos = "🚒 ACTIVADO (Rescate Vehicular)" if "Tránsito" in incidente else "NO requerido"
    
    # Asignación de Hospital
    if es_critico:
        hospital = RED_HOSPITALARIA["CRITICO_TRAUMA"] if "Tránsito" not in incidente else RED_HOSPITALARIA["ALTA_COMPLEJIDAD_CENTRO"]
    else:
        hospital = RED_HOSPITALARIA["ALTA_COMPLEJIDAD_SUR"]

    reporte = (
        "🚒 **DESPACHO MULTI-AGENCIA ACTIVADO** 🚒\n\n"
        f"👤 *Reportado por:* {estado['rol']}\n"
        f"🚨 *Suceso:* {incidente}\n\n"
        "📋 **Asignación de Recursos:**\n"
        f"• **Ambulancia:** {ambulancia}\n"
        f"• **Bomberos:** {bomberos}\n"
        f"• **Policía:** 🚓 ACTIVADO\n\n"
        " Hospital Receptor Pre-alertado:\n"
        f"• **Centro:** {hospital['nombre']}\n"
        f"• **Complejidad:** {hospital['especialidad']} ({hospital['zona']})\n\n"
        "🧠 _ResqAI: Triage dinámico procesado correctamente._"
    )
    
    enviar_mensaje_telegram(chat_id, reporte)
    # Limpiar estado del usuario al terminar
    ESTADOS_USUARIO.pop(chat_id, None)

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
