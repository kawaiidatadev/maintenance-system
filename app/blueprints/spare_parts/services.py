# app/blueprints/spare_parts/services.py
from app import db
from app.blueprints.spare_parts.models import SparePart, InventoryStock, SparePartMovement
from flask_login import current_user


def get_or_create_stock(spare_part_id, warehouse='General'):
    """Obtiene o crea un registro de inventario para una refacción y almacén."""
    stock = InventoryStock.query.filter_by(spare_part_id=spare_part_id, warehouse=warehouse).first()
    if not stock:
        stock = InventoryStock(spare_part_id=spare_part_id, warehouse=warehouse, current_stock=0)
        db.session.add(stock)
        db.session.commit()
    return stock


def update_stock_after_movement(spare_part_id, quantity, movement_type, warehouse='General'):
    """Actualiza el stock actual después de un movimiento."""
    if quantity <= 0:
        return None

    stock = get_or_create_stock(spare_part_id, warehouse)

    if movement_type == 'in':
        stock.current_stock += quantity
    else:  # 'out'
        if stock.current_stock < quantity:
            print(f"⚠️ Stock insuficiente para {spare_part_id}: requiere {quantity}, disponible {stock.current_stock}")
            # Opcional: podrías lanzar una excepción o retornar False
        stock.current_stock -= quantity

    db.session.commit()
    return stock


def register_movement(spare_part_id, quantity, movement_type, warehouse, reference, description,
                      performed_by_id, work_order_id=None, preventive_execution_log_id=None):
    """
    Registra un movimiento (entrada o salida) y actualiza el stock.
    """
    if quantity <= 0:
        return True

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
    update_stock_after_movement(spare_part_id, quantity, movement_type, warehouse)

    return True


def consume_spare_part(spare_part_id, quantity, warehouse, reference, preventive_execution_log_id, performed_by_id):
    """
    Registra un consumo (movimiento 'out') específico para mantenimiento preventivo.
    """
    return register_movement(
        spare_part_id=spare_part_id,
        quantity=quantity,
        movement_type='out',
        warehouse=warehouse,
        reference=reference,
        description=f"Consumo en mantenimiento preventivo (log {preventive_execution_log_id})",
        performed_by_id=performed_by_id,
        preventive_execution_log_id=preventive_execution_log_id
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