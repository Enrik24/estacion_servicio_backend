from rest_framework import viewsets, filters
from rest_framework.permissions import IsAuthenticated
from django_filters.rest_framework import DjangoFilterBackend
from .models import Bitacora
from .serializers import BitacoraSerializer
from utils.permissions import HasPermiso

class BitacoraViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Bitacora.objects.select_related('usuario').all()
    serializer_class = BitacoraSerializer
    permission_classes = [IsAuthenticated, HasPermiso]
    permiso_requerido = 'bitacora.ver'

    
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_fields = ['usuario', 'accion', 'dispositivo']
    ordering_fields = ['creado_en']
    ordering = ['-creado_en']
    
    def get_queryset(self):
        queryset = super().get_queryset()
        fecha_desde = self.request.query_params.get('fecha_desde')
        fecha_hasta = self.request.query_params.get('fecha_hasta')
        
        if fecha_desde:
            queryset = queryset.filter(creado_en__date__gte=fecha_desde)
        if fecha_hasta:
            queryset = queryset.filter(creado_en__date__lte=fecha_hasta)
        return queryset