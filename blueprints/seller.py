import io
import os
import re
import urllib.parse
import urllib.request
import tempfile
from functools import wraps
from flask import (Blueprint, render_template, request, redirect,
                   url_for, flash, current_app, send_file, abort)
from flask_login import login_required, current_user
from extensions import db
from models import User, Category, Product, generate_slug

seller = Blueprint('seller', __name__, url_prefix='/seller')


def seller_required(f):
    @wraps(f)
    @login_required
    def decorated(*args, **kwargs):
        if not current_user.is_seller:
            abort(403)
        return f(*args, **kwargs)
    return decorated


def allowed_file(filename):
    allowed = current_app.config.get('ALLOWED_EXTENSIONS', set())
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in allowed


def _configure_cloudinary():
    import cloudinary
    cloudinary.config(
        cloud_name=current_app.config['CLOUDINARY_CLOUD_NAME'],
        api_key=current_app.config['CLOUDINARY_API_KEY'],
        api_secret=current_app.config['CLOUDINARY_API_SECRET'],
    )


def save_image(file):
    """Upload image to Cloudinary, return the secure URL."""
    import cloudinary.uploader
    _configure_cloudinary()
    result = cloudinary.uploader.upload(file, folder='cs50shop')
    return result['secure_url']


def delete_image(url):
    """Delete an image from Cloudinary by its URL."""
    if not url:
        return
    import cloudinary.uploader
    _configure_cloudinary()
    part = url.split('/upload/')[1]        # "v1234567890/cs50shop/file.jpg"
    part = re.sub(r'^v\d+/', '', part)     # "cs50shop/file.jpg"
    public_id = part.rsplit('.', 1)[0]     # "cs50shop/file"
    cloudinary.uploader.destroy(public_id)


# ── Dashboard ──────────────────────────────────────────────────────────────

@seller.route('/')
@seller_required
def dashboard():
    total_products = Product.query.count()
    active_products = Product.query.filter_by(is_active=True).count()
    total_categories = Category.query.count()
    recent_products = Product.query.order_by(Product.created_at.desc()).limit(5).all()
    return render_template(
        'seller/dashboard.html',
        total_products=total_products,
        active_products=active_products,
        total_categories=total_categories,
        recent_products=recent_products,
    )


# ── Categories ─────────────────────────────────────────────────────────────

@seller.route('/categories')
@seller_required
def categories():
    all_categories = Category.query.order_by(Category.name).all()
    return render_template('seller/categories.html', categories=all_categories)


@seller.route('/categories/new', methods=['GET', 'POST'])
@seller_required
def category_new():
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        if not name:
            flash('El nombre es requerido.', 'error')
            return render_template('seller/category_form.html', category=None)

        if Category.query.filter_by(name=name).first():
            flash('Ya existe una categoría con ese nombre.', 'error')
            return render_template('seller/category_form.html', category=None)

        slug = generate_slug(name)
        base_slug = slug
        counter = 1
        while Category.query.filter_by(slug=slug).first():
            slug = f"{base_slug}-{counter}"
            counter += 1

        background_image_url = None
        bg_file = request.files.get('background_image')
        if bg_file and bg_file.filename:
            if not allowed_file(bg_file.filename):
                flash('Tipo de archivo no permitido.', 'error')
                return render_template('seller/category_form.html', category=None)
            background_image_url = save_image(bg_file)

        cat = Category(name=name, slug=slug, background_image_url=background_image_url)
        db.session.add(cat)
        db.session.commit()
        flash(f'Categoría "{name}" creada.', 'success')
        return redirect(url_for('seller.categories'))

    return render_template('seller/category_form.html', category=None)


@seller.route('/categories/<int:id>/edit', methods=['GET', 'POST'])
@seller_required
def category_edit(id):
    cat = Category.query.get_or_404(id)

    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        if not name:
            flash('El nombre es requerido.', 'error')
            return render_template('seller/category_form.html', category=cat)

        existing = Category.query.filter_by(name=name).first()
        if existing and existing.id != id:
            flash('Ya existe una categoría con ese nombre.', 'error')
            return render_template('seller/category_form.html', category=cat)

        cat.name = name
        cat.slug = generate_slug(name)

        bg_file = request.files.get('background_image')
        if bg_file and bg_file.filename:
            if not allowed_file(bg_file.filename):
                flash('Tipo de archivo no permitido.', 'error')
                return render_template('seller/category_form.html', category=cat)
            delete_image(cat.background_image_url)
            cat.background_image_url = save_image(bg_file)

        db.session.commit()
        flash('Categoría actualizada.', 'success')
        return redirect(url_for('seller.categories'))

    return render_template('seller/category_form.html', category=cat)


