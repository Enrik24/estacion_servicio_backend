import cv2
import requests

# URL de tu nuevo endpoint en Django (Asegúrate de que la ruta coincida)
URL_DJANGO = "http://127.0.0.1:8000/api/vehiculos/procesar_imagen_lpr/"

# RECUERDA: Cambiar esto por la IP exacta de tu DroidCam
url_camara = "http://192.168.0.7:4747/video" 
cap = cv2.VideoCapture(url_camara)

print("Conectando a DroidCam y preparando sistema ligero...")

# Variables de control
frame_count = 0
placa_en_pantalla = "Esperando..."
frame_anterior = None

while True:
    ret, frame = cap.read()
    if not ret:
        print("Se perdió la conexión con DroidCam.")
        break

    alto, ancho, _ = frame.shape

    # 1. Definir coordenadas del cuadro central (Región de Interés - ROI)
    x1, y1 = ancho // 4, alto // 3
    x2, y2 = ancho * 3 // 4, alto * 2 // 3

    # Extraer el fragmento de la placa (a color, porque a PlateRecognizer le sirve el color)
    recorte_placa = frame[y1:y2, x1:x2]
    
    # Convertir a escala de grises SOLO para calcular el movimiento localmente
    gray_roi = cv2.cvtColor(recorte_placa, cv2.COLOR_BGR2GRAY)
    roi_blur = cv2.GaussianBlur(gray_roi, (21, 21), 0)

    if frame_anterior is None:
        frame_anterior = roi_blur
        continue

    # 2. Calcular diferencia de píxeles (Detección de Movimiento)
    diferencia = cv2.absdiff(frame_anterior, roi_blur)
    _, umbral = cv2.threshold(diferencia, 25, 255, cv2.THRESH_BINARY)
    movimiento = cv2.countNonZero(umbral)

    # 3. CONDICIÓN: 1 vez por segundo Y si hay movimiento
    if frame_count % 30 == 0:
        if movimiento > 500:
            print(f"\nMovimiento detectado ({movimiento} px). Tomando foto y enviando a Django...")
            
            # =========================================================
            # PREPARAR Y ENVIAR LA IMAGEN A DJANGO
            # =========================================================
            # Codificamos el recorte (en formato JPG) directo en memoria para no guardarlo en el disco duro
            _, buffer_imagen = cv2.imencode('.jpg', recorte_placa)
            
            # Preparamos el archivo para enviarlo por HTTP POST
            archivos = {
                'upload': ('captura_placa.jpg', buffer_imagen.tobytes(), 'image/jpeg')
            }
            
            try:
                # Enviamos el POST con el archivo adjunto (timeout de 10s porque viaja a la nube y vuelve)
                respuesta = requests.post(URL_DJANGO, files=archivos, timeout=10)
                
                if respuesta.status_code == 200:
                    datos = respuesta.json()
                    
                    if datos.get("encontrado"):
                        placa_en_pantalla = datos['placa_leida_ia']
                        print("--------------------------------------------------")
                        print(f"✅ PLACA LEÍDA POR IA: {placa_en_pantalla}")
                        print(f"👤 CLIENTE: {datos['cliente']['nombre']} (CI/NIT: {datos['cliente']['nit']})")
                        print(f"🚗 VEHÍCULO: {datos['vehiculo']['marca']} {datos['vehiculo']['modelo']}")
                        print("--------------------------------------------------")
                    else:
                        placa_en_pantalla = datos.get('placa_leida_ia', 'Foráneo/No legible')
                        print(f"⚠️ {datos.get('mensaje')}")
                else:
                    print(f"❌ Error en el servidor Django: HTTP {respuesta.status_code}")
                    print(respuesta.text) # Imprimir el error de Django para depurar
            
            except requests.exceptions.RequestException as e:
                print(f"❌ No se pudo conectar a Django (¿Está encendido el servidor?): {e}")
            # =========================================================
    
    # Actualizar el frame_anterior para compararlo en el siguiente ciclo
    frame_anterior = roi_blur 

    # --- INTERFAZ VISUAL ---
    # Rectángulo amarillo para apuntar
    cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 255, 255), 2)
    cv2.putText(frame, "Apunta la placa aqui", (x1, y1 - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 255), 1)
    
    # Mostrar último resultado
    color_texto = (0, 255, 0) if placa_en_pantalla not in ["Esperando...", "Foráneo/No legible"] else (0, 165, 255)
    cv2.putText(frame, f"LPR Nube: {placa_en_pantalla}", (30, 50), cv2.FONT_HERSHEY_SIMPLEX, 1, color_texto, 3)

    cv2.imshow('Terminal de Pista LPR (Modo Nube)', frame)

    frame_count += 1

    if cv2.waitKey(1) & 0xFF == ord('q'):
        break

cap.release()
cv2.destroyAllWindows()