import os
import threading
from flask import Flask
import telebot

# ------------------------------------------------------------------
# CONFIGURACIÓN DE FLASK
# ------------------------------------------------------------------
server = Flask(__name__)

@server.route("/")
def webhook_falso():
    return "ResqAI está vivo y operando con normalidad de forma concurrente.", 200

# ------------------------------------------------------------------
# CONFIGURACIÓN DEL BOT DE TELEGRAM CON CANDADO DE SEGURIDAD
# ------------------------------------------------------------------
TOKEN = os.environ.get('TELEGRAM_TOKEN')
bot = telebot.TeleBot(TOKEN)

# Diccionario global y CANDADO para proteger la memoria concurrente
datos_usuario = {}
lock_memoria = threading.Lock()

# 1. INICIO CON "HOLA"
@bot.message_handler(func=lambda message: message.text.lower() in ['hola', 'buen día', 'buenos días', 'buenas tardes'])
def saludo_inicial(message):
    chat_id = message.chat.id
    
    # Bloqueamos un milisegundo la memoria para registrar al nuevo usuario de forma segura
    with lock_memoria:
        datos_usuario[chat_id] = {}
    
    bot.send_message(chat_id, "¡Hola! Bienvenido al sistema de asistencia de emergencias ResqAI.\n\nPor favor, dime tu **nombre completo** para iniciar el registro.")
    bot.register_next_step_handler(message, guardar_nombre)

# 2. CAPTURA DEL NOMBRE Y PREGUNTA DE PERFIL
def guardar_nombre(message):
    chat_id = message.chat.id
    nombre_usuario = message.text
    
    if nombre_usuario.lower() in ['hola', 'buen día', 'buenos días', 'buenas tardes']:
        saludo_inicial(message)
        return

    with lock_memoria:
        if chat_id not in datos_usuario: datos_usuario[chat_id] = {}
        datos_usuario[chat_id]['nombre'] = nombre_usuario
    
    markup = telebot.types.ReplyKeyboardMarkup(row_width=2, resize_keyboard=True)
    markup.add('Persona del Común', 'Personal de Salud / Rescate')
    
    bot.send_message(
        chat_id, 
        f"Entendido, {nombre_usuario}. Para adecuar las instrucciones de ayuda, por favor indícame tu perfil:",
        reply_markup=markup
    )
    bot.register_next_step_handler(message, guardar_perfil)

# 3. TRIAGE E IDENTIFICACIÓN DEL TIPO DE EMERGENCIA
def guardar_perfil(message):
    chat_id = message.chat.id
    perfil = message.text
    
    with lock_memoria:
        if chat_id not in datos_usuario: datos_usuario[chat_id] = {}
        datos_usuario[chat_id]['perfil'] = perfil
    
    markup = telebot.types.ReplyKeyboardMarkup(row_width=2, resize_keyboard=True)
    markup.add('Urgencia Médica (Salud)', 'Incidente / Bomberos', 'Seguridad (Policía)')
    
    bot.send_message(chat_id, "¿Cuál es el tipo de emergencia principal que estás reportando?", reply_markup=markup)
    bot.register_next_step_handler(message, clasificar_emergencia)

# 4. DETALLE SI ES BOMBEROS
def clasificar_emergencia(message):
    chat_id = message.chat.id
    tipo = message.text
    
    with lock_memoria:
        if chat_id not in datos_usuario: datos_usuario[chat_id] = {}
        datos_usuario[chat_id]['tipo_emergencia'] = tipo

    if tipo == 'Incidente / Bomberos':
        markup = telebot.types.ReplyKeyboardMarkup(row_width=2, resize_keyboard=True)
        markup.add(
            'Incendio Estructural', 'Incendio Forestal', 
            'Fuga de Gas (Casa/Comercio)', 'Animales (Mascotas/Otros)',
            'Abejas / Avispas', 'Atrapados en Vehículo', 
            'Incendio de Vehículo', 'Fuga de Químicos'
        )
        bot.send_message(chat_id, "Selecciona la situación específica:", reply_markup=markup)
        bot.register_next_step_handler(message, guardar_detalle_bomberos)
    else:
        with lock_memoria:
            datos_usuario[chat_id]['detalle_bomberos'] = 'N/A'
        forzar_solicitud_direccion(message)

def guardar_detalle_bomberos(message):
    chat_id = message.chat.id
    with lock_memoria:
        if chat_id not in datos_usuario: datos_usuario[chat_id] = {}
        datos_usuario[chat_id]['detalle_bomberos'] = message.text
    forzar_solicitud_direccion(message)

# 5. CAPTURA DE DIRECCIÓN
def forzar_solicitud_direccion(message):
    chat_id = message.chat.id
    markup = telebot.types.ReplyKeyboardRemove()
    bot.send_message(
        chat_id, 
        "Por favor, escribe la **dirección exacta** del evento (ej: Calle 25 # 98-50) o un punto de referencia claro.",
        reply_markup=markup
    )
    bot.register_next_step_handler(message, finalizar_reporte)

# 6. LÓGICA DE DESPACHO Y CIERRE
def finalizar_reporte(message):
    chat_id = message.chat.id
    direccion = message.text
    
    # Lectura segura con Candado
    with lock_memoria:
        if chat_id not in datos_usuario:
            bot.send_message(chat_id, "Hubo un error de sesión por alta demanda. Por favor escribe 'Hola' de nuevo.")
            return
        nombre = datos_usuario[chat_id].get('nombre', 'Reportante Anónimo')
        perfil = datos_usuario[chat_id].get('perfil', 'Persona del Común')
        tipo = datos_usuario[chat_id].get('tipo_emergencia', 'No especificado')
        detalle = datos_usuario[chat_id].get('detalle_bomberos', 'N/A')
    
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
    else:
        instrucciones_triage = "🚔 **Seguridad:** Patrulla del cuadrante informada. Alértelos visualmente al llegar."
        vehiculos_despachados = "🚓 **Despachado:** Unidad Móvil de la Policía Metropolitana de Cali."
        hospital_destino = "🏥 **Alerta Preventiva:** Red de salud local de cuadrante."

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
    
    # Limpieza segura de memoria
    with lock_memoria:
        datos_usuario.pop(chat_id, None)

# ------------------------------------------------------------------
# CONTROL DE ARRANQUE SEGURO
# ------------------------------------------------------------------
def iniciar_bot_en_segundo_plano():
    print("🚀 ResqAI con Threading Lock activo. Listo para múltiples usuarios en simultáneo.")
    bot.infinity_polling(skip_pending=True)

bot_thread = threading.Thread(target=iniciar_bot_en_segundo_plano)
bot_thread.daemon = True
bot_thread.start()

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 10000))
    server.run(host="0.0.0.0", port=port)