@seller.route('/categories/<int:id>/delete', methods=['POST'])
@seller_required
def category_delete(id):
    cat = Category.query.get_or_404(id)
    if cat.products:
        flash('No se puede eliminar una categoría con productos.', 'error')
        return redirect(url_for('seller.categories'))
    db.session.delete(cat)
    db.session.commit()
    flash('Categoría eliminada.', 'info')
    return redirect(url_for('seller.categories'))


# ── Products ───────────────────────────────────────────────────────────────

@seller.route('/products')
@seller_required
def products():
    all_products = Product.query.order_by(Product.created_at.desc()).all()
    return render_template('seller/products.html', products=all_products)


@seller.route('/products/new', methods=['GET', 'POST'])
@seller_required
def product_new():
    categories = Category.query.order_by(Category.name).all()

    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        description = request.form.get('description', '').strip()
        price_str = request.form.get('price', '').strip()
        cost_price_str = request.form.get('cost_price', '').strip()
        stock_str = request.form.get('stock', '0').strip()
        category_id = request.form.get('category_id') or None
        is_active = request.form.get('is_active') == 'on'

        if not name or not price_str:
            flash('Nombre y precio son requeridos.', 'error')
            return render_template('seller/product_form.html',
                                   product=None, categories=categories)

        try:
            price = float(price_str)
            if price <= 0:
                raise ValueError
        except ValueError:
            flash('El precio debe ser un número positivo.', 'error')
            return render_template('seller/product_form.html',
                                   product=None, categories=categories)

        cost_price = float(cost_price_str) if cost_price_str else None
        stock = int(stock_str) if stock_str else 0

        slug = generate_slug(name)
        base_slug = slug
        counter = 1
        while Product.query.filter_by(slug=slug).first():
            slug = f"{base_slug}-{counter}"
            counter += 1

        image_url = None
        file = request.files.get('image')
        if file and file.filename:
            if not allowed_file(file.filename):
                flash('Tipo de archivo no permitido.', 'error')
                return render_template('seller/product_form.html',
                                       product=None, categories=categories)
            image_url = save_image(file)

        product = Product(
            name=name,
            slug=slug,
            description=description,
            price=price,
            cost_price=cost_price,
            stock=stock,
            image_url=image_url,
            category_id=int(category_id) if category_id else None,
            is_active=is_active,
        )
        db.session.add(product)
        db.session.commit()
        flash(f'Producto "{name}" creado.', 'success')
        return redirect(url_for('seller.products'))

    return render_template('seller/product_form.html',
                           product=None, categories=categories)


@seller.route('/products/<int:id>/edit', methods=['GET', 'POST'])
@seller_required
def product_edit(id):
    product = Product.query.get_or_404(id)
    categories = Category.query.order_by(Category.name).all()

    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        description = request.form.get('description', '').strip()
        price_str = request.form.get('price', '').strip()
        cost_price_str = request.form.get('cost_price', '').strip()
        stock_str = request.form.get('stock', '0').strip()
        category_id = request.form.get('category_id') or None
        is_active = request.form.get('is_active') == 'on'

        if not name or not price_str:
            flash('Nombre y precio son requeridos.', 'error')
            return render_template('seller/product_form.html',
                                   product=product, categories=categories)

        try:
            price = float(price_str)
            if price <= 0:
                raise ValueError
        except ValueError:
            flash('El precio debe ser un número positivo.', 'error')
            return render_template('seller/product_form.html',
                                   product=product, categories=categories)

        product.name = name
        product.description = description
        product.price = price
        product.cost_price = float(cost_price_str) if cost_price_str else None
        product.stock = int(stock_str) if stock_str else 0
        product.category_id = int(category_id) if category_id else None
        product.is_active = is_active

        # Update slug only if name changed
        new_slug = generate_slug(name)
        if new_slug != product.slug:
            base_slug = new_slug
            counter = 1
            while Product.query.filter(
                Product.slug == new_slug, Product.id != id
            ).first():
                new_slug = f"{base_slug}-{counter}"
                counter += 1
            product.slug = new_slug

        file = request.files.get('image')
        if file and file.filename:
            if not allowed_file(file.filename):
                flash('Tipo de archivo no permitido.', 'error')
                return render_template('seller/product_form.html',
                                       product=product, categories=categories)
            delete_image(product.image_url)
            product.image_url = save_image(file)

        db.session.commit()
        flash('Producto actualizado.', 'success')
        return redirect(url_for('seller.products'))

    return render_template('seller/product_form.html',
                           product=product, categories=categories)


