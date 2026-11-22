from .models import ConfiguracionERP


def config_erp(request):
    """Expone la configuración de la empresa (y su logo) a todos los templates."""
    return {'config_erp': ConfiguracionERP.get_instance()}