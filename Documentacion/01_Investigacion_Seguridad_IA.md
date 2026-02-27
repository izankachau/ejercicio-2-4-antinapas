# INVESTIGACIÓN TÉCNICA: SEGURIDAD PERIMETRAL MEDIANTE IA (AntiÑapas-Pons)

## 1. Introducción al Concepto "AntiÑapas"
En el sector del tratamiento de fruta, la elusión de seguridades físicas por parte de operarios es una causa común de accidentes graves. El proyecto **AntiÑapas-Pons** nace para digitalizar la seguridad mediante el uso de redes neuronales de detección de objetos que no pueden ser "engañadas" con métodos mecánicos.

## 2. Tecnologías de Visión Artificial Aplicadas
Para garantizar la precisión milimétrica que requiere una línea de producción, se analizan las siguientes tecnologías:
- **Mediapipe / Pose Tracking**: Permite detectar no solo que hay una persona, sino qué parte del cuerpo ha entrado en la zona prohibida (una mano, un pie).
- **YOLO (You Only Look Once)**: Un algoritmo de detección rápida de objetos ideal para identificar intrusos en milisegundos.
- **Virtual Fencing (Vallado Virtual)**: Técnica de dibujo de polígonos inteligentes sobre el plano de la cámara que activan eventos de seguridad según la posición del centro de gravedad de la persona detectada.

## 3. Normativa de Seguridad Industrial (ISO 13849-1)
Este software se diseña como una capa de seguridad redundante. Según la norma **ISO 13849-1**, los sistemas de control de seguridad deben tener un Nivel de Rendimiento (Performance Level - PL) adecuado.
- **Categoría 3/4**: Requiere que un solo fallo no provoque la pérdida de la función de seguridad.
- **Redundancia**: AntiÑapas-Pons envía un señal de "Heartbeat" al PLC. Si la comunicación falla, el PLC interpreta que el sistema de visión está "ceguero" y para la máquina de forma segura.

## 4. Gestión de Privacidad y Ética
Bajo el cumplimiento del RGPD, el sistema procesa la imagen para detectar la infracción, pero aplica un filtro de **difuminado gaussiano** automático sobre los rostros antes de realizar el guardado en disco de la prueba gráfica del incidente.

## 5. Integración PLC (IT/OT Convergence)
La comunicación se establece mediante **OPC-UA**, permitiendo que el estado de la línea (Automático, Manual, Mantenimiento) condicione la agresividad de la alarma de seguridad.
