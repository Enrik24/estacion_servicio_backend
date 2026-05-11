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
    filterset_fields = ['usuario_nombre', 'usuario_email', 'descripcion', 'ip_address', 'user_agent']
    ordering_fields = ['fecha_hora']
    ordering = ['-fecha_hora']
    
    def get_queryset(self):
        queryset = super().get_queryset()
        fecha_desde = self.request.query_params.get('fecha_desde')
        fecha_hasta = self.request.query_params.get('fecha_hasta')
        
        if fecha_desde:
            queryset = queryset.filter(fecha_hora__date__gte=fecha_desde)
        if fecha_hasta:
            queryset = queryset.filter(fecha_hora__date__lte=fecha_hasta)
        return queryset