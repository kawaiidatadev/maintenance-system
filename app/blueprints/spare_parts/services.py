# app/blueprints/spare_parts/services.py
from app.blueprints.spare_parts.models import StockAlert
from app.models.notification_rule import NotificationRule
from app.notifications_helper import create_notification
from datetime import datetime
from flask import url_for
from app import db
from app.blueprints.spare_parts.models import SparePart, InventoryStock, SparePartMovement
from flask_login import current_user


def get_or_create_stock(spare_part_id, warehouse='General'):
    """Obtiene el stock para una refacción en un almacén específico. Evita duplicados."""
    stock = InventoryStock.query.filter_by(spare_part_id=spare_part_id, warehouse=warehouse).first()
    if not stock:
        # Buscar cualquier stock existente de esa refacción (para no duplicar)
        existing = InventoryStock.query.filter_by(spare_part_id=spare_part_id).first()
        if existing:
            # Si ya existe en otro almacén, no crear uno nuevo
            return existing
        stock = InventoryStock(spare_part_id=spare_part_id, warehouse=warehouse, current_stock=0)
        db.session.add(stock)
        db.session.commit()
    return stock

def update_stock_after_movement(spare_part_id, quantity, movement_type, warehouse='General'):
    """
    Actualiza el stock actual después de un movimiento.
    Retorna True si se pudo actualizar, False si hay stock insuficiente.
    """
    if quantity <= 0:
        return True

    stock = get_or_create_stock(spare_part_id, warehouse)

    if movement_type == 'in':
        stock.current_stock += quantity
        db.session.commit()
        return True
    else:  # 'out'
        if stock.current_stock < quantity:
            print(f"❌ Stock insuficiente para {spare_part_id}: requiere {quantity}, disponible {stock.current_stock}")
            return False
        stock.current_stock -= quantity
        db.session.commit()
        return True


def register_movement(spare_part_id, quantity, movement_type, warehouse, reference, description,
                      performed_by_id, work_order_id=None, preventive_execution_log_id=None):
    """
    Registra un movimiento (entrada o salida) y actualiza el stock.
    Retorna True si se registró correctamente, False si falla (stock insuficiente).
    """
    print(f"\n🔧 DEBUG register_movement:")
    print(f"   spare_part_id: {spare_part_id}")
    print(f"   quantity: {quantity}")
    print(f"   movement_type: {movement_type}")
    print(f"   warehouse: {warehouse}")
    print(f"   reference: {reference}")

    if quantity <= 0:
        print(f"   ❌ Cantidad <= 0, ignorando")
        return True

    # Para salidas, validar stock disponible ANTES de crear el movimiento
    if movement_type == 'out':
        stock = get_or_create_stock(spare_part_id, warehouse)
        print(f"   Stock actual en warehouse '{warehouse}': {stock.current_stock}")
        if stock.current_stock < quantity:
            print(f"   ❌ Stock insuficiente: requiere {quantity}, disponible {stock.current_stock}")
            return False

    # Crear movimiento
    movement = SparePartMovement(
        spare_part_id=spare_part_id,
        warehouse=warehouse,
        movement_type=movement_type,
        quantity=quantity,
        reference_number=reference,
        description=description,
        performed_by_id=performed_by_id,
        work_order_id=work_order_id,
        preventive_execution_log_id=preventive_execution_log_id
    )
    db.session.add(movement)

    # Actualizar stock
    success = update_stock_after_movement(spare_part_id, quantity, movement_type, warehouse)
    if not success:
        db.session.rollback()
        print(f"   ❌ Falló update_stock_after_movement")
        return False

    print(f"   ✅ Movimiento registrado correctamente")
    return True


def consume_spare_part(spare_part_id, quantity, warehouse, reference, preventive_execution_log_id=None,
                       work_order_id=None, performed_by_id=None):
    """
    Registra un consumo (movimiento 'out') para mantenimiento preventivo o correctivo.
    Retorna True si se registró correctamente, False si hay stock insuficiente.
    """
    return register_movement(
        spare_part_id=spare_part_id,
        quantity=quantity,
        movement_type='out',
        warehouse=warehouse,
        reference=reference,
        description=f"Consumo en mantenimiento: {reference}",
        performed_by_id=performed_by_id,
        preventive_execution_log_id=preventive_execution_log_id,
        work_order_id=work_order_id
    )


def add_stock(spare_part_id, quantity, warehouse, reference, description, performed_by_id):
    """
    Registra una entrada de stock (compra, devolución, etc.)
    """
    return register_movement(
        spare_part_id=spare_part_id,
        quantity=quantity,
        movement_type='in',
        warehouse=warehouse,
        reference=reference,
        description=description,
        performed_by_id=performed_by_id
    )


