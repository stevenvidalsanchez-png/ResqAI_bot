import os
import threading
from flask import Flask
import telebot
from telebot.handler_backends import State, StatesGroup
from telebot.storage import StateMemoryStorage

# ------------------------------------------------------------------
# CONFIGURACIÓN DE FLASK (El truco para engañar a Render)
# ------------------------------------------------------------------
server = Flask(__name__)

@server.route("/")
def webhook_falso():
    return "ResqAI está vivo y operando con normalidad.", 200

# ------------------------------------------------------------------
# CONFIGURACIÓN DEL BOT DE TELEGRAM
# ------------------------------------------------------------------
state_storage = StateMemoryStorage()
TOKEN = os.environ.get('TELEGRAM_TOKEN')
bot = telebot.TeleBot(TOKEN, state_storage=state_storage)

class ResqueState(StatesGroup):
    nombre = State()
    perfil = State()
    tipo_emergencia = State()
    detalle_bomberos = State()
    direccion = State()

# 1. INICIO CON "HOLA"
@bot.message_handler(func=lambda message: message.text.lower() in ['hola', 'buen día', 'buenos días', 'buenas tardes'])
def saludo_inicial(message):
    bot.reply_to(message, "¡Hola! Bienvenido al sistema de asistencia de emergencias ResqAI.\n\nPor favor, dime tu **nombre completo** para iniciar el registro.")
    bot.set_state(message.from_user.id, ResqueState.nombre, message.chat.id)

# 2. CAPTURA DEL NOMBRE Y PREGUNTA DE PERFIL
@bot.message_handler(state=ResqueState.nombre)
def guardar_nombre(message):
    nombre_usuario = message.text
    with bot.retrieve_data(message.from_user.id, message.chat.id) as data:
        data['nombre'] = nombre_usuario
    
    markup = telebot.types.ReplyKeyboardMarkup(row_width=2, resize_keyboard=True)
    markup.add('Persona del Común', 'Personal de Salud / Rescate')
    
    bot.send_message(
        message.chat.id, 
        f"Entendido, {nombre_usuario}. Para adecuar las instrucciones de ayuda, por favor indícame tu perfil:",
        reply_markup=markup
    )
    bot.set_state(message.from_user.id, ResqueState.perfil, message.chat.id)

# 3. TRIAGE E IDENTIFICACIÓN DEL TIPO DE EMERGENCIA
@bot.message_handler(state=ResqueState.perfil)
def guardar_perfil(message):
    perfil = message.text
    with bot.retrieve_data(message.from_user.id, message.chat.id) as data:
        data['perfil'] = perfil
    
    markup = telebot.types.ReplyKeyboardMarkup(row_width=2, resize_keyboard=True)
    markup.add('Urgencia Médica (Salud)', 'Incidente / Bomberos', 'Seguridad (Policía)')
    
    bot.send_message(message.chat.id, "¿Cuál es el tipo de emergencia principal que estás reportando?", reply_markup=markup)
    bot.set_state(message.from_user.id, ResqueState.tipo_emergencia, message.chat.id)

# 4. DETALLE SI ES BOMBEROS
@bot.message_handler(state=ResqueState.tipo_emergencia)
def clasificar_emergencia(message):
    tipo = message.text
    with bot.retrieve_data(message.from_user.id, message.chat.id) as data:
        data['tipo_emergencia'] = tipo

    if tipo == 'Incidente / Bomberos':
        markup = telebot.types.ReplyKeyboardMarkup(row_width=2, resize_keyboard=True)
        markup.add(
            'Incendio Estructural', 'Incendio Forestal', 
            'Fuga de Gas (Casa/Comercio)', 'Animales (Mascotas/Otros)',
            'Abejas / Avispas', 'Atrapados en Vehículo', 
            'Incendio de Vehículo', 'Fuga de Químicos'
        )
        bot.send_message(message.chat.id, "Selecciona la situación específica:", reply_markup=markup)
        bot.set_state(message.from_user.id, ResqueState.detalle_bomberos, message.chat.id)
    else:
        forzar_solicitud_direccion(message)

@bot.message_handler(state=ResqueState.detalle_bomberos)
def guardar_detalle_bomberos(message):
    with bot.retrieve_data(message.from_user.id, message.chat.id) as data:
        data['detalle_bomberos'] = message.text
    forzar_solicitud_direccion(message)

