from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView
from rest_framework.response import Response

from .serializers import PrediccionConsumoRequestSerializer
from .prediccion_consumo_service import generar_prediccion_consumo


class PrediccionConsumoAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = PrediccionConsumoRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        # Filtrar por la sucursal del usuario autenticado (multi-tenant)
        sucursal_id = getattr(request.user, 'sucursal_id', None)

        resultado = generar_prediccion_consumo(
            cliente_id=data.get("cliente_id"),
            tipo_combustible_id=data.get("tipo_combustible_id"),
            tipo_periodo=data["tipo_periodo"],
            unidad=data["unidad"],
            dias=data["dias"],
            sucursal_id=sucursal_id,
        )
        return Response(resultado, status=status.HTTP_200_OK)
