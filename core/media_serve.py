import mimetypes
from pathlib import Path
from django.conf import settings
from django.http import FileResponse, Http404


def serve_media_file(request, path: str):
    clean_rel = str(path or '').replace('\\', '/').lstrip('/')
    if not clean_rel or '..' in clean_rel.split('/'):
        raise Http404('Archivo no encontrado')

    base_dir = Path(settings.BASE_DIR)
    roots = []
    if getattr(settings, 'MEDIA_ROOT', None):
        roots.append(Path(settings.MEDIA_ROOT))
    for folder in ('media', 'staticfiles', 'static'):
        candidate_root = base_dir / folder
        if candidate_root not in roots:
            roots.append(candidate_root)

    found = None
    for root in roots:
        candidate = root / clean_rel
        if candidate.is_file():
            found = candidate
            break
        # Coincidencia insensible a may?sculas/min?sculas (.PNG vs .png / .JPG vs .jpg) en Linux/Render
        parent = candidate.parent
        if parent.is_dir():
            target_lower = candidate.name.lower()
            for item in parent.iterdir():
                if item.is_file() and item.name.lower() == target_lower:
                    found = item
                    break
        if found:
            break

    if not found:
        raise Http404('Imagen no encontrada')

    content_type, _ = mimetypes.guess_type(str(found))
    if not content_type:
        ext = found.suffix.lower()
        content_type = {
            '.png': 'image/png',
            '.jpg': 'image/jpeg',
            '.jpeg': 'image/jpeg',
            '.jpng': 'image/jpeg',
            '.webp': 'image/webp',
            '.gif': 'image/gif',
        }.get(ext, 'application/octet-stream')

    response = FileResponse(found.open('rb'), content_type=content_type)
    response['Cache-Control'] = 'public, max-age=3600'
    return response
