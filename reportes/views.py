"""ViewSets para reportes y análisis de datos.

Define los ViewSets para obtener reportes de ventas, turnos, clientes,
sucursales e islas con filtros y análisis agregados.
"""

from rest_framework import viewsets, status
from rest_framework.viewsets import ViewSet
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.utils import timezone
from django.db.models import Sum, Count, Q
from datetime import datetime

from ventas.models import Turno, Venta, Cliente, Isla, Sucursal, Lado, TipoCombustible
from utils.permissions import HasPermiso


class ReportesViewSet(ViewSet):
    """ViewSet para obtener reportes generales de operaciones."""
    permission_classes = [IsAuthenticated]

    def get_queryset_filtrado(self, modelo, filtros):
        """Filtra un queryset según los filtros proporcionados."""
        qs = modelo.objects.all()
        
        # Filtro por fecha
        if filtros.get('fecha_inicio'):
            try:
                fecha_inicio = datetime.strptime(filtros['fecha_inicio'], '%Y-%m-%d').date()
                qs = qs.filter(fecha_apertura__date__gte=fecha_inicio)
            except:
                pass
        
        if filtros.get('fecha_fin'):
            try:
                fecha_fin = datetime.strptime(filtros['fecha_fin'], '%Y-%m-%d').date()
                qs = qs.filter(fecha_apertura__date__lte=fecha_fin)
            except:
                pass
        
        return qs

    @action(detail=False, methods=['get'])
    def ventas(self, request):
        """Obtiene reporte de ventas agrupadas por tipo de combustible."""
        filtros = request.query_params.dict()
        
        try:
            ventas_qs = Venta.objects.filter(estado='COMPLETADA')
            
            # Aplicar filtros de fecha
            if filtros.get('fecha_inicio'):
                try:
                    fecha_inicio = datetime.strptime(filtros['fecha_inicio'], '%Y-%m-%d').date()
                    ventas_qs = ventas_qs.filter(created_at__date__gte=fecha_inicio)
                except:
                    pass
            
            if filtros.get('fecha_fin'):
                try:
                    fecha_fin = datetime.strptime(filtros['fecha_fin'], '%Y-%m-%d').date()
                    ventas_qs = ventas_qs.filter(created_at__date__lte=fecha_fin)
                except:
                    pass
            
            # Filtrar por tipo de combustible
            if filtros.get('tipo_combustible'):
                ventas_qs = ventas_qs.filter(tipo_combustible__tipo=filtros['tipo_combustible'])
            
            # Filtrar por método de pago
            if filtros.get('metodo_pago'):
                ventas_qs = ventas_qs.filter(metodo_pago=filtros['metodo_pago'])
            
            # Filtrar por sucursal
            if filtros.get('sucursal_id'):
                ventas_qs = ventas_qs.filter(turno__isla__sucursal_id=filtros['sucursal_id'])
            
            # Agrupar por tipo de combustible
            por_combustible = []
            for tipo_comb in TipoCombustible.objects.filter(activo=True):
                ventas_tipo = ventas_qs.filter(tipo_combustible=tipo_comb)
                if ventas_tipo.exists():
                    total_recaudado = ventas_tipo.aggregate(Sum('total'))['total__sum'] or 0
                    total_litros = ventas_tipo.aggregate(Sum('litros'))['litros__sum'] or 0
                    cantidad = ventas_tipo.count()
                    
                    por_combustible.append({
                        'tipo_combustible': tipo_comb.get_tipo_display(),
                        'total_recaudado': float(total_recaudado),
                        'total_litros': float(total_litros),
                        'cantidad': cantidad,
                    })
            
            return Response({
                'por_combustible': por_combustible,
                'total_general': sum(c['total_recaudado'] for c in por_combustible),
            })
        
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=False, methods=['get'])
    def turnos(self, request):
        """Obtiene reporte de turnos con detalles de operaciones."""
        filtros = request.query_params.dict()
        
        try:
            turnos_qs = Turno.objects.select_related('operador', 'isla').all()
            
            # Aplicar filtros de fecha
            if filtros.get('fecha_inicio'):
                try:
                    fecha_inicio = datetime.strptime(filtros['fecha_inicio'], '%Y-%m-%d').date()
                    turnos_qs = turnos_qs.filter(fecha_apertura__date__gte=fecha_inicio)
                except:
                    pass
            
            if filtros.get('fecha_fin'):
                try:
                    fecha_fin = datetime.strptime(filtros['fecha_fin'], '%Y-%m-%d').date()
                    turnos_qs = turnos_qs.filter(fecha_apertura__date__lte=fecha_fin)
                except:
                    pass
            
            # Filtrar por horario
            if filtros.get('horario'):
                turnos_qs = turnos_qs.filter(horario=filtros['horario'])
            
            # Filtrar por estado
            if filtros.get('estado'):
                turnos_qs = turnos_qs.filter(estado=filtros['estado'])
            
            # Filtrar por isla
            if filtros.get('isla_id'):
                turnos_qs = turnos_qs.filter(isla_id=filtros['isla_id'])
            
            # Construir respuesta con detalles de cada turno
            turnos_data = []
            for turno in turnos_qs:
                ventas = Venta.objects.filter(turno=turno, estado='COMPLETADA')
                total_recaudado = ventas.aggregate(Sum('total'))['total__sum'] or 0
                total_litros = ventas.aggregate(Sum('litros'))['litros__sum'] or 0
                cantidad_ventas = ventas.count()
                
                turnos_data.append({
                    'id': turno.id,
                    'operador': turno.operador.nombre,
                    'isla': turno.isla.numero,
                    'horario': turno.get_horario_display(),
                    'horario_codigo': turno.horario,
                    'estado': turno.estado,
                    'fecha_apertura': turno.fecha_apertura,
                    'fecha_cierre': turno.fecha_cierre,
                    'total_recaudado': float(total_recaudado),
                    'total_litros': float(total_litros),
                    'cantidad_ventas': cantidad_ventas,
                })
            
            # Agrupar por horario para gráfico
            por_horario = {}
            for turno in turnos_qs:
                horario = turno.get_horario_display()
                if horario not in por_horario:
                    por_horario[horario] = {'horario': horario, 'total_recaudado': 0}
                
                ventas = Venta.objects.filter(turno=turno, estado='COMPLETADA')
                total = ventas.aggregate(Sum('total'))['total__sum'] or 0
                por_horario[horario]['total_recaudado'] += float(total)
            
            return Response({
                'turnos': turnos_data,
                'por_horario': list(por_horario.values()),
            })
        
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=False, methods=['get'])
    def clientes(self, request):
        """Obtiene ranking de clientes por consumo."""
        filtros = request.query_params.dict()
        
        try:
            # Obtener ventas completadas
            ventas_qs = Venta.objects.filter(estado='COMPLETADA', cliente__isnull=False)
            
            # Aplicar filtros de fecha
            if filtros.get('fecha_inicio'):
                try:
                    fecha_inicio = datetime.strptime(filtros['fecha_inicio'], '%Y-%m-%d').date()
                    ventas_qs = ventas_qs.filter(created_at__date__gte=fecha_inicio)
                except:
                    pass
            
            if filtros.get('fecha_fin'):
                try:
                    fecha_fin = datetime.strptime(filtros['fecha_fin'], '%Y-%m-%d').date()
                    ventas_qs = ventas_qs.filter(created_at__date__lte=fecha_fin)
                except:
                    pass
            
            # Filtrar por método de pago
            if filtros.get('metodo_pago'):
                ventas_qs = ventas_qs.filter(metodo_pago=filtros['metodo_pago'])
            
            # Filtrar por cliente específico
            if filtros.get('cliente_id'):
                ventas_qs = ventas_qs.filter(cliente_id=filtros['cliente_id'])
            
            # Agrupar por cliente
            ranking = []
            clientes_ids = ventas_qs.values_list('cliente_id', flat=True).distinct()
            
            for cliente_id in clientes_ids:
                cliente = Cliente.objects.get(id=cliente_id)
                ventas_cliente = ventas_qs.filter(cliente_id=cliente_id)
                
                total_consumido = ventas_cliente.aggregate(Sum('total'))['total__sum'] or 0
                total_litros = ventas_cliente.aggregate(Sum('litros'))['litros__sum'] or 0
                cantidad_ventas = ventas_cliente.count()
                
                ranking.append({
                    'cliente_nombre': cliente.nombre,
                    'cliente_nit': cliente.nit,
                    'cliente_id': cliente.id,
                    'total_consumido': float(total_consumido),
                    'total_litros': float(total_litros),
                    'cantidad_ventas': cantidad_ventas,
                })
            
            # Ordenar por consumo descendente
            ranking.sort(key=lambda x: x['total_consumido'], reverse=True)
            
            return Response({
                'ranking_clientes': ranking,
            })
        
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=False, methods=['get'])
    def sucursales(self, request):
        """Obtiene reporte de sucursales con sus operaciones."""
        filtros = request.query_params.dict()
        
        try:
            sucursales_qs = Sucursal.objects.all()
            
            # Filtrar por estado si se proporciona
            if filtros.get('estado'):
                sucursales_qs = sucursales_qs.filter(estado=filtros['estado'])
            
            # Filtrar por ID específico
            if filtros.get('sucursal_id'):
                sucursales_qs = sucursales_qs.filter(id=filtros['sucursal_id'])
            
            sucursales_data = []
            for sucursal in sucursales_qs:
                # Obtener turnos de la sucursal
                turnos = Turno.objects.filter(isla__sucursal=sucursal)
                
                # Aplicar filtros de fecha
                if filtros.get('fecha_inicio'):
                    try:
                        fecha_inicio = datetime.strptime(filtros['fecha_inicio'], '%Y-%m-%d').date()
                        turnos = turnos.filter(fecha_apertura__date__gte=fecha_inicio)
                    except:
                        pass
                
                if filtros.get('fecha_fin'):
                    try:
                        fecha_fin = datetime.strptime(filtros['fecha_fin'], '%Y-%m-%d').date()
                        turnos = turnos.filter(fecha_apertura__date__lte=fecha_fin)
                    except:
                        pass
                
                # Obtener ventas de la sucursal
                ventas = Venta.objects.filter(
                    turno__isla__sucursal=sucursal,
                    estado='COMPLETADA'
                )
                
                if filtros.get('fecha_inicio'):
                    try:
                        fecha_inicio = datetime.strptime(filtros['fecha_inicio'], '%Y-%m-%d').date()
                        ventas = ventas.filter(created_at__date__gte=fecha_inicio)
                    except:
                        pass
                
                if filtros.get('fecha_fin'):
                    try:
                        fecha_fin = datetime.strptime(filtros['fecha_fin'], '%Y-%m-%d').date()
                        ventas = ventas.filter(created_at__date__lte=fecha_fin)
                    except:
                        pass
                
                total_recaudado = ventas.aggregate(Sum('total'))['total__sum'] or 0
                total_litros = ventas.aggregate(Sum('litros'))['litros__sum'] or 0
                cantidad_ventas = ventas.count()
                cantidad_turnos = turnos.count()
                
                sucursales_data.append({
                    'id': sucursal.id,
                    'nombre': sucursal.nombre,
                    'direccion': sucursal.direccion,
                    'estado': sucursal.estado,
                    'total_recaudado': float(total_recaudado),
                    'total_litros': float(total_litros),
                    'cantidad_ventas': cantidad_ventas,
                    'cantidad_turnos': cantidad_turnos,
                })
            
            return Response({
                'sucursales': sucursales_data,
            })
        
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=False, methods=['get'])
    def islas(self, request):
        """Obtiene reporte de islas y lados con detalles de operaciones."""
        filtros = request.query_params.dict()
        
        try:
            islas_qs = Isla.objects.select_related('sucursal').prefetch_related('lados').all()
            
            # Filtrar por sucursal
            if filtros.get('sucursal_id'):
                islas_qs = islas_qs.filter(sucursal_id=filtros['sucursal_id'])
            
            # Filtrar por isla específica
            if filtros.get('isla_id'):
                islas_qs = islas_qs.filter(id=filtros['isla_id'])
            
            islas_data = []
            for isla in islas_qs:
                lados_data = []
                for lado in isla.lados.all():
                    # Obtener ventas del lado
                    ventas = Venta.objects.filter(
                        lado=lado,
                        estado='COMPLETADA'
                    )
                    
                    # Aplicar filtros de fecha
                    if filtros.get('fecha_inicio'):
                        try:
                            fecha_inicio = datetime.strptime(filtros['fecha_inicio'], '%Y-%m-%d').date()
                            ventas = ventas.filter(created_at__date__gte=fecha_inicio)
                        except:
                            pass
                    
                    if filtros.get('fecha_fin'):
                        try:
                            fecha_fin = datetime.strptime(filtros['fecha_fin'], '%Y-%m-%d').date()
                            ventas = ventas.filter(created_at__date__lte=fecha_fin)
                        except:
                            pass
                    
                    total_recaudado = ventas.aggregate(Sum('total'))['total__sum'] or 0
                    total_litros = ventas.aggregate(Sum('litros'))['litros__sum'] or 0
                    cantidad_ventas = ventas.count()
                    
                    lados_data.append({
                        'lado': lado.get_lado_display(),
                        'lado_codigo': lado.lado,
                        'total_recaudado': float(total_recaudado),
                        'total_litros': float(total_litros),
                        'cantidad_ventas': cantidad_ventas,
                    })
                
                islas_data.append({
                    'numero': isla.numero,
                    'id': isla.id,
                    'sucursal': isla.sucursal.nombre if isla.sucursal else 'Sin sucursal',
                    'sucursal_id': isla.sucursal.id if isla.sucursal else None,
                    'lados': lados_data,
                })
            
            return Response({
                'islas': islas_data,
            })
        
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)
