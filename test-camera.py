import cv2
import easyocr
import re
import requests  # <-- Importante añadir esta librería para conectarse a Django

# 1. Inicializar EasyOCR
print("Cargando modelo de IA para leer texto...")
reader = easyocr.Reader(['en'], gpu=False) 

# RECUERDA: Cambiar esto por la IP exacta de tu DroidCam
url_camara = "http://192.168.0.5:4747/video" 
cap = cv2.VideoCapture(url_camara)

print("Conectando a DroidCam...")

# Variables de control
frame_count = 0
placa_detectada = "Esperando..."
frame_anterior = None

# URL de tu endpoint en Django (Asegúrate de que la ruta coincida con tu urls.py)
URL_DJANGO = "http://127.0.0.1:8000/api/vehiculos/verificar_placa_lpr/"

while True:
    ret, frame = cap.read()
    if not ret:
        print("Se perdió la conexión con DroidCam.")
        break

    alto, ancho, _ = frame.shape

    # Definir coordenadas del cuadro central (Región de Interés - ROI)
    x1, y1 = ancho // 4, alto // 3
    x2, y2 = ancho * 3 // 4, alto * 2 // 3

    # Extraer y convertir solo el fragmento de la placa
    recorte_placa = frame[y1:y2, x1:x2]
    gray_roi = cv2.cvtColor(recorte_placa, cv2.COLOR_BGR2GRAY)

    # Aplicar un desenfoque para evitar que el "ruido" cuente como movimiento
    roi_blur = cv2.GaussianBlur(gray_roi, (21, 21), 0)

    # Inicializar el primer frame si está vacío
    if frame_anterior is None:
        frame_anterior = roi_blur
        continue

    # Calcular diferencia de píxeles entre el frame actual y el anterior
    diferencia = cv2.absdiff(frame_anterior, roi_blur)
    _, umbral = cv2.threshold(diferencia, 25, 255, cv2.THRESH_BINARY)
    
    # Contar cuántos píxeles cambiaron realmente
    movimiento = cv2.countNonZero(umbral)

    # CONDICIÓN DOBLE DE OPTIMIZACIÓN: 1 vez por segundo Y si hay movimiento
    if frame_count % 30 == 0:
        if movimiento > 500:
            # Enviar solo el recorte gris a la Inteligencia Artificial
            resultados = reader.readtext(gray_roi)
            
            for (bbox, texto, prob) in resultados:
                texto_limpio = texto.upper().replace(" ", "").replace("-", "")
                
                # Buscar formato de placa boliviana
                if re.search(r'\d{3,4}[A-Z]{3}', texto_limpio) and prob > 0.4:
                    placa_detectada = texto_limpio
                    print(f"\n✅ ¡PLACA DETECTADA!: {placa_detectada} (Precisión: {prob:.2f})")
                    
                    # =========================================================
                    # AQUÍ SE INCLUYE LA PETICIÓN A DJANGO
                    # =========================================================
                    try:
                        print("Enviando a Django para verificación...")
                        # Hacemos el POST enviando el JSON con la placa
                        respuesta = requests.post(URL_DJANGO, json={"placa": placa_detectada}, timeout=3)
                        
                        if respuesta.status_code == 200:
                            datos = respuesta.json()
                            if datos.get("encontrado"):
                                print("--------------------------------------------------")
                                print(f"👤 CLIENTE: {datos['cliente']['nombre']} (CI/NIT: {datos['cliente']['nit']})")
                                print(f"🚗 VEHÍCULO: {datos['vehiculo']['marca']} {datos['vehiculo']['modelo']}")
                                print("--------------------------------------------------")
                            else:
                                print(f"⚠️ {datos.get('mensaje', 'Vehículo no registrado')}")
                        else:
                            print(f"❌ Error en el servidor Django: HTTP {respuesta.status_code}")
                    
                    except requests.exceptions.RequestException as e:
                        print(f"❌ No se pudo conectar a Django (¿Está encendido el servidor?): {e}")
                    # =========================================================
                    
                    break # Rompe el ciclo for para no seguir analizando otras letras en este mismo frame
    
    # Actualizar el frame_anterior para compararlo en el siguiente ciclo
    frame_anterior = roi_blur 

    # --- INTERFAZ VISUAL ---
    cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 255, 255), 2)
    cv2.putText(frame, "Apunta la placa aqui", (x1, y1 - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 255), 1)
    
    color_texto = (0, 255, 0) if placa_detectada != "Esperando..." else (0, 165, 255)
    cv2.putText(frame, f"LPR: {placa_detectada}", (30, 50), cv2.FONT_HERSHEY_SIMPLEX, 1, color_texto, 3)

    cv2.imshow('Terminal de Pista LPR', frame)

    frame_count += 1

    if cv2.waitKey(1) & 0xFF == ord('q'):
        break

cap.release()
cv2.destroyAllWindows()