#!/usr/bin/env python3
"""
Script de Prueba Automatizado - Endpoint LPR (Reconocimiento de Placas)
Caso de Uso 14: Autorizar Despacho Remoto

Este script realiza las siguientes operaciones:
1. Autentica al usuario y obtiene el JWT access token
2. Realiza una petición POST al endpoint LPR con credenciales de prueba
3. Genera un reporte completo de los resultados
"""

import requests
import json
import sys
from datetime import datetime


class LPRTestAutomation:
    """Clase para automatizar las pruebas del endpoint LPR"""
    #en produccion colocar url del backend en la nube, por ejemplo: "https://api.estacion.com"
    def __init__(self, base_url="http://localhost:8000"):
        """
        Inicializa la configuración de prueba
        
        Args:
            base_url: URL base del servidor Django
        """
        self.base_url = base_url.rstrip('/')
        self.token_endpoint = f"{self.base_url}/api/token/"
        self.lpr_endpoint = f"{self.base_url}/api/monitoreo/surtidores/recibir_evento_lpr/"
        self.access_token = None
        self.test_results = {
            "timestamp": datetime.now().isoformat(),
            "auth_status": None,
            "lpr_status": None,
            "errors": []
        }
    
    def login(self, email, password):
        """
        Realiza la autenticación y extrae el JWT access token
        
        Args:
            email: Email del usuario
            password: Contraseña del usuario
            
        Returns:
            bool: True si la autenticación fue exitosa, False en caso contrario
        """
        print(f"\n{'='*70}")
        print(f"PASO 1: AUTENTICACIÓN - Solicitando JWT Access Token")
        print(f"{'='*70}")
        print(f"Endpoint: POST {self.token_endpoint}")
        print(f"Credenciales: email={email}")
        
        try:
            payload = {
                "email": email,
                "password": password
            }
            
            response = requests.post(
                self.token_endpoint,
                json=payload,
                timeout=10
            )
            
            print(f"Status Code: {response.status_code}")
            
            if response.status_code == 200:
                data = response.json()
                self.access_token = data.get('access')
                
                if self.access_token:
                    self.test_results["auth_status"] = "SUCCESS"
                    print(f"✓ Token obtenido exitosamente")
                    print(f"  Token (primeros 20 caracteres): {self.access_token[:20]}...")
                    return True
                else:
                    error_msg = "No se encontró 'access' en la respuesta"
                    self.test_results["errors"].append(error_msg)
                    print(f"✗ Error: {error_msg}")
                    print(f"  Respuesta: {json.dumps(data, indent=2)}")
                    return False
            else:
                self.test_results["auth_status"] = "FAILED"
                error_msg = f"HTTP {response.status_code}: {response.text}"
                self.test_results["errors"].append(error_msg)
                print(f"✗ Error de autenticación: {error_msg}")
                print(f"  Respuesta: {response.text}")
                return False
                
        except requests.exceptions.Timeout:
            error_msg = "Timeout: El servidor tardó demasiado en responder"
            self.test_results["errors"].append(error_msg)
            self.test_results["auth_status"] = "TIMEOUT"
            print(f"✗ Error: {error_msg}")
            return False
        except requests.exceptions.ConnectionError:
            error_msg = "Error de conexión: No se pudo conectar al servidor"
            self.test_results["errors"].append(error_msg)
            self.test_results["auth_status"] = "CONNECTION_ERROR"
            print(f"✗ Error: {error_msg}")
            return False
        except Exception as e:
            error_msg = f"Error inesperado: {str(e)}"
            self.test_results["errors"].append(error_msg)
            self.test_results["auth_status"] = "ERROR"
            print(f"✗ Error: {error_msg}")
            return False
    
    def test_lpr_event(self, placa, lado_id):
        """
        Realiza una petición POST al endpoint LPR
        
        Args:
            placa: Placa del vehículo (ej: "1234-ABC")
            lado_id: ID del lado/surtidor
            
        Returns:
            bool: True si la petición fue exitosa, False en caso contrario
        """
        print(f"\n{'='*70}")
        print(f"PASO 2: EVENTO LPR - Enviando evento de reconocimiento de placa")
        print(f"{'='*70}")
        
        if not self.access_token:
            error_msg = "No hay token de autenticación disponible"
            self.test_results["errors"].append(error_msg)
            self.test_results["lpr_status"] = "NO_TOKEN"
            print(f"✗ Error: {error_msg}")
            print(f"  Ejecute primero el paso de autenticación")
            return False
        
        print(f"Endpoint: POST {self.lpr_endpoint}")
        print(f"Placa: {placa}")
        print(f"Lado ID: {lado_id}")
        
        try:
            headers = {
                "Authorization": f"Bearer {self.access_token}",
                "Content-Type": "application/json"
            }
            
            payload = {
                "placa": placa,
                "lado_id": lado_id
            }
            
            response = requests.post(
                self.lpr_endpoint,
                json=payload,
                headers=headers,
                timeout=10
            )
            
            print(f"Status Code: {response.status_code}")
            
            # Intenta parsear la respuesta como JSON
            try:
                response_data = response.json()
            except:
                response_data = {"raw_response": response.text}
            
            if response.status_code == 200:
                self.test_results["lpr_status"] = "SUCCESS"
                self.test_results["lpr_response"] = response_data
                print(f"✓ Petición exitosa al endpoint LPR")
                return True
            elif response.status_code == 201:
                self.test_results["lpr_status"] = "CREATED"
                self.test_results["lpr_response"] = response_data
                print(f"✓ Recurso creado exitosamente (201)")
                return True
            elif response.status_code == 401:
                self.test_results["lpr_status"] = "UNAUTHORIZED"
                error_msg = "Token inválido o expirado (401 Unauthorized)"
                self.test_results["errors"].append(error_msg)
                print(f"✗ Error: {error_msg}")
                return False
            elif response.status_code == 403:
                self.test_results["lpr_status"] = "FORBIDDEN"
                error_msg = "Acceso denegado (403 Forbidden)"
                self.test_results["errors"].append(error_msg)
                print(f"✗ Error: {error_msg}")
                return False
            elif response.status_code == 404:
                self.test_results["lpr_status"] = "NOT_FOUND"
                error_msg = "Endpoint no encontrado (404) o recurso no existe"
                self.test_results["errors"].append(error_msg)
                print(f"✗ Error: {error_msg}")
                return False
            elif response.status_code >= 500:
                self.test_results["lpr_status"] = "SERVER_ERROR"
                error_msg = f"Error del servidor (HTTP {response.status_code})"
                self.test_results["errors"].append(error_msg)
                print(f"✗ Error: {error_msg}")
                return False
            else:
                self.test_results["lpr_status"] = f"HTTP_{response.status_code}"
                self.test_results["lpr_response"] = response_data
                print(f"⚠ Respuesta con código {response.status_code}")
                return response.status_code < 400
                
        except requests.exceptions.Timeout:
            error_msg = "Timeout: El servidor tardó demasiado en responder"
            self.test_results["errors"].append(error_msg)
            self.test_results["lpr_status"] = "TIMEOUT"
            print(f"✗ Error: {error_msg}")
            return False
        except requests.exceptions.ConnectionError:
            error_msg = "Error de conexión: No se pudo conectar al servidor"
            self.test_results["errors"].append(error_msg)
            self.test_results["lpr_status"] = "CONNECTION_ERROR"
            print(f"✗ Error: {error_msg}")
            return False
        except Exception as e:
            error_msg = f"Error inesperado: {str(e)}"
            self.test_results["errors"].append(error_msg)
            self.test_results["lpr_status"] = "ERROR"
            print(f"✗ Error: {error_msg}")
            return False
    
    def print_final_report(self):
        """Imprime un reporte final con los resultados de las pruebas"""
        print(f"\n{'='*70}")
        print(f"REPORTE FINAL DE PRUEBAS - ENDPOINT LPR")
        print(f"{'='*70}")
        
        # Resumen de Estado
        print(f"\n📋 RESUMEN DE ESTADO:")
        print(f"   Timestamp: {self.test_results['timestamp']}")
        print(f"   Autenticación: {self._get_status_emoji(self.test_results['auth_status'])} {self.test_results['auth_status']}")
        print(f"   Evento LPR: {self._get_status_emoji(self.test_results['lpr_status'])} {self.test_results['lpr_status']}")
        
        # Respuesta del Endpoint LPR
        if 'lpr_response' in self.test_results and self.test_results['lpr_response']:
            print(f"\n📨 RESPUESTA DEL SERVIDOR (Endpoint LPR):")
            print(f"   {json.dumps(self.test_results['lpr_response'], indent=3)}")
        
        # Errores (si los hay)
        if self.test_results["errors"]:
            print(f"\n❌ ERRORES ENCONTRADOS:")
            for i, error in enumerate(self.test_results["errors"], 1):
                print(f"   {i}. {error}")
        else:
            print(f"\n✓ Sin errores detectados")
        
        # Conclusión
        print(f"\n{'='*70}")
        auth_success = self.test_results['auth_status'] == 'SUCCESS'
        lpr_success = self.test_results['lpr_status'] in ['SUCCESS', 'CREATED']
        
        if auth_success and lpr_success:
            print(f"✅ PRUEBA COMPLETADA EXITOSAMENTE")
            print(f"   El surtidor fue liberado y el evento LPR fue procesado correctamente.")
        elif auth_success and not lpr_success:
            print(f"⚠️  PRUEBA PARCIALMENTE EXITOSA")
            print(f"   La autenticación funcionó, pero hubo un problema en el endpoint LPR.")
        else:
            print(f"❌ PRUEBA FALLÓ")
            print(f"   No se pudo completar el flujo de pruebas.")
        
        print(f"{'='*70}\n")
        
        return auth_success and lpr_success
    
    @staticmethod
    def _get_status_emoji(status):
        """Retorna un emoji según el estado"""
        if status == "SUCCESS":
            return "✅"
        elif status in ["CREATED"]:
            return "✅"
        elif status and "ERROR" in status or "FAIL" in status:
            return "❌"
        elif status in ["TIMEOUT", "CONNECTION_ERROR"]:
            return "🔌"
        else:
            return "⚠️ "


