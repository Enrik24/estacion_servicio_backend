from django.db.models import Sum, Count, F, FloatField, ExpressionWrapper
from django.db.models.functions import Cast
from ventas.models import Venta, Isla

class DashboardService:
    @staticmethod
    def obtener_kpis_principales(ventas_qs):
        """
        Calcula los KPIs principales: ventas totales en Bs, litros totales,
        margen de ganancia y promedio de litros por venta.
        """
        # Excluir ventas anuladas para el cálculo de ganancia real
        ventas_completadas = ventas_qs.filter(estado='COMPLETADA')
        
        # Anotamos el costo total por venta para luego sumarlo (litros * costo_litro)
        # Esto nos permite saber la ganancia (precio - costo)
        # Ganancia = Total Venta - (Litros * Costo_Litro)
        ventas_anotadas = ventas_completadas.annotate(
            costo_total=ExpressionWrapper(
                F('litros') * F('tipo_combustible__costo_litro'),
                output_field=FloatField()
            )
        )
        
        # Agregamos los totales
        totales = ventas_anotadas.aggregate(
            ventas_totales_bs=Sum('total'),
            litros_vendidos=Sum('litros'),
            costo_total_acumulado=Sum('costo_total'),
            total_ventas_count=Count('id')
        )
        
        ventas_bs = totales['ventas_totales_bs'] or 0.0
        litros_vend = totales['litros_vendidos'] or 0.0
        costo_total = totales['costo_total_acumulado'] or 0.0
        count = totales['total_ventas_count'] or 0
        
        margen_ganancia = float(ventas_bs) - float(costo_total)
        promedio_litros = float(litros_vend) / count if count > 0 else 0.0
        
        return {
            "ventas_totales_bs": round(float(ventas_bs), 2),
            "litros_vendidos": round(float(litros_vend), 2),
            "margen_ganancia_bs": round(margen_ganancia, 2),
            "promedio_litros_por_venta": round(promedio_litros, 2)
        }

    @staticmethod
    def obtener_ventas_por_turno(ventas_qs):
        """
        Agrupa las ventas según el horario del turno (MAÑANA, TARDE, NOCHE).
        """
        ventas_completadas = ventas_qs.filter(estado='COMPLETADA')
        turnos_agrupados = ventas_completadas.values('turno__horario').annotate(
            litros=Sum('litros'),
            total_bs=Sum('total')
        ).order_by('turno__horario')
        
        resultados = []
        for item in turnos_agrupados:
            resultados.append({
                "turno": item['turno__horario'],
                "litros": round(float(item['litros'] or 0), 2),
                "total_bs": round(float(item['total_bs'] or 0), 2)
            })
            
        return resultados

    @staticmethod
    def obtener_metodos_pago(ventas_qs):
        """
        Obtiene la distribución de métodos de pago y calcula su porcentaje
        respecto al total.
        """
        ventas_completadas = ventas_qs.filter(estado='COMPLETADA')
        
        # Primero obtenemos el total general para calcular porcentajes
        total_general = ventas_completadas.aggregate(Sum('total'))['total__sum'] or 0.0
        
        pagos_agrupados = ventas_completadas.values('metodo_pago').annotate(
            total_bs=Sum('total')
        ).order_by('-total_bs')
        
        resultados = []
        for item in pagos_agrupados:
            monto = float(item['total_bs'] or 0)
            porcentaje = (monto / float(total_general) * 100) if total_general > 0 else 0
            
            resultados.append({
                "metodo": item['metodo_pago'],
                "porcentaje": round(porcentaje, 2),
                "total_bs": round(monto, 2)
            })
            
        return resultados

    @staticmethod
    def obtener_rendimiento_surtidores(ventas_qs):
        """
        Agrupa las ventas por Isla y Lado para ver cuáles despachan más.
        """
        ventas_completadas = ventas_qs.filter(estado='COMPLETADA')
        surtidores_agrupados = ventas_completadas.values(
            'lado__isla__numero', 
            'lado__lado'
        ).annotate(
            litros=Sum('litros')
        ).order_by('-litros')
        
        resultados = []
        for item in surtidores_agrupados:
            isla_num = item['lado__isla__numero']
            lado_letra = item['lado__lado']
            litros = float(item['litros'] or 0)
            
            resultados.append({
                "surtidor": f"Isla {isla_num} - Lado {lado_letra}",
                "litros": round(litros, 2)
            })
            
        return resultados

    @staticmethod
    def obtener_estado_surtidores(sucursal=None, empresa=None):
        """
        Retorna el conteo de surtidores Activos, Inactivos o en Falla.
        Filtra por sucursal o empresa según corresponda al usuario.
        """
        islas = Isla.objects.all()
        
        if sucursal:
            islas = islas.filter(sucursal=sucursal)
        elif empresa:
            islas = islas.filter(sucursal__empresa=empresa)
            
        estados = islas.values('estado').annotate(cantidad=Count('id'))
        
        # Estructura por defecto
        resultado = {
            "ACTIVO": 0,
            "INACTIVO": 0,
            "FALLA": 0
        }
        
        for item in estados:
            estado = item['estado']
            if estado in resultado:
                resultado[estado] = item['cantidad']
                
        return resultado