# 5. CAPTURA DE DIRECCIÓN
def forzar_solicitud_direccion(message):
    markup = telebot.types.ReplyKeyboardRemove()
    bot.send_message(
        message.chat.id, 
        "Por favor, escribe la **dirección exacta** del evento (ej: Calle 25 # 98-50) o un punto de referencia claro.",
        reply_markup=markup
    )
    bot.set_state(message.from_user.id, ResqueState.direccion, message.chat.id)

# 6, 7 y 8. LÓGICA DE DESPACHO, ASIGNACIÓN DE VEHÍCULOS Y CENTROS MÉDICOS
@bot.message_handler(state=ResqueState.direccion)
def finalizar_reporte(message):
    direccion = message.text
    chat_id = message.chat.id
    
    with bot.retrieve_data(message.from_user.id, chat_id) as data:
        nombre = data.get('nombre')
        perfil = data.get('perfil')
        tipo = data.get('tipo_emergencia')
        detalle = data.get('detalle_bomberos', 'N/A')
    
    instrucciones_triage = ""
    vehiculos_despachados = ""
    hospital_destino = ""

    if tipo == 'Urgencia Médica (Salud)':
        if perfil == 'Personal de Salud / Rescate':
            instrucciones_triage = "🚨 **Triage sugerido: Rojo (Prioridad I).** Inicie RCP si no hay pulso, controle sangrados masivos con torniquete."
            vehiculos_despachados = "🚑 **Despachado:** Ambulancia Medicalizada (TAM) + Apoyo de Tránsito."
            hospital_destino = "🏥 **Remisión sugerida:** Hospital Universitario del Valle (HUV) o Clínica Imbanaco."
        else:
            instrucciones_triage = "⚠️ **Instrucciones:** Mantenga la calma. Si sangra, haga presión fuerte sobre la herida con un paño limpio."
            vehiculos_despachados = "🚑 **Despachado:** Ambulancia Básica (TAB) de la red de salud pública."
            hospital_destino = "🏥 **Remisión sugerida:** Hospital Mario Correa Rengifo o la IPS/Puesto de salud de la Red del Oriente según cercanía."

    elif tipo == 'Incidente / Bomberos':
        vehiculos_despachados = "🚒 **Despachado:** Máquina de Bomberos Cali (Estación más cercana) "
        if detalle in ['Incendio Estructural', 'Atrapados en Vehículo']:
            vehiculos_despachados += "+ Ambulancia de Bomberos + Policía Metropolitana."
            hospital_destino = "🏥 **Alerta Preventiva:** Hospital Primitivo Iglesias o Clínica Rey David."
        elif detalle == 'Fuga de Químicos':
            vehiculos_despachados += "+ Unidad de Materiales Peligrosos (HAZMAT)."
            hospital_destino = "🏥 **Alerta Preventiva:** HUV (Unidad de Toxicología)."
        else:
            vehiculos_despachados += "+ Vehículo de Logística."
            hospital_destino = "🏥 **Alerta Preventiva:** Centros de salud de la Red ESE respectiva."
        
        instrucciones_triage = f"🔥 **Protocolo para {detalle}:** Evacúe el área, no inhale humo/gases."

    respuesta_final = (
        f"✅ **REPORTE REGISTRADO EXITOSAMENTE**\n"
        f"--- \n"
        f"👤 **Reporta:** {nombre} ({perfil})\n"
        f"📍 **Ubicación:** {direccion}\n"
        f"⚠️ **Incidente:** {tipo} -> {detalle if tipo == 'Incidente / Bomberos' else 'N/A'}\n"
        f"--- \n"
        f"{instrucciones_triage}\n\n"
        f"{vehiculos_despachados}\n\n"
        f"{hospital_destino}\n"
        f"--- \n"
        f"📞 *Las unidades van en camino. Mantén esta línea despejada.*"
    )
    
    bot.send_message(chat_id, respuesta_final, parse_mode="Markdown")
    bot.delete_state(message.from_user.id, chat_id)

# ------------------------------------------------------------------
# CONTROL DE ARRANQUE SEGURO (El arreglo de los hilos para Gunicorn)
# ------------------------------------------------------------------
def iniciar_bot_en_segundo_plano():
    print("🚀 Iniciando el bot de Telegram de ResqAI...")
    bot.infinity_polling(skip_pending=True)

# Levantar el hilo del bot inmediatamente al cargar el script
bot_thread = threading.Thread(target=iniciar_bot_en_segundo_plano)
bot_thread.daemon = True
bot_thread.start()

# Bloque requerido para ejecución local o fallback directa
if __name__ == '__main__':
    port = int(os.environ.get("PORT", 10000))
    server.run(host="0.0.0.0", port=port)