def check_stock_availability(spare_part_id, quantity, warehouse=None):
    """
    Verifica si hay suficiente stock disponible.
    Si no se especifica warehouse, busca cualquier almacén.
    Retorna (disponible, stock_actual)
    """
    if warehouse:
        stock = InventoryStock.query.filter_by(spare_part_id=spare_part_id, warehouse=warehouse).first()
    else:
        stock = InventoryStock.query.filter_by(spare_part_id=spare_part_id).first()

    if not stock:
        return False, 0
    return stock.current_stock >= quantity, stock.current_stock


def check_stock_alerts():
    """Verifica todos los stocks y genera alertas no resueltas, además de notificaciones internas."""
    stocks = InventoryStock.query.all()
    for stock in stocks:
        alert_type = None
        if stock.current_stock <= stock.minimum_stock:
            alert_type = 'low_stock'
        elif stock.current_stock <= stock.reorder_point:
            alert_type = 'reorder'

        if alert_type:
            # Verificar si ya hay alerta sin resolver para este stock y tipo
            existing = StockAlert.query.filter_by(
                spare_part_id=stock.spare_part_id,
                warehouse=stock.warehouse,
                alert_type=alert_type,
                resolved_at=None
            ).first()
            if not existing:
                alert = StockAlert(
                    spare_part_id=stock.spare_part_id,
                    warehouse=stock.warehouse,
                    alert_type=alert_type
                )
                db.session.add(alert)
                db.session.commit()  # Guardar para tener ID

                # Crear notificación interna (opcional, si existe regla 'stock_low')
                rule = NotificationRule.query.filter_by(event_type='stock_low', is_active=True).first()
                if rule and rule.target_roles:
                    from app.models.user import User
                    roles = rule.target_roles.split(',')
                    users = User.query.filter(User.role.in_(roles)).all()
                    for user in users:
                        create_notification(
                            user_id=user.id,
                            title=f"⚠️ Alerta de inventario: {stock.spare_part.name}",
                            message=f"Stock actual: {stock.current_stock} {stock.spare_part.unit}. "
                                    f"{'Por debajo del mínimo' if alert_type == 'low_stock' else 'Punto de pedido alcanzado'}.",
                            event_type='stock_low',
                            related_id=stock.spare_part_id,
                            link=url_for('spare_parts.inventory', _external=True)
                        )
        else:
            # Si ya no hay condición, resolver alertas pendientes del mismo ítem
            pending = StockAlert.query.filter_by(
                spare_part_id=stock.spare_part_id,
                warehouse=stock.warehouse,
                resolved_at=None
            ).all()
            for alert in pending:
                alert.resolved_at = datetime.utcnow()
            db.session.commit()


def transfer_stock(spare_part_id, from_warehouse, to_warehouse, quantity, performed_by_id, comment=''):
    """
    Transfiere stock de un almacén a otro.
    Retorna (success, message)
    """
    try:
        from_stock = InventoryStock.query.filter_by(spare_part_id=spare_part_id, warehouse=from_warehouse).first()
        if not from_stock or from_stock.current_stock < quantity:
            return False, f'Stock insuficiente en {from_warehouse}'

        to_stock = InventoryStock.query.filter_by(spare_part_id=spare_part_id, warehouse=to_warehouse).first()
        if not to_stock:
            to_stock = InventoryStock(spare_part_id=spare_part_id, warehouse=to_warehouse, current_stock=0)
            db.session.add(to_stock)

        # Transferir
        from_stock.current_stock -= quantity
        to_stock.current_stock += quantity

        # Descripción con comentario
        desc_out = f'Transferencia interna de {quantity} unidades a {to_warehouse}'
        desc_in = f'Transferencia interna de {quantity} unidades desde {from_warehouse}'
        if comment:
            desc_out += f' Motivo: {comment}'
            desc_in += f' Motivo: {comment}'

        movement_out = SparePartMovement(
            spare_part_id=spare_part_id,
            warehouse=from_warehouse,
            movement_type='out',
            quantity=quantity,
            reference_number=f'Transferencia a {to_warehouse}',
            description=desc_out,
            performed_by_id=performed_by_id
        )
        movement_in = SparePartMovement(
            spare_part_id=spare_part_id,
            warehouse=to_warehouse,
            movement_type='in',
            quantity=quantity,
            reference_number=f'Transferencia desde {from_warehouse}',
            description=desc_in,
            performed_by_id=performed_by_id
        )

        db.session.add(movement_out)
        db.session.add(movement_in)
        db.session.commit()

        return True, f'Transferidos {quantity} unidades de {from_warehouse} a {to_warehouse}'
    except Exception as e:
        db.session.rollback()
        print(f"Error en transfer_stock: {e}")
        return False, f'Error al transferir: {str(e)}'