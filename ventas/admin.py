from django.contrib import admin
from .models import Surtidor, Turno, Cliente, Venta

admin.site.register(Surtidor)
admin.site.register(Turno)
admin.site.register(Cliente)
admin.site.register(Venta)