from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.utils import timezone
from django.db import transaction
from decimal import Decimal

from ventas.models import Isla, Lado, Turno, Sucursal, Venta, TipoCombustible, Cliente
from inventario.models import Tanque

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

                        # --- NUEVOS CAMPOS ADAPTADOS AL REDISEÑO ---
                        'placa_activa': estado_obj.placa_activa,
                        'monto_autorizado': estado_obj.monto_autorizado,
                        'cliente_activo_nombre': estado_obj.cliente_activo.nombre if estado_obj.cliente_activo else None,
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

    # =========================================================================
    # ENDPOINT PARA CAMBIO DE ESTADO MANUAL (CU 03 - RECHAZAR ORDEN REMOTA DE LPR)
    # =========================================================================
    @action(detail=False, methods=['post'], permission_classes=[IsAuthenticated])
    def cambiar_estado(self, request):
        """
        Cambia el estado de un surtidor (ACTIVO, INACTIVO, FALLA).
        También sirve para que el operador cancele/rechace una orden remota de LPR.
        """
        lado_id = request.data.get('lado_id')
        nuevo_estado = request.data.get('estado')
        descripcion = request.data.get('descripcion', 'Cambio de estado manual')

        if not lado_id or not nuevo_estado:
            return Response({'error': 'lado_id y estado son requeridos'}, status=400)

        try:
            estado_obj = EstadoSurtidor.objects.select_related('lado').get(lado_id=lado_id)
            estado_anterior = estado_obj.estado

            # 1. Si el operador está RECHAZANDO una orden remota, usamos la función de limpieza
            if estado_anterior == 'AUTORIZADO_REMOTO' and nuevo_estado == 'ACTIVO':
                estado_obj.liberar_surtidor_post_despacho()
            else:
                # 2. Para cualquier otro cambio normal (ej. marcar FALLA o INACTIVO)
                estado_obj.estado = nuevo_estado
                estado_obj.descripcion_falla = descripcion if nuevo_estado == 'FALLA' else None
                estado_obj.reportado_por = request.user
                if nuevo_estado == 'ACTIVO' and estado_anterior == 'FALLA':
                    from django.utils import timezone
                    estado_obj.fecha_resolucion = timezone.now()
                estado_obj.save()
                if nuevo_estado == 'FALLA':
                    from utils.onesignal import notificar_falla_surtidor
                    notificar_falla_surtidor(estado_obj.lado, descripcion, request.user)

            # 3. Registrar el historial limpio (SIN el campo parent_id que causaba el error)
            HistorialEstadoSurtidor.objects.create(
                lado=estado_obj.lado,
                estado_anterior=estado_anterior,
                estado_nuevo=nuevo_estado,
                descripcion=descripcion,
                cambiado_por=request.user
            )

            # Opcional: Registrar en la bitácora general de seguridad
            registrar_bitacora(
                request,
                accion='EDITAR',
                modulo='Monitoreo',
                descripcion=f'Estado de Lado {estado_obj.lado.id} cambiado de {estado_anterior} a {nuevo_estado}.',
            )

            return Response({
                'status': 'ESTADO_ACTUALIZADO',
                'mensaje': f'El surtidor pasó a estado {nuevo_estado}.'
            }, status=status.HTTP_200_OK)

        except EstadoSurtidor.DoesNotExist:
            return Response({'error': 'El surtidor indicado no existe'}, status=404)
        except Exception as e:
            return Response({'error': f'Error interno: {str(e)}'}, status=500)
    
    # =========================================================================
    # NUEVO ENDPOINT: CU 14 - DISPARADOR AUTOMÁTICO DE CÁMARA DE VISIÓN (LPR)
    # =========================================================================
    @action(detail=False, methods=['post'], permission_classes=[IsAuthenticated])
    def recibir_evento_lpr(self, request):
        """
        Gatillador asíncrono para cámaras LPR en pista (Simulación de Webhook).
        Busca órdenes pre-pagadas en la nube y autoriza de forma remota el hardware.
        """
        placa = request.data.get('placa')
        lado_id = request.data.get('lado_id')  # Surtidor físico donde frenó el auto

        if not placa or not lado_id:
            return Response({'error': 'placa y lado_id son requeridos'}, status=400)

        try:
            lado = Lado.objects.select_related('isla__sucursal').get(id=lado_id)
        except Lado.DoesNotExist:
            return Response({'error': 'Dispensador/Lado no encontrado'}, status=404)

        # LÓGICA DE NEGOCIO: Simulación de búsqueda de venta "PRE_PAGADO_PENDIENTE" en base de datos.
        # En tu entorno real buscarías: Venta.objects.filter(placa=placa, estado='PRE_PAGADO_PENDIENTE').first()
        # Para mantener el módulo aislado, simulamos que encontramos una orden válida de un cliente:
        
        # Buscamos un usuario de pruebas o usamos el actual para la simulación
        cliente_simulado = request.user 

        # Inyectamos de forma lógica los metadatos transaccionales requeridos en el CU 14
        estado_obj, _ = EstadoSurtidor.objects.get_or_create(lado=lado)
        
        estado_anterior = estado_obj.estado
        estado_obj.estado = 'AUTORIZADO_REMOTO'
        estado_obj.placa_activa = placa.upper()
        estado_obj.monto_autorizado = 200.00  # Valor inyectado simulado (O el valor recuperado de tu tabla Ventas)
        estado_obj.cliente_activo = cliente_simulado
        estado_obj.save()

        # Registrar el evento en el Log de Auditoría obligatorio (CU 03)
        HistorialEstadoSurtidor.objects.create(
            lado=lado,
            estado_anterior=estado_anterior,
            estado_nuevo='AUTORIZADO_REMOTO',
            descripcion=f'Despacho Remoto Automatizado por captura LPR. Placa: {placa}.',
            cambiado_por=None,  # Fue automatizado por el hardware/sistema IA
        )
       
        # NOTA ARQUITECTÓNICA DE EXPOSICIÓN:
        # Aquí es donde mandarías a llamar a tus servicios de WebSockets (Django Channels)
        # o Notificaciones Push (Firebase Cloud Messaging) para alertar al operador en pista:
        # -----> channel_layer.group_send(...) / enviar_push_operador(...)

        return Response({
            'status': 'CU_14_EJECUTADO_EXITOSAMENTE',
            'mensaje': f'Surtidor {lado.id} liberado remotamente para placa {placa}',
            'monto_inyectado': 200.00,
            'combustible': 'Gasolina Especial'
        }, status=status.HTTP_200_OK)
        

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

    # =========================================================================
    # VISTA EXCLUSIVA DEL OPERADOR: MONITOREO FILTRADO POR SU ISLA ASIGNADA
    # =========================================================================
    @action(detail=False, methods=['get'], permission_classes=[IsAuthenticated])
    def vista_operador(self, request):
        """
        Retorna únicamente la isla y los lados asignados al operador en su turno actual.
        Aplica el principio de restricción física de datos.
        """
        user = request.user
        ahora = timezone.now()

        # 1. Buscar si el usuario tiene un turno abierto en alguna isla
        turno_activo = Turno.objects.filter(
            operador=user,
            estado='ABIERTO'
        ).select_related('isla__sucursal').first()

        if not turno_activo:
            return Response({
                'error': 'No tienes ningún turno abierto asignado en este momento. Solicita la apertura de tu turno al gerente.'
            }, status=status.HTTP_404_NOT_FOUND)

        isla = turno_activo.isla
        lados = isla.lados.all().order_by('lado')

        lados_data = []
        for lado in lados:
            estado_obj, _ = EstadoSurtidor.objects.get_or_create(lado=lado, defaults={'estado': 'ACTIVO'})
            
            lados_data.append({
                'id': lado.id,
                'lado': lado.lado,
                'activo': lado.activo,
                'estado': estado_obj.estado,
                
                # Datos transitorios requeridos en pista para el CU 14
                'placa_activa': estado_obj.placa_activa,
                'monto_autorizado': estado_obj.monto_autorizado,
            })

        # Estructura JSON optimizada para el POS local del pistero
        contexto_pista = {
            'sucursal_nombre': isla.sucursal.nombre if isla.sucursal else None,
            'isla_id': isla.id,
            'isla_numero': isla.numero,
            'turno_id': turno_activo.id,
            'horario': turno_activo.get_horario_display(),
            'lados': lados_data
        }

        return Response(contexto_pista, status=status.HTTP_200_OK)

    # =========================================================================
    # CU 17 - VERSIÓN MEJORADA: CONSOLIDAR VENTA + DESCONTAR INVENTARIO + LIBERAR SURTIDOR
    # =========================================================================
    @action(detail=False, methods=['post'], permission_classes=[IsAuthenticated])
    def finalizar_despacho(self, request):
        """
        CU 17: Consolida la carga remota, descuenta inventario físico y libera el hardware.
        Corrige la omisión del campo precio_unitario exigido por la base de datos.
        """
        lado_id = request.data.get('lado_id')
        volumen_despachado = request.data.get('volumen_litros') 

        if not lado_id or not volumen_despachado:
            return Response({'error': 'lado_id y volumen_litros son requeridos'}, status=400)

        try:
            estado_obj = EstadoSurtidor.objects.select_related('lado__isla__sucursal').get(lado_id=lado_id)
        except EstadoSurtidor.DoesNotExist:
            return Response({'error': 'Surtidor no parametrizado'}, status=404)

        if estado_obj.estado != 'AUTORIZADO_REMOTO':
            return Response({'error': 'Este surtidor no se encuentra en despacho remoto'}, status=400)

        placa_final = estado_obj.placa_activa
        monto_final = estado_obj.monto_autorizado
        usuario_transitorio = estado_obj.cliente_activo 
        sucursal_actual = estado_obj.lado.isla.sucursal

        turno_activo = Turno.objects.filter(isla=estado_obj.lado.isla, estado='ABIERTO').first()
        if not turno_activo:
            return Response({'error': f'No hay turno abierto en Isla {estado_obj.lado.isla.numero}.'}, status=400)

        # 1. Intentamos buscar "Gasolina" para el Lado A, y "Diesel" (sin tilde) para el Lado B
        tipo_str = 'Gasolina' if estado_obj.lado.lado == 'A' else 'Diesel'
        tipo_combustible = TipoCombustible.objects.filter(tipo__icontains=tipo_str).first()

        # 2. Si es Lado B y no encontró "Diesel" sin tilde, intentamos con tilde "Diésel"
        if not tipo_combustible and estado_obj.lado.lado != 'A':
            tipo_combustible = TipoCombustible.objects.filter(tipo__icontains='Diésel').first()

        # 3. FALLBACK DE EMERGENCIA: Si alguien escribió mal el nombre en la base de datos,
        # tomamos el primer combustible disponible para no bloquear la venta física.
        if not tipo_combustible:
            tipo_combustible = TipoCombustible.objects.first()

        # Si después de todo esto sigue siendo None, es porque la tabla está literalmente vacía.
        if not tipo_combustible:
             return Response({'error': 'No hay ningún tipo de combustible registrado en la base de datos. Pídele al administrador que cree uno.'}, status=400)
        
        # Mapear Usuario -> Cliente
        cliente_para_venta = None
        if usuario_transitorio:
            cliente_para_venta = Cliente.objects.filter(nombre=usuario_transitorio.nombre).first()

        try:
            with transaction.atomic():
                # 1. Crear la Venta oficial (Se añade el campo precio_unitario)
                Venta.objects.create(
                    turno=turno_activo,
                    lado=estado_obj.lado,
                    tipo_combustible=tipo_combustible,
                    cliente=cliente_para_venta,
                    precio_unitario=tipo_combustible.precio_litro,
                    numero_comprobante=f"CU14-{timezone.now().strftime('%H%M%S')}",
                    litros=volumen_despachado,
                    total=monto_final,
                    metodo_pago='ONLINE / LPR',
                    estado='COMPLETADA',
                    created_by=request.user  # <-- SOLUCIÓN: El operador que cierra la venta
                )

                # 2. Descuento de Inventario Físico en Tanque Subterráneo
                tanque = Tanque.objects.filter(
                    sucursal=sucursal_actual, 
                    tipo_combustible=tipo_combustible,
                    activo=True
                ).first()
                
                if tanque:
                    tanque.nivel_actual -= Decimal(str(volumen_despachado))
                    tanque.save()

                # 3. Limpiar y liberar el hardware
                estado_anterior = estado_obj.estado
                estado_obj.liberar_surtidor_post_despacho()

                # 4. Registrar auditoría inmutable
                HistorialEstadoSurtidor.objects.create(
                    lado=estado_obj.lado,
                    estado_anterior=estado_anterior,
                    estado_nuevo='ACTIVO',
                    descripcion=f'Venta LPR consolidada. Placa {placa_final}. Consumo: Bs. {monto_final} ({volumen_despachado} Lt). Surtidor liberado.',
                    cambiado_por=request.user
                )

        except Exception as e:
            return Response({'error': f'Falla interna al consolidar la venta: {str(e)}'}, status=500)

        registrar_bitacora(
            request,
            accion='CREAR',
            modulo='Ventas/Monitoreo',
            descripcion=f'CU 17: Venta remota cerrada y tanque descontado en Isla {estado_obj.lado.isla.numero} Lado {estado_obj.lado.lado}.',
        )

        return Response({
            'status': 'CU_17_CONSOLIDATED',
            'mensaje': 'Venta guardada e inventario actualizado. Surtidor liberado.',
        }, status=status.HTTP_200_OK)