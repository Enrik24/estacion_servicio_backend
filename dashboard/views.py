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
        # 1. Obtener parámetros de fecha
        fecha_inicio_str = request.query_params.get('fecha_inicio')
        fecha_fin_str = request.query_params.get('fecha_fin')
        
        hoy = timezone.now().date()
        
        # Filtro por defecto: desde el día 1 del mes actual hasta hoy
        if not fecha_inicio_str:
            fecha_inicio = hoy.replace(day=1)
        else:
            try:
                fecha_inicio = datetime.strptime(fecha_inicio_str, '%Y-%m-%d').date()
            except ValueError:
                return Response({'error': 'Formato de fecha_inicio inválido. Use YYYY-MM-DD.'}, status=status.HTTP_400_BAD_REQUEST)
                
        if not fecha_fin_str:
            fecha_fin = hoy
        else:
            try:
                fecha_fin = datetime.strptime(fecha_fin_str, '%Y-%m-%d').date()
            except ValueError:
                return Response({'error': 'Formato de fecha_fin inválido. Use YYYY-MM-DD.'}, status=status.HTTP_400_BAD_REQUEST)

        # 2. Control de Acceso (RBAC) - Filtrado Base
        usuario = request.user
        ventas_qs = Venta.objects.filter(fecha_hora__date__range=[fecha_inicio, fecha_fin])
        
        sucursal_filtro = None
        empresa_filtro = None

        if usuario.is_superuser or usuario.tiene_permiso('reportes.ver'):
            # Administradores pueden ver todas las sucursales de la empresa
            empresa_filtro = usuario.empresa
            ventas_qs = ventas_qs.filter(turno__isla__sucursal__empresa=empresa_filtro)
        else:
            # Gerentes / Operadores solo ven su propia sucursal
            sucursal_filtro = usuario.sucursal
            if not sucursal_filtro:
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
