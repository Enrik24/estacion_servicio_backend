import os
import json
import pickle
import numpy as np
import pandas as pd
from datetime import datetime
from django.core.management.base import BaseCommand
from django.utils import timezone
from sklearn.ensemble import RandomForestRegressor
from sklearn.model_selection import train_test_split
from sklearn.metrics import mean_absolute_error, mean_squared_error
from ventas.models import Venta


class Command(BaseCommand):
    help = 'Entrena el modelo Random Forest con datos reales de ventas'

    def handle(self, *args, **kwargs):
        self.stdout.write('Cargando datos de ventas...')

        ventas = Venta.objects.filter(
            estado='COMPLETADA',
            cliente__isnull=False,
        ).select_related('cliente', 'tipo_combustible', 'turno')

        if ventas.count() < 100:
            self.stdout.write(self.style.ERROR('No hay suficientes ventas para entrenar'))
            return

        self.stdout.write(f'  {ventas.count()} ventas encontradas')

        # Construir dataset
        rows = []
        for v in ventas:
            fecha = v.fecha_hora
            rows.append({
                'cliente_id': v.cliente_id,
                'sucursal_id': v.turno.sucursal_id or 0,
                'dia': fecha.day,
                'mes': fecha.month,
                'dia_semana': fecha.weekday(),
                'hora': fecha.hour,
                'tipo_combustible_id': v.tipo_combustible_id,
                'litros': float(v.litros),
                'total': float(v.total),
            })

        df = pd.DataFrame(rows)
        self.stdout.write(f'  Dataset: {len(df)} registros')

        # Agregar rolling mean por cliente
        df = df.sort_values(['cliente_id', 'mes', 'dia'])
        df['rolling_mean_7'] = (
            df.groupby('cliente_id')['litros']
            .transform(lambda x: x.rolling(7, min_periods=1).mean())
        )

        # Features y target
        features = ['cliente_id', 'sucursal_id','dia', 'mes', 'dia_semana', 'hora', 'tipo_combustible_id', 'rolling_mean_7']
        X = df[features]
        y = df['litros']

        # Split train/test
        X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)

        self.stdout.write('Entrenando Random Forest...')
        model = RandomForestRegressor(
            n_estimators=100,
            max_depth=10,
            min_samples_split=5,
            random_state=42,
            n_jobs=-1,
        )
        model.fit(X_train, y_train)

        # Métricas
        y_pred = model.predict(X_test)
        mae = mean_absolute_error(y_test, y_pred)
        rmse = np.sqrt(mean_squared_error(y_test, y_pred))
        mape = np.mean(np.abs((y_test - y_pred) / y_test)) * 100

        self.stdout.write(f'  MAE:  {mae:.2f}')
        self.stdout.write(f'  RMSE: {rmse:.2f}')
        self.stdout.write(f'  MAPE: {mape:.2f}%')

        # Guardar modelo
        artifacts_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'ml_artifacts')
        os.makedirs(artifacts_dir, exist_ok=True)

        model_path = os.path.join(artifacts_dir, 'prediccion_consumo_model.pkl')
        with open(model_path, 'wb') as f:
            pickle.dump(model, f)

        # Guardar metadata
        metadata = {
            'model_version': f'rf-{datetime.now().strftime("%Y%m%d%H%M%S")}',
            'modelo_nombre': 'random_forest_regressor',
            'trained_at': timezone.now().isoformat(),
            'dataset_size': len(df),
            'splits': {'train': len(X_train), 'test': len(X_test)},
            'metricas_test': {'mae': mae, 'rmse': rmse, 'mape': mape},
            'feature_order': features,
            'n_estimators': 100,
            'max_depth': 10,
        }

        metadata_path = os.path.join(artifacts_dir, 'prediccion_consumo_metadata.json')
        with open(metadata_path, 'w') as f:
            json.dump(metadata, f, indent=2)

        self.stdout.write(self.style.SUCCESS(f'\n✅ Modelo entrenado y guardado en {model_path}'))