@seller.route('/products/<int:id>/delete', methods=['POST'])
@seller_required
def product_delete(id):
    product = Product.query.get_or_404(id)
    delete_image(product.image_url)
    db.session.delete(product)
    db.session.commit()
    flash('Producto eliminado.', 'info')
    return redirect(url_for('seller.products'))


@seller.route('/products/<int:id>/toggle', methods=['POST'])
@seller_required
def product_toggle(id):
    product = Product.query.get_or_404(id)
    product.is_active = not product.is_active
    db.session.commit()
    status = 'activado' if product.is_active else 'desactivado'
    flash(f'Producto {status}.', 'info')
    return redirect(url_for('seller.products'))


# ── PDF Export ─────────────────────────────────────────────────────────────

@seller.route('/products/<int:id>/pdf')
@seller_required
def product_pdf(id):
    from reportlab.lib.pagesizes import letter
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import inch
    from reportlab.lib import colors
    from reportlab.platypus import (SimpleDocTemplate, Paragraph, Spacer,
                                    Image, HRFlowable, KeepTogether)
    from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY, TA_LEFT

    product = Product.query.get_or_404(id)
    PAGE_W, PAGE_H = letter
    buffer = io.BytesIO()
    tmp_files = []

    def _download(url, suffix='.jpg'):
        try:
            with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
                path = tmp.name
            urllib.request.urlretrieve(url, path)
            tmp_files.append(path)
            return path
        except Exception:
            return None

    # Download background and product images
    bg_url = (product.category.background_image_url
              if product.category else None)
    bg_path = _download(bg_url) if bg_url else None
    img_path = _download(product.image_url) if product.image_url else None

    # Generate marketing description with Gemini
    marketing_desc = product.description or ''
    api_key = current_app.config.get('GEMINI_API_KEY', '')
    if api_key:
        try:
            from google import genai
            client = genai.Client(api_key=api_key)
            prompt = (
                "Eres un experto en marketing y copywriting con años de experiencia "
                "creando catálogos de productos premium. "
                "Redacta una descripción de producto persuasiva y profesional en español "
                "para un catálogo impreso. Máximo 80 palabras. "
                "Destaca los beneficios clave, genera deseo de compra, usa un tono "
                "confiable, aspiracional y cercano. Evita clichés. "
                f"Producto: {product.name}. "
                f"Categoría: {product.category.name if product.category else 'General'}. "
                f"Precio: Bs{product.price}. "
                f"Información base: {product.description or 'Sin descripción adicional'}. "
                "No uses markdown, asteriscos ni viñetas. Solo texto plano en párrafo corrido."
            )
            response = client.models.generate_content(
                model="gemini-2.5-flash", contents=[prompt]
            )
            marketing_desc = response.text.strip()
        except Exception:
            pass

    # Background drawing callback
    def draw_background(canvas, doc):
        canvas.saveState()
        if bg_path:
            canvas.drawImage(bg_path, 0, 0, width=PAGE_W, height=PAGE_H,
                             preserveAspectRatio=False, mask='auto')
        # White overlay for readability
        canvas.setFillColor(colors.Color(1, 1, 1, alpha=0.84))
        canvas.rect(0, 0, PAGE_W, PAGE_H, fill=1, stroke=0)
        canvas.restoreState()

    doc = SimpleDocTemplate(
        buffer,
        pagesize=letter,
        rightMargin=1.25 * inch,
        leftMargin=1.25 * inch,
        topMargin=1.0 * inch,
        bottomMargin=1.0 * inch,
    )

    styles = getSampleStyleSheet()
    story = []

    # Product image
    if img_path:
        img = Image(img_path, width=4.2 * inch, height=3.1 * inch)
        img.hAlign = 'CENTER'
        story.append(img)
        story.append(Spacer(1, 0.2 * inch))

    # Category label
    if product.category:
        story.append(Paragraph(
            product.category.name.upper(),
            ParagraphStyle('CatLabel', parent=styles['Normal'],
                           fontSize=9, fontName='Helvetica',
                           textColor=colors.HexColor('#888888'),
                           alignment=TA_CENTER, spaceAfter=4,
                           tracking=2),
        ))

    story.append(HRFlowable(width='70%', thickness=0.8,
                            color=colors.HexColor('#BBBBBB'),
                            hAlign='CENTER', spaceBefore=2, spaceAfter=10))

    # Product name
    story.append(Paragraph(
        product.name,
        ParagraphStyle('ProdName', parent=styles['Heading1'],
                       fontSize=26, fontName='Helvetica-Bold',
                       textColor=colors.HexColor('#1a1a1a'),
                       alignment=TA_CENTER, leading=30,
                       spaceAfter=6, spaceBefore=0),
    ))

    # Price
    story.append(Paragraph(
        f"Bs {product.price}",
        ParagraphStyle('Price', parent=styles['Normal'],
                       fontSize=21, fontName='Helvetica-Bold',
                       textColor=colors.HexColor('#2e7d32'),
                       alignment=TA_CENTER, spaceAfter=14),
    ))

    story.append(HRFlowable(width='70%', thickness=0.8,
                            color=colors.HexColor('#BBBBBB'),
                            hAlign='CENTER', spaceBefore=2, spaceAfter=16))

    # Marketing description
    if marketing_desc:
        story.append(KeepTogether([
            Paragraph(
                "Descripción",
                ParagraphStyle('DescHead', parent=styles['Normal'],
                               fontSize=10, fontName='Helvetica-Bold',
                               textColor=colors.HexColor('#555555'),
                               spaceAfter=6, alignment=TA_LEFT),
            ),
            Paragraph(
                marketing_desc,
                ParagraphStyle('DescBody', parent=styles['Normal'],
                               fontSize=11, fontName='Helvetica',
                               textColor=colors.HexColor('#2d2d2d'),
                               leading=17, alignment=TA_JUSTIFY,
                               spaceAfter=20),
            ),
        ]))

    # Footer
    story.append(Spacer(1, 0.15 * inch))
    story.append(Paragraph(
        "CS50 Shop",
        ParagraphStyle('Footer', parent=styles['Normal'],
                       fontSize=8, fontName='Helvetica-Oblique',
                       textColor=colors.HexColor('#AAAAAA'),
                       alignment=TA_CENTER),
    ))

    doc.build(story, onFirstPage=draw_background, onLaterPages=draw_background)
    buffer.seek(0)

    for p in tmp_files:
        try:
            os.unlink(p)
        except Exception:
            pass

    return send_file(
        buffer,
        mimetype='application/pdf',
        as_attachment=True,
        download_name=f"{product.slug}.pdf",
    )


