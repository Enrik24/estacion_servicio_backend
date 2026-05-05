from django.contrib import admin
from .models import Isla, Lado, TipoCombustible, Turno, Cliente, Venta

admin.site.register(Isla)
admin.site.register(Lado)
admin.site.register(TipoCombustible)
admin.site.register(Turno)
admin.site.register(Cliente)
admin.site.register(Venta)