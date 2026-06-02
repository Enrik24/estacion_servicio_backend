#!/usr/bin/env python3
"""
Script Simplificado de Prueba - Endpoint LPR
Versión minimalista para pruebas rápidas
"""

import requests
import sys
import json


def test_lpr_simple(email, password, placa, lado_id, base_url="http://localhost:8000"):
    """
    Realiza una prueba simple del endpoint LPR
    
    Args:
        email: Email del usuario
        password: Contraseña del usuario
        placa: Placa del vehículo
        lado_id: ID del surtidor
        base_url: URL base del servidor
        
    Returns:
        dict: Resultado de la prueba
    """
    
    print("\n" + "="*60)
    print("PRUEBA DEL ENDPOINT LPR - VERSIÓN SIMPLIFICADA")
    print("="*60)
    
    try:
        # PASO 1: Login
        print("\n[1/2] Autenticando...")
        token_response = requests.post(
            f"{base_url}/api/token/",
            json={"email": email, "password": password},
            timeout=10
        )
        
        if token_response.status_code != 200:
            print(f"❌ Autenticación fallida: {token_response.status_code}")
            print(f"   {token_response.text}")
            return None
        
        token = token_response.json()['access']
        print(f"✅ Autenticación exitosa (token: {token[:20]}...)")
        
        # PASO 2: Enviar evento LPR
        print("\n[2/2] Enviando evento LPR...")
        lpr_response = requests.post(
            f"{base_url}/api/monitoreo/surtidores/recibir_evento_lpr/",
            json={"placa": placa, "lado_id": lado_id},
            headers={"Authorization": f"Bearer {token}"},
            timeout=10
        )
        
        print(f"Status Code: {lpr_response.status_code}")
        
        if lpr_response.status_code in [200, 201]:
            print("✅ Evento LPR procesado correctamente")
            try:
                data = lpr_response.json()
                print("\nRespuesta del servidor:")
                print(json.dumps(data, indent=2, ensure_ascii=False))
                return {"status": "success", "data": data}
            except:
                print(f"\nRespuesta: {lpr_response.text}")
                return {"status": "success", "data": lpr_response.text}
        else:
            print(f"❌ Error en evento LPR")
            print(f"   {lpr_response.text}")
            return {"status": "error", "code": lpr_response.status_code}
            
    except requests.exceptions.ConnectionError:
        print("❌ No se pudo conectar al servidor")
        print("   ¿Está ejecutándose Django en http://localhost:8000?")
        return None
    except Exception as e:
        print(f"❌ Error: {str(e)}")
        return None
    finally:
        print("\n" + "="*60 + "\n")


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--help":
        print("""
Uso: python test_lpr_simple.py [email] [password] [placa] [lado_id] [base_url]

Argumentos:
  email       Email del usuario (default: tu_usuario@email.com)
  password    Contraseña (default: tu_password_aqui)
  placa       Placa del vehículo (default: 1234-ABC)
  lado_id     ID del surtidor (default: 1)
  base_url    URL del servidor (default: http://localhost:8000)

Ejemplos:
  python test_lpr_simple.py
  python test_lpr_simple.py usuario@email.com mipassword 5678-XYZ 15
  python test_lpr_simple.py usuario@email.com mipassword 5678-XYZ 15 http://192.168.1.100:8000
        """)
        sys.exit(0)
    
    # Parámetros desde línea de comandos o defaults
    email = sys.argv[1] if len(sys.argv) > 1 else "tu_usuario@email.com"
    password = sys.argv[2] if len(sys.argv) > 2 else "tu_password_aqui"
    placa = sys.argv[3] if len(sys.argv) > 3 else "1234-ABC"
    lado_id = int(sys.argv[4]) if len(sys.argv) > 4 else 12
    base_url = sys.argv[5] if len(sys.argv) > 5 else "http://localhost:8000"
    
    result = test_lpr_simple(email, password, placa, lado_id, base_url)
    sys.exit(0 if result and result.get("status") == "success" else 1)
