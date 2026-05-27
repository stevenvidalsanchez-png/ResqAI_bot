import os
import telebot
from telebot.handler_backends import State, StatesGroup
from telebot.storage import StateMemoryStorage

# Configuración de estados
state_storage = StateMemoryStorage()
TOKEN = os.environ.get('TELEGRAM_TOKEN')
bot = telebot.TeleBot(TOKEN, state_storage=state_storage)

class ResqueState(StatesGroup):
    nombre = State()
    perfil = State()
    tipo_emergencia = State()
    detalle_bomberos = State()
    direccion = State()

# ------------------------------------------------------------------
# 1. INICIO CON "HOLA" (Reemplaza el /start tradicional)
# ------------------------------------------------------------------
@bot.message_handler(func=lambda message: message.text.lower() in ['hola', 'buen día', 'buenos días', 'buenas tardes'])
def saludo_inicial(message):
    bot.reply_to(message, "¡Hola! Bienvenido al sistema de asistencia de emergencias ResqAI.\n\nPor favor, dime tu **nombre completo** para iniciar el registro.")
    bot.set_state(message.from_user.id, ResqueState.nombre, message.chat.id)

# ------------------------------------------------------------------
# 2. CAPTURA DEL NOMBRE Y PREGUNTA DE PERFIL
# ------------------------------------------------------------------
@bot.message_handler(state=ResqueState.nombre)
def guardar_nombre(message):
    nombre_usuario = message.text
    with bot.retrieve_data(message.from_user.id, message.chat.id) as data:
        data['nombre'] = nombre_usuario
    
    # Crear botones para el perfil (Punto 3: Conocimiento técnico o común)
    markup = telebot.types.ReplyKeyboardMarkup(row_width=2, resize_keyboard=True)
    markup.add('Persona del Común', 'Personal de Salud / Rescate')
    
    bot.send_message(
        message.chat.id, 
        f"Entendido, {nombre_usuario}. Para adecuar las instrucciones de ayuda, por favor indícame tu perfil:",
        reply_markup=markup
    )
    bot.set_state(message.from_user.id, ResqueState.perfil, message.chat.id)

# ------------------------------------------------------------------
# 3. TRIAGE E IDENTIFICACIÓN DEL TIPO DE EMERGENCIA
# ------------------------------------------------------------------
@bot.message_handler(state=ResqueState.perfil)
def guardar_perfil(message):
    perfil = message.text
    with bot.retrieve_data(message.from_user.id, message.chat.id) as data:
        data['perfil'] = perfil
    
    markup = telebot.types.ReplyKeyboardMarkup(row_width=2, resize_keyboard=True)
    markup.add('Urgencia Médica (Salud)', 'Incidente / Bomberos', 'Seguridad (Policía)')
    
    bot.send_message(
        message.chat.id,
        "¿Cuál es el tipo de emergencia principal que estás reportando?",
        reply_markup=markup
    )
    bot.set_state(message.from_user.id, ResqueState.tipo_emergencia, message.chat.id)

# ------------------------------------------------------------------
# 4. DETALLE SI ES BOMBEROS (Punto 4 del requerimiento)
# ------------------------------------------------------------------
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
        # Si es salud o policía, salta directo a la dirección
        forzar_solicitud_direccion(message)

@bot.message_handler(state=ResqueState.detalle_bomberos)
def guardar_detalle_bomberos(message):
    with bot.retrieve_data(message.from_user.id, message.chat.id) as data:
        data['detalle_bomberos'] = message.text
    forzar_solicitud_direccion(message)

# ------------------------------------------------------------------
# 5. CAPTURA DE DIRECCIÓN (Punto 5)
# ------------------------------------------------------------------
def forzar_solicitud_direccion(message):
    # Quitamos los teclados de botones para que escriban la dirección
    markup = telebot.types.ReplyKeyboardRemove()
    bot.send_message(
        message.chat.id, 
        "Por favor, escribe la **dirección exacta** del evento (ej: Calle 25 # 98-50) o un punto de referencia claro.",
        reply_markup=markup
    )
    bot.set_state(message.from_user.id, ResqueState.direccion, message.chat.id)

# ------------------------------------------------------------------
# 6, 7 y 8. LÓGICA DE DESPACHO, ASIGNACIÓN DE VEHÍCULOS Y CENTROS MÉDICOS
# ------------------------------------------------------------------
@bot.message_handler(state=ResqueState.direccion)
def finalizar_reporte(message):
    direccion = message.text
    chat_id = message.chat.id
    
    with bot.retrieve_data(message.from_user.id, chat_id) as data:
        nombre = data.get('nombre')
        perfil = data.get('perfil')
        tipo = data.get('tipo_emergencia')
        detalle = data.get('detalle_bomberos', 'N/A')
    
    # --- Lógica de Triage e Instrucciones según el perfil ---
    instrucciones_triage = ""
    vehiculos_despachados = ""
    hospital_destino = ""

    if tipo == 'Urgencia Médica (Salud)':
        if perfil == 'Personal de Salud / Rescate':
            instrucciones_triage = "🚨 **Triage sugerido: Rojo (Prioridad I).** Inicie RCP de alta calidad si no hay pulso, o controle sangrados masivos con torniquete. Asegure vía aérea."
            vehiculos_despachados = "🚑 **Despachado:** Ambulancia Medicalizada (TAM) con Médico y Paramédico + Apoyo de Tránsito."
            hospital_destino = "🏥 **Remisión sugerida:** Hospital Universitario del Valle (HUV) o Clínica Imbanaco (Alta complejidad)."
        else:
            instrucciones_triage = "⚠️ **Instrucciones de Primeros Auxilios:** Mantenga la calma. No mueva al paciente a menos que haya peligro inminente. Si sangra, haga presión fuerte sobre la herida con un paño limpio."
            vehiculos_despachados = "🚑 **Despachado:** Ambulancia Básica (TAB) de la red de salud pública / paramédicos locales."
            hospital_destino = "🏥 **Remisión sugerida:** Hospital Mario Correa Rengifo (Zonas de ladera/sur) o la IPS/Puesto de salud de la Red del Oriente según cercanía."

    elif tipo == 'Incidente / Bomberos':
        vehiculos_despachados = "🚒 **Despachado:** Máquina de Bomberos Cali (Estación más cercana) "
        if detalle in ['Incendio Estructural', 'Atrapados en Vehículo']:
            vehiculos_despachados += "+ Ambulancia de Bomberos + Policía Metropolitana."
            hospital_destino = "🏥 **Alerta Preventiva:** Hospital Primitivo Iglesias o Clínica Rey David."
        elif detalle == 'Fuga de Químicos':
            vehiculos_despachados += "+ Unidad de Materiales Peligrosos (HAZMAT)."
            hospital_destino = "🏥 **Alerta Preventiva:** HUV (Unidad de Toxicología)."
        else:
            vehiculos_despachados += "+ Vehículo de Logística / Rescate Animal si aplica."
            hospital_destino = "🏥 **Alerta Preventiva:** Centros de salud de la Red ESE respectiva."
        
        instrucciones_triage = f"🔥 **Protocolo para {detalle}:** Evacúe el área, no inhale humo/gases. Espere en un punto seguro fuera de la estructura."

    # --- RESPUESTA FINAL AL USUARIO ---
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
    bot.delete_state(message.from_user.id, chat_id) # Limpia el estado para un nuevo reporte

# Iniciar el bot
if __name__ == '__main__':
    bot.infinity_polling()
