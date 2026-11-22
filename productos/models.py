# productos/models.py
"""Modelos de la app productos — ERP Django."""
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.db import models

from proveedores.models import Proveedor


class Categoria(models.Model):
    """Categoría para clasificar productos del catálogo."""

    nombre = models.CharField(
        max_length=100, unique=True, verbose_name='Nombre'
    )
    descripcion = models.TextField(
        blank=True, verbose_name='Descripción'
    )

    class Meta:
        verbose_name = 'Categoría'
        verbose_name_plural = 'Categorías'
        ordering = ['nombre']

    def __str__(self) -> str:
        return self.nombre


class Producto(models.Model):
    """Artículo del inventario del ERP."""

    nombre = models.CharField(
        max_length=200, verbose_name='Nombre'
    )
    precio = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.00'))],
        verbose_name='Precio ($)',
        help_text='El precio no puede ser negativo.'
    )
    stock = models.IntegerField(
        default=0,
        validators=[MinValueValidator(0)],
        verbose_name='Stock disponible'
    )
    categoria = models.ForeignKey(
        Categoria,
        on_delete=models.PROTECT,
        related_name='productos',
        verbose_name='Categoría'
    )
    proveedor = models.ForeignKey(
        Proveedor,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='productos',
        verbose_name='Proveedor'
    )
    imagen = models.ImageField(
        upload_to='productos/',
        null=True,
        blank=True,
        verbose_name='Imagen del producto',
        help_text='Formatos permitidos: JPEG, PNG, WEBP. Máximo 5 MB.'
    )
    activo = models.BooleanField(
        default=True, verbose_name='Activo'
    )
    creado = models.DateTimeField(
        auto_now_add=True, verbose_name='Fecha de registro'
    )

    def clean(self) -> None:
        """Validaciones de negocio cruzadas para Producto."""
        errors = {}

        if self.stock is not None and self.stock < 0:
            errors['stock'] = (
                'El stock no puede ser negativo. '
                f'Valor recibido: {self.stock}'
            )

        if errors:
            raise ValidationError(errors)

    class Meta:
        verbose_name = 'Producto'
        verbose_name_plural = 'Productos'
        ordering = ['nombre']

    def __str__(self) -> str:
        return f"{self.nombre} (${self.precio:.2f})"


class ProductoColor(models.Model):
    producto = models.ForeignKey(
        Producto,
        on_delete=models.CASCADE,
        related_name="colores",
        verbose_name="Producto",
    )
    nombre = models.CharField(max_length=80, verbose_name="Nombre del color")
    codigo_hex = models.CharField(max_length=20, default="#1A1A1A", verbose_name="Código de color")
    imagen_color = models.ImageField(
        upload_to="productos/colores/",
        blank=True,
        null=True,
        verbose_name="Imagen principal del color",
    )
    orden = models.PositiveIntegerField(default=0, verbose_name="Orden")

    class Meta:
        ordering = ["orden", "id"]
        verbose_name = "Color de producto"
        verbose_name_plural = "Colores de producto"

    def __str__(self):
        return f"{self.producto} - {self.nombre}"


class ProductoImagen(models.Model):
    producto = models.ForeignKey(
        Producto,
        on_delete=models.CASCADE,
        related_name="imagenes_extra",
        verbose_name="Producto",
    )
    color = models.ForeignKey(
        ProductoColor,
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name="imagenes",
        verbose_name="Color asociado (opcional)",
    )
    imagen = models.ImageField(
        upload_to="productos/galeria/",
        verbose_name="Imagen adicional",
    )
    titulo = models.CharField(max_length=120, blank=True, default="", verbose_name="Descripción / Ángulo")
    orden = models.PositiveIntegerField(default=0, verbose_name="Orden")

    class Meta:
        ordering = ["orden", "id"]
        verbose_name = "Imagen adicional de producto"
        verbose_name_plural = "Imágenes adicionales de producto"

    def __str__(self):
        return f"Galería {self.producto} (#{self.id})"

from . import variantes_hooks  # noqa: E402,F401
