from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.utils import timezone

from utils.onesignal import enviar_notificacion
from ventas.models import Isla, Lado, Turno, Sucursal
from usuarios.models import Usuario
from seguridad.models import registrar_bitacora
from .models import EstadoSurtidor, HistorialEstadoSurtidor
from .serializers import EstadoSurtidorSerializer, HistorialEstadoSurtidorSerializer


class MonitoreoViewSet(viewsets.ViewSet):
    permission_classes = [IsAuthenticated]

    def list(self, request):
        """Retorna el estado actual de todos los surtidores de la empresa."""
        user = request.user
        if user.is_superuser:
            sucursales = Sucursal.objects.all()
        elif user.empresa:
            sucursales = Sucursal.objects.filter(empresa=user.empresa)
            rol = user.roles.first()
            if rol and 'gerente' in rol.nombre.lower() and user.sucursal:
                sucursales = sucursales.filter(id=user.sucursal.id)
        else:
            return Response([])

        data = []
        for sucursal in sucursales:
            islas_data = []
            for isla in sucursal.islas.all().order_by('numero'):
                lados_data = []
                for lado in isla.lados.all().order_by('lado'):
                    # Obtener o crear estado del surtidor
                    estado_obj, _ = EstadoSurtidor.objects.get_or_create(
                        lado=lado,
                        defaults={'estado': 'ACTIVO'}
                    )
                    # Obtener turno activo en esta isla
                    turno_activo = Turno.objects.filter(
                        isla=isla,
                        estado='ABIERTO'
                    ).select_related('operador').first()

                    lados_data.append({
                        'id': lado.id,
                        'lado': lado.lado,
                        'activo': lado.activo,
                        'estado': estado_obj.estado,
                        'descripcion_falla': estado_obj.descripcion_falla,
                        'fecha_reporte': estado_obj.fecha_reporte,
                    })

                islas_data.append({
                    'id': isla.id,
                    'numero': isla.numero,
                    'estado': isla.estado,
                    'turno_activo': {
                        'id': turno_activo.id,
                        'operador': turno_activo.operador.nombre,
                        'horario': turno_activo.get_horario_display(),
                        'fecha_apertura': turno_activo.fecha_apertura,
                    } if turno_activo else None,
                    'lados': lados_data,
                })

            data.append({
                'sucursal_id': sucursal.id,
                'sucursal_nombre': sucursal.nombre,
                'islas': islas_data,
            })

        return Response(data)

    @action(detail=False, methods=['post'])
    def cambiar_estado(self, request):
        """Cambia el estado de un lado (surtidor)."""
        lado_id = request.data.get('lado_id')
        nuevo_estado = request.data.get('estado')
        descripcion = request.data.get('descripcion', '')

        if not lado_id or not nuevo_estado:
            return Response({'error': 'lado_id y estado son requeridos'}, status=400)

        if nuevo_estado not in ['ACTIVO', 'INACTIVO', 'FALLA']:
            return Response({'error': 'Estado inválido'}, status=400)

        try:
            lado = Lado.objects.select_related('isla__sucursal__empresa').get(id=lado_id)
        except Lado.DoesNotExist:
            return Response({'error': 'Lado no encontrado'}, status=404)

        # Verificar que el lado pertenece a la empresa del usuario
        user = request.user
        if not user.is_superuser:
            if lado.isla.sucursal.empresa != user.empresa:
                return Response({'error': 'Sin permiso'}, status=403)

        estado_obj, _ = EstadoSurtidor.objects.get_or_create(
            lado=lado,
            defaults={'estado': 'ACTIVO'}
        )

        estado_anterior = estado_obj.estado

        # Guardar historial
        HistorialEstadoSurtidor.objects.create(
            lado=lado,
            estado_anterior=estado_anterior,
            estado_nuevo=nuevo_estado,
            descripcion=descripcion,
            cambiado_por=request.user,
        )

        # Actualizar estado
        estado_obj.estado = nuevo_estado
        estado_obj.descripcion_falla = descripcion if nuevo_estado == 'FALLA' else None
        estado_obj.reportado_por = request.user
        if nuevo_estado == 'ACTIVO' and estado_anterior == 'FALLA':
            estado_obj.fecha_resolucion = timezone.now()
        estado_obj.save()
        if nuevo_estado == 'FALLA':
            from utils.onesignal import notificar_falla_surtidor
            notificar_falla_surtidor(lado, descripcion, request.user)
        registrar_bitacora(
            request,
            accion='EDITAR',
            modulo='Monitoreo',
            descripcion=f'Cambió estado de Isla {lado.isla.numero} Lado {lado.lado}: {estado_anterior} → {nuevo_estado}. {descripcion}',
        )

        return Response({
            'mensaje': f'Estado actualizado a {nuevo_estado}',
            'lado_id': lado_id,
            'estado_anterior': estado_anterior,
            'estado_nuevo': nuevo_estado,
        })
    @action(detail=False, methods=['get'])
    def historial(self, request):
        """Retorna el historial de cambios de estado de surtidores."""
        user = request.user
        if user.empresa:
            historial = HistorialEstadoSurtidor.objects.filter(
                lado__isla__sucursal__empresa=user.empresa
            ).select_related('lado__isla__sucursal', 'cambiado_por').order_by('-fecha')[:50]
        else:
            historial = HistorialEstadoSurtidor.objects.none()

        data = [{
            'id': h.id,
            'sucursal': h.lado.isla.sucursal.nombre,
            'isla': h.lado.isla.numero,
            'lado': h.lado.lado,
            'estado_anterior': h.estado_anterior,
            'estado_nuevo': h.estado_nuevo,
            'descripcion': h.descripcion,
            'cambiado_por': h.cambiado_por.nombre if h.cambiado_por else 'Sistema',
            'fecha': h.fecha,
        } for h in historial]

        return Response(data)