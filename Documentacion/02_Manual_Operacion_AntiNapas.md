# MANUAL DE OPERACIÓN: AntiÑapas-Pons v2.0

## 1. Introducción
AntiÑapas-Pons es una solución integral de seguridad perimetral basada en Visión Artificial (IA). Diseñada específicamente para proteger zonas críticas en líneas de tratamiento de fruta donde los operarios suelen eludir las barreras físicas.

## 2. Puesta en Marcha
El sistema se compone de dos interfaces sincronizadas:
- **Software PC (`main_antinapas.py`)**: Interfaz principal de control y visión en tiempo real.
- **Dashboard Web (`app_web.py`)**: Panel remoto para monitorización y configuración de layouts desde cualquier dispositivo.

## 3. Uso del Simulador
Ambas versiones incluyen un simulador de seguridad:
- **Añadir Obstáculos**: Coloca pilares o cuadros eléctricos para representar la estancia real.
- **Definir Zonas**: 
  - **Zona Roja**: Dispara el PARO DE EMERGENCIA y toma una CAPTURA DE PRUEBA (difuminada).
  - **Zona Ámbar**: Activa un aviso visual/sonoro de aproximación peligrosa.
- **Sincronización**: Al guardar el layout en la web, la aplicación PC lo carga automáticamente sin reiniciar.

## 4. Lógica de Seguridad (Eagle Eye)
- **Modo Automático**: La vigilancia está al máximo nivel. Cualquier intrusión en zona roja para la línea.
- **Modo Mantenimiento**: Permite el acceso para reparaciones técnicas sin disparar paros.
- **Anonimización**: El sistema cumple con la privacidad difuminando los rostros de todo el personal detectado.

## 5. Mapeado con PLC
El sistema envía un **Heartbeat** constante al PLC. Si este pulso se detiene, la instalación entra en estado de fallo seguro, garantizando que nunca se trabaje sin supervisión artificial activa.
