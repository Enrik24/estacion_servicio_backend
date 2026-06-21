from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView
from rest_framework.response import Response
from .serializers import PrediccionConsumoRequestSerializer, PrediccionSucursalRequestSerializer
from .prediccion_consumo_service import generar_prediccion_consumo, generar_prediccion_sucursal


class PrediccionConsumoAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = PrediccionConsumoRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        resultado = generar_prediccion_consumo(
            cliente_id=data["cliente_id"],
            tipo_periodo=data["tipo_periodo"],
            unidad=data["unidad"],
            dias=data["dias"],
        )
        return Response(resultado, status=status.HTTP_200_OK)


class PrediccionSucursalAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = PrediccionSucursalRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        resultado = generar_prediccion_sucursal(
            sucursal_id=data["sucursal_id"],
            tipo_combustible_id=data["tipo_combustible_id"],
            dias=data["dias"],
        )
        return Response(resultado, status=status.HTTP_200_OK)