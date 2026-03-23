import urllib.parse
from flask import (Blueprint, render_template, request, redirect,
                   url_for, flash, current_app)
from flask_login import login_required, current_user
from extensions import db
from models import Product, Category, CartItem

shop = Blueprint('shop', __name__)


def _get_cart_items():
    """Return all CartItem rows for the current user (joined with product)."""
    return (CartItem.query
            .filter_by(user_id=current_user.id)
            .join(CartItem.product)
            .all())


@shop.route('/')
def index():
    category_slug = request.args.get('category')
    categories = Category.query.order_by(Category.name).all()

    query = Product.query.filter_by(is_active=True)
    active_category = None

    if category_slug:
        active_category = Category.query.filter_by(slug=category_slug).first()
        if active_category:
            query = query.filter_by(category_id=active_category.id)

    products = query.order_by(Product.created_at.desc()).all()

    return render_template(
        'index.html',
        products=products,
        categories=categories,
        active_category=active_category
    )


@shop.route('/product/<slug>')
def product_detail(slug):
    product = Product.query.filter_by(slug=slug, is_active=True).first_or_404()
    return render_template('product.html', product=product)


@shop.route('/cart/add', methods=['POST'])
@login_required
def cart_add():
    product_id = request.form.get('product_id', type=int)
    quantity = request.form.get('quantity', 1, type=int)

    if not product_id:
        flash('Producto inválido.', 'error')
        return redirect(url_for('shop.index'))

    product = Product.query.get(product_id)
    if not product or not product.is_active:
        flash('Producto no disponible.', 'error')
        return redirect(url_for('shop.index'))

    item = CartItem.query.filter_by(
        user_id=current_user.id, product_id=product_id
    ).first()

    if item:
        item.quantity += quantity
    else:
        item = CartItem(user_id=current_user.id,
                        product_id=product_id,
                        quantity=quantity)
        db.session.add(item)

    db.session.commit()
    flash(f'"{product.name}" agregado al carrito.', 'success')
    return redirect(request.referrer or url_for('shop.index'))


@shop.route('/cart')
@login_required
def cart_view():
    cart_items = _get_cart_items()
    items = []
    total = 0
    stale_ids = []

    for ci in cart_items:
        if ci.product and ci.product.is_active:
            subtotal = float(ci.product.price) * ci.quantity
            total += subtotal
            items.append({
                'product': ci.product,
                'quantity': ci.quantity,
                'subtotal': subtotal,
            })
        else:
            stale_ids.append(ci.id)

    if stale_ids:
        CartItem.query.filter(CartItem.id.in_(stale_ids)).delete(synchronize_session=False)
        db.session.commit()

    return render_template('cart/cart.html', items=items, total=total)


@shop.route('/cart/update', methods=['POST'])
@login_required
def cart_update():
    product_id = request.form.get('product_id', type=int)
    quantity = request.form.get('quantity', type=int)

    if not product_id or quantity is None:
        return redirect(url_for('shop.cart_view'))

    item = CartItem.query.filter_by(
        user_id=current_user.id, product_id=product_id
    ).first()

    if item:
        if quantity <= 0:
            db.session.delete(item)
        else:
            item.quantity = quantity
        db.session.commit()

    return redirect(url_for('shop.cart_view'))


@shop.route('/cart/remove', methods=['POST'])
@login_required
def cart_remove():
    product_id = request.form.get('product_id', type=int)
    if product_id:
        CartItem.query.filter_by(
            user_id=current_user.id, product_id=product_id
        ).delete()
        db.session.commit()
    flash('Producto eliminado del carrito.', 'info')
    return redirect(url_for('shop.cart_view'))


@shop.route('/cart/whatsapp')
@login_required
def cart_whatsapp():
    seller_number = current_app.config.get('SELLER_WHATSAPP', '')
    if not seller_number:
        flash('El número de WhatsApp del vendedor no está configurado.', 'warning')
        return redirect(url_for('shop.cart_view'))

    cart_items = _get_cart_items()
    if not cart_items:
        flash('Tu carrito está vacío.', 'warning')
        return redirect(url_for('shop.cart_view'))

    lines = []
    total = 0
    for ci in cart_items:
        if ci.product and ci.product.is_active:
            subtotal = float(ci.product.price) * ci.quantity
            total += subtotal
            lines.append(f"- {ci.product.name} x{ci.quantity} @ Bs{ci.product.price}")

    if not lines:
        flash('No hay productos disponibles en tu carrito.', 'warning')
        return redirect(url_for('shop.cart_view'))

    text = "Mi pedido:\n" + "\n".join(lines)
    text += f"\nTotal: Bs{total:.2f}"

    number = seller_number.replace('+', '').replace(' ', '').replace('-', '')
    whatsapp_url = f"https://wa.me/{number}?text={urllib.parse.quote(text)}"

    return redirect(whatsapp_url)
