from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework import status
from datetime import datetime
from django.utils import timezone
from ventas.models import Venta
from .services import DashboardService

class DashboardKPIsAPIView(APIView):
    """
    Vista de API que retorna los indicadores clave (KPIs) para el Dashboard Ejecutivo.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        # ==========================================
        # 1. Obtener parámetros de fecha
        # ==========================================
        # Se extraen las fechas de inicio y fin desde la URL (query parameters).
        fecha_inicio_str = request.query_params.get('fecha_inicio')
        fecha_fin_str = request.query_params.get('fecha_fin')
        
        hoy = timezone.now().date()
        
        # Filtro por defecto: Si no se especifica fecha de inicio, se toma el día 1 del mes actual.
        if not fecha_inicio_str:
            fecha_inicio = hoy.replace(day=1)
        else:
            try:
                # Parsear el string de la fecha a un objeto Date
                fecha_inicio = datetime.strptime(fecha_inicio_str, '%Y-%m-%d').date()
            except ValueError:
                return Response({'error': 'Formato de fecha_inicio inválido. Use YYYY-MM-DD.'}, status=status.HTTP_400_BAD_REQUEST)
                
        # Filtro por defecto: Si no se especifica fecha de fin, se toma el día de hoy.
        if not fecha_fin_str:
            fecha_fin = hoy
        else:
            try:
                # Parsear el string de la fecha a un objeto Date
                fecha_fin = datetime.strptime(fecha_fin_str, '%Y-%m-%d').date()
            except ValueError:
                return Response({'error': 'Formato de fecha_fin inválido. Use YYYY-MM-DD.'}, status=status.HTTP_400_BAD_REQUEST)

        # ==========================================
        # 2. Control de Acceso (RBAC) - Filtrado Base
        # ==========================================
        # Extraemos el usuario que está realizando la petición a la API.
        usuario = request.user
        
        # Validación principal: Verificamos si el usuario es un superusuario (acceso total) 
        # o si tiene explícitamente el permiso 'dashboard.ver' (ej. Gerentes o Administradores).
        if not (usuario.is_superuser or usuario.tiene_permiso('dashboard.ver')):
            return Response(
                {'error': 'No tiene permisos suficientes para ver el dashboard.'}, 
                status=status.HTTP_403_FORBIDDEN
            )

        # Filtramos inicialmente todas las ventas para que solo correspondan al rango de fechas solicitado.
        ventas_qs = Venta.objects.filter(fecha_hora__date__range=[fecha_inicio, fecha_fin])
        
        # Estas variables nos ayudarán a saber si estamos filtrando a nivel de empresa o de sucursal
        sucursal_filtro = None
        empresa_filtro = None

        # Acceso global para el Administrador
        # Si el usuario es superusuario o tiene el rol de Administrador, puede ver la información consolidada 
        # de TODAS las sucursales que pertenecen a su empresa.
        if usuario.is_superuser or usuario.nombre_rol.lower() == 'administrador':
            empresa_filtro = usuario.empresa
            ventas_qs = ventas_qs.filter(turno__isla__sucursal__empresa=empresa_filtro)
        else:
            # Acceso restringido para Gerentes
            # Si no es Administrador, restringimos el QuerySet para que solo traiga las ventas de la sucursal 
            # a la que está asignado el usuario.
            sucursal_filtro = usuario.sucursal
            if not sucursal_filtro:
                # Un gerente que no tiene sucursal asignada no debe poder consultar datos
                return Response({'error': 'El usuario no tiene una sucursal asignada.'}, status=status.HTTP_403_FORBIDDEN)
            ventas_qs = ventas_qs.filter(turno__isla__sucursal=sucursal_filtro)

        # 3. Procesar datos usando el servicio (Servicios limpios, vista rápida)
        kpis_principales = DashboardService.obtener_kpis_principales(ventas_qs)
        ventas_por_turno = DashboardService.obtener_ventas_por_turno(ventas_qs)
        metodos_pago = DashboardService.obtener_metodos_pago(ventas_qs)
        rendimiento_surtidores = DashboardService.obtener_rendimiento_surtidores(ventas_qs)
        estado_surtidores = DashboardService.obtener_estado_surtidores(
            sucursal=sucursal_filtro, 
            empresa=empresa_filtro
        )

        # 4. Retornar el JSON estructurado
        data = {
            "rango_fechas": {
                "fecha_inicio": fecha_inicio.strftime('%Y-%m-%d'),
                "fecha_fin": fecha_fin.strftime('%Y-%m-%d')
            },
            "kpis_principales": kpis_principales,
            "ventas_por_turno": ventas_por_turno,
            "metodos_pago": metodos_pago,
            "rendimiento_surtidores": rendimiento_surtidores,
            "estado_surtidores": estado_surtidores
        }
        
        return Response(data, status=status.HTTP_200_OK)
