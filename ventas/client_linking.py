import re
import unicodedata

from .models import Cliente
from usuarios.models import Usuario


def _normalize_person_name(value):
    if not value:
        return ''
    normalized = unicodedata.normalize('NFKD', value)
    normalized = ''.join(ch for ch in normalized if not unicodedata.combining(ch))
    normalized = re.sub(r'\s+', ' ', normalized).strip().lower()
    return normalized


def _cliente_users_queryset():
    return Usuario.objects.filter(
        sucursal__isnull=True,
        is_staff=False,
        is_superuser=False,
    )


def link_cliente_to_usuario(cliente, usuario):
    if cliente is None or usuario is None:
        return cliente

    updates = []
    normalized_email = (usuario.email or '').strip().lower() or None

    if cliente.usuario_id != usuario.id:
        cliente.usuario = usuario
        updates.append('usuario')
    if normalized_email and cliente.email != normalized_email:
        cliente.email = normalized_email
        updates.append('email')
    if not cliente.activo:
        cliente.activo = True
        updates.append('activo')
    if not cliente.nombre and usuario.nombre:
        cliente.nombre = usuario.nombre
        updates.append('nombre')

    if updates:
        cliente.save(update_fields=updates)
    return cliente


def resolve_cliente_for_usuario(usuario, create_if_missing=False):
    if usuario is None:
        return None

    cliente = Cliente.objects.filter(usuario=usuario).first()
    if cliente:
        return link_cliente_to_usuario(cliente, usuario)

    normalized_email = (usuario.email or '').strip().lower()
    if normalized_email:
        cliente = Cliente.objects.filter(email__iexact=normalized_email).order_by('id').first()
        if cliente:
            return link_cliente_to_usuario(cliente, usuario)

    coincidencias_nombre = Cliente.objects.filter(
        nombre__iexact=usuario.nombre,
        activo=True,
    ).order_by('id')
    if coincidencias_nombre.count() == 1:
        return link_cliente_to_usuario(coincidencias_nombre.first(), usuario)

    if create_if_missing:
        return Cliente.objects.create(
            nombre=usuario.nombre,
            email=normalized_email or None,
            activo=True,
            usuario=usuario,
        )

    return None


def resolve_cliente_for_sale(cliente):
    if cliente is None:
        return None

    if cliente.usuario_id:
        return link_cliente_to_usuario(cliente, cliente.usuario)

    normalized_email = (cliente.email or '').strip().lower()
    if normalized_email:
        usuario = _cliente_users_queryset().filter(email__iexact=normalized_email).first()
        if usuario:
            return resolve_cliente_for_usuario(usuario, create_if_missing=True)

    same_name_candidates = Cliente.objects.filter(
        nombre__iexact=cliente.nombre,
        activo=True,
    ).exclude(id=cliente.id).select_related('usuario').order_by('id')

    canonical_matches = {}
    for candidate in same_name_candidates:
        resolved = None
        if candidate.usuario_id:
            resolved = resolve_cliente_for_usuario(candidate.usuario, create_if_missing=True)
        elif candidate.email:
            candidate_user = _cliente_users_queryset().filter(email__iexact=candidate.email).first()
            if candidate_user:
                resolved = resolve_cliente_for_usuario(candidate_user, create_if_missing=True)
        if resolved is not None:
            canonical_matches[resolved.id] = resolved

    if len(canonical_matches) == 1:
        return next(iter(canonical_matches.values()))

    normalized_target_name = _normalize_person_name(cliente.nombre)
    matching_users = []
    for usuario in _cliente_users_queryset().only('id', 'nombre', 'email'):
        if _normalize_person_name(usuario.nombre) == normalized_target_name:
            matching_users.append(usuario)
            if len(matching_users) > 1:
                break

    if len(matching_users) == 1:
        return resolve_cliente_for_usuario(matching_users[0], create_if_missing=True)

    return cliente