# ── AI WhatsApp Share ──────────────────────────────────────────────────────

# @seller.route('/products/<int:id>/share-whatsapp')
# @seller_required
# def product_share_whatsapp(id):
#     product = Product.query.get_or_404(id)
#     api_key = current_app.config.get('GEMINI_API_KEY', '')
#     seller_number = current_app.config.get('SELLER_WHATSAPP', '')

#     if not seller_number:
#         flash('El número de WhatsApp del vendedor no está configurado.', 'warning')
#         return redirect(url_for('seller.products'))

#     if not api_key:
#         flash('La API key de GEMINI no está configurada.', 'warning')
#         return redirect(url_for('seller.products'))

#     try:
#         from google import genai
#         client = genai.Client(api_key=api_key)

#         prompt = (
#             f"Escribe una descripción corta y entusiasta para WhatsApp del producto: "
#             f"Nombre: {product.name}, Precio: Bs{product.price}, "
#             f"Descripción: {product.description or 'Sin descripción'}. "
#             f"No uses emojis. Sin markdown."
#         )

#         message = client.models.generate_content(
#             model="gemini-2.5-flash",
#             contents=[prompt]
#         )
#         ai_text = message.text

#     except Exception as e:
#         flash(f'Error al generar descripción IA: {str(e)}', 'error')
#         return redirect(url_for('seller.products'))

#     number = seller_number.replace('+', '').replace(' ', '').replace('-', '')
#     text = f"{product.name}\n\n{ai_text}\n\nPrecio: Bs{product.price}"
#     encoded = urllib.parse.quote(text.encode('utf-8'), safe='')
#     whatsapp_url = f"https://wa.me/{number}?text={encoded}"

#     return redirect(whatsapp_url)


# ── Seller Account Management ──────────────────────────────────────────────

@seller.route('/sellers/new', methods=['GET', 'POST'])
@seller_required
def seller_new():
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')

        if not username or not email or not password:
            flash('Todos los campos son requeridos.', 'error')
            return render_template('seller/seller_form.html')

        if len(password) < 8:
            flash('La contraseña debe tener al menos 8 caracteres.', 'error')
            return render_template('seller/seller_form.html')

        if User.query.filter_by(username=username).first():
            flash('Ese nombre de usuario ya está en uso.', 'error')
            return render_template('seller/seller_form.html')

        if User.query.filter_by(email=email).first():
            flash('Ese email ya está registrado.', 'error')
            return render_template('seller/seller_form.html')

        user = User(username=username, email=email, role='seller')
        user.set_password(password)
        db.session.add(user)
        db.session.commit()
        flash(f'Cuenta vendedor "{username}" creada.', 'success')
        return redirect(url_for('seller.dashboard'))

    return render_template('seller/seller_form.html')