def main():
    """Función principal para ejecutar el script"""
    
    print("\n╔" + "="*68 + "╗")
    print("║" + " "*68 + "║")
    print("║" + "  SISTEMA DE PRUEBAS AUTOMATIZADO - ENDPOINT LPR".center(68) + "║")
    print("║" + "  Caso de Uso 14: Autorizar Despacho Remoto".center(68) + "║")
    print("║" + " "*68 + "║")
    print("╚" + "="*68 + "╝")
    
    # Configuración de credenciales
    EMAIL = "operador.norte@estacion.com"
    PASSWORD = "operador123"
    
    # Configuración del evento LPR
    PLACA = "1234-ABC"
    LADO_ID = 2
    
    # Crear instancia del automator
    tester = LPRTestAutomation(base_url="http://localhost:8000")
    
    # Paso 1: Autenticación
    if not tester.login(EMAIL, PASSWORD):
        print("\n❌ No se pudo autenticar. Verifique:")
        print("   - Las credenciales sean correctas")
        print("   - El servidor esté ejecutándose en http://localhost:8000")
        print("   - El endpoint /api/token/ esté disponible")
        sys.exit(1)
    
    # Paso 2: Enviar evento LPR
    tester.test_lpr_event(PLACA, LADO_ID)
    
    # Paso 3: Imprimir reporte final
    success = tester.print_final_report()
    
    # Retornar código de salida
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n⚠️  Prueba interrumpida por el usuario")
        sys.exit(130)
    except Exception as e:
        print(f"\n❌ Error fatal: {str(e)}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
