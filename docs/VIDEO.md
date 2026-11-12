# Video simulado y pipeline de frames

Implementado: fuente sintética o archivo local, captura con OpenCV, resize,
codificación JPEG y distribución MJPEG autenticada. No requiere cámara física.
La fuente sintética muestra un rectángulo móvil y un contador; no representa
personas ni humo y no produce detecciones de IA.

## Activar

Instalar `requirements.txt`. La dependencia `opencv-python-headless` evita
necesitar un servidor gráfico. En `.env`:

```ini
VIDEO_ENABLED=true
VIDEO_SOURCE=synthetic
VIDEO_WIDTH=640
VIDEO_HEIGHT=360
VIDEO_FPS=10
VIDEO_JPEG_QUALITY=80
```

Arrancar con un solo worker, igual que el control de vuelo:

```bash
uvicorn app.main:app --host 127.0.0.1 --port 8000 --workers 1
```

La captura empieza en el lifespan de la API y se detiene al apagarla. Por defecto
`VIDEO_ENABLED=false`: no abre archivos, cámaras ni conexiones.

Para reproducir un archivo como fuente simulada:

```ini
VIDEO_ENABLED=true
VIDEO_SOURCE=file
VIDEO_FILE=/ruta/absoluta/camera.avi
```

Se leen frames a `VIDEO_FPS`, independientemente del FPS original: es una
simulación, no una reproducción que conserve el tiempo original del archivo.
Se redimensiona al ancho y alto configurados, sin conservar necesariamente la
relación de aspecto. Al terminar el archivo o fallar la lectura se libera la
captura y se vuelve a abrir después de `VIDEO_RECONNECT_SECONDS` (1 segundo).
Un archivo que aún no existe puede aparecer después y la fuente se recuperará.
Solo admite archivos locales regulares; todavía no admite RTSP, USB ni cámaras
de Gazebo. En Docker, montar el archivo en una ruta legible para `appuser`.

## Endpoints

Todos requieren un token ADMIN o GUARDIA en `Authorization: Bearer ...`.

| Endpoint | Resultado |
|---|---|
| `GET /api/v1/video/status` | Estado, fuente, frames publicados, reconexiones, antigüedad y tiempo de procesamiento |
| `GET /api/v1/video/frame` | Último frame JPEG con `X-Frame-Sequence` y `X-Captured-At` |
| `GET /api/v1/video/stream` | MJPEG `multipart/x-mixed-replace; boundary=frame` |

Ejemplos después de obtener el token con `/api/v1/auth/login`:

```bash
# Definir TOKEN con el token obtenido, sin guardarlo en el repositorio.
curl -f -H "Authorization: Bearer $TOKEN" \
  http://127.0.0.1:8000/api/v1/video/status

curl -f -H "Authorization: Bearer $TOKEN" \
  http://127.0.0.1:8000/api/v1/video/frame -o /tmp/drone-frame.jpg

curl -f --max-time 65 -H "Authorization: Bearer $TOKEN" \
  http://127.0.0.1:8000/api/v1/video/stream -o /tmp/drone-stream.mjpeg
```

El stream termina a los `VIDEO_STREAM_SECONDS` (60 por defecto; máximo 300).
El consumidor debe renovar la conexión con su token. La autorización se valida
al abrir cada conexión; no se reevalúa durante los frames de esa conexión.
No poner tokens en query strings. Un `<img src>` directo no puede enviar este
header: un cliente web necesita `fetch` y lectura de multipart, o solicitar
snapshots y mostrarlos mediante una URL de Blob. No se añadió un reproductor web.

Cada parte incluye `Content-Length`, `X-Frame-Sequence`, `X-Captured-At` y el JPEG.
La respuesta impide caché (`Cache-Control: no-store`). Si no hay frame reciente,
`/frame` y el inicio de `/stream` devuelven 503. Si la fuente se pierde durante
un stream, este termina y el cliente puede reintentar. También puede suceder al
reiniciar el archivo después de EOF. No se presenta el último frame antiguo
como si fuera una captura actual.

## Procesamiento y límites

Existe un único hilo de captura y un buffer del último JPEG por proceso.
Los espectadores comparten ese buffer. Un cliente lento omite frames intermedios;
no acumula una cola de imágenes. Cerrar un consumidor no detiene la fuente.

- `VIDEO_STALE_SECONDS`: 3 por defecto, máximo 30; antigüedad máxima admitida.
- `processing_ms`: apertura/lectura o generación, resize y codificación del último
  frame. No incluye transferencia al cliente ni inferencia.
- `captured_at`: hora UTC cuando el backend terminó de leer/generar el frame,
  no el timestamp original de una cámara o del archivo.
- `frame_age_seconds`: tiempo monotónico desde la publicación del JPEG.
- Estados: `disabled`, `starting`, `running`, `reconnecting`, `stale`,
  `unavailable`, `stopping`, `stopped`. Una dependencia faltante deja la fuente
  `unavailable` sin impedir el arranque de la API.

Faltan el consumidor de inferencia, los modelos de personas/humo, la persistencia
de imágenes de evidencia, el transporte de cámara real y las mediciones de
latencia end-to-end. MJPEG es una primera entrega funcional para simulación;
no constituye una validación de ancho de banda ni latencia de vuelo real.

## Verificar

```bash
pytest tests/test_video.py -v
```

Las pruebas decodifican JPEGs reales, crean un AVI temporal, verifican repetición,
recuperación de fuente, autenticación, stream multipart, cliente lento, datos
caducados y cierre del hilo. No utilizan cámara ni dron.
